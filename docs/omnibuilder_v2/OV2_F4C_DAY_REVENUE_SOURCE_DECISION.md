# OV2-F.4C — DAY REVENUE SOURCE DECISION

> **Date:** 2026-06-08
> **Status:** DECIDED — Option B (Hybrid)

## AUDIT

`ops.driver_day_slice_fact` has **NO** revenue columns. Confirmed via `information_schema.columns`.

## OPTIONS

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A | Add revenue to bridge | Exact per-driver revenue | Requires re-querying raw trips |
| **B** | **Hybrid: bridge trips + day_fact revenue** | No raw trips, preserves existing revenue | day_fact must have revenue populated |
| C | New `revenue_day_slice_fact` | Clean separation | Over-engineering |

## DECISION: B — Hybrid

- trips/drivers/empty_supply from `driver_day_slice_fact`
- revenue from existing `ops.real_business_slice_day_fact` (LEFT JOIN)
- Revenue is already populated (99.6% fill in day_fact)

## RISK

If a new business_slice appears in bridge but not in day_fact, revenue = 0 for that slice. Mitigated: bridge slices match day_fact slices (same `business_slice_mapping_rules`).
