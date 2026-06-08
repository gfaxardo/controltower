# OV2-D.3A — DRILL PERFORMANCE GUARD

> **Date:** 2026-06-08
> **Status:** IMPLEMENTED

## GUARDS

| Guard | Value | Rationale |
|-------|-------|-----------|
| Driver limit | 20 (configurable 1-100) | Prevents large responses |
| Park limit | None (few parks) | Max 5-10 per city |
| No raw scans | Bridge only | 162K rows vs 6.8M |
| Response timeout | <500ms | Fast fail |
| No blocking matrix | Independent endpoint | Inspector ajax, matrix unaffected |

## SOURCE

- `ops.driver_day_slice_fact` — pre-aggregated driver×day×slice
- No JOINs to trips_2026
- No resolved views
- Single query per park breakdown + single query for driver list

---

*End of Performance Guard*
