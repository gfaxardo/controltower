# YEGO CONTROL TOWER — TRUTH MAP

**Version:** 1.0.0
**Date:** 2026-06-13
**Status:** FIRST DRAFT — Evidence from live code audit (router → service → repository → DB)
**Method:** Deep trace of all 87 routers, 217 services, actual SQL queries, actual data flows

---

## 1. MOTORS — ACTUAL STATE (not documentation)

### 1.1 ACTIVE Motors

| # | Motor | Código | Estado Real | Evidencia |
|---|-------|--------|-------------|-----------|
| 1 | **Control Foundation** | CF | **REOPENED / P0** | `ai_current_phase.md:16` — OMNI-P0 False GO Recovery. Control Foundation CLOSED el 2026-05-29 pero REOPENED 2026-06-03. El cierre previo fue invalidado por validación DOM-only. |
| 2 | **Growth Machine** | GM | **ACTIVE** | 50+ routers bajo `/yego-lima-growth/*`, pipeline diario con scheduler autónomo, 15-step pipeline orquestado por `yego_lima_daily_pipeline_service.py`. NO depende de Control Foundation para operar. |
| 3 | **Omniview V2** | OV2 | **ACTIVE (parallel)** | 3 routers activos (`omniview_v2.py`, `shadow`, `shell`), snapshot-first architecture, driver bridge cascade. No integración con UI todavía pero backend 100% funcional. |

### 1.2 READY NEXT

| # | Motor | Estado Real | Evidencia |
|---|-------|-------------|-----------|
| 4 | **Diagnostic Engine** | **PAUSED** | `ai_current_phase.md:123` — "PAUSED hasta que OMNI-P0 cierre con GO real". Servicios existen pero no activados como motor. |

### 1.3 BLOCKED

| # | Motor | Estado Real | Bloqueado por |
|---|-------|-------------|---------------|
| — | Forecast Engine | BLOCKED | Control Foundation no cerrado con GO real |
| — | Suggestion Engine | BLOCKED | Forecast Engine no activo |
| — | Decision Engine | BLOCKED | Suggestion Engine no activo |
| — | Action Engine | BLOCKED | Decision Engine no activo |
| — | AI Copilot | BLOCKED | Motores previos no completados |
| — | Learning Engine | BLOCKED | Sin historial de acciones ejecutadas (mín 3 meses) |

### 1.4 EXPERIMENTAL / PROTOTYPE

| Código | Motor real | Estado | Nota |
|--------|-----------|--------|------|
| `action_engine_service.py` | Control Foundation | **PROTOTYPE** | Almacena alertas operativas por ciudad/día en `ops.action_engine_output`. NO es Action Engine real. La API de "cohortes" es capa de compatibilidad: mapea `action_id` → `cohort_type`. |
| `projection_integrity_service.py` | Control Foundation | **PILOT** | Proyecciones con seasonality curves. Funciona, pero NO debe considerarse Forecast Engine. |
| `action_learning_service.py` | Learning Engine | **PROTOTYPE** | Multiplicadores de efectividad para action_engine. No activable sin 3+ meses de datos. |

---

## 2. FASES — RECONSTRUCCIÓN REAL

### 2.1 Fase Actual

**Omniview P0 Recovery (OMNI-P0)**

- **Estado:** ACTIVE (reopened 2026-06-03)
- **Objetivo:** Deprecar Evolution, canonizar Vs Proy, contrato de celda cross-métrica, Revenue serving completo, CLOSED/PARTIAL visibility, certificación semántica real
- **Bloquea:** Diagnostic Engine 2A.3

### 2.2 Fase Siguiente

**Diagnostic Engine 2A.3 — Behavioral Pattern Diagnosis**

- **Estado:** PAUSED (hasta GO real en OMNI-P0)
- **Pre-requisito:** OMNI-P0 cerrado con validación semántica real

### 2.3 Fases Cerradas (con GO real)

| Fase | Documento | Fecha | GO |
|------|-----------|------|----|
| Control Foundation Phase 1 | `CONTROL_FOUNDATION_CLOSURE_REPORT.md` | 2026-05-29 | 11 GO / 1 CONDITIONAL |
| CF-H1: Revenue Certification | `CF_H1_FINAL_CERTIFICATION.md` | — | GO |
| CF-H1 Operational | `CF_H1_OPERATIONAL_CLOSURE.md` | — | GO |
| Phase 1G.2 Closure | `CIERRE_FASE1G2_CONTROL_FOUNDATION_CLOSURE.md` | — | GO |
| Phase 1H.4 Maturity Governance | `CIERRE_FASE1H4_MATURITY_GOVERNANCE.md` | — | GO |

### 2.4 Fases Parcialmente Cerradas

| Fase | Estado | Razón |
|------|--------|-------|
| Omniview Hardening (1H) | **REOPENED** | False GO — validación era DOM tokens, no semántica operacional |
| Control Foundation (completo) | **REOPENED** | OMNI-P0 recovery activo |

### 2.5 Fases Reabiertas

| Fase | Reabierta | Razón |
|------|-----------|-------|
| OMNI-P0 | 2026-06-03 | Evolution confunde usuarios, Revenue celdas vacías, lógica cross-métrica inconsistente, CLOSED/PARTIAL no visible, falsos positivos en alertas |

---

## 3. CANÓNICOS POR DOMINIO

### 3.1 OMNIVIEW V2

| Capa | Fuente de Verdad | Evidencia |
|------|-----------------|-----------|
| **Tabla RAW** | `public.trips_2026` | Fuente de todos los viajes. Leída por `build_driver_bridge_direct.py`. |
| **Driver Bridge** | `ops.driver_day_slice_fact` | **CANONICAL FOUNDATION.** Agrega viajes por (driver, día, park, business_slice). Construido por `build_driver_bridge_direct.py` con UPSERT. 1 solo writer. Leído por Omniview V2 matrix/drill/audit/reconciliation/freshness. |
| **Day Fact** | `ops.real_business_slice_day_fact` | Reconstruido desde Driver Bridge por `rebuild_day_from_bridge.py`. Leído directamente por UI (daily grain). 6 writers — riesgo de race condition. |
| **Week Fact** | `ops.real_business_slice_week_fact` | Reconstruido desde Day Fact + Bridge por `rebuild_week_from_day_and_bridge.py`. Leído directamente por UI (weekly grain). 6 writers (1 BROKEN: `rebuild_week_fact_from_day_fact.py`). |
| **Month Fact** | `ops.real_business_slice_month_fact` | Reconstruido desde Day Fact + Bridge por `rebuild_month_from_day_and_bridge.py`. 4 writers. |
| **Serving View** | `ops.v_real_business_slice_month_serving` | VIEW redirector: locked → `ops.real_business_slice_month_snapshot`, open → `ops.real_business_slice_month_fact`. Solo para monthly. |
| **Serving Snapshot** | `ops.omniview_v2_serving_snapshot` | Cache pre-construido. `/matrix` y `/shell` sirven desde aquí (snapshot-first). Runtime solo si `allow_runtime=true` o multi-day. |
| **Snapshot Builder** | `backend/scripts/refresh_omniview_v2_snapshots.py` | Script que llama `build_and_store_shell_snapshot()` y `build_and_store_matrix_snapshot()`. |
| **Pipeline** | `backend/scripts/run_ov2_refresh_cascade.py` | Cascade: bridge → day_fact → week_fact → month_fact → snapshot. |
| **Scheduler** | APScheduler (via `main.py`) | Disabled en producción (`CT_SCHEDULER_ENABLED=false`). |
| **Endpoint canónico** | `GET /ops/omniview-v2/matrix` | Snapshot-first. Runtime con `allow_runtime=true` o multi-day. |
| **UI consume** | `BusinessSliceOmniviewMatrix.jsx` | Omniview V1. Omniview V2 aún sin integración UI (docstrings confirman "No UI connection"). |

### 3.2 GROWTH MACHINE

| Capa | Fuente de Verdad | Evidencia |
|------|-----------------|-----------|
| **API externa** | Yango Fleet API | 3 endpoints: `orders/list`, `transactions/list`, `driver-profiles/list`. Auth: X-Client-ID + X-API-Key. |
| **Raw landing** | `raw_yango.orders_raw`, `raw_yango.transactions_raw`, `raw_yango.driver_profiles_raw` | INSERT ON CONFLICT DO NOTHING. Escritos por `yango_raw_ingestion_service.py`. |
| **Driver 360** | `growth.yango_lima_driver_360_daily` | 25 columnas. Construido por `yego_lima_driver_360_service.py`. UPSERT por (driver_profile_id, date). |
| **Driver History** | `growth.yango_lima_driver_history_weekly` | **STATUS: UNKNOWN WRITER.** Leído por driver_state_service como universo primario pero su writer no está en los servicios auditados. Posiblemente ETL externo o MV. |
| **State Snapshot** | `growth.yango_lima_driver_state_snapshot` | 3-axis canonical state: LIFECYCLE (7 estados), PERFORMANCE (5), RETENTION (4). Construido por `yego_lima_driver_state_service.py`. UPSERT. |
| **Program Eligibility** | `growth.yango_lima_program_eligibility_daily` | 3 programas: PROGRAM_14_90, PROGRAM_ACTIVE_GROWTH, PROGRAM_CHURN_PREVENTION. DELETE+INSERT por fecha. |
| **Opportunity Lists** | `growth.yango_lima_daily_opportunity_list` | DELETE+INSERT por fecha. Desde program_eligibility + state_snapshot. |
| **Action Registry** | `growth.yango_lima_driver_action_registry` | INSERT action, UPDATE status. Tabla canónica de acciones. |
| **Control Loop State** | `growth.yango_lima_control_loop_state` | State machine: READY→CONTACTED→DONE. Sincronizado desde assignment_queue. |
| **Pipeline** | `yego_lima_daily_pipeline_service.py` | 15-step pipeline. Orquestador maestro. Logs en `growth.yango_lima_pipeline_run_log`. |
| **Scheduler** | `yego_lima_scheduler_service.py` | Dual-mode: Daily Closed Pipeline + Live 5-min Monitoring. Autónomo (no depende de APScheduler de main.py). |
| **Export** | `yego_lima_loopcontrol_export_service.py` | HTTP POST a LoopControl API externa. DRY_RUN cuando `LOOPCONTROL_ENABLED=false`. |

### 3.3 CONTROL LOOP (Plan Data)

| Capa | Fuente de Verdad | Evidencia |
|------|-----------------|-----------|
| **Plan Staging** | `staging.control_loop_plan_metric_long` | **CANONICAL.** Long format. Upload vía `/plan/upload_control_loop_projection`. |
| **Plan View** | `ops.v_plan_projection_control_loop` | VIEW que lee desde staging. |
| **Real Source** | `ops.real_business_slice_month_fact` | Misma fuente que Omniview Matrix. |
| **Comparison Service** | `control_loop_plan_vs_real_service.py` | CANONICAL. Strict mode ON. Forbidden: legacy views. |
| **Resolution** | `control_loop_business_slice_resolve.py` | 3-tier: rules_exact → control_loop_map → candidate_rules. |
| **Projection Serving** | `serving.omniview_projection_daily_fact` | DELETE+INSERT idempotente. Cache layer, no source of truth. |
| **Endpoint canónico** | `GET /ops/control-loop/plan-vs-real` | Plan vs Real by business slice. |
| **Upload canónico** | `POST /plan/upload_control_loop_projection` | Único upload endpoint canónico. |
| **Plan versions** | `GET /plan/versions` | Desde `plan.plan_versions_metadata`. |
| **Default version** | `ruta27_2026_04_21` | Hardcoded en `serving_refresh_scheduler.py:30`. |

### 3.4 COHORTES

| Concepto | Tabla | Significado Real |
|----------|-------|-----------------|
| **Lifecycle Cohorts** | `ops.mv_driver_cohorts_weekly`, `ops.mv_driver_cohort_kpis` | SaaS-style retention cohorts: conductores agrupados por `cohort_week = DATE_TRUNC('week', activation_ts)`. Retention en W+1, W+4, W+8, W+12. |
| **Pilot Cohorts** | `ops.driver_pilot_cohort`, `ops.driver_pilot_assignment` | Grupos congelados de conductores para pilotos operativos. UUID-based. |
| **Action Engine "Cohorts"** | `ops.action_engine_output` | **NO son cohortes reales.** Legacy UI compatibility: `action_id` (ej. `TRIPS_DROP_CITY`) se mapea a `cohort_type`. Son alertas operativas por ciudad/día, no grupos de conductores. El endpoint `get_action_engine_cohort_detail()` retorna vacío con nota: "Detalle por conductor no disponible". |

### 3.5 YANGO API CANONICAL LAYER

| Capa | Fuente de Verdad | Evidencia |
|------|-----------------|-----------|
| **Ingestion** | `yango_raw_ingestion_service.py` | 3 endpoints Yango Fleet API. Escribe a `raw_yango.*`. |
| **Loyalty** | `yango_loyalty_service.py` | Oro Tracker. Lee `ops.mv_yango_loyalty_performance_monthly_v1`. |
| **Shadow** | Omniview V2 shadow (`YANGO_API_RAW`) | `canonical_ready=false` permanentemente. Lee `raw_yango.mv_orders_day`, `raw_yango.mv_revenue_day`. |
| **Reconciliation** | `yango_shadow_reconciliation_service.py` | Compara CT vs Yango. |
| **Profitability** | `yego_pro_profitability_service.py` | Yego Pro profit sharing. SQL: `backend/sql/yego_pro_*.sql`. |
| **Riesgo** | `yango_loyalty_definition_service.py` | **Permanent runtime fallback.** `preview_all_sets()` siempre devuelve `"serving_source": "runtime_fallback"` — no tiene serving fact. Cada llamada ejecuta queries pesadas contra `public.module_ct_fleet_summary_daily`. |

---

## 4. LEGACY — CLASIFICACIÓN REAL

### 4.1 LEGACY ACTIVO (aún sirve endpoints pero tiene reemplazo canónico)

| Objeto | Tipo | Reemplazo | Riesgo |
|--------|------|-----------|--------|
| `real_lob_service.py` (v1) | Service | `real_lob_service_v2.py` | Endpoints `/ops/real-lob/monthly` y `/weekly` v1 aún activos |
| `core_service.py` | Service | `business_slice_service.py` | Solo consumido por `MonthlyView.jsx` |
| `plan_real_split_service.py` | Service | `business_slice_service.py` | Solo consumido por `MonthlySplitView.jsx` |
| `plan_vs_real_service.py` (legacy PvR) | Service | `control_loop_plan_vs_real_service.py` | Usa REALKEY views legacy |
| `mv_real_trips_by_lob_month` | MV | `mv_real_lob_month_v3` | v1 LOB aggregation |
| `mv_real_trips_by_lob_week` | MV | `mv_real_lob_week_v3` | v1 weekly LOB |
| `mv_real_trips_monthly` | MV | `mv_real_monthly_canonical_hist` | Legacy real monthly |
| `mv_plan_vs_real_monthly_fact` | MV | `mv_plan_vs_real_monthly_fact_canonical` | Legacy PvR |
| `MonthlyView.jsx` | UI | Omniview | Vista legacy monthly |
| `MonthlySplitView.jsx` | UI | Omniview | Vista legacy split |
| `plan_long_raw/valid/out_of_universe/missing` | Tablas | `staging.control_loop_plan_metric_long` | Legacy plan upload |
| `ops.plan_trips_monthly` | Tabla | `staging.control_loop_plan_metric_long` | Legacy Ruta27 format |

### 4.2 LEGACY MUERTO (reemplazado, debe eliminarse)

| Objeto | Estado | Bloqueo |
|--------|--------|---------|
| `refresh_omniview_real_slice.py` | BLOCKED by safety guard | Siempre redirige a incremental |
| `backfill_week_from_day_fact.py` | BLOCKED by safety guard | Siempre redirige a incremental |
| `backfill_real_lob_mvs.py` | DEPRECATED | Replaced by `populate_real_drill_from_hourly_chain` |
| `BusinessSliceOmniviewProjectionTable.jsx` | DEPRECATED | Replaced by MatrixTable mode='projection' |
| `BusinessSliceOmniviewProjectionCell.jsx` | DEPRECATED | Replaced by MatrixCell mode='projection' |

### 4.3 PENDIENTE DE DEPRECACIÓN (aún usado, plan de migración)

| Objeto | Dependencia | Plan |
|--------|-------------|------|
| `mv_supply_weekly` | `/ops/supply/*` endpoints | NO refrescado por ningún pipeline → datos permanentemente stale. Fix pipeline o deprecar endpoints. |
| `mv_supply_monthly` | `/ops/supply/*` endpoints | Mismo problema. |
| `RealLOBView.jsx` (v1 mode) | UI | Migrar a v2 mode como default. |
| `ops.refresh_supply_mvs()` | migration 060 | Nunca llamada por ningún scheduler/pipeline. |
| `rebuild_week_fact_from_day_fact.py` | script | **BROKEN** — produce `active_drivers` incorrectos (SUM de daily distincts). No bloqueado. |

---

## 5. RIESGOS — EVIDENCIA DE CÓDIGO (no documentación)

### 5.1 CRÍTICOS (HIGH)

| # | Riesgo | Evidencia | Impacto |
|---|--------|-----------|---------|
| R1 | **6+ writers concurrentes a `real_business_slice_week_fact`** | `business_slice_incremental_load.py`, `backfill_week_from_day_fact.py`, `quick_backfill_may2026_week.py`, `backfill_week_fact_apr_may.py`, `rebuild_week_from_day_and_bridge.py`, `rebuild_week_fact_from_day_fact.py` | Race conditions. Advisory lock solo protege pipelines nombrados, no scripts ad-hoc. |
| R2 | **`rebuild_week_fact_from_day_fact.py` BROKEN pero ejecutable** | Produce `SUM(DISTINCT)` para `active_drivers` — auto-documentado como broken en `omniview_v1_trust_sensor.py:334`. Sin bloqueo. | Datos corruptos si se ejecuta. |
| R3 | **`DELETE FROM growth.yego_lima_assignment_queue` sin WHERE** | `backend/scripts/rebuild_queue.py:8`. DELETE completo de la tabla. | Pérdida total de datos de assignment queue si se ejecuta accidentalmente. |
| R4 | **`yango_loyalty_definition_service` sin serving fact** | `preview_all_sets()` hardcodea `"serving_source": "runtime_fallback"`. Cada request ejecuta queries pesadas contra `public.module_ct_fleet_summary_daily`. | Degradación de performance. Sin protección de serving governance. |
| R5 | **`mv_supply_weekly` / `mv_supply_monthly` permanentemente stale** | `ops.refresh_supply_mvs()` nunca llamada por ningún pipeline, scheduler ni script. | Endpoints `/ops/supply/*` sirven datos stale sin advertencia. |

### 5.2 MEDIOS (MEDIUM)

| # | Riesgo | Evidencia |
|---|--------|-----------|
| R6 | **Frontend recalcula `avg_ticket`/`commission_pct` incorrectamente** | `omniviewMatrixUtils.js:667-718` usa `AVG(avg_ticket)` en lugar de `SUM(revenue)/SUM(trips)` para subtotales por ciudad. Produce valores agregados matemáticamente incorrectos. |
| R7 | **GROWTH pipeline DELETE antes de INSERT sin transacción** | 9 tablas en `yego_lima_v2_daily_pipeline_service.py` hacen DELETE WHERE target_date + INSERT. Si INSERT falla, datos perdidos hasta próximo run. |
| R8 | **`run_refresh_driver_lifecycle()` con `statement_timeout=0`** | `run_pipeline_refresh_and_audit.py:91`. Timeout infinito. Si la query se cuelga, bloquea permanentemente. |
| R9 | **`CT_SCHEDULER_ENABLED` bypass en dev** | `is_scheduler_enabled()` retorna True en non-prod sin leer variable. Staging podría ejecutar scheduler contra producción. |
| R10 | **Main pipeline no refreshea fact tables** | `run_pipeline_refresh_and_audit.py` refreshea MVs de LOB pero NO `real_business_slice_{day,week,month}_fact`. Requiere OV2 cascade separado. |

### 5.3 BAJOS (LOW)

| # | Riesgo | Evidencia |
|---|--------|-----------|
| R11 | **`allow_runtime` bypass para multi-day en Omniview V2 matrix** | `omniview_v2.py:117-130` — requests multi-day siempre ejecutan runtime sin verificar snapshot, ignorando el flag `allow_runtime`. |
| R12 | **`ops.action_engine_output` con API "cohortes" vacía** | `get_action_engine_cohort_detail()` retorna vacío. UI muestra "cohortes" que son alertas por ciudad, no grupos de conductores. |
| R13 | **Snapshots solo para month fact** | Day y week facts no tienen snapshots ni serving views. Solo month tiene `v_real_business_slice_month_serving`. |
| R14 | **Browserslist data 6 meses old** | Vite warning al iniciar. Sin impacto funcional pero señal de falta de mantenimiento de dependencias. |

### 5.4 BYPASS DETECTADOS

| Patrón | Ubicación | Gravedad |
|--------|-----------|----------|
| **Bypass a serving facts:** `yango_loyalty_definition_service` nunca intenta leer serving facts | `preview_all_sets()` hardcoded runtime | MEDIUM |
| **Bypass a Driver Bridge:** `business_slice_incremental_load.py` lee `public.trips_2026` directamente sin pasar por bridge | Línea 1152+ | LOW (es el writer legacy, bridge es el writer canónico nuevo) |
| **Bypass a Month Fact:** `control_loop_plan_vs_real_service.py` lee `ops.real_business_slice_month_fact` directamente (correcto — es la fuente canónica) | N/A | NO RISK |
| **Bypass en UI:** Frontend recalcula `avg_ticket`/`commission_pct` para subtotales | `omniviewMatrixUtils.js` | MEDIUM |
| **Runtime recalculation:** `projection_expected_progress_service.py` acepta `_allow_runtime_fallback=True` en modo refresh | Solo desde scripts, no API | LOW |
| **Refresh manual:** `CT_SCHEDULER_ENABLED=false` → todos los refreshes son manuales o CLI | `main.py:263` | HIGH |

---

## 6. CERTIFICACIONES VIGENTES

| Certificación | Documento | Estado | Válida? |
|---------------|-----------|--------|---------|
| Control Foundation Closure | `CONTROL_FOUNDATION_CLOSURE_REPORT.md` | GO (11/1) | **Válida pero superada** — OMNI-P0 reopen no invalida CF completo, solo Omniview UI |
| CF-H1: Revenue Certification | `CF_H1_FINAL_CERTIFICATION.md` | GO | Válida |
| CF-H1 Operational | `CF_H1_OPERATIONAL_CLOSURE.md` | GO | Válida |
| Phase 1G.2 Closure | `CIERRE_FASE1G2_CONTROL_FOUNDATION_CLOSURE.md` | GO | Válida |
| Phase 1H.4 Maturity | `CIERRE_FASE1H4_MATURITY_GOVERNANCE.md` | GO | Válida |
| Revenue Canonical | `CF_H2_REVENUE_CANONICAL_DEFINITION.md` | GO | Válida |
| Lima Growth Control Loop | `LG_CF_OPERATIONAL_CLOSURE.md` | GO | Válida |
| Lima Growth Canonicalization | `LG_CAN_1A_CANONICALIZATION_CERTIFICATION.md` | GO | Válida |
| Yango Reconciliation | `OV2_F6_YANGO_RECONCILIATION_REPORT.md` | GO | Válida |

### 6.1 CERTIFICACIONES SOSPECHOSAS

| Certificación | Razón de sospecha |
|---------------|-------------------|
| Omniview Hardening Closure | **INVALIDADA.** Validación era DOM tokens, no semántica operacional. `OMNIVIEW_HARDENING_CLOSURE.md` fue creado con 15/15 PASS en DOM tokens pero el usuario detectó problemas operacionales reales (Revenue vacío, Evolution confuso, cross-metric inconsistente). |
| OMNI-GOV-001 Visual Certification | **INVALIDADA.** Mismo problema: 0 FAIL visuales F1-F10 pero basado en DOM tokens, no en semántica operacional. |

---

## 7. BLOQUEADORES ACTUALES

| # | Bloqueador | Impacto | Resolución |
|---|-----------|---------|------------|
| B1 | **OMNI-P0 no cerrado** | Blockea Diagnostic Engine 2A.3 | Cerrar Vs Proy canonicalization, Revenue serving, cell contract, CLOSED/PARTIAL visibility |
| B2 | **`CT_SCHEDULER_ENABLED=false`** | Todos los refreshes son manuales. Omniview V2 snapshots y projection serving no se actualizan automáticamente. | Activar en producción con monitoring. |
| B3 | **`mv_supply_weekly`/`mv_supply_monthly` stale** | Supply endpoints sirven datos incorrectos. | Integrar refresh en pipeline o deprecar endpoints. |
| B4 | **6+ writers a week_fact** | Riesgo de race condition y datos corruptos. | Consolidar en 1 writer canónico (bridge cascade). Bloquear writers legacy. |
| B5 | **`rebuild_week_fact_from_day_fact.py` ejecutable** | Datos corruptos si se ejecuta. | Bloquear o eliminar. |
| B6 | **Omniview V2 sin integración UI** | Frontend sigue usando Omniview V1. V2 existe pero no visible. | Integrar V2 en navegación cuando esté listo. |

---

## 8. FOCO OBLIGATORIO: OMNIVIEW V2 CLOSURE

### ¿Qué necesita Omniview V2 para cerrarse?

1. **Estabilizar el Driver Bridge cascade** como único writer canónico:
   - Eliminar/bloquear los 5 writers legacy a day/week/month fact
   - `rebuild_week_fact_from_day_fact.py` → BLOQUEAR (BROKEN)
   - `business_slice_incremental_load.py` (legacy path) → DEPRECAR
   - `backfill_week_from_day_fact.py` → ELIMINAR (ya bloqueado por guard)

2. **Resolver serving gaps:**
   - Day y week facts sin serving views → crear `v_real_business_slice_day_serving` y `v_real_business_slice_week_serving`
   - Day y week facts sin snapshots → implementar snapshot para locked periods

3. **Activar scheduler en producción** (`CT_SCHEDULER_ENABLED=true`) para:
   - `serving_fact_daily_refresh` (projection)
   - `business_slice_real_refresh` (facts)
   - `real_data_watchdog` (freshness)

4. **Cerrar OMNI-P0:**
   - Vs Proy como vista canónica única
   - Evolution oculto (legacy flag)
   - Revenue `revenue_yego_final` en todos los grains
   - CLOSED/PARTIAL/CURRENT/FUTURE visible en cada celda
   - Certificación semántica real (no DOM tokens)

5. **Conectar Omniview V2 a UI** (actualmente backend-only)

6. **Corregir recálculo de frontend** (`AVG(avg_ticket)` → `SUM(revenue)/SUM(trips)`)

### ¿Qué piezas son imprescindibles para Omniview V2?

| Pieza | Imprescindible? | Razón |
|-------|----------------|-------|
| Driver Bridge (`ops.driver_day_slice_fact`) | **SI** | Fundación canónica de toda la cascade |
| Day Fact (`ops.real_business_slice_day_fact`) | **SI** | Lectura directa para daily grain |
| Week Fact | **SI** | Lectura directa para weekly grain |
| Month Fact + Serving View | **SI** | Lectura para monthly grain con snapshot/locked logic |
| Serving Snapshot (`ops.omniview_v2_serving_snapshot`) | **SI** | Snapshot-first architecture |
| Plan staging (`staging.control_loop_plan_metric_long`) | **SI** | Para projection mode |
| Projection serving (`serving.omniview_projection_daily_fact`) | **SI** | Cache para projection mode |
| Yango shadow (`raw_yango.*`) | NO | Solo para shadow/comparison, no operacional |
| Supply MVs | NO | No usado por Omniview |
| Driver lifecycle MVs | NO | No usado por Omniview |

---

## 9. FOCO OBLIGATORIO: GROWTH MACHINE CLOSURE

### ¿Qué necesita Growth Machine para cerrarse?

1. **Resolver writer de `growth.yango_lima_driver_history_weekly`:**
   - Es la fuente primaria de driver_state_service
   - Su writer NO está en los servicios auditados
   - **NEEDS VERIFICATION:** ¿Quién lo construye?

2. **Resolver writer de `growth.yango_lima_orders_raw`:**
   - Leído por driver_360_service para orders
   - Su writer NO está en los servicios auditados
   - **NEEDS VERIFICATION:** ¿Es MV o ETL externo?

3. **Eliminar DELETEs sin WHERE:**
   - `DELETE FROM growth.yego_lima_assignment_queue` (rebuild_queue.py:8) → agregar WHERE

4. **Proteger DELETEs con transacción en pipeline V2:**
   - 9 tablas en `yego_lima_v2_daily_pipeline_service.py` hacen DELETE antes de INSERT
   - Envolver en transacción para evitar pérdida de datos si INSERT falla

5. **Activar `LOOPCONTROL_ENABLED=true`** si se desea exportación real a LoopControl externo

6. **Estabilizar scheduler autónomo:**
   - `yego_lima_scheduler_service.py` ya funciona independientemente
   - Verificar que `CT_SCHEDULER_ENABLED` no lo bloquee indirectamente

### ¿Qué piezas son imprescindibles para Growth Machine?

| Pieza | Imprescindible? | Razón |
|-------|----------------|-------|
| Yango Fleet API ingestion | **SI** | Fuente de datos externa |
| Driver 360 (`growth.yango_lima_driver_360_daily`) | **SI** | Base de datos de conductores |
| Driver History Weekly | **SI** | Universo primario para state classification |
| State Snapshot | **SI** | Classificación canónica de estados |
| Program Eligibility | **SI** | Reglas de programas |
| Opportunity Lists | **SI** | Listas diarias accionables |
| Action Registry | **SI** | Tracking de acciones |
| LoopControl Export | NO | Solo si se exporta a sistema externo |
| Scheduler autónomo | **SI** | Pipeline diario |
| Loyalty Sub50 | NO | Feature específica, no core |
| RNA Pilot | NO | Piloto, no producción |

### ¿Qué piezas pueden ignorarse temporalmente?

| Pieza | Razón |
|-------|-------|
| `growth.yango_lima_loopcontrol_campaign_export` | Solo si LOOPCONTROL_ENABLED=false |
| `growth.yango_lima_loopcontrol_result_sync` | Solo si hay resultados externos que sincronizar |
| `growth.yango_lima_rna_pilot_*` | Piloto, no producción |
| `growth.yango_lima_loyalty_sub50_*` | Feature específica |
| `growth.yango_lima_productivity_*` | ETL externo no auditado |
| Supply MVs (`mv_supply_*`) | No usado por Growth Machine |
| Driver lifecycle MVs | No usado por Growth Machine |

---

## 10. RESUMEN: QUÉ ES VERDAD ACTUAL

1. **Omniview V1** sigue siendo la UI operacional. Omniview V2 existe en backend (3 routers, snapshot-first architecture, Driver Bridge cascade) pero sin conexión a UI.

2. **Growth Machine** opera con pipeline y scheduler independientes. Su fuente canónica es `growth.yango_lima_driver_state_snapshot` (3-axis state: lifecycle + performance + retention).

3. **El Driver Bridge** (`ops.driver_day_slice_fact`) es la capa de fundación canónica de Omniview V2. Agrega `public.trips_2026` por (driver, día, park, business_slice). Alimenta toda la cascade: day_fact → week_fact → month_fact → serving_snapshot.

4. **Hay dos "Control Loops" completamente independientes:** Plan Data (proyección, Plan vs Real) y Lima Growth (acciones, agentes, estados). Comparten nombre pero cero tablas o servicios.

5. **"Cohortes" son 3 conceptos distintos:** Lifecycle cohorts (retención por semana de activación), Pilot cohorts (grupos congelados para pilotos), y Action Engine "cohorts" (capa de compatibilidad UI que mapea alertas operativas a API de cohortes — no son cohortes reales).

6. **Los riesgos más graves son:** Multi-writers a week_fact (6 paths), script BROKEN ejecutable, DELETE sin WHERE en assignment_queue, y Yango loyalty sin serving fact (permanent runtime fallback).

---

## CROSS-REFERENCES

- [SYSTEM_MAP.md](SYSTEM_MAP.md) — Mapa completo del sistema
- [KNOWN_CONSTRAINTS.md](KNOWN_CONSTRAINTS.md) — Restricciones conocidas
- [OMNIVIEW_V2_CANONICAL.md](OMNIVIEW_V2_CANONICAL.md) — Dominio Omniview V2
- [GROWTH_MACHINE_CANONICAL.md](GROWTH_MACHINE_CANONICAL.md) — Dominio Growth Machine
- [CONTROL_LOOP_CANONICAL.md](CONTROL_LOOP_CANONICAL.md) — Dominio Control Loop
- [YANGO_API_CANONICAL.md](YANGO_API_CANONICAL.md) — Dominio Yango API
- [OMNIVIEW_CANONICAL_REGISTRY.md](../../OMNIVIEW_CANONICAL_REGISTRY.md) — Registro completo de objetos
- [ai_current_phase.md](../../ai_current_phase.md) — Fase activa actual

---

*Generated from live code audit. Evidence: `backend/app/routers/omniview_v2.py` (740 lines, 15 endpoints), `backend/app/services/omniview_v2_*.py` (7 services), `backend/app/services/yego_lima_*.py` (50+ services), `backend/app/services/business_slice_*.py`, `backend/scripts/build_driver_bridge_direct.py`, `backend/scripts/rebuild_*_from_*.py`, `backend/scripts/run_pipeline_refresh_and_audit.py`, `frontend/src/components/omniview/omniviewMatrixUtils.js`.*
