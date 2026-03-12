# Behavioral Alerts — Migration Report

**Date:** 2026-03-11  
**Phase:** 2 — Apply migrations if needed

---

## Commands run

1. `alembic current` → `080_mv_driver_segment_migrations_weekly_optional`
2. `alembic heads` → `085_behavior_alerts_risk_score (head)`
3. `alembic upgrade head` (multiple attempts)

---

## First attempt

- **Result:** Failure at 085.
- **Error:** `missing FROM-clause entry for table "b"` at `CASE b.segment_current` in risk_components CTE.
- **Classification:** Schema/code bug in migration 085 (wrong alias).

---

## Fix 1 applied (see behavioral_alerts_fix_log.md)

- In 085, `_SEG_ORD` and `_PREV_ORD` used alias `b`; in risk_components the alias is `c`. Changed to `c.segment_current` and `c.segment_previous`.

---

## Second attempt

- **Result:** Failure at 085.
- **Error:** `cannot change name of view column "avg_trips_baseline" to "segment_previous"`.
- **Classification:** PostgreSQL CREATE OR REPLACE VIEW does not allow changing column order/names; new columns were inserted in the middle.

---

## Fix 2 applied (see behavioral_alerts_fix_log.md)

- In 085 upgrade: add `DROP VIEW IF EXISTS ops.v_driver_behavior_alerts_weekly CASCADE` after dropping the MV; use `CREATE VIEW` instead of `CREATE OR REPLACE VIEW`.

---

## Third attempt

- **Command:** `alembic upgrade head`
- **Output:** 081, 082, 083, 084, and start of 085 ran. Process was backgrounded and hit timeout (180s) while 085 was executing (likely during creation of `mv_driver_behavior_alerts_weekly` and indexes).
- **DB state after timeout:** Transaction may have rolled back; `alembic current` still reports **080**.

---

## Required user action

**Migrations are not yet confirmed at head.**

1. Run in backend directory:
   ```bash
   alembic upgrade head
   ```
2. Wait for completion (083 and 085 create/refresh the materialized view; can take several minutes depending on data volume).
3. Confirm:
   ```bash
   alembic current
   ```
   Expected: `085_behavior_alerts_risk_score`.

If 085 fails again, check the exact error and ensure no other view/object still references the old view definition.

---

## Success criteria (to be confirmed by user)

- [ ] `alembic upgrade head` completes without error.
- [ ] `alembic current` shows `085_behavior_alerts_risk_score`.
