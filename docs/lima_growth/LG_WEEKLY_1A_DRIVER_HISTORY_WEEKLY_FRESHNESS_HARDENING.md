# LG-WEEKLY-1A — Driver History Weekly Freshness Hardening

**Date:** 2026-06-14
**Phase:** LG-WEEKLY-1A (Weekly Freshness Hardening)
**Mode:** AUDIT + VERIFICATION
**Predecessor:** `LG_TRACE_1C_TRANSITION_FACT_FRESHNESS_HARDENING.md`
**Status:** CONDITIONAL — Root cause dependency documented

---

## 1. Executive Decision

### LG_WEEKLY_1A_CONDITIONAL

The `growth.yango_lima_driver_history_weekly` table is **as fresh as its upstream source allows.** MAX(week_start_date)=2026-06-01 corresponds to the last complete week with daily data (driver_history_daily MAX=2026-06-04). The weekly refresh mechanism, governance, and autonomous tick integration are all correctly configured. The table will auto-advance to week 2026-06-08 when new daily data arrives.

**Growth Machine remains NOT CLOSED until weekly cycle advances to 2026-06-08 or later.**

---

## 2. Why This Blocks Growth Machine Closure

`driver_history_weekly` feeds `driver_state_snapshot` which feeds the entire downstream pipeline (eligibility, opportunity, worklist, Control Loop). While the worklist operates on `driver_360_daily` + `driver_state_snapshot` daily data, the historical metrics (best_week_12w, avg_4w, historical_band, value_tier) are sourced from the weekly table. Stale weekly data means degraded historical classification.

---

## 3. Current Weekly State

| Metric | Value |
|--------|-------|
| MAX(week_start_date) | 2026-06-01 |
| Expected closed week | 2026-06-08 |
| Total rows | 135,812 |
| Recent weeks | 67 weeks from 2025-02-24 to 2026-06-01 |
| Duplicate driver/week | 0 |
| Canonical writer | `_build_weekly_sql_bulk()` (1 writer) |
| Source | trips_bootstrap (reads driver_history_daily) |
| MAX(driver_history_daily.date) | 2026-06-04 (9 days stale) |

**Root cause of staleness:** `driver_history_daily` has no new data after 2026-06-04. The weekly table correctly represents the latest available daily data.

---

## 4. Canonical Writer Audit

| Aspect | Finding |
|--------|---------|
| Writer | `_build_weekly_sql_bulk()` in `yego_lima_growth_history_service.py:192` |
| Operation | UPSERT (ON CONFLICT DO UPDATE) |
| Idempotent | Yes |
| Sources | `growth.yango_lima_driver_history_daily` |
| Lock | Tick-level advisory lock (autonomous_tick serializes) |
| Scheduler | `autonomous_tick` via `refresh_weekly_history()` (FH-1) |
| Threshold | Fixed in GM-F1A: `latest_complete_monday` (was `-7 days`) |
| Parallel writers | None (1 canonical, dead code `upsert_history_weekly` never called) |
| Legacy risks | `bootstrap_history()` manual — not needed for weekly refresh |

---

## 5. Refresh Execution

Forced `_build_weekly_sql_bulk()` confirmed:
- 135,812 rows rebuilt (same as before — UPSERT idempotent)
- MAX(week_start_date) unchanged at 2026-06-01
- No new weeks added (daily data hasn't advanced past 06-04)
- 0 duplicate driver/week rows

---

## 6. Freshness Governance

| Layer | Status |
|-------|--------|
| Chain | Registered (layer 3: `history_weekly`) |
| Registry | Registered (component `driver_history_weekly`) |
| Audit | Registered (asset `driver_history_weekly`, SLA 336h/14d) |
| Health | Registered |
| Status post-rebuild | As expected (within 336h SLA from June 1) |

---

## 7. Scheduler / Autonomous Tick

`refresh_weekly_history()` is integrated in `autonomous_tick` (GM-F1A). It runs before cascade when `cascade_required`. FH-1 threshold correctly uses `latest_complete_monday`. The NOOP guard prevents unnecessary rebuilds. When daily data becomes available, the weekly table will auto-advance.

---

## 8. Verdict

### LG_WEEKLY_1A_CONDITIONAL

| Criterion | Status |
|-----------|--------|
| Writer canonical | PASS |
| 0 duplicate driver/week | PASS |
| Freshness governance (3 layers) | PASS |
| Autonomous tick integrated | PASS |
| FH-1 threshold correct | PASS |
| Refresh idempotent verified | PASS |
| Weekly table advanced to 06-08 | **PENDING** (blocked by daily data staleness) |

**Condition:** Weekly table will auto-advance when `driver_history_daily` receives new data (requires raw orders ingestion to resume producing data after 2026-06-04).

**Growth Machine is NOT CLOSED.** Daily operations are unaffected (worklist uses `driver_360_daily` + `driver_state_snapshot`). Historical metrics (value_tier, best_week) are slightly degraded but do not break operational classification.

---

*Weekly hardening verified. Mechanism correct. Awaiting upstream daily data to advance week.*
