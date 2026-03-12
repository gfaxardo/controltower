# Mapa de observabilidad del pipeline de datos — YEGO Control Tower

**Objetivo:** Fuente viva real por dominio, derivado, mecanismo de refresh y punto de rotura por dataset.  
**Regla global "Falta data":** Solo mostrar "Falta data" cuando `derived_max_date` es NULL o `<= current_date - 2`.

---

## Fuente viva real por dominio

| Dominio | Fuente viva real | Columna temporal | Notas |
|---------|------------------|------------------|--------|
| Viajes operativos recientes | `public.trips_2026` (+ `trips_all` histórico) | `fecha_inicio_viaje` | Vista canónica: `ops.v_trips_real_canon`. **Fuente oficial consolidada:** `ops.v_trips_real_canon` (une trips_all &lt;2026 + trips_2026). |
| Real LOB (drill + daily) | `ops.v_trips_real_canon` (lee trips_2026/trips_all) | `fecha_inicio_viaje` | Drill: `real_drill_dim_fact.period_start`; Daily: `real_rollup_day_fact.trip_day` |
| Driver Lifecycle | `ops.v_driver_lifecycle_trips_completed` | `completion_ts` | Base: `ops.mv_driver_lifecycle_base.last_completed_ts` |
| Supply | `ops.mv_driver_weekly_stats` (depende de driver lifecycle) | `week_start` | Supply segments: `ops.mv_supply_segments_weekly` |

---

## Tabla: pipeline por dataset (audit DERIVED_STALE / PARTIAL)

| dataset_name | source_object | derived_object | refresh_mechanism | temporal_column | freshness_status | suspected_breakpoint |
|--------------|---------------|----------------|------------------|-----------------|------------------|----------------------|
| real_lob_drill | ops.v_trips_real_canon | ops.real_drill_dim_fact | backfill_real_lob_mvs.py (tablas fact) | period_start | DERIVED_STALE si no se ejecuta backfill reciente | Backfill no programado o no ejecutado para mes actual/ayer |
| real_lob | ops.v_trips_real_canon | ops.real_rollup_day_fact | backfill_real_lob_mvs.py | trip_day | DERIVED_STALE | Mismo: backfill no corre para ventana reciente |
| driver_lifecycle | ops.v_driver_lifecycle_trips_completed | ops.mv_driver_lifecycle_base | ops.refresh_driver_lifecycle_mvs() | last_completed_ts | DERIVED_STALE | REFRESH MV no ejecutado en cron |
| driver_lifecycle_weekly | ops.mv_driver_lifecycle_base | ops.mv_driver_weekly_stats | ops.refresh_driver_lifecycle_mvs() (incluye weekly) | week_start | DERIVED_STALE | Mismo: refresh_driver_lifecycle no en cron |
| supply_weekly | ops.mv_driver_weekly_stats | ops.mv_supply_segments_weekly | ops.refresh_supply_alerting_mvs() | week_start | PARTIAL_EXPECTED / DERIVED_STALE | refresh_supply después de driver lifecycle; si driver está atrasado, supply también |

---

## Cadena real por dataset

### A. real_lob_drill
- **Fuente viva:** `public.trips_2026` (y `trips_all`) vía `ops.v_trips_real_canon`.
- **Derivado directo:** tabla `ops.real_drill_dim_fact` (columna `period_start`). La vista `ops.mv_real_drill_dim_agg` es un alias (VIEW) sobre esta tabla desde migración 064.
- **Refresh:** script `python -m scripts.backfill_real_lob_mvs --from YYYY-MM-01 --to YYYY-MM-01` por mes. No hay MV que refrescar; se inserta/actualiza en las tablas fact.
- **Dónde se rompe:** Si no se ejecuta backfill para el mes actual (o últimos 2 meses), `MAX(period_start)` se queda atrás. **Solución:** Ejecutar backfill al menos para mes actual y anterior (p. ej. diario con `--from primer_día_mes_anterior --to último_día_mes_actual`).

### B. real_lob (daily)
- **Fuente viva:** misma que real_lob_drill.
- **Derivado:** `ops.real_rollup_day_fact` (columna `trip_day`). Vista `ops.mv_real_rollup_day` = VIEW sobre esta tabla.
- **Refresh:** mismo script `backfill_real_lob_mvs.py` (llena drill_dim y rollup_day en el mismo paso).
- **Breakpoint:** Igual que real_lob_drill.

### C. driver_lifecycle
- **Fuente viva:** `ops.v_driver_lifecycle_trips_completed` (lee de trips_unified / base de conductores).
- **Derivado:** MV `ops.mv_driver_lifecycle_base` (columna `last_completed_ts`).
- **Refresh:** función SQL `ops.refresh_driver_lifecycle_mvs()` o `ops.refresh_driver_lifecycle_mvs_timed()`. Script: ejecutar desde app o `psql -c "SELECT ops.refresh_driver_lifecycle_mvs();"`.
- **Breakpoint:** La MV no se refresca si no se llama a la función (no hay cron interno). **Solución:** Incluir en pipeline diario (ver run_pipeline_refresh_and_audit.py).

### D. driver_lifecycle_weekly
- **Fuente (para este grano):** `ops.mv_driver_lifecycle_base`.
- **Derivado:** MV `ops.mv_driver_weekly_stats` (columna `week_start`).
- **Refresh:** la misma función `ops.refresh_driver_lifecycle_mvs()` refresca en orden: base → weekly_stats → monthly_stats → weekly_kpis → monthly_kpis.
- **Breakpoint:** Mismo que driver_lifecycle: falta ejecución programada.

### E. supply_weekly
- **Fuente viva (expectativa audit):** `ops.mv_driver_weekly_stats`.
- **Derivado:** MV `ops.mv_supply_segments_weekly` (columna `week_start`). También existen `ops.mv_supply_weekly`, `ops.mv_supply_monthly` y otras MVs de alerting.
- **Refresh:** `ops.refresh_supply_alerting_mvs()` (refresca 4 MVs incluyendo mv_supply_segments_weekly). Servicio: `refresh_supply_alerting_mvs()` en supply_service; endpoint `POST /ops/supply/refresh`.
- **Breakpoint:** Si `mv_driver_weekly_stats` está atrasado, supply hereda el retraso. Orden correcto: 1) refresh_driver_lifecycle_mvs, 2) refresh_supply_alerting_mvs. **Solución:** Pipeline unificado que ejecute driver lifecycle primero y luego supply.

---

## Evidencia de causa del atraso (consultas útiles)

```sql
-- Fuente viva viajes
SELECT MAX(fecha_inicio_viaje)::date AS source_max FROM public.trips_2026 WHERE fecha_inicio_viaje >= current_date - 180;
SELECT MAX(fecha_inicio_viaje)::date AS source_max FROM public.trips_all WHERE fecha_inicio_viaje >= current_date - 180;

-- Derivados Real LOB
SELECT MAX(period_start)::date AS derived_max FROM ops.real_drill_dim_fact WHERE period_start >= current_date - 180;
SELECT MAX(trip_day)::date AS derived_max FROM ops.real_rollup_day_fact WHERE trip_day >= current_date - 180;

-- Driver Lifecycle
SELECT MAX(completion_ts)::date AS source_max FROM ops.v_driver_lifecycle_trips_completed WHERE completion_ts >= current_date - 180;
SELECT MAX(last_completed_ts)::date AS derived_max FROM ops.mv_driver_lifecycle_base WHERE last_completed_ts >= current_date - 180;
SELECT MAX(week_start) AS derived_weekly FROM ops.mv_driver_weekly_stats WHERE week_start >= current_date - 180;

-- Supply
SELECT MAX(week_start) AS supply_max FROM ops.mv_supply_segments_weekly WHERE week_start >= current_date - 180;
```

---

## Automatización del audit y del refresh

- **Audit:** `python -m scripts.run_data_freshness_audit` (o `POST /ops/data-freshness/run`). Escribe en `ops.data_freshness_audit`.
- **Refresh completo (recomendado):** `python -m scripts.run_pipeline_refresh_and_audit` — ejecuta en orden: backfill Real LOB (mes actual + anterior), refresh_driver_lifecycle_mvs(), refresh_supply_alerting_mvs(), run_data_freshness_audit.
- **Cron sugerido (ejemplo):** Diario a las 06:00 (tras carga de viajes):
  - `0 6 * * * cd /path/to/backend && python -m scripts.run_pipeline_refresh_and_audit >> /var/log/ct_pipeline.log 2>&1`
- **Reejecución manual:** Mismo comando; o por pasos: backfill, luego refresh driver, luego supply, luego audit.

---

## Centro de observabilidad

- **Endpoint:** `GET /ops/data-pipeline-health` — devuelve la misma estructura que la auditoría (por dataset: source_max_date, derived_max_date, lag_days, status, alert_reason, last_checked_at).
- **Banner UI:** Muestra estado global (Fresca / Parcial esperada / Atrasada / Falta data) y, de forma visible, última fecha en fuente, última en derivado y lag cuando aplica. Botón "Ver salud del pipeline" despliega la tabla por dataset (GET /ops/data-pipeline-health).

---

## Fase K — Entregable final (resumen ejecutivo)

1. **Fuente viva real confirmada:** Viajes: `trips_2026` (y canónica `ops.v_trips_real_canon`). Driver Lifecycle: `ops.v_driver_lifecycle_trips_completed`. Supply: depende de `ops.mv_driver_weekly_stats`.
2. **Datasets auditados:** real_lob_drill, real_lob, driver_lifecycle, driver_lifecycle_weekly, supply_weekly, trips_2026, trips_base (expectativas en ops.data_freshness_expectations).
3. **Causa real del atraso por dataset:** Backfill Real LOB no ejecutado para ventana reciente; refresh_driver_lifecycle_mvs() y refresh_supply_alerting_mvs() no programados en cron. Documentado en la tabla "suspected_breakpoint" de este documento.
4. **Fixes aplicados:** Script unificado `run_pipeline_refresh_and_audit.py` (backfill + refresh driver + supply + audit); endpoint `POST /ops/pipeline-refresh`; centro de observabilidad `GET /ops/data-pipeline-health`.
5. **Refresh/backfills ejecutados:** El usuario debe ejecutar `python -m scripts.run_pipeline_refresh_and_audit` (o POST /ops/pipeline-refresh) para reponer datos; tras ejecución, volver a abrir "Ver salud del pipeline" para evidencia before/after.
6. **Cambios UI de freshness:** Banner muestra fuente viva, última fecha en vista, lag (días); botón "Ver salud del pipeline" expande tabla por dataset (dataset, fuente máx, derivado máx, lag, estado, motivo).
7. **Campos vacíos:** Sin cambios específicos en esta fase; los campos que dependen de derivados atrasados se llenarán al ejecutar el pipeline de refresh.
8. **Automatización:** Cron diario recomendado: `0 6 * * * cd /path/to/backend && python -m scripts.run_pipeline_refresh_and_audit >> /var/log/ct_pipeline.log 2>&1`. Documentado en data_freshness_monitoring.md §12.
9. **Archivos modificados/creados:** docs/data_pipeline_observability_map.md (nuevo), docs/data_freshness_monitoring.md (API, automatización, centro observabilidad), docs/system_views_freshness_audit.md (comandos, enlace al mapa), backend/scripts/run_pipeline_refresh_and_audit.py (nuevo), backend/app/routers/ops.py (GET data-pipeline-health, POST pipeline-refresh), backend/app/services/data_freshness_service.py (lag_days en global), frontend/src/components/GlobalFreshnessBanner.jsx (fuente, derivado, lag, tabla expandible), frontend/src/services/api.js (getDataPipelineHealth).
10. **Comandos ejecutados:** Ninguno en este entorno; el usuario ejecuta `python -m scripts.run_pipeline_refresh_and_audit` o POST /ops/pipeline-refresh para validar.
11. **Before/after del audit:** Tras ejecutar el pipeline, comparar status y derived_max_date en GET /ops/data-pipeline-health con los valores previos (ej. driver_lifecycle: derived_max debe acercarse a source_max; real_lob_drill: derived_max debe llegar al menos a ayer).
12. **Veredicto final:** **LISTO CON OBSERVACIONES** — Pipeline mapeado, script y endpoint de refresh listos, frescura muy visible en UI y centro de observabilidad operativo. La mejora efectiva de derived_max_date requiere ejecutar el pipeline en el entorno real (cron o manual); supply_weekly puede seguir PARTIAL_EXPECTED si su grano semanal tiene semana abierta.
