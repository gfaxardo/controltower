# OV2-F.2D — FAIL FAST + CLOSED PERIOD RULES

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Refresh Chain
> **Status:** RULES DEFINED

---

## ERROR CODES

| Code | Condition | Severity | Remediation |
|------|-----------|----------|-------------|
| `DRIVER_BRIDGE_STALE` | Bridge max date > D-3 | WARNING | Run `build_driver_day_slice_fact` for missing days |
| `DRIVER_BRIDGE_EMPTY` | 0 rows in bridge for country/city | CRITICAL | Run initial backfill |
| `DRIVER_BRIDGE_MISMATCH` | Bridge trips != day_fact trips > 1% | CRITICAL | Audit bridge vs day_fact |
| `WEEK_FACT_REQUIRES_BRIDGE` | week rebuilt without bridge (active_drivers=0) | BLOCKED | Build bridge first |
| `ACTIVE_DRIVERS_UPPER_BOUND` | active_drivers from SUM(day_fact), not bridge | WARNING | Rebuild with bridge |
| `EMPTY_SUPPLY_AVAILABLE` | empty_supply_drivers column populated | INFO | New KPI available |
| `CLOSED_PERIOD_IMMUTABLE` | Refresh attempted on date < D-1 without --allow-backfill | BLOCKED | Use --allow-backfill flag |
| `BACKFILL_REQUIRED` | date range spans > 7 days without --confirm | WARNING | Confirm backfill intent |

## CLOSED PERIOD ENFORCEMENT

- `activity_date < today - 1` → IMMUTABLE (no overwrite without `--allow-backfill`)
- Daily incremental: only inserts rows for `activity_date >= today - 1`
- Backfill: explicit `--allow-backfill` flag required for historical dates

---

*End of Fail-Fast Rules*
