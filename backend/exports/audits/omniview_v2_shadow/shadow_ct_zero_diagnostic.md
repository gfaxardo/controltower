# Omniview V2 Shadow — CT Zero Diagnostic

**Generated:** 2026-06-05T16:22:40.116481-05:00

## Root Cause

The initial reconciliation (OV2-B.4) returned `CT=0` for `country='peru' city='lima' date=2026-06-04`.
Investigation revealed:

- CT table `ops.real_business_slice_day_fact` **has data** for Lima/Peru.
- CT date range: **2025-02-28** to **2026-06-04**.
- The requested target date is **outside** this range.
- CT has not been refreshed for dates after `ct_max`.
- MV `raw_yango.mv_orders_day` has fresher data (ingested from Yango API).
- This is a **data latency gap**, not a reconciliation bug.

## Reconciliation Context

| Field | Value |
|-------|-------|
| MV orders | 2,977 |
| MV revenue | 1,256.37 |
| CT trips | 14,213 |
| CT revenue | 5,832.27 |
| CT match level | EXACT_CITY_DATE |
| CT data date used | 2026-06-04 |
| CT filter | country='peru' city='lima' date=2026-06-04 |
| Status | MAJOR_DELTA |
| Basis | CITY_DATE |


## Resolution

1. The shadow reconciliation now uses a **controlled fallback strategy**:
   - Level 1: Exact match by country/city/date
   - Level 2: Nearest available date <= target (within 30 days)
   - Level 3: Mark as UNAVAILABLE if no data exists
2. The `ct_match_level` field reveals which strategy was used.
3. When fallback is used, a `CT_FALLBACK` warning appears in the response.
4. This is **shadow mode only** — no CT data is modified.