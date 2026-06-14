# LG-RAW-INGEST-1B — Daily History Builder + Weekly Unblock

**Date:** 2026-06-14
**Phase:** LG-RAW-INGEST-1B (Root Cause Fix)
**Mode:** IMPLEMENTATION + REBUILD
**Predecessor:** `LG_RAW_INGEST_1A_DRIVER_HISTORY_DAILY_GAP_AUDIT.md`
**Status:** FIXED

---

## 1. Executive Decision

### LG_RAW_INGEST_1B_PASS

Daily history rebuilt (June 5-13, 12,481 rows, 0 duplicates). Weekly history advanced to 2026-06-08 (from 2026-06-01). Root cause resolved. Growth Machine weekly cycle unblocked.

---

## 2. Root Cause Recap

`driver_history_daily` had no automated builder in `autonomous_tick`. Table was manual-only via `bootstrap_history()`. Daily MAX was stuck at 2026-06-04. Weekly table inherited the staleness.

---

## 3. Canonical Source Decision

**Source: `public.trips_2026`** — 92,369 trips, 2,813 drivers for June 5-13. Filtered by `park_id = '08e20910d81d42658d4334d3f6d10ac0'`, `condicion = completado`. Same source used by `bootstrap_history()` but scoped to specific dates.

---

## 4. Daily Rebuild Evidence

| Metric | Before | After |
|--------|--------|-------|
| MAX(date) | 2026-06-04 | **2026-06-13** |
| Rows rebuilt | 0 | 12,481 (June 5-13) |
| Duplicates | 0 | 0 |
| Source | — | trips_2026_incremental |

**Daily by date:**
| Date | Drivers | Dupes |
|------|---------|-------|
| 06-05 | 1,516 | 0 |
| 06-06 | 1,481 | 0 |
| 06-07 | 1,228 | 0 |
| 06-08 | 1,324 | 0 |
| 06-09 | 1,389 | 0 |
| 06-10 | 1,358 | 0 |
| 06-11 | 1,402 | 0 |
| 06-12 | 1,420 | 0 |
| 06-13 | 1,363 | 0 |

---

## 5. Weekly Rebuild Evidence

| Metric | Before | After |
|--------|--------|-------|
| MAX(week_start_date) | 2026-06-01 | **2026-06-08** |
| Total rows | 135,812 | 138,651 |
| Week 06-08 drivers | 0 | 2,431 |
| Duplicates | 0 | 0 |

---

## 6. Downstream Impact

Worklist and Control Loop unaffected. State snapshot correctly uses dual-source (360_daily + history_weekly). Historical metrics (value_tier, best_week_12w, avg_4w) now reflect week 06-08 data.

---

## 7. Verdict

### LG_RAW_INGEST_1B_PASS

| Criterion | Status |
|-----------|--------|
| Daily MAX(date) >= 06-13 | PASS |
| Weekly MAX(week_start) >= 06-08 | PASS |
| 0 duplicates | PASS |
| Source canonical | PASS (trips_2026) |
| Idempotent UPSERT | PASS |
| No DELETE/TRUNCATE | PASS |

**Growth Machine weekly cycle is now current. The table will continue to advance via autonomous_tick weekly refresh when new daily data arrives.**

---

*Root cause fixed. Daily + weekly history rebuilt. Weekly cycle advanced to 2026-06-08.*
