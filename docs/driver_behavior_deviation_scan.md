# Driver Behavioral Deviation Engine — Architecture Scan (Phase 0)

**Project:** YEGO Control Tower  
**Date:** 2026-03-11  
**Mode:** Read-only. No implementation until this scan is complete.

---

## A) Existing weekly driver-level sources

### 1. ops.mv_driver_behavior_alerts_weekly / ops.v_driver_behavior_alerts_weekly

- **Purpose:** Behavioral Alerts — driver-week deviation vs own baseline (fixed 6-week baseline).
- **Columns (relevant):** driver_key, driver_name, week_start, week_label, country, city, park_id, park_name, trips_current_week, segment_current, segment_previous, movement_type, avg_trips_baseline, median_trips_baseline, stddev_trips_baseline, active_weeks_in_window, delta_abs, delta_pct, z_score_simple, weeks_declining_consecutively, weeks_rising_consecutively, alert_type, severity, risk_score, risk_band, risk_score_behavior, risk_score_migration, risk_score_fragility, risk_score_value.
- **Source chain:** ops.mv_driver_segments_weekly → ops.v_driver_behavior_baseline_weekly → ops.v_driver_behavior_alerts_weekly (→ optional MV).
- **Note:** In v_driver_behavior_baseline_weekly the CTE `consec` currently returns **0** for weeks_declining_consecutively and weeks_rising_consecutively (placeholders). So persistence streaks are not computed in the baseline view.

### 2. ops.mv_driver_segments_weekly

- **Purpose:** One row per (driver_key, week_start) with segment and park; feeds Supply and Behavioral Alerts.
- **Columns:** driver_key, week_start, park_id, trips_completed_week, segment_week, prev_segment_week, segment_change_type, baseline_trips_4w_avg, weeks_active_rolling_4w, etc. (exact set from 067/078).
- **Source:** ops.mv_driver_weekly_stats (driver_key, week_start, trips_completed_week, park_id, …) + ops.driver_segment_config for segment_week.
- **Grain:** One row per driver per week. No configurable recent/baseline windows; baseline in behavior layer is fixed 6 weeks.

### 3. ops.mv_driver_weekly_stats

- **Purpose:** Driver lifecycle weekly aggregation.
- **Columns:** driver_key (from conductor_id), week_start, trips_completed_week, work_mode_week, park_id, tipo_servicio, segment, is_active_week.
- **Source:** ops.v_driver_lifecycle_trips_completed (completion_ts, conductor_id, park_id, …). Ultimate source: trips (e.g. v_driver_lifecycle_trips_completed built from trips with completion_ts).
- **Grain:** One row per driver per week. No last_trip_date at this level.

### 4. ops.mv_supply_segments_weekly

- **Purpose:** Aggregate supply by week, park, segment (driver counts, trips sum). Not driver-level.
- **Use for deviation engine:** Only for context; driver-level logic must use driver-week sources above.

### 5. Driver lifecycle / trips

- **ops.mv_driver_lifecycle_base:** driver-level lifecycle base (last_completed_ts possible here or in trips view).
- **ops.v_driver_lifecycle_trips_completed:** trip-level completed trips with conductor_id, completion_ts, park_id, etc.
- **trips_all / trips:** Contains conductor_id, fecha_inicio_viaje, fecha_finalizacion. Used for last_trip_date in territory_quality_service (MAX(fecha_inicio_viaje) per driver). No standard driver-level “last_trip_date” view exposed for Behavior Alerts.

### 6. Action Engine

- **ops.v_action_engine_driver_base:** Built from ops.v_driver_behavior_alerts_weekly; adds cohort_type, suggested_priority, suggested_channel, etc. Grain: driver-week. Reads weeks_declining_consecutively, weeks_rising_consecutively from alerts view (currently 0 in baseline).
- **ops.v_action_engine_cohorts_weekly, v_action_engine_recommendations_weekly:** Cohort-level; not driver-level for this new module.

### Summary of driver-week sources

| Source | driver_key | week_start | trips | segment | baseline/delta | last_trip | Geo |
|--------|------------|------------|-------|---------|----------------|-----------|-----|
| mv_driver_weekly_stats | ✓ | ✓ | trips_completed_week | segment | — | — | park_id |
| mv_driver_segments_weekly | ✓ | ✓ | trips_completed_week | segment_week | baseline_trips_4w_avg (4w) | — | park_id |
| v_driver_behavior_baseline_weekly | ✓ | ✓ | trips_current_week | segment_current | 6w baseline, delta_pct, z | — | country, city, park |
| v_driver_behavior_alerts_weekly | ✓ | ✓ | ✓ | ✓ | ✓ + risk_score, alert_type | — | ✓ |

**last_trip_date / days_since_last_trip:** Not present in any of the above. Available only via trips (e.g. MAX(fecha_inicio_viaje) or completion_ts per conductor_id) or a dedicated driver-level view/MV.

---

## B) Existing frontend structure

- **Tabs (App.jsx):** real_lob, driver_lifecycle, supply, behavioral_alerts, action_engine, snapshot, system_health, legacy (and legacy sub-tabs).
- **Pattern:** One main component per tab (e.g. BehavioralAlertsView, ActionEngineView). Filters in component state (from, to, country, city, park_id, segment, alert_type, severity, risk_band, etc.). KPIs at top, then table, drilldown modal, export link/button.
- **Reusable pieces:** getSupplyGeo for country/city/park; api.js for all API calls; explainabilitySemantics.js and theme/decisionColors.js for labels and colors; no shared “driver table” component.
- **Filters:** Typically from/to dates, country, city, park, segment; Behavioral Alerts also baseline_window, movement_type, alert_type, severity, risk_band.
- **Exports:** CSV/Excel via URL (e.g. getBehaviorAlertsExportUrl, getActionEngineExportUrl) or client-side CSV from current table data.
- **Drilldown:** Modal with driver detail (e.g. driver detail = timeline of weeks from driver-detail API). Behavioral Alerts has “Driver Behavior Timeline” line chart (trips last 8 weeks) in modal.

---

## C) Canonical driver identifier

- **driver_key** is the canonical identifier across:
  - ops.mv_driver_weekly_stats (conductor_id AS driver_key)
  - ops.mv_driver_segments_weekly
  - ops.v_driver_behavior_baseline_weekly / v_driver_behavior_alerts_weekly
  - Action Engine (v_action_engine_driver_base)
- **Origin:** conductor_id in trips / v_driver_lifecycle_trips_completed, exposed as driver_key in MVs and views.
- **Recommendation:** Use **driver_key** consistently for the new Driver Behavior Deviation module (APIs, exports, drilldown).

---

## D) Data freshness path

- **mv_driver_weekly_stats:** Refreshed as part of driver lifecycle / supply pipeline (run_driver_lifecycle_build, refresh scripts). Data freshness expectations in ops.data_freshness_expectations reference mv_driver_lifecycle_base and mv_driver_weekly_stats.
- **mv_driver_segments_weekly:** Depends on mv_driver_weekly_stats; refreshed in supply chain (e.g. run_supply_refresh_pipeline).
- **v_driver_behavior_alerts_weekly:** View (live); no separate refresh. Optional mv_driver_behavior_alerts_weekly is refreshed when used.
- **New module:** If implemented as views on top of existing MVs, freshness is inherited (no extra refresh). If new MVs are added, they should be documented and, if needed, included in existing refresh pipelines. **days_since_last_trip** will require either a view/MV on trips (or equivalent) or a scheduled job that updates driver-level last trip; that path is not currently part of Behavioral Alerts.

---

## Recommended source-of-truth dataset for the new module

- **Primary:** Build the new **driver-level** (one row per driver, not per driver-week) logic on top of **ops.mv_driver_segments_weekly** (or equivalently ops.mv_driver_weekly_stats) for trip/segment history, with **configurable** recent and baseline windows applied in SQL or in a new view/MV.
- **Alternative:** Keep using **ops.v_driver_behavior_alerts_weekly** only for weekly snapshots and build a **separate** layer that:
  - Aggregates driver-weeks into one row per driver over a chosen “reference week” or “as-of date”,
  - Applies recent_window (e.g. last 4 weeks) and baseline_window (e.g. previous 16 weeks) to compute recent_avg_trips, baseline_avg_trips, delta_pct, etc.,
  - Joins to a **driver-level last_trip** source for days_since_last_trip.
- **Recommendation:** Add **new** SQL objects (e.g. ops.v_driver_behavior_deviation_base or ops.mv_driver_behavior_deviation_base) that:
  1. Read from ops.mv_driver_segments_weekly (and geo, driver name as today).
  2. Define **configurable** recent_window_weeks and baseline_window_weeks (e.g. via view parameters or a small config table / function args).
  3. Compute per-driver: recent_window_trips, recent_avg_weekly_trips, baseline_window_trips, baseline_avg_weekly_trips, baseline_stddev, delta_abs, delta_pct, declining_weeks_consecutive, rising_weeks_consecutive.
  4. Join to a **new or existing** driver-level last_trip source to add days_since_last_trip and inactivity_status (Active/Cooling/Dormant/Churn Risk).
  5. Do **not** replace or alter v_driver_behavior_baseline_weekly / v_driver_behavior_alerts_weekly or Action Engine views.

---

## Fields already available (from existing objects)

- driver_key, driver_name (v_dim_driver_resolved), country, city, park_id, park_name (dim.v_geo_park).
- Per driver-**week:** week_start, trips_current_week (= trips_completed_week), segment_current, avg_trips_baseline (fixed 6w), delta_abs, delta_pct, z_score_simple, active_weeks_in_window, segment_previous, movement_type, weeks_declining_consecutively, weeks_rising_consecutively (latter two currently 0 in baseline), alert_type, severity, risk_score, risk_band.

---

## Fields missing for the new module

- **Configurable windows:** recent_window_weeks (4/8/16/32), baseline_window_weeks (8/16/32); current logic is fixed 6-week baseline.
- **Driver-level (one row per driver):** recent_window_trips, recent_avg_weekly_trips, baseline_window_trips, baseline_avg_weekly_trips, baseline_median_weekly_trips, baseline_stddev_weekly_trips, baseline_active_weeks.
- **Persistence / recency:** days_since_last_trip, weeks_since_behavior_change_started; meaningful declining_weeks_consecutive / rising_weeks_consecutive (computed over the chosen windows).
- **Inactivity status:** Active (0–3 days), Cooling (4–7), Dormant (8–14), Churn Risk (15+).
- **New alert taxonomy (optional):** Sharp Degradation, Sustained Degradation, Recovery, Dormant Risk, High Volatility, Stable — can map from or extend existing alert_type/severity.
- **Actionability:** suggested_action, suggested_channel, rationale at **driver** level (Action Engine has them at cohort level).

---

## Performance concerns

- **Views on top of driver-week MVs:** Filtering by recent/baseline window and aggregating to one row per driver will require window functions and GROUP BY over potentially large driver-week sets. For large datasets, a **materialized view** (e.g. ops.mv_driver_behavior_deviation_base) with parameters fixed at refresh time (e.g. recent=4, baseline=16) may be necessary; or a view with strict date filters to limit scan.
- **days_since_last_trip:** If computed from trips_all per request, it can be expensive. Prefer a driver-level table or MV (e.g. “last_trip_per_driver”) refreshed with the same pipeline as mv_driver_weekly_stats, and join it into the deviation view/MV.
- **Indexes:** Existing indexes on (driver_key, week_start), (week_start), (park_id, week_start), (country), (city) on mv_driver_segments_weekly / mv_driver_behavior_alerts_weekly help. New MVs should add indexes on filter columns (country, city, park_id, segment_current, alert_type, risk_band, inactivity_status).

---

## Proposed additive architecture (high level)

1. **SQL (additive only)**  
   - **ops.v_driver_last_trip** (or equivalent): driver_key, last_trip_date / last_trip_ts. Source: trips or v_driver_lifecycle_trips_completed. Used to compute days_since_last_trip and inactivity_status.  
   - **ops.v_driver_behavior_deviation_base:** One row per driver (and optionally per reference_week or as-of date). Reads from mv_driver_segments_weekly + geo + driver name + v_driver_last_trip. Parameters: recent_window_weeks, baseline_window_weeks (e.g. via function or view with literal/configuration). Outputs: identity, current behavior, baseline, deviation, persistence, days_since_last_trip, inactivity_status.  
   - **ops.v_driver_behavior_deviation_alerts:** Same grain; adds alert_type, severity, risk_score, risk_band, suggested_action, suggested_channel, rationale (driver-level logic).  
   - **ops.v_driver_behavior_deviation_summary:** Aggregates (e.g. drivers_monitored, high_degradation, recovery, dormant_risk) for KPIs.  
   - Optionally **ops.mv_driver_behavior_deviation_*** if view performance is insufficient; refresh strategy to be defined without changing existing pipelines.

2. **Backend (additive only)**  
   - New service (e.g. driver_behavior_deviation_service) with get_summary, get_drivers, get_driver_detail, get_export.  
   - New routes under **/ops/driver-behavior-deviation/** (summary, drivers, driver-detail, export).  
   - Filters: recent_window, baseline_window, country, city, park_id, segment_current, alert_type, severity, risk_band, inactivity_status, optional min_baseline_trips, min_delta_pct.

3. **Frontend (additive only)**  
   - New tab “Driver Behavior” (or “Behavior Deviation” / “Driver Degradation Monitor”) next to Behavioral Alerts and Action Engine.  
   - New component (e.g. DriverBehaviorDeviationView) with filter panel, KPIs, main table, driver detail drilldown, explainability panel, export.  
   - Reuse getSupplyGeo, decisionColors/explainabilitySemantics where appropriate.

4. **What will NOT be touched**  
   - Existing views/MVs: v_driver_behavior_baseline_weekly, v_driver_behavior_alerts_weekly, mv_driver_behavior_alerts_weekly, mv_driver_segments_weekly, mv_driver_weekly_stats, Action Engine views.  
   - Existing modules: Real LOB, Driver Lifecycle, Supply, Migration, Behavioral Alerts, Action Engine, Top Driver Behavior.  
   - Existing API routes and frontend tabs for those modules.

---

## Files to touch (implementation phases)

- **Docs:** docs/driver_behavior_deviation_logic.md, docs/driver_behavior_deviation_ui_wiring_report.md, docs/driver_behavior_deviation_render_validation.md.  
- **SQL:** New migration(s) for v_driver_last_trip (or equivalent), v_driver_behavior_deviation_base, v_driver_behavior_deviation_alerts, v_driver_behavior_deviation_summary; optional MVs.  
- **Backend:** New service module, new router under ops (e.g. driver-behavior-deviation endpoints).  
- **Frontend:** api.js (new getDriverBehaviorDeviation*), new component DriverBehaviorDeviationView (or similar), App.jsx (new tab + route).  
- **Constants/themes:** Reuse or extend explainabilitySemantics / decisionColors for behavior direction, risk band, inactivity status, delta.

---

## What will NOT be touched

- No destructive changes to existing SQL objects (no DROP/REPLACE of v_driver_behavior_baseline_weekly, v_driver_behavior_alerts_weekly, action engine views, mv_driver_segments_weekly, mv_driver_weekly_stats).  
- No removal or replacement of Behavioral Alerts or Action Engine tabs or their APIs.  
- No change to existing data freshness expectations other than optionally registering new MVs if added.

---

---

## Legacy endpoints / services / components that must NOT power the visible Driver Behavior UI

- **Endpoints:** Do NOT use `/controltower/*`, `/ops/behavior-alerts/*`, `/ops/action-engine/*` for the new Driver Behavior tab. The visible UI must be powered only by the new additive routes under `/ops/driver-behavior/*`.
- **Services:** Do NOT reuse behavior_alerts_service or action_engine_service to drive the Driver Behavior table or KPIs; use a dedicated driver_behavior_deviation service (or driver_behavior service) that reads from the new deviation logic and v_driver_last_trip.
- **Components:** Do NOT mount BehavioralAlertsView or ActionEngineView for the Driver Behavior tab; use a new component (e.g. DriverBehaviorView) that calls only the new API functions (getDriverBehaviorSummary, getDriverBehaviorDrivers, getDriverBehaviorDriverDetail, getDriverBehaviorExportUrl).
- **Data source:** The new module must NOT silently read from ops.v_driver_behavior_alerts_weekly or ops.v_action_engine_driver_base for its main list; it must use the new driver-level aggregation with configurable recent/baseline windows and v_driver_last_trip.

---

**Scan complete.** Implementation may proceed from Phase 1 onward after approval of this architecture.
