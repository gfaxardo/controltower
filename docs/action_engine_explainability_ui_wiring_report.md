# Action Engine + Behavioral Alerts — Explainability UI Wiring Report (Phase 14)

**Project:** YEGO Control Tower  
**Date:** 2026-03-11

---

## Active path (upgraded explainability)

### Behavioral Alerts

| Step | Implementation |
|------|----------------|
| **DB/View/MV** | ops.mv_driver_behavior_alerts_weekly (includes weeks_declining_consecutively, weeks_rising_consecutively). |
| **Backend service** | behavior_alerts_service.get_behavior_alerts_drivers — SELECT now includes weeks_declining_consecutively, weeks_rising_consecutively. get_behavior_alerts_driver_detail includes weeks_rising_consecutively. |
| **API route** | GET /ops/behavior-alerts/drivers, GET /ops/behavior-alerts/driver-detail (unchanged paths). |
| **Frontend service** | api.js getBehaviorAlertsDrivers, getBehaviorAlertsDriverDetail (unchanged). |
| **Component** | BehavioralAlertsView.jsx — imports getBehaviorDirection, getPersistenceLabel, getDeltaPctColor, getDecisionContextLabel, BEHAVIOR_DIRECTION_COLORS from explainabilitySemantics.js. Table columns: Estado conductual, Persistencia; Delta % uses getDeltaPctColor; time context label above table; driver detail modal shows Estado conductual, Persistencia, and decision context. |
| **Mounted** | App.jsx activeTab === 'behavioral_alerts' → BehavioralAlertsView. |

**Proof that visible UI reflects new changes:** BehavioralAlertsView renders "Estado conductual" and "Persistencia" from row data (weeks_* from API); getBehaviorDirection(row) and getPersistenceLabel(row) use that data. No legacy component or path used for these fields.

### Action Engine

| Step | Implementation |
|------|----------------|
| **DB/View** | ops.v_action_engine_driver_base (088: includes weeks_rising_consecutively). ops.v_action_engine_cohorts_weekly, ops.v_action_engine_recommendations_weekly. |
| **Backend service** | action_engine_service.get_action_engine_cohort_detail — SELECT includes active_weeks_in_window, weeks_declining_consecutively, weeks_rising_consecutively. get_action_engine_export includes same. |
| **API route** | GET /ops/action-engine/cohort-detail, GET /ops/action-engine/export (unchanged paths). |
| **Frontend service** | api.js getActionEngineCohortDetail, getActionEngineExportUrl (unchanged). |
| **Component** | ActionEngineView.jsx — imports explainabilitySemantics (getBehaviorDirection, getPersistenceLabel, getDeltaPctColor, getDecisionContextLabel, COHORT_RATIONALE, BEHAVIOR_DIRECTION_COLORS, SEMANTIC_ALERT_COLORS). Recommendation cards show week, decision context, avg delta %, rationale. Cohort table shows rationale and delta color. Drilldown: header with decision context and rationale; columns Estado conductual, Persistencia; delta and alert badges with semantic colors. |
| **Mounted** | App.jsx activeTab === 'action_engine' → ActionEngineView. |

**Proof that visible UI reflects new changes:** ActionEngineView uses COHORT_RATIONALE, getDecisionContextLabel, getBehaviorDirection(d), getPersistenceLabel(d) and SEMANTIC_ALERT_COLORS for drilldown. Data for persistence/behavior direction comes from cohort_detail API (weeks_declining_consecutively, weeks_rising_consecutively).

---

## Legacy paths NOT used

- Visible Behavioral Alerts table and detail use getBehaviorAlertsDrivers and getBehaviorAlertsDriverDetail only (/ops/behavior-alerts/*).
- Visible Action Engine uses getActionEngine* only (/ops/action-engine/*).
- No /controltower/* or other legacy endpoint powers the explainability fields. New semantics are computed in the frontend from the new/expanded API response fields.

---

## Backend route used

- GET /ops/behavior-alerts/drivers (returns weeks_declining_consecutively, weeks_rising_consecutively).
- GET /ops/behavior-alerts/driver-detail (returns weeks_rising_consecutively).
- GET /ops/action-engine/cohort-detail (returns weeks_declining_consecutively, weeks_rising_consecutively, active_weeks_in_window).

## Frontend service function used

- getBehaviorAlertsDrivers, getBehaviorAlertsDriverDetail.
- getActionEngineCohorts, getActionEngineCohortDetail, getActionEngineRecommendations.

## Component path used

- frontend/src/components/BehavioralAlertsView.jsx.
- frontend/src/components/ActionEngineView.jsx.
- frontend/src/constants/explainabilitySemantics.js (shared).
