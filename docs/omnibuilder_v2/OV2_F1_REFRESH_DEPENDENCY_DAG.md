# OV2-F.1 — REFRESH DEPENDENCY DAG

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Refresh Chain
> **Status:** DOCUMENTED

---

## 1. COMPLETE DAG

```
RAW/API
  │
  ├─1─► public.trips_2026 ──► safe_refresh ──► ops.mv_real_drill_enriched
  │         │
  │         ├─2─► refresh_omniview_real_slice_incremental
  │         │         │
  │         │         ├─► ops.real_business_slice_day_fact       [D-1: 2026-06-06 ✓]
  │         │         │         │
  │         │         │         ├─► ops.real_business_slice_week_fact   [STALE: 2026-04-20]
  │         │         │         │         │
  │         │         │         │         └─► ops.real_business_slice_month_fact  [2026-06-01]
  │         │         │         │
  │         │         │         └─► GET /ops/omniview-v2/operating-date
  │         │         │
  │         │         └─► refresh_omniview_v2_snapshots
  │         │                   │
  │         │                   └─► ops.omniview_v2_serving_snapshot  [2026-06-05]
  │         │                            │
  │         │                            ├─► GET /ops/omniview-v2/shell
  │         │                            └─► GET /ops/omniview-v2/matrix
  │         │
  │         └─► driver_lifecycle ──► ops.mv_driver_lifecycle_base
  │
  ├─3─► Yango Fleet API ──► refresh_raw_yango_mvs
  │         │
  │         ├─► raw_yango.mv_orders_day          [2026-06-05]
  │         ├─► raw_yango.mv_revenue_day
  │         └─► raw_yango.mv_source_coverage_day
  │
  └─4─► Excel Plan Template ──► plan_template_parser
            │
            └─► ops.plan_trips_monthly ──► GET /plan-real/monthly
                    │
                    └─► refresh_plan_vs_real_monthly_mvs
```

## 2. DEPENDENCY RULES

### What breaks what

| If this fails... | Then these are STALE... |
|-----------------|------------------------|
| `trips_2026` has no new data | day_fact, week_fact, month_fact, snapshots, operating-date |
| `day_fact` refresh fails | week_fact (depends on day_fact aggregation), snapshots |
| `week_fact` refresh fails | month_fact (aggregated from week), operating-date (for weekly grain) |
| `snapshot` refresh fails | Shell and Matrix endpoints degrade to runtime (slower) |
| `plan_template_parser` fails | Plan vs Real shows old plan version |

### What can refresh independently

| Layer | Can run standalone? | Notes |
|-------|-------------------|-------|
| RAW Yango MVs | YES | Independent API pipeline |
| Plan ingestion | YES | Independent from trip data |
| Snapshots | YES | Can refresh from existing facts even if upstream didn't change |
| Driver lifecycle | YES | Reads from trips_2026, independent of business slice facts |
| Financials | YES | Independent aggregation |

### What must NOT refresh if upstream fails

| If upstream STALE | DO NOT refresh |
|------------------|----------------|
| trips_2026 no new data after 2+ days | Skip snapshot refresh (serve stale snapshot) |
| day_fact STALE | Skip week_fact refresh |
| day_fact has 0-row days | Abort month_fact refresh |
| plan version missing | Fail plan-real endpoint fast (NO_PLAN) |

## 3. CRITICAL PATH (minimum for UI to work)

```
trips_2026 (any data) → day_fact (D-1) → snapshots (within 2 days) → UI ✓
                                                       OR
                                                    runtime fallback (slower, blocked in H.2)
```

## 4. CURRENT BOTTLENECKS

| Bottleneck | Impact | Fix |
|-----------|--------|-----|
| week_fact STALE (2026-04-20) | Week-level matrix/rollup broken | Run `refresh_omniview_real_slice_incremental` for missing weeks |
| Snapshots D-2 (2026-06-05) | Shell/matrix serve 2-day-old data | Run `refresh_omniview_v2_snapshots` daily |
| month_fact revenue NULL for Jan-Feb | Plan vs Real revenue shows OFF_TRACK gap | Run month_fact refresh with revenue data |

---

*End of Dependency DAG*
