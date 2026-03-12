# Action Engine + Top Driver Behavior — Preflight Inventory (Phase 1)

**Project:** YEGO Control Tower  
**Date:** 2026-03-11  
**Mode:** Read-only existence check. No changes applied.

---

## A) SQL layer

### Migration files

| File | Revision | Creates |
|------|----------|---------|
| backend/alembic/versions/086_action_engine_views.py | 086_action_engine_views | ops.v_action_engine_driver_base, ops.v_action_engine_cohorts_weekly, ops.v_action_engine_recommendations_weekly |
| backend/alembic/versions/087_top_driver_behavior_views.py | 087_top_driver_behavior_views | ops.v_top_driver_behavior_weekly, ops.v_top_driver_behavior_benchmarks, ops.v_top_driver_behavior_patterns |

### Views (defined in migrations)

| Object | Type | Source |
|--------|------|--------|
| ops.v_action_engine_driver_base | VIEW | ops.mv_driver_behavior_alerts_weekly |
| ops.v_action_engine_cohorts_weekly | VIEW | ops.v_action_engine_driver_base |
| ops.v_action_engine_recommendations_weekly | VIEW | ops.v_action_engine_cohorts_weekly |
| ops.v_top_driver_behavior_weekly | VIEW | ops.mv_driver_behavior_alerts_weekly |
| ops.v_top_driver_behavior_benchmarks | VIEW | ops.v_top_driver_behavior_weekly |
| ops.v_top_driver_behavior_patterns | VIEW | ops.v_top_driver_behavior_weekly |

### Materialized views

- **Action Engine / Top Driver Behavior:** No dedicated MVs. Both rely on **ops.mv_driver_behavior_alerts_weekly** (existing). If that MV is stale, Action Engine and Top Driver Behavior views will reflect stale data.

### Refresh functions

- No dedicated refresh for Action Engine or Top Driver Behavior. Refresh of **ops.mv_driver_behavior_alerts_weekly** (e.g. ops.refresh_driver_behavior_alerts if present) is the dependency.

### Gaps

- None for views. Existence of views in DB depends on migrations 086 and 087 being applied.

---

## B) Backend layer

### Services

| File | Functions |
|------|-----------|
| backend/app/services/action_engine_service.py | get_action_engine_summary, get_action_engine_cohorts, get_action_engine_cohort_detail, get_action_engine_recommendations, get_action_engine_export |
| backend/app/services/top_driver_behavior_service.py | get_top_driver_behavior_summary, get_top_driver_behavior_benchmarks, get_top_driver_behavior_patterns, get_top_driver_behavior_playbook_insights, get_top_driver_behavior_export |

### Routers

| File | Router | Prefix |
|------|--------|--------|
| backend/app/routers/ops.py | ops.router | /ops |

### Mounting (main.py)

- **app.include_router(ops.router)** confirmed. All /ops routes are mounted.

### Routes (Action Engine)

| Method | Path | Handler |
|--------|------|---------|
| GET | /ops/action-engine/summary | get_action_engine_summary_endpoint |
| GET | /ops/action-engine/cohorts | get_action_engine_cohorts_endpoint |
| GET | /ops/action-engine/cohort-detail | get_action_engine_cohort_detail_endpoint |
| GET | /ops/action-engine/recommendations | get_action_engine_recommendations_endpoint |
| GET | /ops/action-engine/export | get_action_engine_export_endpoint |

### Routes (Top Driver Behavior)

| Method | Path | Handler |
|--------|------|---------|
| GET | /ops/top-driver-behavior/summary | get_top_driver_behavior_summary_endpoint |
| GET | /ops/top-driver-behavior/benchmarks | get_top_driver_behavior_benchmarks_endpoint |
| GET | /ops/top-driver-behavior/patterns | get_top_driver_behavior_patterns_endpoint |
| GET | /ops/top-driver-behavior/playbook-insights | get_top_driver_behavior_playbook_insights_endpoint |
| GET | /ops/top-driver-behavior/export | get_top_driver_behavior_export_endpoint |

### Gaps

- None. Backend routes and services are present and wired.

---

## C) Frontend layer

### Tabs (App.jsx)

| Tab state | Label | Component |
|-----------|-------|-----------|
| activeTab === 'action_engine' | "Action Engine" | ActionEngineView |

- **Import:** `import ActionEngineView from './components/ActionEngineView'`
- **Render:** `{activeTab === 'action_engine' && <ActionEngineView key={...} />}`

### Components

| Component | File | Sub-tabs / sections |
|-----------|------|----------------------|
| ActionEngineView | frontend/src/components/ActionEngineView.jsx | "Cohortes y acciones", "Top Driver Behavior" |

### Service functions (api.js)

| Function | Endpoint called |
|----------|------------------|
| getActionEngineSummary | GET /ops/action-engine/summary |
| getActionEngineCohorts | GET /ops/action-engine/cohorts |
| getActionEngineCohortDetail | GET /ops/action-engine/cohort-detail |
| getActionEngineRecommendations | GET /ops/action-engine/recommendations |
| getActionEngineExportUrl | URL to /ops/action-engine/export |
| getTopDriverBehaviorSummary | GET /ops/top-driver-behavior/summary |
| getTopDriverBehaviorBenchmarks | GET /ops/top-driver-behavior/benchmarks |
| getTopDriverBehaviorPatterns | GET /ops/top-driver-behavior/patterns |
| getTopDriverBehaviorPlaybookInsights | GET /ops/top-driver-behavior/playbook-insights |
| getTopDriverBehaviorExportUrl | URL to /ops/top-driver-behavior/export |

### Consumer → service mapping (ActionEngineView.jsx)

- loadSummary → getActionEngineSummary
- loadRecommendations → getActionEngineRecommendations
- loadCohorts → getActionEngineCohorts
- loadCohortDetail → getActionEngineCohortDetail
- getActionEngineExportUrl used for "Exportar CSV" and "Exportar esta cohorte"
- loadTdb (Top Driver Behavior) → getTopDriverBehaviorSummary, getTopDriverBehaviorBenchmarks, getTopDriverBehaviorPatterns, getTopDriverBehaviorPlaybookInsights
- getTopDriverBehaviorExportUrl for "Exportar Top Driver Behavior"

### Exports / drilldowns

- Cohort table → "Ver" opens drilldown modal → getActionEngineCohortDetail(cohort_type, week_start, ...)
- Export links use getActionEngineExportUrl / getTopDriverBehaviorExportUrl with current filters.

### Gaps

- None. Frontend uses only the new /ops/action-engine/* and /ops/top-driver-behavior/* paths. No reference to /controltower/* or /ops/behavior-alerts/* for Action Engine or Top Driver Behavior data.

---

## Summary

| Layer | Present | Notes |
|-------|---------|-------|
| SQL (migrations + view definitions) | Yes | 086, 087; 6 views total |
| Backend services | Yes | action_engine_service, top_driver_behavior_service |
| Backend routes | Yes | 10 routes under /ops |
| Router mounted in main | Yes | ops.router included |
| Frontend tab | Yes | "Action Engine" in App.jsx |
| Frontend component | Yes | ActionEngineView.jsx |
| Frontend API functions | Yes | All call /ops/action-engine/* or /ops/top-driver-behavior/* |
| Legacy path used for this feature | No | Confirmed not used |

**Obvious gaps:** None in codebase. DB state (migrations applied, views existing) and runtime (API responding, UI calling correct endpoints) require Phases 2–8.
