# Action Engine Explainability — Fix Log (Phase 16)

**Project:** YEGO Control Tower  
**Date:** 2026-03-11

---

## Fix 1: Migration 088 — view column list change

- **Issue:** PostgreSQL does not allow CREATE OR REPLACE VIEW to change the number or order of columns (error: "cannot change name of view column cohort_type to weeks_rising_consecutively").
- **Root cause:** Adding weeks_rising_consecutively between weeks_declining_consecutively and cohort_type changed the view’s column list.
- **Fix:** In 088_action_engine_driver_base_weeks_rising.py: DROP VIEW IF EXISTS ops.v_action_engine_driver_base CASCADE; then CREATE VIEW with the new SELECT including weeks_rising_consecutively. Recreate dependent views v_action_engine_cohorts_weekly and v_action_engine_recommendations_weekly after creating driver_base.
- **Files changed:** backend/alembic/versions/088_action_engine_driver_base_weeks_rising.py.
- **Why required:** Without it, upgrade 088 failed and the view would not expose weeks_rising_consecutively for persistence labels in the UI.

---

## Other changes (additive, no fix log entry)

- Backend: behavior_alerts_service and action_engine_service expanded SELECTs to include persistence columns (no breaking change).
- Frontend: New explainabilitySemantics.js; BehavioralAlertsView and ActionEngineView updated to show estado conductual, persistence, time context, rationale, and semantic colors. No legacy path or component replaced.
