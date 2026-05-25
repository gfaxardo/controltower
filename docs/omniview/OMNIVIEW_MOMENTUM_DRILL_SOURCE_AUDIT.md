# OMNIVIEW MOMENTUM DRILL — Source Audit

**Date**: 2026-05-25

---

## REUSABLE_NOW

| Source | What it provides | Grain |
|--------|-----------------|-------|
| `ops.real_business_slice_day_fact` | Daily trips, revenue, drivers, ticket per city/slice | daily |
| `ops.real_business_slice_week_fact` | Weekly aggregated same columns | weekly |
| `ops.real_business_slice_month_fact` | Monthly aggregated same columns | monthly |
| `_fetch_resolved_daily_metrics_for_dates()` | Baseline metrics for same-weekday comparison | daily |
| `apply_period_over_period_inplace()` | Delta computation (abs + pct) for sequential periods | all |
| Router pattern in `ops.py` | Existing endpoint registration pattern | all |

## DESIGN CHOICE

**Single endpoint approach**: Query the relevant fact table directly, filter by date range, compute momentum deltas server-side. This avoids:
- Creating new MVs
- Runtime-heavy frontend computation
- Raw queries from frontend

## UNSAFE (do not use)

| Source | Reason |
|--------|--------|
| Raw `staging.control_loop_*` tables | Not serving-governed. Use fact tables. |
| Direct cross-join between fact tables | Use sequential query with simple filters. |
