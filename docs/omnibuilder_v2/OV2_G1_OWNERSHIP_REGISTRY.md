# OV2-G.1 — OWNERSHIP REGISTRY

> **Date:** 2026-06-08
> **Status:** REGISTRY DEFINED

---

## 1 OBJECT = 1 OWNER

| Object | Owner | Readers | Writer | Status |
|--------|-------|---------|--------|--------|
| `public.trips_2026` | ELT Pipeline | Bridge, day_fact | External | ACTIVE |
| `ops.driver_day_slice_fact` | Bridge Cascade | V2 drill, day_fact | `build_driver_bridge_direct.py` | ACTIVE |
| `ops.real_business_slice_day_fact` | Bridge Cascade | V1, V2 | `rebuild_day_from_bridge.py` | ACTIVE |
| `ops.real_business_slice_week_fact` | Bridge Cascade | V1, V2 | `rebuild_week_from_day_and_bridge.py` | ACTIVE |
| `ops.real_business_slice_month_fact` | Bridge Cascade | V1, V2, Plan vs Real | `rebuild_month_from_day_and_bridge.py` | ACTIVE |
| `ops.plan_trips_monthly` | Plan Service | Plan vs Real | `plan_template_parser` | ACTIVE |
| `ops.omniview_v2_serving_snapshot` | Snapshot Service | V2 Shell, V2 Matrix | `refresh_omniview_v2_snapshots.py` | ACTIVE |
| `serving.omniview_projection_daily_fact` | Projection Service | V2 Projection | `refresh_omniview_projection_facts.py` | ACTIVE |

## 2. CONFLICT RESOLUTION

If two processes attempt to write the same table:
1. LEGACY_REFRESH_BLOCKED (F.4A/F.4C guard)
2. Only CANONICAL writer allowed
3. Manual override requires `--allow-backfill` flag

---

*End of Ownership Registry*
