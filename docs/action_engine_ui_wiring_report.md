# Action Engine + Top Driver Behavior — UI Wiring Report (Phase 19)

**Project:** YEGO Control Tower  
**Date:** 2026-03-11  
**Scope:** Verification that DB → service → API → frontend → visible tab is correctly wired and no legacy path is used.

---

## Action Engine

| # | Item | Implementation |
|---|------|----------------|
| 1 | **Source SQL object** | ops.v_action_engine_driver_base (driver-week with cohort_type), ops.v_action_engine_cohorts_weekly (aggregates), ops.v_action_engine_recommendations_weekly (cohorts + priority_score). All read from ops.mv_driver_behavior_alerts_weekly. |
| 2 | **Backend function** | action_engine_service.py: get_action_engine_summary, get_action_engine_cohorts, get_action_engine_cohort_detail, get_action_engine_recommendations, get_action_engine_export. |
| 3 | **API route** | GET /ops/action-engine/summary, /ops/action-engine/cohorts, /ops/action-engine/cohort-detail, /ops/action-engine/recommendations, /ops/action-engine/export. All under prefix /ops. |
| 4 | **Frontend service function** | api.js: getActionEngineSummary, getActionEngineCohorts, getActionEngineCohortDetail, getActionEngineRecommendations, getActionEngineExportUrl. All call /ops/action-engine/*. |
| 5 | **Visible mounted component** | ActionEngineView.jsx (sub-tabs: "Cohorts" and "Top Driver Behavior"). Renders KPI cards, recommended actions panel, cohort table, cohort drilldown modal, export link. |
| 6 | **Tab mounted in App.jsx** | activeTab === 'action_engine' → <ActionEngineView />. Nav button label: "Action Engine". |
| 7 | **No legacy path** | Confirmed: no use of /controltower/* or /ops/behavior-alerts/* for Action Engine data. Action Engine uses only /ops/action-engine/*. |
| 8 | **Filters and export** | Filters (from, to, country, city, park_id, segment_current, cohort_type, priority) are passed to summary, cohorts, recommendations, and getActionEngineExportUrl; export uses same query params. |

---

## Top Driver Behavior

| # | Item | Implementation |
|---|------|----------------|
| 1 | **Source SQL object** | ops.v_top_driver_behavior_weekly (driver-week ELITE/LEGEND/FT), ops.v_top_driver_behavior_benchmarks (by segment_current), ops.v_top_driver_behavior_patterns (by segment, city, park). All read from ops.mv_driver_behavior_alerts_weekly. |
| 2 | **Backend function** | top_driver_behavior_service.py: get_top_driver_behavior_summary, get_top_driver_behavior_benchmarks, get_top_driver_behavior_patterns, get_top_driver_behavior_playbook_insights, get_top_driver_behavior_export. |
| 3 | **API route** | GET /ops/top-driver-behavior/summary, /ops/top-driver-behavior/benchmarks, /ops/top-driver-behavior/patterns, /ops/top-driver-behavior/playbook-insights, /ops/top-driver-behavior/export. All under prefix /ops. |
| 4 | **Frontend service function** | api.js: getTopDriverBehaviorSummary, getTopDriverBehaviorBenchmarks, getTopDriverBehaviorPatterns, getTopDriverBehaviorPlaybookInsights, getTopDriverBehaviorExportUrl. All call /ops/top-driver-behavior/*. |
| 5 | **Visible mounted component** | Same ActionEngineView.jsx, sub-tab "Top Driver Behavior": summary KPIs (Elite/Legend/FT counts), benchmarks table, playbook insights list, patterns table, export link. |
| 6 | **Tab** | No separate top-level tab; Top Driver Behavior is a sub-tab inside Action Engine. |
| 7 | **No legacy path** | Confirmed: Top Driver Behavior uses only /ops/top-driver-behavior/*. |
| 8 | **Filters and export** | Filters (from, to, country, city, park_id, segment_current) passed to summary, patterns, playbook-insights; getTopDriverBehaviorExportUrl uses same params. |

---

## Explicit chain (DB → visible UI)

### Action Engine (example: summary KPIs)

```
ops.v_action_engine_driver_base / ops.v_action_engine_cohorts_weekly / ops.v_action_engine_recommendations_weekly
  → backend/app/services/action_engine_service.py  (get_action_engine_summary, get_action_engine_cohorts, …)
  → backend/app/routers/ops.py  (GET /ops/action-engine/summary, /cohorts, /cohort-detail, /recommendations, /export)
  → frontend/src/services/api.js  (getActionEngineSummary, getActionEngineCohorts, … → baseURL + '/ops/action-engine/…')
  → frontend/src/components/ActionEngineView.jsx  (loadSummary(), loadCohorts(), loadRecommendations(), …)
  → frontend/src/App.jsx  (activeTab === 'action_engine' → <ActionEngineView />)
  → visible tab: "Action Engine" in nav bar
```

### Top Driver Behavior (example: benchmarks)

```
ops.v_top_driver_behavior_weekly / ops.v_top_driver_behavior_benchmarks / ops.v_top_driver_behavior_patterns
  → backend/app/services/top_driver_behavior_service.py  (get_top_driver_behavior_benchmarks, …)
  → backend/app/routers/ops.py  (GET /ops/top-driver-behavior/summary, /benchmarks, /patterns, /playbook-insights, /export)
  → frontend/src/services/api.js  (getTopDriverBehaviorSummary, getTopDriverBehaviorBenchmarks, … → baseURL + '/ops/top-driver-behavior/…')
  → frontend/src/components/ActionEngineView.jsx  (loadTdb() when subTab === 'top_driver_behavior')
  → same App.jsx tab "Action Engine" → sub-tab "Top Driver Behavior"
  → visible: section inside Action Engine tab
```

### Legacy paths NOT used

- **/controltower/** — Not used by ActionEngineView or api.js for Action Engine / Top Driver Behavior.
- **/ops/behavior-alerts/** — Used only by BehavioralAlertsView; ActionEngineView does not call it for cohort or recommendation data.
- No old/archaic route, service, or component is powering the visible Action Engine or Top Driver Behavior UI.

---

## Checklist summary

- [x] Action Engine: source view/MV → service → /ops/action-engine/* → api.js → ActionEngineView → tab "Action Engine".
- [x] Top Driver Behavior: source views → service → /ops/top-driver-behavior/* → api.js → ActionEngineView (sub-tab) → same tab.
- [x] No legacy endpoint powers the new features.
- [x] Export URLs use the same filters as the current view.
