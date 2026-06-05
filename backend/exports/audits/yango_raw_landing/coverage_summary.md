# raw_yango Coverage Audit

**Generated:** 2026-06-05T06:47:09.150101-05:00
**Date Range:** 2026-06-04 -> 2026-06-04
**Park ID (masked):** 08e20910***

## 1. Table Coverage

| Table | Exists | Rows | Distinct Days | Min Date | Max Date |
|-------|--------|------|---------------|----------|----------|
| orders_raw | YES | 1,500 | 1 | 2026-06-04 | 2026-06-04 |
| transactions_raw | YES | 500 | 1 | 2026-06-04 | 2026-06-04 |
| driver_profiles_raw | YES | 300 | 1 | 2026-06-05 | 2026-06-05 |

## 2. Revenue Candidates

- **Partner fee for trip** count: 110
- **SUM(ABS(amount))**: 51.59

## 3. Missing Days

- **orders_raw**: none missing
- **transactions_raw**: none missing
- **driver_profiles_raw** (1 days): 2026-06-04

## 4. Coverage Score

- **orders_raw** coverage: 100.0% (1/1 days)
- **transactions_raw** coverage: 100.0% (1/1 days)
- **driver_profiles_raw** coverage: 100.0% (1/1 days)