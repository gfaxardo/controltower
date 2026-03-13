# Observabilidad — Data lineage por módulo

Flujo extremo a extremo: **source → transform → view/MV → backend service → endpoint → frontend**.

---

## Real LOB

- **Source:** `ops.v_trips_real_canon`, `ops.v_real_trips_with_lob_v2`.
- **Transform / MVs:** `ops.mv_real_lob_month_v2`, `ops.mv_real_lob_week_v2`; `ops.real_drill_dim_fact`, `ops.real_rollup_day_fact` (vistas compatibilidad sobre estas).
- **Refresh:** `scripts/refresh_real_lob_mvs_v2.py` (REFRESH MATERIALIZED VIEW CONCURRENTLY); `refresh_real_lob_drill_pro_mv.py` para drill.
- **Backend:** real_lob_filters_service, real_lob_v2_data_service, ops router (real-lob/*, real-drill/*, real-strategy/*).
- **Frontend:** RealLOBDrillView, RealLOBDailyView; api.js getRealLobV2Data, getRealLobDrillPro.
- **Trazabilidad:** observability_refresh_log (instrumentado en refresh_real_lob_mvs_v2.py).

---

## Driver Lifecycle

- **Source:** Viajes (trips_unified / v_driver_lifecycle_trips_completed).
- **Transform / MVs:** `ops.mv_driver_lifecycle_base`, `ops.mv_driver_weekly_stats`, `ops.mv_driver_weekly_behavior`, `ops.mv_driver_churn_segments_weekly`, etc.
- **Refresh:** `ops.refresh_driver_lifecycle_mvs()` (SQL); scripts `refresh_driver_lifecycle.py`, `apply_driver_lifecycle_v2.py`.
- **Backend:** driver_lifecycle_service; router driver_lifecycle (prefix /ops/driver-lifecycle).
- **Frontend:** DriverLifecycleView; api.js getDriverLifecycle*.
- **Trazabilidad:** Sin log centralizado aún; pendiente instrumentar con log_refresh.

---

## Supply Dynamics

- **Source:** `ops.mv_driver_weekly_stats`, `ops.driver_segment_config`.
- **Transform / MVs:** `ops.mv_driver_segments_weekly` → `ops.mv_supply_segments_weekly`, `ops.mv_supply_segment_anomalies_weekly`, `ops.mv_supply_alerts_weekly`; `ops.mv_supply_weekly`, `ops.mv_supply_monthly`.
- **Refresh:** `ops.refresh_supply_alerting_mvs()`; script `run_supply_refresh_pipeline.py`.
- **Backend:** supply_service (get_supply_freshness, refresh_supply_alerting_mvs, log_supply_refresh_done); ops router supply/*.
- **Frontend:** SupplyView; api.js getSupply*, getSupplyFreshness.
- **Trazabilidad:** ops.supply_refresh_log (started_at, finished_at, status).

---

## Behavioral Alerts

- **Source:** Vistas de behavioral alerts (semanal, risk score) definidas en migraciones 082, 085, 090.
- **Backend:** behavior_alerts_service; ops y controltower routers (behavior-alerts/*).
- **Frontend:** BehavioralAlertsView.
- **Trazabilidad:** Sin refresh propio; depende de MVs de driver/supply. Observabilidad vía data_freshness_audit si se incluye dataset.

---

## Fleet Leakage

- **Source:** `ops.mv_driver_segments_weekly`, `ops.v_driver_last_trip`, `ops.v_fleet_leakage_snapshot` (091).
- **Backend:** leakage_service; ops router leakage/*.
- **Frontend:** FleetLeakageView.
- **Trazabilidad:** Sin refresh dedicado; datos derivados de Supply/Driver Lifecycle.

---

## Plan vs Real

- **Source:** plan.plan_*, ops.mv_real_trips_weekly, ops.v_plan_trips_monthly_latest, etc.
- **Transform / Views:** ops.v_plan_vs_real_weekly, ops.v_plan_vs_real_realkey_final, ops.v_alerts_2b_weekly; phase2b/phase2c tablas.
- **Refresh:** Carga de plan (upload); refresh_plan_weekly_weighted; MVs real se refrescan con Real LOB / pipeline.
- **Backend:** plan, phase2b, phase2c, ops (plan-vs-real/*).
- **Frontend:** MonthlySplitView, WeeklyPlanVsRealView, Phase2BActionsTrackingView, Phase2CAccountabilityView, LobUniverseView.
- **Trazabilidad:** data_freshness_audit (datasets real_lob_drill, etc.) y carga de plan vía API.

---

## Ingestion

- **Source:** ETL externo (no en repo).
- **Tabla:** bi.ingestion_status (dataset_name, max_year, max_month, last_loaded_at, is_complete_2025).
- **Backend:** ingestion router GET /ingestion/status.
- **Frontend:** GlobalFreshnessBanner, System Health (ingestion_summary vía v_ingestion_audit).
- **Trazabilidad:** last_loaded_at en ingestion_status.

---

## System Health

- **Source:** ops.v_control_tower_integrity_report, ops.data_integrity_audit, ops.v_mv_freshness, ops.v_ingestion_audit, ops.data_freshness_audit.
- **Backend:** data_integrity_service.get_system_health, data_freshness_service; ops router system-health, data-freshness/*, integrity-report, pipeline-refresh.
- **Frontend:** SystemHealthView, GlobalFreshnessBanner.
- **Trazabilidad:** data_integrity_audit (timestamp por ejecución), data_freshness_audit (checked_at por dataset).

---

## Dependencias críticas (resumen)

- Real LOB v2 MVs ← v_real_trips_with_lob_v2 ← v_trips_real_canon ← trips_all / trips_2026.
- Supply MVs ← mv_driver_segments_weekly ← mv_driver_weekly_stats ← mv_driver_lifecycle_base.
- Driver Lifecycle base ← v_driver_lifecycle_trips_completed / trips_unified.
- Behavioral Alerts y Fleet Leakage ← mv_driver_segments_weekly y vistas de conductores.
