# Omniview V2 Shadow API Audit

**Generated:** 2026-06-05T16:22:40.109696-05:00
**Date Range:** 2026-06-04 -> 2026-06-04
**Total elapsed:** 15.54s

## Endpoints

| Endpoint | Status | Elapsed (ms) |
|----------|--------|-------------|
| daily | OK | 6532.8 |
| coverage | OK | 1498.3 |
| reconciliation | OK | 1498.1 |
| health | OK | 6010.8 |

## Warnings
- **SHORT_SERIES** [warning]: Only 2 days of data available. Minimum 7 recommended.
- **REVENUE_DELTA** [warning]: Revenue delta vs CT is -78.46%. Above 5% threshold.
- **SINGLE_PARK_SCOPE** [info]: Only one park (Lima) ingested. Multi-park coverage pending.

## Reconciliation
- **Status:** MAJOR_DELTA
- **Basis:** CITY_DATE
- **CT match level:** EXACT_CITY_DATE
- **CT data date:** 2026-06-04
- MV orders: 2,977
- CT trips: 14,213
- MV revenue: 1,256.37
- CT revenue: 5,832.27
- Trips delta: -79.05%
- Revenue delta: -78.46%
- MV rev/order: 0.4220
- CT rev/trip: 0.4103

### CT Fallback Warnings
- None