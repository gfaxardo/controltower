# Behavioral Alerts — Architecture Scan (Phase 0)

**Project:** YEGO Control Tower  
**Feature:** Behavioral Alerts (Baseline Behavior Deviation)  
**Date:** 2025-03-11  
**Scope:** Read-only system scan prior to implementation.

---

## 1. Existing Weekly Driver Datasets

| Object | Schema | Grain | Key columns | Source |
|--------|--------|-------|-------------|--------|
| **mv_driver_weekly_stats** | ops | driver_key, week_start | driver_key, week_start, park_id, trips_completed_week, work_mode_week, tipo_servicio, segment | ops.v_driver_lifecycle_trips_completed |
| **mv_driver_segments_weekly** | ops | driver_key, week_start | driver_key, week_start, park_id, trips_completed_week, segment_week, prev_segment_week, segment_change_type, weeks_active_rolling_4w, **baseline_trips_4w_avg** | ops.mv_driver_weekly_stats + ops.driver_segment_config |
| **mv_driver_weekly_behavior** | ops | driver_key, week_start | driver_key, week_start, park_id_dominante, trips_completed_week, active_days_week, work_mode_week | ops.v_driver_lifecycle_trips_completed |
| **mv_driver_behavior_shifts_weekly** | ops | driver_key, week_start | driver_key, week_start, park_id, trips_current_week, avg_trips_prev_4w, **behavior_shift** (drop/spike/stable) | ops.mv_driver_weekly_behavior (baseline = 4 weeks preceding) |

- **Preferred source for Behavioral Alerts baseline:** `ops.mv_driver_segments_weekly` or `ops.mv_driver_weekly_stats` (both have driver_key, week_start, trips per week; segments_weekly already has segment_week and a 4w baseline; we need configurable 4/6/8w and **baseline excluding current week**).
- **mv_driver_behavior_shifts_weekly** already implements a simple “drop vs 4w average” and “spike”; Behavioral Alerts extends this with configurable window, more alert types, severity, and UI/export.

---

## 2. Lifecycle MVs

| Object | Purpose |
|--------|--------|
| **mv_driver_lifecycle_base** | One row per driver: driver_key, activation_ts, last_completed_ts, total_trips_completed, lifetime_days, registered_ts, hire_date, driver_park_id |
| **mv_driver_lifecycle_weekly_kpis** | Weekly KPIs derived from base + weekly_stats |
| **mv_driver_lifecycle_monthly_kpis** | Monthly KPIs |

- Refresh order (from `driver_lifecycle_refresh_*.sql`): `mv_driver_weekly_stats` → `mv_driver_monthly_stats` → `mv_driver_lifecycle_base` → `mv_driver_lifecycle_weekly_kpis` → `mv_driver_lifecycle_monthly_kpis`.
- **Behavioral Alerts must not change these MVs.** It can read from `mv_driver_weekly_stats` / `mv_driver_segments_weekly` only.

---

## 3. Supply Datasets

| Object | Grain | Notes |
|--------|-------|------|
| **mv_supply_segments_weekly** | week_start, park_id, segment_week | drivers_count, trips_sum, share_of_active; geo from dim.v_geo_park |
| **mv_supply_segment_anomalies_weekly** | week_start, park_id, segment_week | baseline_avg, baseline_std, delta_abs, delta_pct, z_score (aggregate-level, not driver-level) |
| **mv_supply_alerts_weekly** | week_start, park_id, segment_week | Alert flags at segment level |
| **v_driver_segment_migrations_weekly** | week_start, park_id, from_segment, to_segment | Migration aggregates (upgrade/downgrade/same) |
| **mv_driver_segment_migrations_weekly** (optional) | Same | Materialized copy of the view (080) |

- Geo: **dim.v_geo_park** (park_id, park_name, city, country); fallback **ops.v_dim_park_resolved**.
- Supply and Migration are **segment-level** and **park-level**; Behavioral Alerts is **driver-level** and complements them.

---

## 4. Segment Logic

- **ops.driver_segment_config:** segment_code, segment_name, min_trips_week, max_trips_week, ordering, effective_from, effective_to.
- Default taxonomy: **FT** ≥60, **PT** 20–59, **CASUAL** 5–19, **OCCASIONAL** 1–4, **DORMANT** 0.
- **ops.get_driver_segment(trips_completed_week, week_start)** returns segment_code (used for compatibility); **mv_driver_segments_weekly** is built via JOIN to `driver_segment_config` (067) for performance.
- Segment for “current week” in Behavioral Alerts = **segment_week** from the same driver-week row (e.g. from mv_driver_segments_weekly or from our baseline view).
- **mv_driver_segments_weekly** exposes **prev_segment_week** and **segment_change_type** (upshift/downshift/stable/drop/new) for segment_previous and movement_type.

### Segment taxonomy (current)

After migration 078: DORMANT (0), OCCASIONAL (1-4), CASUAL (5-19), PT (20-59), FT (60-119), ELITE (120-179), LEGEND (180+). Ordering 1-7. See ops.driver_segment_config.

---

## 5. week_start Usage

- **Definition:** `DATE_TRUNC('week', completion_ts)::date` (Monday as start of week).
- Used consistently in: mv_driver_weekly_stats, mv_driver_segments_weekly, mv_supply_segments_weekly, migration views, driver lifecycle.
- **Behavioral Alerts:** baseline window = N weeks **before** current week (current week excluded). Example: for week_start = 2026-03-09, 6-week baseline = 2026-01-27 to 2026-03-02.

---

## 6. Driver Identifiers

- **Trips:** `conductor_id` (trips_all / trips_unified).
- **MVs:** `driver_key` = conductor_id (e.g. in mv_driver_weekly_stats, mv_driver_segments_weekly).
- **Display:** **ops.v_dim_driver_resolved**: driver_id (= conductor_id), **driver_name** (= MAX(conductor_nombre) from trips_unified). So driver_name is available for UI/exports.

---

## 7. Trips per Driver Tables

- **ops.mv_driver_weekly_stats:** one row per (driver_key, week_start) with **trips_completed_week**.
- **ops.mv_driver_segments_weekly:** same grain + segment_week, prev_segment_week, baseline_trips_4w_avg (4-week preceding average).
- No direct “trips_all per driver” table; aggregation is via v_driver_lifecycle_trips_completed → weekly_stats. For Behavioral Alerts we only need **weekly** trips per driver, so **mv_driver_weekly_stats** or **mv_driver_segments_weekly** is sufficient.

---

## 8. Existing Backend Endpoints

- **Router prefix:** **/ops** (no /controltower prefix in codebase). All Control Tower–style APIs live under **/ops**.
- **Supply:** /ops/supply/geo, /ops/supply/parks, /ops/supply/series, /ops/supply/segments/series, /ops/supply/summary, /ops/supply/alerts, /ops/supply/alerts/drilldown, /ops/supply/migration, /ops/supply/migration/drilldown, /ops/supply/migration/weekly-summary, /ops/supply/migration/critical, /ops/supply/freshness, /ops/supply/definitions, etc.
- **Driver Lifecycle:** /ops/driver-lifecycle/ (prefix) → /weekly, /weekly-kpis, /monthly, /drilldown, /parks, /summary, /cohorts, /pro/churn-segments, /pro/behavior-shifts, etc.
- **Recommendation:** Implement Behavioral Alerts under the same prefix for consistency: **/ops/behavior-alerts/** (e.g. GET /ops/behavior-alerts/summary, GET /ops/behavior-alerts/drivers, GET /ops/behavior-alerts/driver-detail, GET /ops/behavior-alerts/export). If the product requirement explicitly expects a **/controltower** prefix, add a thin router that forwards to the same service.

---

## 9. Frontend Tab Architecture

- **File:** `frontend/src/App.jsx`.
- **State:** `activeTab` (string): 'real_lob' | 'driver_lifecycle' | 'supply' | 'snapshot' | 'system_health' | 'legacy' (and legacy sub-tabs).
- **Tabs rendered:** Real LOB, Driver Lifecycle, Driver Supply Dynamics (Supply), Snapshot, System Health, Legacy. **Migration** is a sub-tab **inside** SupplyView (Overview / Composition / Migration / Alerts).
- **Adding Behavioral Alerts:** Add a new nav button (e.g. “Behavioral Alerts”) and a new branch: `activeTab === 'behavioral_alerts' && <BehavioralAlertsView />`. Place it next to “Driver Lifecycle” and “Driver Supply Dynamics” as requested. **No changes** to existing tab logic or routes.

---

## 10. Reusable UI Components

| Component / utility | Use in Behavioral Alerts |
|---------------------|---------------------------|
| **CollapsibleFilters** | Global filters (country, city, etc.); Behavioral Alerts can use its own filter panel (date range, baseline window, country, city, park, segment, alert type, severity) without reusing CollapsibleFilters if the latter is tied to plan/real; otherwise reuse pattern. |
| **GlobalFreshnessBanner** | Already global; no change. |
| **KPICards** | Pattern for KPI cards (Drivers monitored, Critical drops, etc.); can reuse or mirror structure from SupplyView/DriverLifecycleView. |
| **formatNum / formatPct** | Used inline in SupplyView, DriverLifecycleView; define locally or in a shared util for Behavioral Alerts. |
| **DriverSupplyGlossary** | Semantic panel pattern; add a small “Behavioral Alerts” help panel (Segment, Movement, Baseline) as in Phase 11. |
| **Segment semantics** | `frontend/src/constants/segmentSemantics.js` (e.g. SEGMENT_LEGEND_MINIMAL); reuse for segment_current labels and colors. |
| **api.js** | Add new functions: getBehaviorAlertsSummary, getBehaviorAlertsDrivers, getBehaviorAlertsDriverDetail, getBehaviorAlertsExport. |
| **Supply geo** | getSupplyGeo() and getSupplyParks() already provide country, city, parks; reuse for filters in Behavioral Alerts. |

---

## 11. Risks and Constraints

1. **Baseline excludes current week:** All baseline metrics (avg, median, stddev, etc.) must be computed over the N weeks **strictly before** the current week. mv_driver_behavior_shifts_weekly uses “4 PRECEDING AND 1 PRECEDING”; we need the same for 4/6/8 weeks.
2. **Overlap with mv_driver_behavior_shifts_weekly:** That MV already has drop/spike vs 4w. Behavioral Alerts is additive: configurable window, more alert types (Critical Drop, Moderate Drop, Silent Erosion, Strong Recovery, High Volatility, Stable), severity, and full UI/export. We can either build on top of mv_driver_weekly_stats/mv_driver_segments_weekly only, or reference behavior_shifts for “drop/spike” and extend with extra logic; recommended: single source (weekly_stats or segments_weekly) for clarity.
3. **Performance:** A view that computes baseline + deltas + z_score + consecutive weeks over many driver-weeks may be heavy. Plan for **ops.v_driver_behavior_baseline_weekly** (view) and, if needed, **ops.mv_driver_behavior_alerts_weekly** with indexes (driver_key, week_start, country, city, park_id, alert_type) and **ops.refresh_driver_behavior_alerts()**.
4. **driver_name:** Available via **ops.v_dim_driver_resolved** (driver_id, driver_name). Join by driver_key = driver_id in baseline/alert view or in API layer.
5. **Geo on driver-week:** mv_driver_segments_weekly and mv_driver_weekly_stats have **park_id** only. Country/city come from **dim.v_geo_park** (or ops.v_dim_park_resolved) via park_id. Join once in the baseline view so that v_driver_behavior_baseline_weekly and v_driver_behavior_alerts_weekly expose country, city, park_name.

---

## 12. Minimal Integration Approach

1. **Data layer (ops schema only):**
   - **ops.v_driver_behavior_baseline_weekly:** View on top of ops.mv_driver_weekly_stats (or mv_driver_segments_weekly) + dim.v_geo_park + ops.v_dim_driver_resolved. Parameters: baseline_window_weeks (4/6/8) and “current” week_start; baseline window = current_week_start - (N * 7) to current_week_start - 7. Columns: driver_key, driver_name, week_start, week_label, country, city, park_id, park_name, trips_current_week, segment_current, avg_trips_baseline, median_trips_baseline, stddev_trips_baseline, min/max_trips_baseline, active_weeks_in_window, delta_abs, delta_pct, z_score_simple, weeks_declining_consecutively, weeks_rising_consecutively.
   - **ops.v_driver_behavior_alerts_weekly:** View on top of v_driver_behavior_baseline_weekly with alert_type and severity. (If the view is parameterized, implement via function or a view that uses a fixed default baseline window; filter by week_start and baseline_window in API.)
   - Optional: **ops.mv_driver_behavior_alerts_weekly** + **ops.refresh_driver_behavior_alerts()** if volume requires it.

2. **API (additive):**
   - New endpoints under **/ops/behavior-alerts/** (or /controltower/behavior-alerts if mandated): summary, drivers, driver-detail, export. Reuse existing get_db(), supply geo helpers, and response shapes.

3. **Frontend (additive):**
   - New tab **Behavioral Alerts** and **BehavioralAlertsView** with filters, KPI cards, insight banner, alerts table, driver drilldown, semantic panel, and export. Reuse Supply geo, segment semantics, and existing patterns (formatNum, formatPct, table + drilldown).

4. **No changes to:**
   - Migration views or Supply MVs, Driver Lifecycle MVs, existing tabs or routes.

---

## Recommended source of truth (Behavioral Alerts)

- **ops.mv_driver_segments_weekly** — driver-week trips, segment_week, prev_segment_week, segment_change_type.
- **ops.v_driver_behavior_baseline_weekly** — baseline metrics (6 weeks before current week), geo, driver_name, segment_previous, movement_type (from 084).
- **ops.v_driver_behavior_alerts_weekly** — alert_type, severity, risk_score, risk_band (from 085).

---

## What will NOT be touched

- Migration views and Supply MVs (mv_supply_segments_weekly, mv_driver_segment_migrations_weekly, etc.).
- Driver Lifecycle MVs and refresh order.
- ops.driver_segment_config (read-only; no schema or seed changes).
- Other routers (/plan, /real, /ops for non–behavior-alerts routes) and frontend tabs (Real LOB, Driver Lifecycle, Supply, Snapshot, System Health, Legacy).

---

## Driver Risk Score (planned)

Transparent, explainable score 0–100 for operational prioritization.

- **Components:** A) Behavior Deviation (0–40), B) Segment Migration Risk (0–30), C) Activity Fragility (0–20), D) Value/Priority Weight (0–10).
- **Bands:** 0–24 stable, 25–49 monitor, 50–74 medium risk, 75–100 high risk.
- **Requirement:** Formula and constants documented in code and docs; auditable, not a black box.

---

## 13. Summary Table

| Item | Finding |
|------|--------|
| **Weekly driver datasets** | mv_driver_weekly_stats, mv_driver_segments_weekly (with baseline_trips_4w_avg), mv_driver_weekly_behavior, mv_driver_behavior_shifts_weekly |
| **Lifecycle MVs** | mv_driver_lifecycle_base, mv_driver_lifecycle_weekly_kpis, mv_driver_lifecycle_monthly_kpis; refreshed after mv_driver_weekly_stats |
| **Supply datasets** | mv_supply_segments_weekly, mv_supply_segment_anomalies_weekly, mv_supply_alerts_weekly; migration views 079/080 |
| **Segment logic** | ops.driver_segment_config + get_driver_segment(); FT/PT/CASUAL/OCCASIONAL/DORMANT |
| **week_start** | Monday-based; baseline = N weeks before current week (current excluded) |
| **Driver identifiers** | driver_key = conductor_id; driver_name from ops.v_dim_driver_resolved (conductor_nombre) |
| **Trips per driver** | trips_completed_week in mv_driver_weekly_stats / mv_driver_segments_weekly |
| **Backend** | /ops prefix; add /ops/behavior-alerts/* |
| **Frontend tabs** | Add Behavioral Alerts tab next to Driver Lifecycle and Driver Supply Dynamics |
| **Reusable UI** | Supply geo, segment semantics, KPICards pattern, DriverSupplyGlossary-style panel, api.js |

This scan is the only deliverable for Phase 0. Implementation (Phases 1–16) will follow this document without modifying or breaking existing features.

---

## Implementation Summary (Post-Phase 0)

- **081:** `ops.v_driver_behavior_baseline_weekly` — baseline 6 weeks before current week; geo + driver_name; delta_abs, delta_pct, z_score_simple; weeks_declining/rising_consecutively (placeholder 0).
- **082:** `ops.v_driver_behavior_alerts_weekly` — alert_type (Critical Drop, Moderate Drop, Silent Erosion, Strong Recovery, High Volatility, Stable Performer), severity (critical/moderate/positive/neutral).
- **083:** Optional `ops.mv_driver_behavior_alerts_weekly` + `ops.refresh_driver_behavior_alerts()` with indexes.
- **API:** `/ops/behavior-alerts/summary`, `/ops/behavior-alerts/insight`, `/ops/behavior-alerts/drivers`, `/ops/behavior-alerts/driver-detail`, `/ops/behavior-alerts/export` (CSV/Excel).
- **Frontend:** Tab "Behavioral Alerts", BehavioralAlertsView (filters, KPIs, insight, table, drilldown, glossary, export).
