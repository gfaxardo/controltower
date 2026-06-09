# OV2-F.6B — RAW TO MV RECONCILIATION

> **Date:** 2026-06-08
> **Status:** AUDIT COMPLETE — MV ACCURATE

## RAW ORDERS (2026-06-06, park=08e20910...)

| Metric | Value |
|--------|-------|
| Total raw rows | 1,000 |
| `order_status='complete'` | 1,000 |
| `order_status='cancelled'` | 0 |
| Distinct driver_profile_id | 468 |

## MV ORDERS DAY

| Metric | Value |
|--------|-------|
| Rows | 1 |
| orders_total | 1,000 |
| orders_completed | 1,000 |
| orders_cancelled | 0 |
| unique_drivers | 468 |

## RECONCILIATION

| Metric | Raw | MV | Match |
|--------|-----|-----|-------|
| Completed orders | 1,000 | 1,000 | ✅ |
| Unique drivers | 468 | 468 | ✅ |

## VERDICT

**MV ACCURATE** — `raw_yango.mv_orders_day` correctly aggregates from `raw_yango.orders_raw`. No data loss in the MV layer. The gap is upstream (ingestion volume), not in MV processing.

---

*End of Raw-to-MV Reconciliation*
