# OV2-G.1 — SHARED REALITY INVENTORY

> **Date:** 2026-06-08
> **Motor:** Control Foundation / Shared Reality Governance
> **Status:** INVENTORY COMPLETE

---

## 1. OBJECTS SHARED BETWEEN V1 AND V2

| Object | Layer | Consumers | Writer | Freshness Source | Owner |
|--------|-------|-----------|--------|-----------------|-------|
| `ops.real_business_slice_day_fact` | REAL_SHARED | V1, V2 Matrix, V2 Shell, operating-date | `rebuild_day_from_bridge.py` | bridge MAX date | Bridge Cascade |
| `ops.real_business_slice_week_fact` | REAL_SHARED | V1, V2 Matrix (week grain), V2 Plan vs Real | `rebuild_week_from_day_and_bridge.py` | day_fact MAX date | Bridge Cascade |
| `ops.real_business_slice_month_fact` | REAL_SHARED | V1, V2 Matrix (month grain), V2 Plan vs Real | `rebuild_month_from_day_and_bridge.py` | week_fact MAX date | Bridge Cascade |
| `ops.driver_day_slice_fact` | REAL_SHARED | V2 Matrix (drill), V2 Inspector, V1 (indirect) | `build_driver_bridge_direct.py` | trips_2026 MAX date | Bridge Cascade |
| `ops.omniview_v2_serving_snapshot` | SNAPSHOT_SHARED | V2 Shell, V2 Matrix | `refresh_omniview_v2_snapshots.py` | day_fact MAX date | Snapshot Service |
| `ops.plan_trips_monthly` | PLAN_SHARED | V2 Plan vs Real | `plan_template_parser_service.py` | Plan template upload | Plan Service |
| `serving.omniview_projection_daily_fact` | PROJECTION_SHARED | V2 Projection | `refresh_omniview_projection_facts.py` | Plan table | Projection Service |

## 2. OBJECTS EXCLUSIVE TO V1

| Object | Notes |
|--------|-------|
| `ops.mv_real_trips_monthly` | V1 legacy monthly view (not used by V2) |
| `ops.mv_real_trips_weekly` | V1 legacy weekly view |
| `ops.v_trips_real_canon` | V1 canonical chain (hourly-first) |

## 3. OBJECTS EXCLUSIVE TO V2

| Object | Notes |
|--------|-------|
| `ops.omniview_v2_serving_snapshot` | V2-only serving layer |
| `backend/app/routers/omniview_v2.py` | V2-only router |
| Plan vs Real monthly matrix | V2-only feature |

## 4. KEY INSIGHT

**V1 and V2 share the SAME REAL layer.** If `week_fact` is stale, BOTH V1 and V2 show stale data — regardless of projection or snapshot freshness.

---

*End of Shared Reality Inventory*
