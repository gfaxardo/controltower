# Behavioral Alerts — Fix Log (Technical Closure)

**Date:** 2026-03-11  
**Context:** End-to-end closure; migrations 084/085 required fixes to apply successfully.

---

## Fix 1: Migration 085 — Wrong table alias in risk_components CTE

**Issue:** `alembic upgrade head` failed with:
`missing FROM-clause entry for table "b"` at `CASE b.segment_current`.

**Root cause:** In migration 085, the constants `_SEG_ORD` and `_PREV_ORD` used alias `b` (from `base b`), but they are embedded in the `risk_components` CTE which selects `FROM classified c`. So `b` is not in scope there.

**Fix:** In `backend/alembic/versions/085_behavior_alerts_risk_score.py`, change `_SEG_ORD` and `_PREV_ORD` to use alias `c`:
- `CASE b.segment_current` → `CASE c.segment_current`
- `CASE b.segment_previous` → `CASE c.segment_previous`

**Files changed:** `backend/alembic/versions/085_behavior_alerts_risk_score.py`

---

## Fix 2: Migration 085 — CREATE OR REPLACE VIEW column order

**Issue:** After Fix 1, upgrade failed with:
`cannot change name of view column "avg_trips_baseline" to "segment_previous"`.

**Root cause:** In PostgreSQL, `CREATE OR REPLACE VIEW` does not allow changing the order or names of existing columns; the new SELECT is matched by position. The view from 082 had columns (..., segment_current, avg_trips_baseline, ...). The new definition inserted segment_previous and movement_type after segment_current, so the 11th column became segment_previous instead of avg_trips_baseline, which PostgreSQL rejects.

**Fix:** In 085 upgrade, do not use CREATE OR REPLACE. Instead:
1. Keep `DROP MATERIALIZED VIEW IF EXISTS ops.mv_driver_behavior_alerts_weekly CASCADE`.
2. Add `DROP VIEW IF EXISTS ops.v_driver_behavior_alerts_weekly CASCADE`.
3. Use `CREATE VIEW ops.v_driver_behavior_alerts_weekly AS` (not CREATE OR REPLACE).

**Files changed:** `backend/alembic/versions/085_behavior_alerts_risk_score.py`

---

## Summary

- **Fix 1:** Alias `b` → `c` in segment ordering expressions used in risk_components.
- **Fix 2:** DROP VIEW + CREATE VIEW in 085 so the new view can define all columns (including segment_previous, movement_type, risk_*) without position constraints.

After these fixes, run `alembic upgrade head` and wait for it to complete (083 and 085 create/refresh the materialized view, which can take several minutes on large data).
