# OV2-F.4C — DAY FACT LINEAGE AUDIT

> **Date:** 2026-06-08
> **Status:** COMPLETE

## 1. `load_business_slice_day_for_month()` — Legacy Path

**File:** `backend/app/services/business_slice_incremental_load.py:1695`

### Tables read:
- `public.trips_2025` + `public.trips_2026` (6.8M rows) — raw trips, UNION ALL + dedup
- `dim.dim_park` — park → country/city
- `public.drivers` — works_terms
- `ops.business_slice_mapping_rules` — slice resolution

### Why stuck at 2026-05-31:
The enriched temp table `_bs_enriched_month` is materialized from raw trips. If the raw trips have data through 2026-06-07 but the enriched materialization doesn't include all dates (due to the view's logic or filters), day_fact stops at the last date that had data in the enriched view.

### Columns produced:
trips_completed, trips_cancelled, active_drivers, avg_ticket, trips_per_driver, revenue_yego_final, revenue_yego_net, commission_pct

### Differences vs bridge:
| Metric | Legacy | Bridge |
|--------|--------|--------|
| trips | COUNT from raw | SUM from bridge |
| drivers | COUNT DISTINCT from raw (exact) | COUNT DISTINCT from bridge (exact) |
| revenue | SUM from raw | Preserved from existing day_fact |
| fleet columns | Resolved via mapping rules | Limited (park_id only) |
| Row count | ~150/day (all slices+fleets) | ~84 (bridge slices only) |

## 2. DEPRECATION

**DEPRECATED for scheduled use.** Replaced by `rebuild_day_from_bridge.py`.
