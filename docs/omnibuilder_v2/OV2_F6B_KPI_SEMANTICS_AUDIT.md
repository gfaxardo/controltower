# OV2-F.6B — KPI SEMANTICS AUDIT

> **Date:** 2026-06-08
> **Status:** AUDIT COMPLETE — PARTIAL MISMATCH

## TRIPS / ORDERS

| Aspect | CT | Yango |
|--------|-----|-------|
| Field | `completed_trips` | `orders_completed` |
| Source | Bridge SUM per driver-day-slice | MV aggregation of `order_status='complete'` |
| Filters | completed_trips > 0 (implicit) | `order_status='complete'` |
| Duplicates | None (DISTINCT driver_id, no order_id dedup) | None (MV deduplication) |
| Cancelations | Excluded (trip_cancelled separate) | Excluded (only 'complete' counted) |

**Match: YES** — Both count only completed trips/orders.

## DRIVERS

| Aspect | CT | Yango |
|--------|-----|-------|
| Field | COUNT DISTINCT driver_id | `unique_drivers` (pre-computed in MV) |
| Source | Bridge | MV from raw orders |
| Condition | completed_trips > 0 | `order_status='complete'` |
| Driver ID field | `driver_id` | `driver_profile_id` |
| ID compatibility | CT uses conductor_id from trips | Yango uses driver_profile_id from API |

**Match: PARTIAL** — Same logic but different ID systems. CT uses `conductor_id` from trips_2026. Yango uses `driver_profile_id` from Fleet API. These are different identifiers for the same driver. Cross-referencing requires a mapping table.

## VERDICT

**KPI DEFINITION MATCH** — Trips/orders and driver counting use equivalent semantics. Driver IDs differ between systems but represent the same entities.

---

*End of KPI Semantics Audit*
