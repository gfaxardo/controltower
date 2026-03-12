# Behavioral Alerts — UI Wiring Report

**Date:** 2026-03-11  
**Phase:** 5 — Frontend service wiring (mandatory)

---

## End-to-end path

```
DB/MV/View  →  backend service  →  route  →  frontend service  →  mounted component  →  visible tab
```

| Layer | Implementation |
|-------|----------------|
| **DB/View** | ops.v_driver_behavior_baseline_weekly (081, 084), ops.v_driver_behavior_alerts_weekly (082, 085). Optional: ops.mv_driver_behavior_alerts_weekly. |
| **Backend service** | app.services.behavior_alerts_service: get_behavior_alerts_summary, get_behavior_alerts_drivers, get_behavior_alerts_driver_detail, get_behavior_alerts_export, get_behavior_alerts_insight. Source: ops.v_driver_behavior_alerts_weekly. |
| **Route** | GET /ops/behavior-alerts/summary, /insight, /drivers, /driver-detail, /export (backend/app/routers/ops.py). Same under /controltower (backend/app/routers/controltower.py). |
| **Frontend service** | frontend/src/services/api.js: getBehaviorAlertsSummary, getBehaviorAlertsInsight, getBehaviorAlertsDrivers, getBehaviorAlertsDriverDetail, getBehaviorAlertsExportUrl. Base path: **/ops/behavior-alerts/** (not /controltower). |
| **Component** | frontend/src/components/BehavioralAlertsView.jsx (default export). Uses the five API helpers above. |
| **Tab registration** | frontend/src/App.jsx: nav button "Behavioral Alerts" sets activeTab to 'behavioral_alerts'; conditional render `{activeTab === 'behavioral_alerts' && <BehavioralAlertsView key={...} />}`. |

---

## File and symbol summary

| Role | File | Symbol / detail |
|------|------|------------------|
| API base | frontend/src/services/api.js | api (axios instance), base URL from env |
| Summary | frontend/src/services/api.js | getBehaviorAlertsSummary → GET /ops/behavior-alerts/summary |
| Insight | frontend/src/services/api.js | getBehaviorAlertsInsight → GET /ops/behavior-alerts/insight |
| Drivers list | frontend/src/services/api.js | getBehaviorAlertsDrivers → GET /ops/behavior-alerts/drivers |
| Driver detail | frontend/src/services/api.js | getBehaviorAlertsDriverDetail → GET /ops/behavior-alerts/driver-detail |
| Export URL | frontend/src/services/api.js | getBehaviorAlertsExportUrl → builds /ops/behavior-alerts/export?… |
| View component | frontend/src/components/BehavioralAlertsView.jsx | BehavioralAlertsView (default) |
| Tab mount | frontend/src/App.jsx | import BehavioralAlertsView; button "Behavioral Alerts" → setActiveTab('behavioral_alerts'); render when activeTab === 'behavioral_alerts' |

---

## Legacy / duplicate paths

- **No legacy Behavioral Alerts endpoints** — Only /ops/behavior-alerts/* and /controltower/behavior-alerts/* exist; no old path still used.
- **Frontend uses /ops only** — getBehaviorAlerts* and getBehaviorAlertsExportUrl point to /ops/behavior-alerts/*. /controltower is available but not used by the UI; both hit the same service.
- **No duplicate component** — Single BehavioralAlertsView; no other component implements the same tab.
- **No stale path shadowing** — No evidence of an archaic URL or component taking precedence over the new one.

---

## Conclusion

- **DB → backend → route → frontend service → mounted component → visible tab** is wired and consistent.
- The visible "Behavioral Alerts" tab is driven by BehavioralAlertsView.jsx and the /ops/behavior-alerts/* API only.
- Legacy endpoints or components are not powering this tab.
