# Growth API vs Control Tower — Reconciliation

**Generated:** 2026-06-04T23:24:54.537842-05:00
**Date Range:** 2026-06-01 → 2026-06-04
**Park ID (masked):** 08e20910***
**CT Country/City:** peru / lima

## 1. Summary Comparison

| Metric | Growth API | Control Tower | Delta | Delta % |
|--------|-----------|---------------|-------|---------|
| Trips Completed | 0 | 39,176 | -39,176 | -100.0% |
| Active Drivers | 0 | 5,002 | -5,002 | -100.0% |
| Revenue | 0 | 16,151.06 | -16,151 | -100.0% |

- Days with data (API): 0
- Days with data (CT): 3

## 2. CT Slices Found

| Slice | Trips | Drivers | Revenue |
|-------|-------|---------|---------|
| Auto regular | 31,469 | 4,476 | 14,233.27 |
| Tuk Tuk | 3,692 | 157 | 417.66 |
| YMA | 1,779 | 123 | 702.18 |
| PRO | 1,257 | 66 | 367.53 |
| Delivery | 923 | 146 | 287.68 |
| Carga | 56 | 34 | 142.75 |

## 3. Notes & Caveats

- CT filter: country=peru, city=lima, slice=all
- CT slices found: 6
- Revenue in CT is revenue_yego_final (COALESCE(real, proxy))
- Growth API revenue = SUM(price.final_cost) across completed orders
- Active drivers in CT may be summed across slices (possible double-count)
- Date range is exclusive-end in CT queries (trip_date < date_to)
- Growth API orders are filtered by ended_at in PET timezone

## 4. Classification Guidance

Based on reconciliation results, classify the Growth API per OV2_A1_SOURCE_CERTIFICATION_MATRIX.md.
