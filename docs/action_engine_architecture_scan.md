# Action Engine + Top Driver Behavior — Architecture Scan (Phase 0)

**Project:** YEGO Control Tower  
**Feature:** Action Engine + Top Driver Behavior  
**Date:** 2026-03-11  
**Scope:** Read-only scan prior to implementation. **Do NOT implement before completing this scan.**

---

## A) Existing signal sources

### Behavioral Alerts & Driver Risk Score

| Object | Schema | Grain | Key columns (for Action Engine) |
|--------|--------|-------|---------------------------------|
| **v_driver_behavior_baseline_weekly** | ops | driver_key, week_start | driver_key, driver_name, week_start, week_label, country, city, park_id, park_name, trips_current_week, segment_current, segment_previous, movement_type, avg_trips_baseline, delta_abs, delta_pct, z_score_simple, active_weeks_in_window, weeks_declining_consecutively, weeks_rising_consecutively |
| **v_driver_behavior_alerts_weekly** | ops | driver_key, week_start | All baseline columns + alert_type, severity, risk_score, risk_band, risk_score_behavior, risk_score_migration, risk_score_fragility, risk_score_value |
| **mv_driver_behavior_alerts_weekly** | ops | Same | Same as view; used for list/export (faster). Refresh: ops.refresh_driver_behavior_alerts() |

- **Source of truth for Action Engine driver-level signals:** `ops.mv_driver_behavior_alerts_weekly` (or view) — already has segment_current, segment_previous, movement_type, alert_type, severity, risk_score, risk_band, baseline deviation, geo.

### Migration datasets (read-only; do not modify)

| Object | Grain | Use for Action Engine |
|--------|-------|------------------------|
| **v_driver_segment_migrations_weekly** | week_start, park_id, from_segment, to_segment | Aggregate migration flows; optional for “near upgrade/downgrade” context. |
| **mv_driver_segment_migrations_weekly** | Same | Materialized copy (080). |

### Segment datasets

| Object | Notes |
|--------|--------|
| **ops.driver_segment_config** | segment_code, min/max_trips_week, ordering. Taxonomy: DORMANT (0), OCCASIONAL (1–4), CASUAL (5–19), PT (20–59), FT (60–119), ELITE (120–179), LEGEND (180+). Read-only. |
| **ops.mv_driver_segments_weekly** | driver_key, week_start, segment_week, prev_segment_week, segment_change_type, trips_completed_week. Input to baseline/alerts. |

### Driver weekly activity

| Object | Use |
|--------|-----|
| **ops.mv_driver_weekly_stats** | trips_completed_week per driver-week. |
| **ops.mv_driver_segments_weekly** | Trips + segment + movement type. |
| **ops.mv_driver_behavior_alerts_weekly** | **Primary input for Action Engine:** one row per driver-week with alerts, risk, baseline, geo. |

### Park / city / country dimensions

| Object | Use |
|--------|-----|
| **dim.v_geo_park** | park_id, park_name, city, country. Already joined in Behavioral Alerts views. |
| **ops.v_dim_driver_resolved** | driver_id, driver_name. Already in baseline/alerts. |

---

## B) Existing frontend structure

### Tabs (App.jsx)

- **State:** `activeTab`: 'real_lob' | 'driver_lifecycle' | 'supply' | 'behavioral_alerts' | 'snapshot' | 'system_health' | 'legacy'.
- **Nav buttons:** Real LOB, Driver Lifecycle, Driver Supply Dynamics, **Behavioral Alerts**, Snapshot, System Health, Legacy.
- **Render:** `{activeTab === 'behavioral_alerts' && <BehavioralAlertsView />}` etc. **Additive only:** new tab(s) for Action Engine (and optionally Top Driver Behavior as sub-tab or section).

### Sub-tabs pattern (SupplyView)

- **TABS:** overview, composition, migration, alerts (internal state `activeTab` within SupplyView).
- **Pattern:** Tabs as buttons; load data per tab (loadOverview, loadComposition, loadMigration, loadAlerts); drilldown (e.g. Migration drilldown via getSupplyMigrationDrilldown).
- **Reuse for Action Engine:** One top-level tab “Action Engine” with optional internal sub-tabs: e.g. “Cohorts” and “Top Driver Behavior”, or single view with sections (Recommended actions → Cohorts table → Top Driver Behavior section).

### KPI cards

- **BehavioralAlertsView:** Grid of cards (drivers monitored, high risk, medium risk, critical drops, etc.); each card shows a number from summary API.
- **SupplyView:** Overview summary cards, Migration KPIs.
- **Pattern:** Summary endpoint returns counts; frontend maps to cards. Action Engine will need summary with actionable_drivers, cohorts_detected, high_priority_cohorts, recoverable_drivers, high_value_at_risk, near_upgrade_opportunities.

### Grouped tables & filters

- **BehavioralAlertsView:** Filters (date range, baseline window, country, city, park, segment, movement type, alert type, severity, risk band); table with sort (risk_score desc, delta_pct); export CSV/Excel.
- **SupplyView Migration:** Filters (from, to, type, week, segment); table with expandable weeks; drilldown modal.
- **Action Engine:** Filters aligned with Behavioral Alerts (week/date range, country, city, park, segment, movement_type, alert_type, severity, risk_band) **plus** cohort_type, priority. Table: cohorts with drilldown to driver list.

### Exports

- **Behavioral Alerts:** getBehaviorAlertsExportUrl(params) → `/ops/behavior-alerts/export?…`; CSV/Excel with columns including risk_score, risk_band, movement_type.
- **Pattern:** Export URL with same filters as view; backend returns file. Action Engine: export cohort(s) and/or recommended-action population with same pattern.

### Drilldown patterns

- **Behavioral Alerts:** Row click or “Ver detalle” → driver detail (timeline + “Why flagged” + risk_reasons).
- **Supply Migration:** Row click → getSupplyMigrationDrilldown → modal with driver list for that transition.
- **Action Engine:** Cohort row click → cohort drilldown (list of drivers in cohort, why they belong, export filtered list).

---

## C) Existing services / APIs

### Behavioral Alerts (do not replace; read from)

| Endpoint | Method | Use |
|----------|--------|-----|
| /ops/behavior-alerts/summary | GET | KPIs (drivers_monitored, high_risk_drivers, medium_risk_drivers, critical_drops, …). |
| /ops/behavior-alerts/insight | GET | Text summary. |
| /ops/behavior-alerts/drivers | GET | Paginated driver list (from MV). |
| /ops/behavior-alerts/driver-detail | GET | Driver timeline + risk_reasons. |
| /ops/behavior-alerts/export | GET | CSV/Excel with filters. |

- **Backend:** `backend/app/services/behavior_alerts_service.py` (get_behavior_alerts_summary, get_behavior_alerts_drivers, …). Reads from **ops.mv_driver_behavior_alerts_weekly** (drivers/export) and **ops.v_driver_behavior_alerts_weekly** (summary).
- **Frontend:** `frontend/src/services/api.js` — getBehaviorAlertsSummary, getBehaviorAlertsDrivers, getBehaviorAlertsDriverDetail, getBehaviorAlertsExportUrl. All use **/ops/behavior-alerts/** (not /controltower in UI).
- **Router:** `backend/app/routers/ops.py` (prefix /ops); also `controltower.py` (prefix /controltower) mirrors behavior-alerts.

### Supply / Migration (do not modify)

- **Endpoints:** /ops/supply/geo, /ops/supply/segments/config, /ops/supply/definitions, /ops/supply/migration, /ops/supply/migration/drilldown, /ops/supply/migration/weekly-summary, /ops/supply/migration/critical, etc.
- **Frontend:** getSupplyGeo, getSupplySegmentConfig, getSupplyMigration, getSupplyMigrationDrilldown, etc. (api.js).

### Reusable components / utilities

| Item | Location | Use for Action Engine |
|------|----------|------------------------|
| getSupplyGeo, getSupplySegmentConfig | api.js | Filters: country, city, park; segment options. |
| formatNum, formatPct | Inline in views | Reuse or mirror for cohort table and KPIs. |
| Segment semantics / colors | constants/segmentSemantics.js, SupplyView/BehavioralAlertsView | Cohort “dominant segment” and driver list. |
| Table + modal drilldown | BehavioralAlertsView, SupplyView | Cohort table → cohort drilldown modal. |
| Export URL pattern | getBehaviorAlertsExportUrl | getActionEngineExportUrl( params ) for cohort/action export. |

---

## D) Existing driver value proxies

Available in **ops.v_driver_behavior_alerts_weekly** / **ops.mv_driver_behavior_alerts_weekly** (and thus for Action Engine):

| Proxy | Column(s) | Use |
|-------|-----------|-----|
| Historical volume | avg_trips_baseline | Value weight, “high value” cohorts. |
| Current volume | trips_current_week | Current performance. |
| Segment level | segment_current, segment_previous | FT/ELITE/LEGEND = high value; ordering from driver_segment_config. |
| Baseline deviation | delta_abs, delta_pct | Deterioration / recovery. |
| Risk | risk_score, risk_band | Prioritization. |
| Alert type / severity | alert_type, severity | Critical Drop, Moderate Drop, Strong Recovery, etc. |
| Movement | movement_type | upshift, downshift, stable, drop, new. |
| Consistency / fragility | active_weeks_in_window, weeks_declining_consecutively, stddev_trips_baseline (in baseline) | Silent erosion, volatility. |

These are sufficient to define cohorts (High Value Deteriorating, Silent Erosion, Recoverable Mid Performers, Near Upgrade, Near Drop Risk, Volatile, High Value Recovery) and to feed Top Driver Behavior (Elite/Legend/FT filters, avg trips, consistency).

---

## Source-of-truth datasets (Action Engine & Top Driver Behavior)

| Layer | Source | Notes |
|-------|--------|--------|
| **Driver-level signals** | ops.mv_driver_behavior_alerts_weekly (or ops.v_driver_behavior_alerts_weekly) | Single source for driver-week with alert, risk, segment, movement, baseline. No new raw driver-week table; build cohorts on top of this. |
| **Cohorts** | New: ops.v_action_engine_cohorts_weekly (derived from alerts view/MV) | Aggregates by cohort_type, week_start, optional geo; cohort_size, avg_risk_score, avg_delta_pct, dominant_segment, suggested_priority, suggested_channel. |
| **Recommendations** | New: ops.v_action_engine_recommendations_weekly | Action name, target cohort, urgency, channel, rationale; can be view or derived in API from cohorts. |
| **Top Driver Behavior** | New: ops.v_top_driver_behavior_weekly, ops.v_top_driver_behavior_patterns / benchmarks | Input: same alerts MV/view filtered by segment_current IN ('ELITE','LEGEND') (and optionally FT). Derive consistency, avg trips, % weeks high segment, city/park concentration; day-of-week if available in source. |

---

## Files to touch (additive only)

### Backend

| File | Change |
|------|--------|
| **backend/alembic/versions/** | New migrations: e.g. 086_action_engine_views, 087_top_driver_behavior_views (views/MVs for cohorts, recommendations, top-driver patterns). |
| **backend/app/services/action_engine_service.py** | **New.** Summary, cohorts, cohort_detail, export; read from ops.v_action_engine_cohorts_weekly and driver list from mv_driver_behavior_alerts_weekly with cohort filter. |
| **backend/app/services/top_driver_behavior_service.py** | **New.** Summary, benchmarks, patterns, export; read from new top_driver views. |
| **backend/app/routers/ops.py** | **Add** routes: /ops/action-engine/summary, /ops/action-engine/cohorts, /ops/action-engine/cohort-detail, /ops/action-engine/export; /ops/top-driver-behavior/summary, /ops/top-driver-behavior/benchmarks, /ops/top-driver-behavior/patterns, /ops/top-driver-behavior/export. No changes to existing routes. |
| **backend/app/main.py** | No change (ops router already included). |

### Frontend

| File | Change |
|------|--------|
| **frontend/src/App.jsx** | **Add** nav button “Action Engine” and branch `activeTab === 'action_engine' && <ActionEngineView />`. Do not remove or replace existing tabs. |
| **frontend/src/components/ActionEngineView.jsx** | **New.** Filters, KPI cards, recommended actions panel, cohort table, cohort drilldown, export, help panel; optional sub-section or sub-tab for Top Driver Behavior. |
| **frontend/src/services/api.js** | **Add** getActionEngineSummary, getActionEngineCohorts, getActionEngineCohortDetail, getActionEngineExportUrl; getTopDriverBehaviorSummary, getTopDriverBehaviorBenchmarks, getTopDriverBehaviorPatterns, getTopDriverBehaviorExportUrl. All under **/ops/** (same base URL as existing). |

### Docs (new)

| File | Content |
|------|--------|
| docs/action_engine_logic.md | Cohort definitions, rules, priority, recommended actions. |
| docs/top_driver_behavior_logic.md | Metrics, benchmarks, patterns, playbook-style insights. |
| docs/action_engine_ui_wiring_report.md | Verification: DB → service → route → api.js → component → tab (Phase 19). |

---

## Recommended minimal architecture

1. **Data (additive)**  
   - **v_action_engine_driver_base:** Optional; can be “SELECT * FROM ops.mv_driver_behavior_alerts_weekly” with optional computed cohort_type per row.  
   - **v_action_engine_cohorts_weekly:** Aggregation by (week_start, cohort_type, optional country/city/park_id). Columns: cohort_type, cohort_size, avg_risk_score, avg_delta_pct, avg_baseline_value, dominant_segment, suggested_priority, suggested_channel, action_name, action_objective.  
   - **v_action_engine_recommendations_weekly:** One row per (week_start, cohort_type) with action_name, urgency, channel, why_this_matters; can be same as cohorts or a separate view.  
   - **v_top_driver_behavior_weekly:** Driver-week for segment_current IN ('ELITE','LEGEND','FT') from alerts MV; optional extra metrics (consistency, active_weeks).  
   - **v_top_driver_behavior_patterns / benchmarks:** Aggregates (e.g. by segment_current, city, park) for consistency, avg trips, % high weeks.  

2. **API**  
   - New endpoints under **/ops/action-engine/** and **/ops/top-driver-behavior/** only. Same router (ops) and prefix /ops.  

3. **UI**  
   - One new tab “Action Engine” with: filters → KPI cards → recommended actions panel → cohort table → cohort drilldown → export; then section or sub-tab “Top Driver Behavior” (benchmarks, patterns, playbook insights, export).  

4. **No changes to**  
   - Migration, Supply, Driver Lifecycle, Behavioral Alerts (tabs, routes, MVs, views, services).  

---

## Performance concerns

- **Cohort views:** Built on top of mv_driver_behavior_alerts_weekly; avoid full scan per request—prefer aggregation by week_start + cohort_type (and optional geo) with indexes. If heavy, add ops.mv_action_engine_cohorts_weekly + refresh after behavior_alerts refresh.  
- **Top Driver Behavior:** Filter by segment_current IN ('ELITE','LEGEND','FT') reduces rows; aggregates by segment/city/park should remain fast. Optional MV for benchmarks if needed.  
- **Statement timeout:** For any new heavy list/export, use same pattern as behavior_alerts (SET statement_timeout in session or use MV).  
- **Refresh order:** If new MVs added: refresh_driver_behavior_alerts() first, then action_engine and top_driver MVs (if any).  

---

## UI integration strategy

- **New tab only:** Add “Action Engine” in the same nav bar as “Behavioral Alerts”, “Driver Supply Dynamics”, etc.  
- **Single component:** ActionEngineView.jsx owns filters, KPIs, recommended actions, cohort table, drilldown, and Top Driver Behavior (as section or sub-tab inside the same view).  
- **Reuse:** getSupplyGeo, getSupplySegmentConfig for filters; same date-range and geo filter pattern as Behavioral Alerts; export URL pattern like getBehaviorAlertsExportUrl.  
- **No replacement:** Behavioral Alerts tab and all its endpoints remain; Migration remains under Supply; Driver Lifecycle unchanged.  

---

## Legacy paths that must NOT be used

- **Do not** point Action Engine UI at any legacy or deprecated endpoint (e.g. old /plan, /real, or internal driver-lifecycle cohort endpoints that are not designed for Action Engine).  
- **Do not** reuse Behavioral Alerts tab for Action Engine: keep Behavioral Alerts as-is; add a **new** tab and **new** /ops/action-engine/* and /ops/top-driver-behavior/* endpoints.  
- **Do not** call /controltower/* from the new UI unless the product explicitly requires it; use **/ops/action-engine/** and **/ops/top-driver-behavior/** consistently (same as rest of Control Tower).  
- **Do not** modify existing behavior_alerts_service or behavior-alerts routes to implement cohorts; implement cohorts in **new** action_engine_service and action-engine routes.  

---

## Wiring verification plan (Phase 19)

Before marking the feature complete, verify the following for **Action Engine** and **Top Driver Behavior** separately.

### Action Engine

1. **Source SQL:** Which view/MV feeds cohorts and driver list? (e.g. ops.v_action_engine_cohorts_weekly, ops.mv_driver_behavior_alerts_weekly for driver list filtered by cohort.)  
2. **Backend function:** e.g. get_action_engine_summary, get_action_engine_cohorts, get_action_engine_cohort_detail, get_action_engine_export in action_engine_service.py.  
3. **API route:** GET /ops/action-engine/summary, /ops/action-engine/cohorts, /ops/action-engine/cohort-detail, /ops/action-engine/export.  
4. **Frontend service:** getActionEngineSummary, getActionEngineCohorts, getActionEngineCohortDetail, getActionEngineExportUrl in api.js calling /ops/action-engine/*.  
5. **Visible component:** ActionEngineView.jsx using the above API functions.  
6. **Mounted tab:** App.jsx: button “Action Engine” sets activeTab to 'action_engine'; render {activeTab === 'action_engine' && <ActionEngineView />}.  
7. **No legacy path:** Confirm no fallback or duplicate code path that uses old endpoints or a different base URL.  
8. **Filters and export:** Same filters passed to summary, cohorts, and export; export URL includes filter params.  

### Top Driver Behavior

1. **Source SQL:** ops.v_top_driver_behavior_weekly and/or ops.v_top_driver_behavior_patterns (or benchmarks view).  
2. **Backend function:** get_top_driver_behavior_summary, get_top_driver_behavior_benchmarks, get_top_driver_behavior_patterns, get_top_driver_behavior_export.  
3. **API route:** GET /ops/top-driver-behavior/summary, /benchmarks, /patterns, /export.  
4. **Frontend service:** getTopDriverBehaviorSummary, getTopDriverBehaviorBenchmarks, getTopDriverBehaviorPatterns, getTopDriverBehaviorExportUrl calling /ops/top-driver-behavior/*.  
5. **Visible component:** Section or sub-tab inside ActionEngineView (or dedicated TopDriverBehaviorView if preferred).  
6. **Mounted:** Visible when user is on Action Engine tab (and optionally on a “Top Driver Behavior” sub-tab).  
7. **No legacy path:** Same as above.  
8. **Export:** Export uses same filters and /ops/top-driver-behavior/export.  

### Deliverable for Phase 19

- **docs/action_engine_ui_wiring_report.md** with:  
  - For Action Engine: (1)–(8) above filled with actual object names and file paths.  
  - For Top Driver Behavior: (1)–(8) above filled with actual object names and file paths.  
  - Explicit confirmation: “No legacy endpoint or service powers the visible Action Engine or Top Driver Behavior UI.”  

---

## Summary table

| Item | Finding |
|------|--------|
| **Behavioral Alerts / Risk source** | ops.v_driver_behavior_alerts_weekly, ops.mv_driver_behavior_alerts_weekly (summary from view; drivers/export from MV). |
| **Migration** | ops.v_driver_segment_migrations_weekly, mv (079/080); read-only. |
| **Segment taxonomy** | ops.driver_segment_config: DORMANT→LEGEND (078); read-only. |
| **Driver value proxies** | avg_trips_baseline, trips_current_week, segment_current/previous, risk_score/band, alert_type, severity, movement_type, active_weeks, weeks_declining. |
| **Backend pattern** | New service + new routes under /ops (action-engine, top-driver-behavior). |
| **Frontend pattern** | New tab Action Engine; new component ActionEngineView; new api.js functions; optional sub-section Top Driver Behavior. |
| **Reusable** | getSupplyGeo, getSupplySegmentConfig; table/drilldown/export patterns; segment semantics. |
| **Must not touch** | Migration, Supply, Lifecycle, Behavioral Alerts (tabs, routes, MVs, views). |
| **Wiring verification** | Phase 19: document source → service → route → api → component → tab for both modules; confirm no legacy path. |

---

This scan is the only deliverable for Phase 0. Implementation (Phases 1–23) will follow this document and must remain **additive and non-destructive**.
