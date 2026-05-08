# RCA — Lag / freshness E2E (YEGO Control Tower)

**Fecha investigación:** 2026-05-08  
**Alcance:** trazabilidad pipeline REAL operacional, banner de frescura, Omniview (cadena hourly-first).

- **Este cierre (fase 1.3):** [`INCIDENT_FRESHNESS_CLOSURE_PHASE1_3.md`](INCIDENT_FRESHNESS_CLOSURE_PHASE1_3.md) — validación post-fix, pipeline driver/supply/audit, smoke HTTP, GO/NO-GO.

---

## 1. Causa raíz exacta

**Las materialized views `ops.mv_real_lob_hour_v2` → `day_v2` → `week_v3` → `month_v3` estaban definidas leyendo `ops.staging_bootstrap_mv_real_lob_hour_v2` (tabla de staging del script `bootstrap_hourly_first.py`), no `ops.v_real_trip_fact_v2`.**

- `REFRESH MATERIALIZED VIEW` re-ejecuta la consulta **almacenada** en el catálogo de PostgreSQL.
- Si esa consulta apunta al staging, el refresco **nunca** incorpora viajes nuevos que ya existen en `v_trips_real_canon_120d` / `v_real_trip_fact_v2`.
- Evidencia en catálogo (primeros 600 caracteres de `pg_matviews.definition`):

```text
SELECT staging_bootstrap_mv_real_lob_hour_v2.trip_date, ...
```

- La vista viva `ops.v_real_trip_fact_v2` sí tenía millones de filas posteriores a 2026-03-14 (`COUNT(*) WHERE fecha > 2026-03-14` ≈ 6,2M), mientras `MAX(trip_date)` en `mv_real_lob_day_v2` permanecía **2026-03-14**.

**Secundario:** `ops.data_freshness_audit` no se había ejecutado recientemente (última corrida previa **2026-03-16**), lo que ocultaba el estado real en UI hasta volver a lanzar `run_data_freshness_audit`.

**No fue un bug de timezone:** `SHOW timezone` = `America/Lima`; `CURRENT_DATE` en PostgreSQL y `date.today()` en el host coincidieron con **2026-05-08**.

**`trips_all`:** `MAX(fecha_inicio_viaje)` en ventana reciente = **2026-01-31** (legacy); el tráfico 2026 vive en **`trips_2026`** — coherente con el diseño documentado.

---

## 2. Pipeline afectado

| Capa | Objeto | Estado antes del fix |
|------|--------|----------------------|
| Fuente | `public.trips_2026` | OK hasta 2026-05-07 |
| Canon | `ops.v_trips_real_canon_120d` | OK hasta 2026-05-07 |
| Fact | `ops.v_real_trip_fact_v2` | OK hasta 2026-05-07 |
| Derivado | `ops.mv_real_lob_*_v2/v3` | **Congelado ~2026-03-14** (definición MV incorrecta) |
| Rollup vista | `ops.real_rollup_day_fact` | Atrasado (depende de `day_v2`) |
| Auditoría | `ops.data_freshness_audit` | Desactualizada hasta nueva corrida |
| API banner | `GET /ops/data-freshness/global` | Lee audit; reflejaba lag / estado viejo |

---

## 3. Fix implementado (código / migración)

| Entregable | Descripción |
|------------|-------------|
| Migración **135** | [`backend/alembic/versions/135_fix_hourly_first_mv_source_live_fact.py`](../backend/alembic/versions/135_fix_hourly_first_mv_source_live_fact.py): DROP CASCADE de las cuatro MV y recreación con `FROM ops.v_real_trip_fact_v2` (definición alineada a 099). `statement_timeout=0` en sesión. |
| Migración **136** | [`backend/alembic/versions/136_restore_real_rollup_views_after_hourly_mv_rebuild.py`](../backend/alembic/versions/136_restore_real_rollup_views_after_hourly_mv_rebuild.py): restaura `v_real_rollup_day_from_day_v2`, `real_rollup_day_fact`, `mv_real_rollup_day`, coberturas y `v_revenue_quality_daily_summary` (el CASCADE de 135 las había eliminado). |
| Script diagnóstico | [`backend/scripts/diagnose_data_lag_snapshot.py`](../backend/scripts/diagnose_data_lag_snapshot.py): snapshot reproducible (TZ, max fechas, audit, snippet definición MV). |
| API / pipeline | `--skip-backfill` aceptado como **no-op** en `run_pipeline_refresh_and_audit.py`; docstring `POST /ops/pipeline-refresh` alineado en [`ops.py`](../backend/app/routers/ops.py). |
| Documentación | [`docs/data_freshness_monitoring.md`](data_freshness_monitoring.md): orden real del pipeline; `skip_backfill` documentado. |
| Bootstrap | Comentario de riesgo en [`bootstrap_hourly_first.py`](../backend/scripts/bootstrap_hourly_first.py) (MV enlazada a staging). |

**Post-migración operativa (obligatoria tras aplicar 135):**

1. `python -m scripts.populate_real_drill_from_hourly_chain` (o pipeline completo).
2. `python -m scripts.run_data_freshness_audit` (o `POST /ops/data-freshness/run`).
3. Rehabilitar **cron** diario: `python -m scripts.run_pipeline_refresh_and_audit` (o `POST /ops/pipeline-refresh`).

La migración 135 puede **tardar mucho** en producción (agregación completa sobre el fact). Ejecutar en ventana de mantenimiento.

---

## 4. Evidencia antes / después (muestras)

**Antes (2026-05-08, sesión DB):**

- `v_trips_real_canon_120d` MAX = **2026-05-07**
- `mv_real_lob_day_v2` MAX(`trip_date`) = **2026-03-14**
- `pg_matviews.definition` de `mv_real_lob_hour_v2` → prefijo **`staging_bootstrap_mv_real_lob_hour_v2`**
- `data_freshness_audit.checked_at` más reciente (datasets clave) = **2026-03-16** (pre re-audit)

**Después de `run_data_freshness_audit` (sin aún corregir MV):**

- `real_operational`: `source_max_date` = 2026-05-07, `derived_max_date` = 2026-03-14, `status` = **DERIVED_STALE** (coherente con catálogo incorrecto).

**Después esperado (tras 135 + populate + audit):**

- `mv_real_lob_day_v2` MAX(`trip_date`) alineado con canon (≤1 día de retraso operativo típico).
- `GET /ops/data-freshness/global` sin **DERIVED_STALE** masivo en `real_operational` por desfase fuente/MV.

**Después (2026-05-08, post 135 + 136 + populate drill + `run_data_freshness_audit`):**

- `mv_real_lob_day_v2` MAX(`trip_date`) = **2026-05-07** (alineado con canon).
- `pg_matviews.definition` de `mv_real_lob_hour_v2` → prefijo **`v_real_trip_fact_v2`**.
- `run_data_freshness_audit`: **real_operational**, **real_lob**, **real_lob_drill** → **OK** (source y derived 2026-05-07).
- Pendiente operativo: **driver_lifecycle** / **supply_weekly** siguen atrasados hasta ejecutar `refresh_driver_lifecycle_mvs` y refresh de supply en el pipeline diario.

---

## 5. Jobs / MVs afectados

- **MVs:** `ops.mv_real_lob_hour_v2`, `mv_real_lob_day_v2`, `mv_real_lob_week_v3`, `mv_real_lob_month_v3`.
- **Jobs:** cualquier cron que ejecute solo `refresh_hourly_first_chain` **sin** corregir la definición **no** bastaba; hacía falta **redefinición** (migración 135) o bootstrap corregido.
- **pg_cron:** no instalado en la instancia inspeccionada.

---

## 6. Riesgo remanente

- **Duración migración 135** en tablas muy grandes: bloqueos y tiempo de inactividad de lecturas sobre MVs durante DROP/CREATE.
- **`mv_real_trips_monthly` (legacy):** sigue alimentada solo desde `trips_all` (documentado en análisis previo); no corrige este RCA.
- **Cron ausente o fallido:** si no se programa `run_pipeline_refresh_and_audit`, pueden reaparecer desfaces en otras capas (driver lifecycle, supply).

---

## 7. Recomendaciones preventivas

1. Tras cualquier `bootstrap_hourly_first.py`, verificar `pg_matviews.definition` de `mv_real_lob_hour_v2` contiene **`v_real_trip_fact_v2`**, no `staging_bootstrap`.
2. Alerta si `MAX(checked_at)` en `data_freshness_audit` > N horas.
3. Incluir en runbook: `python -m scripts.diagnose_data_lag_snapshot` tras despliegues que toquen MVs REAL.

---

## 8. Confirmaciones solicitadas

| Requisito | Estado |
|-----------|--------|
| Omniview / cadena canónica intactos (sin hacks en UI) | Sí: sin cambios de cálculo en frontend; fix en capa BD/pipeline. |
| Sin hardcode de fechas | Sí. |
| Sin falsificar freshness | Sí: audit lee MAX reales. |
| Frontend no calcula freshness | Sin cambios; sigue consumiendo API. |
| Source of truth validado | `v_real_trip_fact_v2` y canon 120d verificados por SQL. |

---

## 9. Archivos modificados (resumen)

- `backend/alembic/versions/135_fix_hourly_first_mv_source_live_fact.py` (nuevo)
- `backend/alembic/versions/136_restore_real_rollup_views_after_hourly_mv_rebuild.py` (nuevo)
- `backend/scripts/diagnose_data_lag_snapshot.py` (nuevo)
- `backend/scripts/run_pipeline_refresh_and_audit.py`
- `backend/scripts/bootstrap_hourly_first.py` (comentario)
- `backend/app/routers/ops.py`
- `docs/data_freshness_monitoring.md`
- `docs/INCIDENT_FRESHNESS_E2E_RCA_2026-05-08.md` (este archivo)
