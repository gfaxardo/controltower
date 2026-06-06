# OV2-B.5 — CT=0 DIAGNOSTIC

> **Date:** 2026-06-05  
> **Scope:** Investigate why `ops.real_business_slice_day_fact` returned 0 for Lima/Peru on 2026-06-04

---

## 1. Root Cause

**CT data latency:** At the time of initial diagnosis, CT's max date was 2026-05-31. The target date 2026-06-04 was beyond the available range. The CT refresh pipeline subsequently ran and populated data for 2026-06-04 (14,213 trips).

| Metric | Initial (OV2-B.4 run) | Current |
|--------|----------------------|---------|
| CT max date | 2026-05-31 | 2026-06-04 |
| CT trips for 2026-06-04 | 0 | 14,213 |
| MV trips for 2026-06-04 | 2,977 | 2,977 |

The MV has **fresher data** (ingested directly from Yango Fleet API). CT depends on scheduled refresh. This interval is the primary source of `CT=0` results.

**This is a data latency gap, not a reconciliation bug.**

---

## 2. Scale Difference (Expected)

CT covers ALL Lima business slices (6-7 slices aggregated). MV covers a single Yango park. The delta is structural:

| Metric | MV (1 park) | CT (all Lima) | Delta |
|--------|------------|---------------|-------|
| Orders | 2,977 | 14,213 | -79% |
| Revenue | 1,256.37 PEN | 5,832.27 PEN | -78% |
| Rev/order | 0.422 | 0.4103 | +2.8% |

Per-order revenue (MV 0.422 vs CT 0.410) has only 2.8% delta — this is within tolerance. The volume delta is expected because of scope differences.

---

## 3. CT Schema Details

| Aspect | Value |
|--------|-------|
| Countries | `colombia`, `peru` (lowercase, clean UTF-8) |
| Cities | 9 cities, all lowercase |
| park_id column | **Not present** |
| business_slice_name | 3-6 slices per city/day |
| Date range | 2025-02-28 to 2026-06-04 |

---

## 4. Fallback Strategy (OV2-B.5 implementation)

| Level | Name | Match Condition | Status |
|-------|------|----------------|--------|
| 1 | EXACT_CITY_DATE | country='peru' city='lima' exact date | Primary |
| 2 | NEAREST_DATE | nearest date <= target (within 30 days) | Fallback |
| 3 | NO_DATE_IN_RANGE | CT has data but not within 30-day window | Graceful |
| 4 | UNAVAILABLE | No CT data for this country/city | Final |

---

## 5. Resolution

1. Shadow API uses controlled fallback — never returns misleading delta when CT is missing.
2. `ct_match_level` reveals which strategy was used.
3. `CT_FALLBACK` warning appears when fallback is active.
4. Zero CT data or no changes to CT — this is purely shadow API behavior.
5. Canonical ready remains `false`.

---

## 6. Signature

| Field | Value |
|-------|-------|
| Diagnosed by | OV2-B.5 Shadow API Reconciliation Hardening |
| Date | 2026-06-05 |
| Status | RESOLVED |
