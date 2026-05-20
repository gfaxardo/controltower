# Auditoría Fase 1 — Refresh & Serving Hardening

**Fecha**: 2026-05-19
**Alcance**: Supply Migration, Driver Lifecycle, Omniview Matrix, Business Slice, Hourly-first chain, Real ejecutado, Plan vs Real, Freshness, Ingestion.
**Regla**: NO implementar cambios. NO modificar lógica. NO refrescar data productiva. Auditoría de lectura.

---

## 1. Resumen ejecutivo

| Dimensión | Estado |
|-----------|--------|
| **Estado GO / NO-GO** | **NO-GO** para hardening de estabilidad operativa. Hay riesgos estructurales que deben resolverse antes de confiar en automatización completa. |
| **Riesgo principal** | Los refrescos de MVs son COMPLETOS (full refresh), sin protección de periodo cerrado. Cada corrida de pipeline recalcula TODO el histórico (~59M trips × 5 MVs encadenadas), lo que hace que cualquier fallo deje datos corruptos o inconsistentes. |
| **Hallazgo más grave** | No existe mecanismo de "closed period protection". Los scripts `ops.refresh_driver_lifecycle_mvs()` y `ops.refresh_supply_alerting_mvs()` hacen `REFRESH MATERIALIZED VIEW CONCURRENTLY` sin WHERE, recalculando todas las semanas/meses desde el origen de los datos. Si la corrida anterior estaba bien, la nueva puede romperla sin trazabilidad de qué cambió. |
| **Quick wins seguros** | 1. Agregar `pg_try_advisory_lock()` en cada función de refresh para evitar concurrencia. 2. Crear tabla `ops.refresh_ledger` con versión, hash y status. 3. Agregar metadata `last_refresh_at` / `data_freshness_warning` en cada endpoint de lectura. |

---

## 2. Inventario de scripts de refresh

| Script | Ubicación | Lee | Escribe/Refresca | Scope | Toca cerrado | Corre en | Logs | Lock | Riesgo | Recomendación |
|--------|-----------|-----|-----------------|-------|-------------|----------|------|------|--------|---------------|
| `run_pipeline_refresh_and_audit.py` | `backend/scripts/` | `trips_unified`, `drivers`, 5 cadenas de MVs | 1) hourly-first chain 2) real_drill_dim_fact 3) driver lifecycle MVs 4) supply MVs 5) plan vs real MVs 6) audit tables | **Completo** (todos los dominios) | **SÍ** — full refresh de todas las MVs recalculando todo el histórico | **Cron (externo)** recomendado `0 6 * * *`; también vía `POST /ops/pipeline-refresh` | Parcial (stdout/stderr de subprocess) | `lock_timeout=60s` en funciones DB, pero sin advisory lock entre pasos | **CRITICAL** — si falla en paso 3 de 6, pasos 1-2 ya refrescaron y 3-5 quedan stale | Dividir en jobs independientes con idempotencia por paso. Agregar `pg_try_advisory_lock` global. |
| `run_driver_lifecycle_build.py` | `backend/scripts/` | `trips_unified`, `drivers` | 1) Crea/sobrescribe todas las MVs del driver lifecycle (base, weekly_stats, monthly_stats, weekly_kpis, monthly_kpis) vía `driver_lifecycle_build.sql` 2) `ops.refresh_driver_lifecycle_mvs()` | **Completo** — recrea MVs desde `trips_unified` completo | **SÍ** — `CREATE MATERIALIZED VIEW` sin WHERE (full scan trips_unified) | Manual y vía `run_pipeline_refresh_and_audit.py` paso 3 | Sí (validaciones 1-7 al final) | `statement_timeout=60min`, `lock_timeout=60s` en función DB; sin advisory lock | **CRITICAL** — recrea MVs desde cero (DROP + CREATE), no es un refresh; si falla, pierde datos | Migrar a refresh CONCURRENTLY si las MVs ya existen (no drop). Agregar lock. |
| `run_supply_refresh_pipeline.py` | `backend/scripts/` | `mv_driver_weekly_stats` | `ops.refresh_supply_alerting_mvs()`: `mv_driver_segments_weekly` → `mv_supply_segments_weekly` → `mv_supply_segment_anomalies_weekly` → `mv_supply_alerts_weekly` | **Completo** — 4 MVs encadenadas en orden | **SÍ** — todos los segmentos de todas las semanas recalculados | Manual, vía `run_pipeline_refresh_and_audit.py` paso 4, vía `POST /ops/supply/refresh` | Sí (`ops.supply_refresh_log`) | `lock_timeout=60s`; sin advisory lock | **HIGH** — 4 MVs se refrescan secuencialmente; si falla en MV 3, MV 1-2 ya están con nueva data y 3-4 con data vieja | Agregar advisory lock. Si falla a medias, restaurar último estado bueno. |
| `refresh_hourly_first_chain.py` | `backend/scripts/` | `trips_2026` (vía `OMNIVIEW_UPSTREAM_TRIPS_TABLE`) | `mv_real_lob_hour_v2` → `mv_real_lob_day_v2` → `mv_real_lob_week_v3` → `mv_real_lob_month_v3` | **Completo** — 4 MVs en cadena | **SÍ** — todas las horas/días/semanas/meses desde el origen | Manual, vía `run_pipeline_refresh_and_audit.py` paso 1 | Solo stdout | `lock_timeout` no configurado explícitamente; sin advisory lock | **HIGH** — si falla en `week_v3`, `hour_v2` y `day_v2` ya están refrescados, cadena rota | Agregar lock y opción de rollback. |
| `refresh_business_slice_mvs.py` | `backend/scripts/` | `trips_2026` → función `ops.fn_real_trips_business_slice_resolved_subset` | `ops.real_business_slice_month_fact`, `day_fact`, `week_fact` (son **tablas fact**, no MVs) | **Por mes** (--month) o **backfill** (--backfill-from/to) | **SÍ** (si se corre con --backfill-from o sin --month recálculo del mes actual) | Manual, vía `run_business_slice_real_refresh_job` (APScheduler), vía `POST /ops/business-slice/real-refresh-omniview` | Sí (prints) | Sin advisory lock; usa transacciones por chunk | **MEDIUM** — es el único script que permite scope por mes. Pero el scheduler recalcula mes actual + anterior cada vez | Bien diseñado para incremental. Agregar lock para evitar overlap con backfill. |
| `run_business_slice_real_refresh_job` (APScheduler) | `backend/app/services/business_slice_real_refresh_job.py` | `trips_2026` upstream status | `day_fact` + `week_fact` + `month_fact` para [mes anterior, mes actual] | **2 meses** (prev + current) | **SÍ** — recalcula el mes anterior cada vez | **APScheduler en startup de backend** (`BackgroundScheduler`, cron configurable) | Sí (`logger.info`) | Cooldown vía `_last_refresh_completed_ts` (in-process), no advisory lock DB | **HIGH** — corre en el proceso del backend; si el backend tiene múltiples workers, pueden solaparse | Usar advisory lock DB en lugar de cooldown en memoria. |
| `refresh_plan_vs_real_monthly_mvs.py` | `backend/scripts/` | Plan tables + `mv_real_trips_monthly` | `mv_plan_vs_real_monthly_fact`, `mv_plan_vs_real_monthly_fact_canonical` | **Completo** — MVs completas | **SÍ** | vía `run_pipeline_refresh_and_audit.py` paso 5 | Sí (vía pipeline) | `CONCURRENTLY` | **MEDIUM** | Agregar lock. |
| `populate_real_drill_from_hourly_chain.py` | `backend/scripts/` | `mv_real_lob_day_v2`, `week_v3`, `month_v3` | `real_drill_dim_fact` (tabla) | Ventana configurable: días=120, semanas=18, meses=6 | **SÍ** (ventana acotada pero incluye meses cerrados) | vía `run_pipeline_refresh_and_audit.py` paso 2 | Sí | Sin advisory lock | **MEDIUM** | OK con ventana; agregar lock. |

---

## 3. Inventario de endpoints críticos

### 3A — Supply Migration (UI → service → MVs)

| Endpoint | Router | Service | Solo lectura | Llama refresh | Fuentes leídas | Riesgo performance | Riesgo data cerrada | Recomendación |
|----------|--------|---------|-------------|---------------|----------------|---------------------|---------------------|---------------|
| `GET /ops/supply/migration` | `ops.py:1180` | `supply_service.get_supply_migration()` | **SÍ** | No | `mv_driver_segments_weekly`, `mv_supply_segments_weekly` | Medio (2 MVs joined, CTE + window) | **SÍ** — si las MVs no se refrescaron, muestra data stale sin advertir | Agregar `X-Data-Freshness` header con `last_refresh` de `supply_refresh_log` |
| `GET /ops/supply/migration/drilldown` | `ops.py:1202` | `supply_service.get_supply_migration_drilldown()` | **SÍ** | No | `mv_driver_segments_weekly` | Bajo (filtrado por week_start + park_id) | **SÍ** — mismo riesgo de stale data | Mismo header de freshness |
| `GET /ops/supply/migration/weekly-summary` | `ops.py:1223` | `supply_service.get_supply_migration_weekly_summary()` | **SÍ** | No | `ops.v_driver_segments_weekly_summary` (VIEW sobre `mv_driver_segments_weekly`) | Bajo (vista pre-agregada) | **SÍ** | Mismo header de freshness |
| `GET /ops/supply/migration/critical` | `ops.py:1238` | `supply_service.get_supply_migration_critical()` | **SÍ** | No | `ops.v_driver_segment_critical_movements` (VIEW) | Bajo | **SÍ** | Mismo header de freshness |
| `GET /ops/supply/overview-enhanced` | `ops.py:1144` | `supply_service.get_supply_overview_enhanced()` | **SÍ** | No | `mv_supply_weekly`, `mv_supply_segments_weekly`, `mv_supply_monthly` | Medio (join de 2-3 MVs + cálculos WoW en Python) | **SÍ** | Header freshness |
| `GET /ops/supply/composition` | `ops.py:1160` | `supply_service.get_supply_composition()` | **SÍ** | No | `mv_supply_segments_weekly` | Bajo (una sola MV, filtrada) | **SÍ** | Header freshness |
| `GET /ops/supply/alerts` | `ops.py:1072` | `supply_service.get_supply_alerts()` | **SÍ** | No | `mv_supply_alerts_weekly`, `mv_supply_segment_anomalies_weekly` | Bajo | **SÍ** | Header freshness |
| `GET /ops/supply/freshness` | `ops.py:1263` | `supply_service.get_supply_freshness()` | **SÍ** | No | `mv_supply_segments_weekly`, `supply_refresh_log` | Bajo | N/A (es el propio chequeo) | OK, es buen patrón |

### 3B — Endpoints de refresh (POST, mutación)

| Endpoint | Router | Service | Dispara refresh | Qué refresca | Riesgo | Recomendación |
|----------|--------|---------|-----------------|-------------|--------|---------------|
| `POST /ops/supply/refresh` | `ops.py:2379` | `supply_service.refresh_supply_alerting_mvs()` | **SÍ** | 4 MVs supply encadenadas | **HIGH** — sin protección de concurrencia, sin validación previa | Agregar `pg_try_advisory_lock`. Rechazar si ya hay refresh en curso. |
| `POST /ops/supply/refresh-alerting` | `ops.py:2390` | Mismo | **SÍ** (requiere `SUPPLY_REFRESH_ALLOWED=true`) | 4 MVs supply encadenadas | **MEDIUM** — tiene gate de env var pero sin lock | Agregar lock. |
| `POST /ops/pipeline-refresh` | `ops.py:2339` | `run_pipeline_refresh_and_audit.py` (subprocess) | **SÍ** | **TODO**: hourly chain + drill + driver lifecycle + supply + PvR + audits | **CRITICAL** — subprocess con timeout 3600s (1h). Si timeout, estado indefinido. No verifica si ya hay otro pipeline corriendo. | Agregar lock global. No usar subprocess; usar funciones DB con transactional guarantees. |
| `POST /ops/business-slice/real-refresh-omniview` | `ops.py:508` | `run_business_slice_real_refresh_job()` | **SÍ** | day_fact + week_fact + month_fact (2 meses) | **HIGH** — puede solaparse con el scheduler | Agregar advisory lock DB. |

### 3C — Driver Lifecycle (UI → service → MVs)

| Endpoint | Router | Service | Solo lectura | Fuentes | Riesgo |
|----------|--------|---------|-------------|---------|--------|
| `GET /ops/driver-lifecycle/weekly` | `driver_lifecycle.py:34` | `driver_lifecycle_service.get_weekly()` | **SÍ** | `mv_driver_lifecycle_weekly_kpis`, `mv_driver_weekly_stats`, `mv_driver_lifecycle_base`, `v_driver_weekly_churn_reactivation` | Medio — queries complejos con múltiples CTEs |
| `GET /ops/driver-lifecycle/monthly` | `driver_lifecycle.py:51` | `driver_lifecycle_service.get_monthly()` | **SÍ** | `mv_driver_lifecycle_monthly_kpis`, `mv_driver_monthly_stats`, `mv_driver_lifecycle_base` | Medio |
| `GET /ops/driver-lifecycle/series` | `driver_lifecycle.py:171` | `driver_lifecycle_service.get_series()` | **SÍ** | Mismos MVs, con CTEs complejos | **HIGH** — cuando no tiene park_id, hace full outer joins y window functions sobre datasets grandes |
| `GET /ops/driver-lifecycle/cohorts` | `driver_lifecycle.py:254` | `driver_lifecycle_service.get_cohorts()` | **SÍ** | `mv_driver_cohort_kpis`, `mv_driver_cohorts_weekly` | Medio — MVs de cohortes son opcionales |

### 3D — Omniview / Business Slice / Freshness

| Endpoint | Solo lectura | Fuentes | Riesgo |
|----------|-------------|---------|--------|
| `GET /ops/business-slice/omniview` | **SÍ** | `real_business_slice_month_fact`, `week_fact`, `day_fact` (tablas fact, no MVs) | Medio |
| `GET /ops/business-slice/real-freshness` | **SÍ** | `real_business_slice_day_fact`, `week_fact`, `month_fact`, upstream `trips_2026` | Bajo |
| `GET /ops/business-slice/omniview-projection` | **SÍ** | Plan projection + real facts | Medio |
| `GET /ops/data-freshness` | **SÍ** | `ops.data_freshness_audit` | Bajo |
| `GET /ops/plan-vs-real/monthly` | **SÍ** | `mv_plan_vs_real_monthly_fact` o legacy `v_plan_vs_real_realkey_final` | Medio — tiene fallback automático canonical/legacy |

---

## 4. Inventario de MVs y views

### 4A — Driver Lifecycle MVs

| MV/View | Upstream | Downstream | Refresh | Unique Index | Tipo | Riesgo | Recomendación |
|---------|----------|------------|---------|-------------|------|--------|---------------|
| `ops.mv_driver_lifecycle_base` | `v_driver_lifecycle_trips_completed` → `trips_unified` → `trips_2025+trips_2026` + `public.drivers` | `mv_driver_weekly_stats`, `mv_driver_monthly_stats`, `mv_driver_lifecycle_weekly_kpis`, `mv_driver_lifecycle_monthly_kpis` | **CONCURRENTLY** vía `ops.refresh_driver_lifecycle_mvs()` | **SÍ** (`driver_key`) | **Intermedia** (no serving directo a UI) | **CRITICAL** — si esta MV se corrompe, toda la cadena driver+supply colapsa | Agregar backup/restore. Validar post-refresh. |
| `ops.mv_driver_weekly_stats` | `v_driver_lifecycle_trips_completed` → `trips_unified` | `mv_driver_lifecycle_weekly_kpis`, `mv_driver_segments_weekly`, `mv_driver_monthly_stats` (indirecto), `driver_lifecycle_service` (todos los endpoints), `supply_service` (vía `mv_driver_segments_weekly`) | **CONCURRENTLY** | **SÍ** (`driver_key, week_start`) | **Intermedia crítica** — alimenta TODO supply y driver lifecycle | **CRITICAL** — full scan de `trips_unified` (~59M rows). Puede tomar >30min. Sin particionamiento. | Evaluar particionar por año/semana. Agregar refresh incremental para semanas nuevas. |
| `ops.mv_driver_monthly_stats` | `v_driver_lifecycle_trips_completed` → `trips_unified` | `mv_driver_lifecycle_monthly_kpis`, `mv_supply_monthly`, `driver_lifecycle_service` | **CONCURRENTLY** | **SÍ** (`driver_key, month_start`) | **Intermedia** | **HIGH** — mismo problema de full scan | Particionar. |
| `ops.mv_driver_lifecycle_weekly_kpis` | `mv_driver_weekly_stats`, `mv_driver_lifecycle_base`, `v_driver_weekly_churn_reactivation` | `driver_lifecycle_service` (endpoints weekly, series, summary) | **CONCURRENTLY** | **SÍ** (`week_start`) | **Serving** (directo a UI) | **MEDIUM** — agrega sobre MVs ya existentes, menos pesado | OK como serving layer. |
| `ops.mv_driver_lifecycle_monthly_kpis` | `mv_driver_monthly_stats`, `mv_driver_lifecycle_base` | `driver_lifecycle_service` | **CONCURRENTLY** | **SÍ** (`month_start`) | **Serving** | **MEDIUM** | OK. |
| `ops.v_driver_weekly_churn_reactivation` | `mv_driver_weekly_stats` (VIEW, no MV) | `mv_driver_lifecycle_weekly_kpis`, `driver_lifecycle_service` | N/A (es VIEW) | N/A | **Intermedia** | **LOW** | OK. |

### 4B — Supply MVs

| MV/View | Upstream | Downstream | Refresh | Unique Index | Tipo | Riesgo | Recomendación |
|---------|----------|------------|---------|-------------|------|--------|---------------|
| `ops.mv_driver_segments_weekly` | `mv_driver_weekly_stats` (+ `driver_segment_config` thresholds) | `mv_supply_segments_weekly`, `supply_service` (migration, drilldown, critical), `v_driver_segments_weekly_summary`, `v_driver_segment_critical_movements` | **CONCURRENTLY** vía `ops.refresh_supply_alerting_mvs()` | **SÍ** (`driver_key, week_start`) | **Intermedia** — alimenta supply segments + migration | **HIGH** — window functions LAG/AVG sobre dataset completo. Umbrales de segmentos via `driver_segment_config` (tabla), no hardcodeados. | Monitorear tiempo de refresh (>10min esperado). |
| `ops.mv_supply_segments_weekly` | `mv_driver_segments_weekly` | `supply_service` (segments series, composition, overview enhanced, migration), `mv_supply_segment_anomalies_weekly`, `confidence_signals` | **CONCURRENTLY** | **SÍ** (`week_start, park_id, segment_week`) | **Serving** (directo a UI) | **MEDIUM** — agrega drivers por segmento. Denominador del migration_rate. | OK como serving layer. |
| `ops.mv_supply_weekly` | `mv_driver_weekly_stats`, `v_driver_weekly_churn_reactivation` | `supply_service` (series, summary, global, overview) | **CONCURRENTLY** vía `ops.refresh_supply_mvs()` (función legacy, NO usada por pipeline principal) | **SÍ** (`week_start, park_id`) | **Serving** | **MEDIUM** — se refresca vía `refresh_supply_mvs()`, pero el pipeline principal usa `refresh_supply_alerting_mvs()` que NO la incluye. Puede quedar stale. | Incluir en `refresh_supply_alerting_mvs()` o unificar. |
| `ops.mv_supply_monthly` | `mv_driver_monthly_stats` | `supply_service` | **CONCURRENTLY** vía `ops.refresh_supply_mvs()` (mismo problema) | **SÍ** (`month_start, park_id`) | **Serving** | **MEDIUM** — mismo problema que `mv_supply_weekly` | Incluir en pipeline o unificar. |
| `ops.mv_supply_segment_anomalies_weekly` | `mv_supply_segments_weekly` | `mv_supply_alerts_weekly`, `supply_service` (alerts drilldown) | **CONCURRENTLY** | **SÍ** (`week_start, park_id, segment_week`) | **Intermedia** | **MEDIUM** — window function STDDEV_POP sobre 8 semanas. Baseline mínimo 30 drivers. | OK. |
| `ops.mv_supply_alerts_weekly` | `mv_supply_segment_anomalies_weekly` | `supply_service` (alerts) | **CONCURRENTLY** | **SÍ** (`week_start, park_id, segment_week, alert_type`) | **Serving** (directo a UI) | **LOW** | OK. |

### 4C — Real LOB / Hourly-first chain MVs

| MV | Upstream | Downstream | Refresh | Unique Index | Tipo | Riesgo |
|-----|----------|------------|---------|-------------|------|--------|
| `ops.mv_real_lob_hour_v2` | `trips_2026` (configurable) | `mv_real_lob_day_v2` | **CONCURRENTLY** (fallback non-concurrent) | UNKNOWN (verificar) | **Intermedia** | **HIGH** — si no tiene unique index, fallback a refresh no concurrente bloquea lecturas | Verificar unique index |
| `ops.mv_real_lob_day_v2` | `mv_real_lob_hour_v2` | `mv_real_lob_week_v3`, `real_drill_dim_fact` | **CONCURRENTLY** | UNKNOWN | **Intermedia** | **HIGH** | Verificar unique index |
| `ops.mv_real_lob_week_v3` | `mv_real_lob_day_v2` | `mv_real_lob_month_v3`, `real_drill_dim_fact` | **CONCURRENTLY** | UNKNOWN | **Intermedia** | **HIGH** | Verificar unique index |
| `ops.mv_real_lob_month_v3` | `mv_real_lob_week_v3` | Plan vs Real, endpoints Real LOB v2 | **CONCURRENTLY** | UNKNOWN | **Serving** | **HIGH** | Verificar unique index |

### 4D — Business Slice Fact Tables (NO son MVs)

| Tabla | Upstream | Refresh | Unique Index | Tipo | Riesgo |
|-------|----------|---------|-------------|------|--------|
| `ops.real_business_slice_month_fact` | `trips_2026` vía `ops.fn_real_trips_business_slice_resolved_subset` | **Carga incremental** (DELETE + INSERT por mes/chunk). NO es MV. | Índices compuestos | **Serving** (Omniview Matrix) | **LOW** — diseño incremental correcto |
| `ops.real_business_slice_week_fact` | `real_business_slice_day_fact` (rollup) | **Carga incremental** (INSERT desde day_fact) | Índices compuestos | **Serving** | **LOW** |
| `ops.real_business_slice_day_fact` | `trips_2026` vía función resuelta | **Carga incremental** por mes/día | Índices compuestos | **Serving** | **LOW** |
| `ops.real_business_slice_hour_fact` | `trips_2026` | **Carga incremental** por bloque horario | Índices | **Serving** (hourly-first) | **LOW** |

### 4E — Plan vs Real MVs

| MV | Upstream | Downstream | Refresh | Riesgo |
|----|----------|------------|---------|--------|
| `ops.mv_plan_vs_real_monthly_fact` | Plan tables + `mv_real_trips_monthly` | `plan_vs_real_service`, `/ops/plan-vs-real/monthly` | **CONCURRENTLY** | **MEDIUM** — tiene fallback canonical/legacy |
| `ops.mv_plan_vs_real_monthly_fact_canonical` | Plan tables + `mv_real_monthly_canonical_hist` | Mismo endpoint (source=canonical) | **CONCURRENTLY** | **LOW** — es más nueva, más rápida |

### 4F — Configuración de segmentos

| Tabla | Descripción | Refresh | Lectura |
|-------|-------------|---------|---------|
| `ops.driver_segment_config` | Umbrales de segmentos (FT>=60, PT>=20, CASUAL>=5, OCCASIONAL>=1, DORMANT=0, + ELITE/LEGEND) con `is_active`, `effective_from/to` | No requiere | `supply_service.get_supply_segment_config()`, `mv_driver_segments_weekly` (indirectamente) |

---

## 5. Mapas de dependencia

### 5A — Supply / Lifecycle

```
public.trips_2025 ──┐
                     ├──> public.trips_unified (VIEW)
public.trips_2026 ──┘           │
public.drivers ─────────────────┤
                                ▼
                ops.v_driver_lifecycle_trips_completed (VIEW)
                                │
            ┌───────────────────┼───────────────────────┐
            ▼                   ▼                       ▼
ops.mv_driver_lifecycle_base   ops.mv_driver_weekly_stats   ops.mv_driver_monthly_stats
 (1 fila x driver)              (driver x week)              (driver x month)
            │                   │                           │
            │   ┌───────────────┤                           │
            │   │               │                           │
            ▼   ▼               ▼                           ▼
ops.mv_driver_lifecycle    ops.mv_driver_segments_weekly    ops.mv_driver_lifecycle
  _weekly_kpis               (segment_week por driver)        _monthly_kpis
  (serving)                          │                        (serving)
            │                        │
            │    ┌───────────────────┤
            │    ▼                   ▼
            │ ops.mv_supply_       ops.mv_supply_segments_weekly
            │   weekly               (agregado park x segment)
            │   (serving)                   │
            │                               ├──> ops.mv_supply_segment_anomalies_weekly
            │                               │         (z-score, baseline 8w)
            │                               │              │
            │                               │              ▼
            │                               │    ops.mv_supply_alerts_weekly
            │                               │         (serving → UI)
            │                               │
            ▼                               ▼
     driver_lifecycle_service           supply_service
            │                               │
            ▼                               ▼
  GET /ops/driver-lifecycle/*        GET /ops/supply/*
  (weekly, monthly, series,           (migration, composition,
   summary, cohorts, parks)            alerts, overview, segments)
```

**Nota crítica**: `ops.mv_supply_weekly` y `ops.mv_supply_monthly` NO se refrescan en el pipeline principal (`refresh_supply_alerting_mvs`). Se refrescan vía `ops.refresh_supply_mvs()` (función legacy en migración 060) que NO es llamada por ningún script del pipeline. **Pueden quedar permanentemente stale**.

### 5B — Business Slice / Omniview

```
public.trips_2026 (OMNIVIEW_UPSTREAM_TRIPS_TABLE)
            │
            ├──> ops.mv_real_lob_hour_v2 ──> ops.mv_real_lob_day_v2
            │         (hourly-first chain)        │
            │                                     ├──> ops.mv_real_lob_week_v3
            │                                     │         │
            │                                     │         └──> ops.mv_real_lob_month_v3
            │                                     │
            │                                     └──> real_drill_dim_fact (tabla)
            │
            └──> ops.fn_real_trips_business_slice_resolved_subset()
                      │
                      ├──> ops.real_business_slice_hour_fact
                      ├──> ops.real_business_slice_day_fact
                      │         │
                      │         └──> ops.real_business_slice_week_fact (rollup desde day)
                      │
                      └──> ops.real_business_slice_month_fact
                                │
                                ▼
                      business_slice_omniview_service
                                │
                                ▼
                      GET /ops/business-slice/omniview
                      GET /ops/business-slice/omniview-projection
                      (Omniview Matrix → frontend)
```

**Nota**: Las business slice fact tables NO dependen de las MVs de hourly-first chain. Son dos pipelines paralelos que leen de `trips_2026`. Esto es BUENO para desacoplamiento pero MALO si divergen.

### 5C — Plan vs Real

```
Plan tables (staging Control Loop) ──┐
                                      ├──> ops.mv_plan_vs_real_monthly_fact (legacy)
ops.mv_real_trips_monthly ────────────┘         │
                                                ▼
ops.mv_real_monthly_canonical_hist ──> ops.mv_plan_vs_real_monthly_fact_canonical
                                                │
                                                ▼
                                      plan_vs_real_service
                                                │
                                    ┌───────────┴───────────┐
                                    ▼                       ▼
                          GET /ops/plan-vs-real/monthly    GET /ops/plan-vs-real/alerts
                          (source=canonical o legacy)
```

### 5D — Freshness / Observability

```
┌─────────────────────────────────────────────────────────────┐
│ FUENTES MONITOREADAS                                        │
│                                                             │
│ trips_2026 ────> upstream_real_status_service              │
│   │             (max_event_date, lag_days, row_count)       │
│   │                                                         │
│   ├──> mv_real_lob_hour_v2 ──> day_v2 ──> week_v3 ──> month_v3
│   │                                                         │
│   └──> real_business_slice_{day,week,month}_fact            │
│                                                             │
│ mv_driver_weekly_stats ──> supply MVs                       │
│                                                             │
│ mv_driver_weekly_stats ──> driver_lifecycle MVs             │
│                                                             │
│ Plan tables ──> plan_vs_real MVs                            │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
                    data_freshness_service
                    (ops.data_freshness_audit)
                    confidence_engine
                    (completeness + consistency)
                                │
                                ▼
              GET /ops/data-freshness
              GET /ops/data-freshness/alerts
              GET /ops/data-freshness/global
              GET /ops/data-confidence
              GET /ops/business-slice/real-freshness
              GET /ops/supply/freshness
```

---

## 6. Separación open vs closed period

### Cómo funciona hoy

| Componente | Estado actual | Detalle |
|------------|--------------|---------|
| `period_semantics_service.py` | **EXISTE** — define `last_closed_week`, `last_closed_month`, `current_open_week`, `current_open_month` | `backend/app/services/period_semantics_service.py:27-112` — solo para labels de UI y lógica de comparativos. **No se usa para protección de datos.** |
| `period_closed` en vistas drill | **EXISTE** — vistas de drill (`v_real_drill_calendar_month`, `v_real_drill_calendar_week`) tienen columna `period_closed` | Definido como `period_start < current_month` (o `current_week`). Se usa para marcar `VACIO` si un periodo cerrado tiene 0 trips. Solo en vistas de drill, no en MVs principales. |
| Protección de periodo cerrado en refrescos | **NO EXISTE** | Ningún script de refresh verifica si un periodo está cerrado. Todos los `REFRESH MATERIALIZED VIEW` son completos. |
| `last_reliable_data_date` | **NO EXISTE** | No hay un concepto explícito de "último día confiable". El freshness se calcula como `max(trip_date)` vs `today`. |
| Backfill explícito | **PARCIAL** — `refresh_business_slice_mvs.py` tiene `--backfill-from/to` | Solo para business slice facts. Driver lifecycle y supply no tienen modo backfill. |

### Qué falta

1. **No hay flag `is_closed` en ninguna tabla de hechos o MVs**. Los periodos cerrados no se distinguen de los abiertos a nivel de datos.
2. **No hay `refresh_ledger`** que registre qué periodos fueron refrescados, cuándo y con qué hash.
3. **No hay `advisory_lock` por periodo** que impida refrescar un mes/trimestre cerrado.
4. **No hay `data_version` o `snapshot_id`** que permita saber si los datos que ve el usuario son de la corrida N o N-1.
5. **Los refrescos completos de MVs tocan TODO el histórico**, incluyendo meses/semanas de 2023, 2024, 2025 que deberían ser inmutables.

### Riesgo

| Riesgo | Severidad | Descripción |
|--------|-----------|-------------|
| Recalcular historia sin backfill explícito | **CRITICAL** | Cada `REFRESH MATERIALIZED VIEW` recalcula desde el primer viaje en `trips_unified`. Si hay un cambio en la lógica de negocio (umbrales de segmentos, mapeo de parks, etc.), TODOS los periodos históricos cambian sin trazabilidad. |
| Datos cerrados corruptos por refresh fallido | **CRITICAL** | Si `ops.refresh_supply_alerting_mvs()` falla en la 3ra MV, las 2 primeras ya tienen datos nuevos (posiblemente corruptos o parciales) y no hay rollback. |
| Divergencia entre fuentes | **HIGH** | `mv_supply_weekly` y `mv_supply_monthly` se refrescan vía una función distinta (`ops.refresh_supply_mvs()`) que NO es llamada por el pipeline principal. Pueden mostrar datos de semanas diferentes a `mv_driver_segments_weekly`. |

### Recomendación

1. **Crear tabla `ops.period_state`** con columnas `period_start`, `grain` (week/month), `is_closed`, `closed_at`, `data_hash`, `refresh_count`.
2. **Modificar funciones de refresh** para que, si `is_closed = true`, requieran flag explícito `allow_closed_period_refresh`.
3. **Agregar `ops.refresh_ledger`** que registre cada corrida con: `run_id`, `started_at`, `finished_at`, `status`, `affected_periods`, `data_hash_before`, `data_hash_after`.
4. **Crear política**: periodos con `is_closed = true` solo se recalculan vía backfill autorizado con ticket/documento.

---

## 7. Hallazgos críticos

### CRITICAL

| ID | Hallazgo | Archivo/Ubicación | Impacto |
|----|----------|-------------------|---------|
| **C1** | **Refrescos completos sin protección de periodo cerrado** | `ops.refresh_driver_lifecycle_mvs()` en `backend/sql/driver_lifecycle_build.sql:272-288`, `ops.refresh_supply_alerting_mvs()` en `backend/alembic/versions/063_supply_segments_alerts_weekly.py:316-328` | Cada corrida recalcula TODO el histórico (~59M trips). Datos de 2023-2025 se recalculan innecesariamente. Si hay bug en lógica, corrompe historia. |
| **C2** | **Sin advisory lock entre pasos del pipeline** | `run_pipeline_refresh_and_audit.py:76-117` (steps 1-6 secuenciales), `refresh_hourly_first_chain.py:36-86` | Dos crons simultáneos pueden correr pipelines solapados. Si un refresh falla a mitad, estado inconsistente entre MVs. |
| **C3** | **mv_supply_weekly y mv_supply_monthly NO se refrescan en el pipeline principal** | `run_pipeline_refresh_and_audit.py:107` solo llama `refresh_supply_alerting_mvs()` que refresca 4 MVs pero NO incluye `mv_supply_weekly` ni `mv_supply_monthly`. Esas solo se refrescan vía `ops.refresh_supply_mvs()` (migración 060) que no es llamada por nadie. | Los endpoints `GET /ops/supply/series`, `GET /ops/supply/summary`, `GET /ops/supply/global/series` leen `mv_supply_weekly`/`mv_supply_monthly` que pueden estar **permanentemente stale**. |
| **C4** | **No hay trazabilidad de qué datos ve el usuario** | Todos los endpoints GET de supply, driver lifecycle, etc. | El usuario no sabe si está viendo datos de la corrida de refresh de hoy, de ayer o de hace una semana. No hay header `X-Data-Freshness` ni `X-Last-Refresh`. |
| **C5** | **Driver lifecycle MVs se recrean con DROP + CREATE en build** | `backend/sql/driver_lifecycle_build.sql:14-286` — cada sentencia hace `DROP MATERIALIZED VIEW IF EXISTS ... CASCADE` seguido de `CREATE MATERIALIZED VIEW ...` | Si el script falla después del DROP y antes del CREATE, la MV desaparece y todos los endpoints que dependen de ella fallan. No es idempotente. |

### HIGH

| ID | Hallazgo | Archivo/Ubicación | Impacto |
|----|----------|-------------------|---------|
| **H1** | **APScheduler en backend puede solaparse con pipelines externos** | `backend/app/main.py:121-176` — `BackgroundScheduler` corre `run_business_slice_real_refresh_job` y `run_real_data_watchdog` en el proceso del backend. Si hay múltiples workers (gunicorn con >1 worker), múltiples schedulers corren simultáneamente. | Race condition: múltiples workers refrescando las mismas fact tables. El cooldown `_last_refresh_completed_ts` es in-process, no compartido entre workers. |
| **H2** | **No hay rollback si refresh de supply falla a medias** | `ops.refresh_supply_alerting_mvs()` en migración 063 refresca 4 MVs secuencialmente. Si falla en la 3ra, las 2 primeras ya tienen datos nuevos. | Estado inconsistente: `mv_driver_segments_weekly` actualizada pero `mv_supply_alerts_weekly` stale. |
| **H3** | **Hourly-first chain sin unique index confirmado en todas las MVs** | `refresh_hourly_first_chain.py:60-82` — fallback a refresh no CONCURRENTLY si unique index no existe. | Refresh no CONCURRENTLY bloquea LECTURAS en la MV durante el refresh (~minutos). UI se congela para usuarios de Real LOB / Drill. |
| **H4** | **GET /ops/driver-lifecycle/series sin park_id hace full outer joins pesados** | `driver_lifecycle_service.py:936-1047` — 6 CTEs con FULL OUTER JOINs y window functions cuando no hay park_id. | Puede saturar la DB si un usuario pide un rango amplio sin filtro. |
| **H5** | **POST /ops/pipeline-refresh usa subprocess con timeout 3600s** | `ops.py:2339-2376` — ejecuta `run_pipeline_refresh_and_audit.py` como subprocess. Si timeout, el subprocess sigue corriendo en background. | Dos pipelines pueden correr simultáneamente sin detección. |
| **H6** | **Business slice month_fact se recalcula cada vez que corre el scheduler** | `business_slice_real_refresh_job.py:128-144` — recalcula `month_fact` para mes actual + anterior CADA vez. `OMNIVIEW_REAL_REFRESH_INCLUDE_MONTH_FACT` default=True. | El mes anterior (cerrado) se recalcula innecesariamente. Es caro (re-materialización completa). |

### MEDIUM

| ID | Hallazgo | Archivo/Ubicación | Impacto |
|----|----------|-------------------|---------|
| **M1** | **No hay timeout de query en endpoints de lectura** | `supply_service.py` y `driver_lifecycle_service.py` — solo `driver_lifecycle_service` tiene `statement_timeout=60000ms`. `supply_service` no configura timeout. | Una query lenta puede mantener conexiones abiertas indefinidamente. |
| **M2** | **Falta de índices en `trips_unified` para filtros comunes** | `backend/sql/driver_lifecycle_build.sql:14-27` — la vista `v_driver_lifecycle_trips_completed` filtra por `condicion='Completado'`, `conductor_id IS NOT NULL`, `fecha_inicio_viaje IS NOT NULL`. | Full scan de `trips_unified` (~59M rows) cada refresh. |
| **M3** | **Supply freshness solo mira `mv_supply_segments_weekly`, no `mv_supply_weekly`** | `supply_service.py:587-658` | Si `mv_supply_segments_weekly` está fresca pero `mv_supply_weekly` está stale (no se refresca en pipeline), el freshness reporta "fresh" incorrectamente. |
| **M4** | **No hay métricas de duración de refresh por paso** | `run_pipeline_refresh_and_audit.py` tiene logs pero no persiste duraciones en DB. | Imposible detectar degradación de performance sin consultar logs. |
| **M5** | **`driver_segment_config` puede cambiar umbrales sin invalidar MVs** | `ops.driver_segment_config` — los umbrales de segmentos (FT>=60, PT>=20, etc.) se leen de esta tabla. Si se cambian, las MVs no se invalidan automáticamente. | Discrepancia entre configuración y datos hasta el próximo refresh. |

### LOW

| ID | Hallazgo | Archivo/Ubicación | Impacto |
|----|----------|-------------------|---------|
| **L1** | `ops.refresh_supply_mvs()` es función legacy no utilizada | `backend/alembic/versions/060_supply_mvs_and_refresh.py:156-168` | Código muerto. Puede confundir. |
| **L2** | `skip-backfill` es no-op en pipeline | `run_pipeline_refresh_and_audit.py:221-233` | Flag aceptado pero ignorado. Puede confundir a operadores. |
| **L3** | `get_supply_freshness()` usa lógica de fecha hardcodeada | `supply_service.py:615-635` — expected_week, cutoff 36h | Umbrales no configurables. |

---

## 8. Recomendaciones de hardening por fases

### Fase 1A — Auditoría y mapa de dependencias (ESTA FASE)

- [x] Completada con este documento.

### Fase 1B — Separar lectura vs refresh

**Objetivo**: Ningún GET dispara refresh. Todo refresh es explícito y trazable.

1. Crear `POST /ops/admin/refresh/{domain}` con parámetros explícitos: `--domain driver|supply|business-slice|plan-vs-real`, `--scope full|recent|period`, `--period-from`, `--period-to`.
2. Eliminar `POST /ops/supply/refresh` sin gate de lock.
3. Mover `POST /ops/pipeline-refresh` a un endpoint admin con autenticación.
4. Validar que ningún GET en `ops.py`, `driver_lifecycle.py`, `real.py`, `plan.py` llame funciones de refresh.

### Fase 1C — Refresh ledger

**Objetivo**: Cada refresh deja registro inmutable.

1. Crear tabla `ops.refresh_ledger`:
   ```sql
   CREATE TABLE ops.refresh_ledger (
       run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
       domain TEXT NOT NULL,           -- 'driver_lifecycle', 'supply', 'hourly_chain', 'business_slice'
       started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
       finished_at TIMESTAMPTZ,
       status TEXT NOT NULL DEFAULT 'running',  -- 'running', 'ok', 'failed', 'partial'
       affected_objects TEXT[],        -- ARRAY de MVs/tablas refrescadas
       rows_before BIGINT[],
       rows_after BIGINT[],
       data_hash_before TEXT,
       data_hash_after TEXT,
       error_message TEXT,
       triggered_by TEXT,              -- 'cron', 'manual', 'scheduler', 'api'
       advisory_lock_acquired BOOLEAN
   );
   ```
2. Modificar todas las funciones de refresh para insertar en `refresh_ledger`.
3. Agregar `GET /ops/admin/refresh-ledger?domain=X&limit=N` para auditoría.

### Fase 1D — Closed period protection

**Objetivo**: Datos de periodos cerrados no se recalculan sin backfill explícito.

1. Crear tabla `ops.period_state`:
   ```sql
   CREATE TABLE ops.period_state (
       period_start DATE NOT NULL,
       grain TEXT NOT NULL,            -- 'day', 'week', 'month'
       domain TEXT NOT NULL,           -- 'driver_lifecycle', 'supply', 'business_slice'
       is_closed BOOLEAN NOT NULL DEFAULT false,
       closed_at TIMESTAMPTZ,
       closed_by TEXT,
       data_hash TEXT,
       refresh_count INT DEFAULT 0,
       last_refresh_at TIMESTAMPTZ,
       PRIMARY KEY (period_start, grain, domain)
   );
   ```
2. Modificar `ops.refresh_driver_lifecycle_mvs()` y `ops.refresh_supply_alerting_mvs()` para:
   - Leer `period_state` y solo refrescar periodos con `is_closed = false`.
   - Si se pasa flag `force_closed = true`, refrescar todo pero registrar en ledger.
3. Agregar `POST /ops/admin/period/close` y `POST /ops/admin/period/reopen`.
4. Agregar política: cerrar mes anterior el día 5 del mes siguiente. Cerrar semana anterior el lunes siguiente.

### Fase 1E — Serving layer Omniview

**Objetivo**: Omniview Matrix lee de serving MVs rápidas, no de MVs intermedias pesadas.

1. Business slice facts YA son serving (tablas fact, no MVs). **Mantener.**
2. Crear serving MVs para supply migration que pre-agreguen los datos más consultados:
   - `ops.mv_supply_migration_serving` (agregado pre-calculado por semana, park, from_segment, to_segment).
3. Agregar políticas de caché en endpoints de lectura (CDN o Redis para datos de periodos cerrados).

### Fase 1F — Performance / indexes

**Objetivo**: Refrescos rápidos, lecturas < 2s.

1. Agregar índice en `trips_unified` para `(condicion, conductor_id, fecha_inicio_viaje)`.
2. Agregar índice en `trips_unified` para `(fecha_inicio_viaje)` para filtros de fecha.
3. Agregar `statement_timeout` configurable en `supply_service` (actualmente no tiene).
4. Migrar MVs de driver lifecycle a particionamiento por año (2023, 2024, 2025, 2026).
5. Monitorear tiempos de refresh vía `refresh_ledger` y alertar si exceden baseline.

### Fase 1G — QA regression

**Objetivo**: Detectar regresiones antes de producción.

1. Agregar tests de integración que:
   - Ejecuten refresh de un dominio y verifiquen row counts pre/post.
   - Verifiquen que periodos cerrados no cambian.
   - Verifiquen que el hash de datos de periodo cerrado es estable.
2. Agregar smoke test que llame a los endpoints críticos y verifique HTTP 200 + freshness header.
3. Agregar test de concurrencia: dos refrescos simultáneos → el segundo debe ser rechazado.

---

## 9. Cambios que NO deben hacerse todavía

| Prohibición | Razón |
|-------------|-------|
| **NO migrar MVs a particionamiento sin antes tener refresh ledger** | Sin trazabilidad, un error de particionamiento podría perder datos históricos sin forma de recuperarlos. |
| **NO cambiar la lógica de umbrales en `driver_segment_config`** | Cambiar umbrales de segmentos (FT>=60, PT>=20, etc.) cambiaría TODOS los datos históricos en el próximo refresh. Requiere backfill planificado y ventana de mantenimiento. |
| **NO desactivar el APScheduler sin antes tener cron externo** | El scheduler es la única forma en que business slice facts se mantienen frescos. Si se desactiva, Omniview muestra datos stale. |
| **NO unificar `refresh_supply_mvs()` con `refresh_supply_alerting_mvs()` sin antes validar que `mv_supply_weekly` y `mv_supply_monthly` existen y tienen unique index** | Podría romper el pipeline si las MVs no están listas. |
| **NO tocar frontend** | Esta fase es solo backend/data. |
| **NO modificar Omniview Matrix** | Es la superficie de serving principal. Cualquier cambio debe ser coordinado con validación visual. |
| **NO crear nuevas migraciones sin revisión** | Cualquier migración debe ser revisada en entorno staging primero. |
| **NO eliminar código legacy sin inventario completo** | `ops.refresh_supply_mvs()`, `backfill_real_lob_mvs`, etc. pueden ser usados por scripts externos no versionados. |

---

## 10. Primer prompt de implementación recomendado

**ATENCIÓN**: NO ejecutar este prompt ahora. Es una propuesta para la siguiente fase.

---

### Prompt: Fase 1B — Advisory Locks + Refresh Ledger (base de confiabilidad)

```
Tarea: Implementar advisory locks y refresh ledger para proteger las cadenas de refresh.

ARCHIVOS A MODIFICAR (EN ORDEN):

1. backend/alembic/versions/139_refresh_ledger_and_locks.py (NUEVA migración):
   - Crear tabla ops.refresh_ledger con columnas: run_id UUID, domain TEXT, started_at, finished_at, status, affected_objects TEXT[], rows_before BIGINT[], rows_after BIGINT[], data_hash_before TEXT, data_hash_after TEXT, error_message TEXT, triggered_by TEXT, advisory_lock_acquired BOOLEAN.
   - NO crear period_state todavía (eso es Fase 1D).
   - Hacer downgrade con DROP TABLE IF EXISTS.

2. backend/sql/driver_lifecycle_build.sql (función ops.refresh_driver_lifecycle_mvs):
   - Agregar pg_try_advisory_lock(173648291) al inicio. Si no se adquiere, RAISE EXCEPTION 'refresh_driver_lifecycle_mvs: otro refresh en curso'.
   - Insertar fila en ops.refresh_ledger con status='running'.
   - Al finalizar, actualizar status='ok' + rows_after.
   - En EXCEPTION, actualizar status='failed' + error_message.
   - SOLTAR advisory lock al final.

3. backend/alembic/versions/063_supply_segments_alerts_weekly.py:
   - NO modificar migración 063. Crear NUEVA migración 140 que haga CREATE OR REPLACE de ops.refresh_supply_alerting_mvs() con locks y ledger.
   - Mismo patrón: advisory_lock, ledger insert, try/catch, unlock.

4. backend/app/services/supply_service.py (refresh_supply_alerting_mvs):
   - Agregar log de run_id.
   - No hacer cambios estructurales, solo logging.

5. backend/scripts/run_pipeline_refresh_and_audit.py:
   - Agregar --force flag que ignora locks (para admin).
   - Verificar que cada paso captura errores sin detener el pipeline (actualmente usa `and ok`).

6. backend/app/services/business_slice_real_refresh_job.py:
   - Reemplazar cooldown en memoria (_last_refresh_completed_ts) con pg_try_advisory_lock(173648292).
   - Insertar en refresh_ledger (domain='business_slice').

VALIDACIONES:
- Ejecutar migración 139: verificar que ops.refresh_ledger existe.
- Ejecutar migración 140: verificar que ops.refresh_supply_alerting_mvs() tiene lock.
- Correr dos refresh simultáneos: el segundo debe fallar con mensaje claro.
- Verificar que refresh_ledger tiene filas después de un refresh exitoso.
- Verificar que refresh_ledger tiene fila con status='failed' después de un refresh fallido.

NO HACER:
- NO crear period_state.
- NO modificar lógica de qué datos se refrescan (solo agregar locks y ledger).
- NO cambiar endpoints de lectura.
- NO tocar frontend.
```

---

## Apéndice A: Referencias rápidas a archivos clave

| Archivo | Línea(s) clave | Qué contiene |
|---------|---------------|-------------|
| `backend/sql/driver_lifecycle_build.sql` | 272-288 | `ops.refresh_driver_lifecycle_mvs()` — 5 MVs CONCURRENTLY |
| `backend/alembic/versions/063_supply_segments_alerts_weekly.py` | 316-328 | `ops.refresh_supply_alerting_mvs()` — 4 MVs CONCURRENTLY |
| `backend/alembic/versions/060_supply_mvs_and_refresh.py` | 156-168 | `ops.refresh_supply_mvs()` — 2 MVs (LEGACY, no usada en pipeline) |
| `backend/scripts/run_pipeline_refresh_and_audit.py` | 76-117, 205-273 | Orquestador: 6 pasos secuenciales |
| `backend/scripts/refresh_hourly_first_chain.py` | 36-86 | 4 MVs: hour→day→week→month |
| `backend/scripts/run_supply_refresh_pipeline.py` | 38-111 | Wrapper de `refresh_supply_alerting_mvs()` con log |
| `backend/app/services/supply_service.py` | 533-545, 980-1155 | `refresh_supply_alerting_mvs()` + 4 migration endpoints |
| `backend/app/services/driver_lifecycle_service.py` | 162-453, 936-1154 | weekly, monthly, series, drilldown |
| `backend/app/services/business_slice_real_refresh_job.py` | 46-200 | Scheduler job: recalcula 2 meses |
| `backend/app/services/business_slice_real_freshness_service.py` | 167-259 | Payload freshness Omniview |
| `backend/app/services/period_semantics_service.py` | 27-112 | open/closed week/month (solo labels) |
| `backend/app/services/upstream_real_status_service.py` | 72-185 | Estado de `trips_2026` |
| `backend/app/main.py` | 121-176 | APScheduler startup (refresh + watchdog) |
| `backend/app/routers/ops.py` | 1180-1250, 2339-2401 | Supply migration GETs + pipeline POSTs |
| `backend/app/routers/driver_lifecycle.py` | 34-391 | Driver Lifecycle GETs |
| `backend/app/routers/ops_refresh.py` | 18-122 | Refresh status GETs + trigger POST |
| `backend/alembic/versions/092_observability_artifact_registry_and_refresh_log.py` | 146-148 | Registro de MVs en observability |

## Apéndice B: ¿Cómo confirmar hallazgos UNKNOWN?

1. **Unique index en MVs de hourly-first chain**: Ejecutar `SELECT indexdef FROM pg_indexes WHERE schemaname='ops' AND tablename IN ('mv_real_lob_hour_v2','mv_real_lob_day_v2','mv_real_lob_week_v3','mv_real_lob_month_v3') AND indexdef ILIKE '%UNIQUE%'`.
2. **Si `ops.refresh_supply_mvs()` es llamada desde algún script externo**: Buscar en cron del servidor, PM2 config, o scripts de deploy.
3. **Tiempos reales de refresh**: Ejecutar `EXPLAIN ANALYZE REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_weekly_stats` en entorno staging.
4. **Si `mv_supply_weekly` está stale**: Comparar `MAX(week_start)` de `mv_supply_weekly` vs `mv_supply_segments_weekly` vs `mv_driver_weekly_stats`.
