# OV2-F.2C — WEEK FACT REBUILD PROPOSAL

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Refresh Chain
> **Status:** PROPOSAL — SAFE_TO_IMPLEMENT

---

## 1. PROPOSAL

Build week_fact from **ops.real_business_slice_day_fact** instead of raw trips.

### Source
- `ops.real_business_slice_day_fact` (2.5K rows for Lima, 2 months)

### Method
- Group by `date_trunc('week', trip_date)::date` (ISO Monday)
- SUM() for additive metrics
- Recalculate derived metrics
- SUM() daily active_drivers with warning

### NO
- NO raw trips (public.trips_2026)
- NO enriched views
- NO month_fact
- NO 600s timeouts
- NO DB saturation

## 2. CLASSIFICATION

| Factor | Status |
|--------|--------|
| Trips/revenue from day_fact | **SAFE_TO_IMPLEMENT** — exact sums |
| avg_ticket recalculation | **SAFE_TO_IMPLEMENT** — derived from sums |
| TPD recalculation | **SAFE_TO_IMPLEMENT** — derived from sums |
| active_drivers from day_fact | **SAFE_TO_IMPLEMENT** — with upper bound warning |
| ISO week_start from trip_date | **SAFE_TO_IMPLEMENT** — `date_trunc('week')` is correct |
| week_end computation | **SAFE_TO_IMPLEMENT** — week_start + 6 days |
| No raw trips | **SAFE_TO_IMPLEMENT** — day_fact has all needed data |
| No month crossing issues | **SAFE_TO_IMPLEMENT** — GROUP BY week_start, not month |
| Atomic swap (delete + insert) | **SAFE_TO_IMPLEMENT** — staging → validate → swap |

| Factor | Status |
|--------|--------|
| Exact weekly active_drivers | **NEEDS_BRIDGE** — requires driver_daily_activity_fact with slice mapping |
| commission_pct exact | **SAFE_TO_IMPLEMENT** — recalculated from net/final sums |
| fleet/subfleet drill | **BLOCKED** — day_fact may not have full fleet hierarchy |

## 3. EXECUTION PLAN

```bash
# Step 1: Dry-run (validates SQL, no writes)
python -m scripts.rebuild_week_fact_from_day_fact \
  --date-from 2026-04-01 --date-to 2026-06-06 --country peru --city lima --dry-run

# Step 2: Real rebuild (if dry-run PASS)
python -m scripts.rebuild_week_fact_from_day_fact \
  --date-from 2026-04-01 --date-to 2026-06-06 --country peru --city lima --confirm

# Step 3: Validate waterfall
python -m scripts.validate_refresh_waterfall

# Step 4: Rebuild month_fact too
python -m scripts.rebuild_week_fact_from_day_fact ... --grain month (TODO)
```

## 4. ROLLBACK

If the rebuild produces incorrect data:
1. The old week_fact rows were deleted only for the affected ISO weeks
2. Re-run the original `refresh_omniview_real_slice_incremental` to restore from raw (heavy but correct)
3. Or restore from DB backup

---

*End of Rebuild Proposal*
