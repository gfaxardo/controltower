# Behavioral Alerts — GO / NO-GO Decision Report

**Date:** 2026-03-11  
**Phase:** 11 — Final decision report

---

## What is ready

- **Codebase:** Migrations 081–085 exist; 084 and 085 fixed (084: column order for CREATE OR REPLACE; 085: alias c in risk_components, DROP VIEW + CREATE VIEW). Backend service and ops/controltower routes implement summary, insight, drivers, driver-detail, export with filters (including movement_type, risk_band) and new fields (risk_score, risk_band, high_risk_drivers, medium_risk_drivers, risk_reasons). Frontend: BehavioralAlertsView with filters, KPIs, table (Risk Score, Risk Band), drilldown "Por qué se destaca", help panel, export; wired to /ops/behavior-alerts/*; tab mounted in App.jsx.
- **Documentation:** Precheck, migration report, refresh report, API validation, UI wiring, UI render checklist, filter checklist, export checklist, fix log, final QA, and this go/no-go report.

---

## What is not ready

- **Database:** Migrations were not confirmed at head. DB remained at 080 after a timed-out run of `alembic upgrade head` (085 was executing when the process was stopped). The view `ops.v_driver_behavior_alerts_weekly` and the optional MV do not exist until 085 completes successfully.
- **Live validation:** Backend routes were not called (would 500 without the view). UI render, filters, and export were not exercised in a browser.

---

## What the user must do next

1. **Apply migrations (mandatory)**  
   From the backend directory run:
   ```bash
   alembic upgrade head
   ```
   Wait until it finishes (083 and 085 create/refresh the materialized view; may take several minutes). Then run:
   ```bash
   alembic current
   ```
   Expected: `085_behavior_alerts_risk_score`.

2. **Optional: refresh MV after upstream data refresh**  
   If you refresh supply/lifecycle MVs, then run:
   ```sql
   SELECT ops.refresh_driver_behavior_alerts();
   ```

3. **Validate backend**  
   Start backend (`uvicorn app.main:app --reload`), then call:
   - `GET /ops/behavior-alerts/summary?from=2025-01-01&to=2025-03-01`
   - `GET /ops/behavior-alerts/drivers?from=2025-01-01&to=2025-03-01&limit=5`
   Confirm 200 and presence of risk_score, risk_band, high_risk_drivers, medium_risk_drivers (see docs/behavioral_alerts_api_validation.md).

4. **Validate UI**  
   Start frontend (`npm run dev`), open the app, go to **Behavioral Alerts**, and confirm: tab visible, KPIs and table load, Risk Score/Risk Band columns, drilldown "Por qué se destaca", help panel, export (see docs/behavioral_alerts_ui_render_validation.md, behavioral_alerts_filter_validation.md, behavioral_alerts_export_validation.md).

---

## Exact commands (manual, only if still needed)

```bash
# Backend directory
cd "c:\Users\Pc\Documents\Cursor Proyectos\YEGO CONTROL TOWER\backend"
alembic upgrade head
alembic current
# If 085 shown:
uvicorn app.main:app --reload
```

```bash
# Frontend directory (separate terminal)
cd "c:\Users\Pc\Documents\Cursor Proyectos\YEGO CONTROL TOWER\frontend"
npm run dev
```

---

## Final decision

**NO-GO** until migrations are at 085 and the user confirms the feature in the running environment.

After the user runs `alembic upgrade head` successfully and confirms:
- backend returns 200 with expected fields for summary/drivers/driver-detail/export,
- UI tab is visible and shows data, KPIs, table with Risk Score/Risk Band, drilldown, and export,

then the status becomes **GO** (or **GO WITH OBSERVATIONS** if minor non-blocking issues remain).

---

## Summary

| Criterion | Status |
|-----------|--------|
| Feature wired (DB → backend → route → frontend → tab) | Yes |
| Migrations applied at head (085) | No — user must run and wait |
| Backend routes live-validated | No |
| UI visible and data-bound | Not verified (blocked by DB) |
| Export and filters documented | Yes; user to verify |

**Conclusion:** Implementation and wiring are complete; two migration fixes were applied. **Unblock by running `alembic upgrade head` and completing the validation steps above** to move to GO.
