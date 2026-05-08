# FASE 1.5B — Plan vs Real: materialización mensual

## Cadena endpoint → objeto

| Paso | Artefacto |
|------|-----------|
| API | `GET /ops/plan-vs-real/monthly`, `GET /ops/plan-vs-real/alerts` |
| Servicio | `app/services/plan_vs_real_service.py` |
| Lectura preferente | `ops.mv_plan_vs_real_monthly_fact` (legacy) o `ops.mv_plan_vs_real_monthly_fact_canonical` (`source=canonical`) |
| Fallback | `ops.v_plan_vs_real_realkey_final` / `ops.v_plan_vs_real_realkey_canonical` si la MV no existe (`USE_PLAN_VS_REAL_MONTHLY_MV` o relación ausente) |
| Fuente semántica MV | Mismo `SELECT` que la vista: agregado realkey + FULL OUTER JOIN plan/real (sin cambiar negocio). |

## Migración

- **Alembic:** `137_plan_vs_real_monthly_materialized_facts`
- **Función SQL:** `ops.refresh_plan_vs_real_monthly_facts(boolean)` — `TRUE` = `REFRESH ... CONCURRENTLY` (requiere índices únicos creados en la migración).

## Refresh y pipeline

1. Tras **carga plan** (`staging.plan_projection_realkey_raw`) y datos **trips** que alimentan `v_real_universe_by_park_realkey` / canónica, ejecutar refresh.
2. **`python -m scripts.run_pipeline_refresh_and_audit`** incluye el paso **Plan vs Real MV** después de Supply y antes del audit (flag `--skip-plan-vs-real-mv` para omitir).
3. Script dedicado: **`python -m scripts.refresh_plan_vs_real_monthly_mvs`** (`--no-concurrent` si falla CONCURRENTLY).

## Configuración

- **`USE_PLAN_VS_REAL_MONTHLY_MV`** (settings, default `True`): `False` fuerza solo vistas (emergencia / diagnóstico).

## EXPLAIN ANALYZE (rellenar en entorno real)

**Antes (vista):**

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT country, city, park_id, park_name, real_tipo_servicio, period_date,
       trips_plan, trips_real, revenue_plan, revenue_real, variance_trips, variance_revenue
FROM ops.v_plan_vs_real_realkey_final
WHERE period_date >= '2026-04-01'::date AND period_date < '2026-05-01'::date
  AND LOWER(TRIM(country)) = LOWER(TRIM('co'));
```

**Después (MV refrescada):** sustituir `FROM` por `ops.mv_plan_vs_real_monthly_fact` con los mismos predicados.

Pegar tiempos y buffers en la tabla operativa before/after.

## Índices creados (justificación breve)

- **Único (expresión)** sobre grano `(country, city, park_id, real_tipo_servicio, period_date)` con `COALESCE` → `REFRESH CONCURRENTLY` y unicidad de fila.
- **`(period_date)`**, **`(country, period_date)`**, **`(country, city, real_tipo_servicio, period_date)`** → filtros del endpoint (mes, país, ciudad, tipo servicio).

## Validación funcional

- Paridad MV vs vista: mismos totales agregados y mismos KPIs por clave (tras `REFRESH`); tolerancia solo redondeo en %.
- Si la MV está desfasada respecto a trips/plan hasta el siguiente refresh, los datos pueden lag respecto a la vista en vivo — operar el refresh en el pipeline acordado.

## GO / NO-GO operativo

| Criterio | Condición |
|----------|-----------|
| GO | Latencia mejora de forma material; paridad MV/vista OK en muestras; pipeline refresca sin bloquear hourly-first de forma inaceptable |
| NO-GO | Paridad rota; endpoint > 15s de forma sistemática sin cuello residual documentado; refresh no automatizable |

---
*Los placeholders EXPLAIN y tiempos before/after deben completarse en la base de producción/staging con carga real.*
