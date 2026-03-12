# Behavioral Alerts — Precheck / Inventory

**Date:** 2026-03-11  
**Purpose:** Initial state before end-to-end technical closure.

---

## 1. Git status

- **Branch:** master (tracking origin/master)
- **Modified (M):** backend/alembic/versions/070_*, connection.py, main.py, ops.py, data_freshness_service, real_lob_drill_pro_service, supply_definitions, supply_service; frontend App.jsx, api.js, several components; docs.
- **Untracked (??):** Migrations 074–085 (including 081–085 Behavioral Alerts), backend/app/routers/controltower.py, backend/app/services/behavior_alerts_service.py, frontend BehavioralAlertsView.jsx, docs (behavioral_alerts_*, etc.).

---

## 2. Alembic state

| Check | Result |
|-------|--------|
| **alembic current** | `080_mv_driver_segment_migrations_weekly_optional` |
| **alembic heads** | `085_behavior_alerts_risk_score (head)` |
| **DB behind head?** | **Yes.** Pending: 081 → 082 → 083 → 084 → 085 |

---

## 3. Behavioral Alerts migrations

| Revision | File | Purpose |
|----------|------|---------|
| 081 | 081_driver_behavior_baseline_weekly_view.py | Creates ops.v_driver_behavior_baseline_weekly |
| 082 | 082_driver_behavior_alerts_weekly_view.py | Creates ops.v_driver_behavior_alerts_weekly |
| 083 | 083_mv_driver_behavior_alerts_weekly_optional.py | Creates ops.mv_driver_behavior_alerts_weekly + ops.refresh_driver_behavior_alerts() |
| 084 | 084_behavior_baseline_segment_movement.py | Replaces baseline view: adds segment_previous, movement_type (at end of columns) |
| 085 | 085_behavior_alerts_risk_score.py | Replaces alerts view: risk_score, risk_band, components; recreates MV + risk_band index |

All five migration files exist in backend/alembic/versions/.

---

## 4. Backend routes

| Route | Router | File |
|-------|--------|------|
| GET /ops/behavior-alerts/summary | ops | backend/app/routers/ops.py |
| GET /ops/behavior-alerts/insight | ops | backend/app/routers/ops.py |
| GET /ops/behavior-alerts/drivers | ops | backend/app/routers/ops.py |
| GET /ops/behavior-alerts/driver-detail | ops | backend/app/routers/ops.py |
| GET /ops/behavior-alerts/export | ops | backend/app/routers/ops.py |
| GET /controltower/behavior-alerts/summary | controltower | backend/app/routers/controltower.py |
| GET /controltower/behavior-alerts/insight | controltower | backend/app/routers/controltower.py |
| GET /controltower/behavior-alerts/drivers | controltower | backend/app/routers/controltower.py |
| GET /controltower/behavior-alerts/driver-detail | controltower | backend/app/routers/controltower.py |
| GET /controltower/behavior-alerts/export | controltower | backend/app/routers/controltower.py |

- **Service:** backend/app/services/behavior_alerts_service.py  
- **Source:** `_ALERTS_SOURCE = "ops.v_driver_behavior_alerts_weekly"` (view; MV exists as optional materialization).
- **main.py:** includes both ops.router and controltower.router.

---

## 5. Frontend

| Item | Location |
|------|----------|
| **Tab** | "Behavioral Alerts" button in nav; activeTab === 'behavioral_alerts' |
| **Component** | frontend/src/components/BehavioralAlertsView.jsx (default export) |
| **Mount** | App.jsx: `{activeTab === 'behavioral_alerts' && <BehavioralAlertsView key={...} />}` |
| **API usage** | frontend/src/services/api.js: getBehaviorAlertsSummary, getBehaviorAlertsInsight, getBehaviorAlertsDrivers, getBehaviorAlertsDriverDetail, getBehaviorAlertsExportUrl |
| **Base path** | All calls use `/ops/behavior-alerts/...` (not /controltower) |

No duplicate or legacy Behavioral Alerts component/tab found. No stale path shadowing the new one.

---

## 6. SQL objects (from migrations)

| Object | Type | Created in |
|--------|------|------------|
| ops.v_driver_behavior_baseline_weekly | VIEW | 081; replaced 084 (segment_previous, movement_type appended) |
| ops.v_driver_behavior_alerts_weekly | VIEW | 082; replaced 085 (risk_score, risk_band, components) |
| ops.mv_driver_behavior_alerts_weekly | MATERIALIZED VIEW | 083; dropped/recreated in 085 |
| ops.refresh_driver_behavior_alerts() | FUNCTION | 083 |

---

## 7. Unresolved gaps

1. **Migrations not applied:** DB at 080; 081–085 must be applied (Phase 2).
2. **Refresh:** After migrations, MV refresh may be needed (Phase 3).
3. **Live API/UI:** Not yet validated in running environment (Phases 4–8).

---

## 8. Summary

- **Files found:** All Behavioral Alerts migrations (081–085), service, ops + controltower routes, BehavioralAlertsView, api.js helpers, App.jsx tab and mount.
- **Migration revisions:** 081, 082, 083, 084, 085 present; current DB at 080.
- **Routes:** /ops/behavior-alerts/* and /controltower/behavior-alerts/* implemented.
- **Frontend:** Single component, single tab, wired to /ops/behavior-alerts/*.
- **Next:** Apply migrations (Phase 2), then refresh, API validation, UI wiring verification, and UI/render/filter/export validation.
