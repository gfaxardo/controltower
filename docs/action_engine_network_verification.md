# Action Engine — Network / Actual UI Call Verification (Phase 8)

**Project:** YEGO Control Tower  
**Date:** 2026-03-11  
**Method:** Code trace (no live browser DevTools run in this session).

---

## Endpoints actually called by the visible UI

The following is derived from the source code of the **mounted** component (ActionEngineView.jsx) and the frontend service (api.js).

### Action Engine tab (sub-tab "Cohortes y acciones")

| Component | Function | Endpoint called |
|-----------|----------|------------------|
| ActionEngineView.jsx | loadSummary | getActionEngineSummary → **GET /ops/action-engine/summary** |
| ActionEngineView.jsx | loadRecommendations | getActionEngineRecommendations → **GET /ops/action-engine/recommendations** |
| ActionEngineView.jsx | loadCohorts | getActionEngineCohorts → **GET /ops/action-engine/cohorts** |
| ActionEngineView.jsx | loadCohortDetail | getActionEngineCohortDetail → **GET /ops/action-engine/cohort-detail** |
| ActionEngineView.jsx | Export link (table) | getActionEngineExportUrl(…) → **GET /ops/action-engine/export?…** |
| ActionEngineView.jsx | Export link (drilldown) | getActionEngineExportUrl({…cohort_type, week_start}) → **GET /ops/action-engine/export?…** |

**api.js:** All of the above use `api.get('/ops/action-engine/...')` or URL `${base}/ops/action-engine/export?${q}`. No reference to /controltower or /ops/behavior-alerts for these flows.

### Top Driver Behavior (sub-tab "Top Driver Behavior")

| Component | Function | Endpoint called |
|-----------|----------|------------------|
| ActionEngineView.jsx | loadTdb (useEffect when subTab === 'top_driver_behavior') | getTopDriverBehaviorSummary → **GET /ops/top-driver-behavior/summary** |
| ActionEngineView.jsx | loadTdb | getTopDriverBehaviorBenchmarks → **GET /ops/top-driver-behavior/benchmarks** |
| ActionEngineView.jsx | loadTdb | getTopDriverBehaviorPatterns → **GET /ops/top-driver-behavior/patterns** |
| ActionEngineView.jsx | loadTdb | getTopDriverBehaviorPlaybookInsights → **GET /ops/top-driver-behavior/playbook-insights** |
| ActionEngineView.jsx | Export link | getTopDriverBehaviorExportUrl(…) → **GET /ops/top-driver-behavior/export?…** |

**api.js:** All use `api.get('/ops/top-driver-behavior/...')` or URL `${base}/ops/top-driver-behavior/export?${q}`. No legacy path.

---

## Pass/fail

| Check | Result |
|-------|--------|
| Action Engine visible tab calls Action Engine endpoints | **Pass** — Only getActionEngine* and getActionEngineExportUrl are used for summary, cohorts, recommendations, detail, export. |
| Top Driver Behavior visible section calls Top Driver Behavior endpoints | **Pass** — Only getTopDriverBehavior* and getTopDriverBehaviorExportUrl are used. |
| No fallback to legacy endpoints | **Pass** — No /controltower/* or /ops/behavior-alerts/* in ActionEngineView for this feature. |

---

## Mismatch found

- None. The mounted UI (ActionEngineView) uses only the new /ops/action-engine/* and /ops/top-driver-behavior/* endpoints.
