# raw_yango vs Control Tower — Reconciliation

**Generated:** 2026-06-05T06:35:04.467601-05:00
**Date Range:** 2026-06-04 -> 2026-06-05 (CT exclusive end)
**Park ID (masked):** 08e20910***
**CT Country/City:** peru / lima

## 1. Summary Comparison

| Metric | raw_yango | Control Tower | Delta | Delta % |
|--------|-----------|---------------|-------|---------|
| Trips | 1,500 | 0 | +1,500 | N/A |
| Revenue | 51.59 | 0.00 | +51.59 | N/A |

## 2. Daily Breakdown

| Date | Raw Trips | CT Trips | Trip Class | Raw Revenue | CT Revenue | Rev Class |
|------|-----------|----------|------------|-------------|------------|-----------|
| 2026-06-04 | 1,500 | 0 | **API_ONLY** | 51.59 | 0.00 | **API_ONLY** |

## 3. Classification Legend

| Classification | Criteria |
|----------------|----------|
| MATCH | |delta| < 1% |
| MINOR_DELTA | 1% <= |delta| < 5% |
| MAJOR_DELTA | 5% <= |delta| < 20% |
| CT_ONLY | Data in CT but not in raw |
| API_ONLY | Data in raw but not in CT |
| NEEDS_INVESTIGATION | Any anomaly |

## 4. Notes

- Revenue from raw_yango = SUM(ABS(amount)) WHERE category_name = 'Partner fee for trip'
- Revenue from CT = revenue_yego_final (COALESCE(real, proxy))
- CT date range is exclusive-end (trip_date < date_to)
- raw_yango date range is inclusive on fetched_at_date
- Trips from raw_yango = COUNT(*) from orders_raw (status complete)
