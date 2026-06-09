# CT-GOV-043 — Refresh Ownership Registry

**Date:** 2026-06-08
**Motor:** Control Foundation / Global Freshness Governance
**Status:** CANONICAL

---

## 1. PRINCIPLE

```
1 TABLE = 1 WRITER
```

No table may have more than one service, script, or scheduler that writes to it. Multiple writers cause data conflicts, stale overwrites, and untraceable bugs.

---

## 2. OMNIVIEW OWNERSHIP

| Table | Writer | Service/File | Type | Status |
|-------|--------|-------------|------|:---:|
| `driver_day_slice_fact` | `build_driver_bridge_direct` | bridge script | CANONICAL | ACTIVE |
| `day_fact` | `load_business_slice_day_for_month` | APScheduler 04:00 | CANONICAL | ACTIVE |
| `week_fact` | `rebuild_week_from_day_and_bridge` | bridge cascade | CANONICAL | ACTIVE |
| `month_fact` | `rebuild_month_from_day_and_bridge` | bridge cascade | CANONICAL | ACTIVE |
| `serving_snapshot` | `refresh_omniview_v2_snapshots` | cascade orchestrator | CANONICAL | ACTIVE |
| `driver_daily_activity_fact` | N/A (view) | — | DERIVED | — |
| `mv_driver_lifecycle_base` | N/A (view) | — | DERIVED | — |

### Legacy Writers (DEPRECATED per OV2-F.4A)

| Function | Table | Status |
|----------|-------|:---:|
| `load_business_slice_week_for_month` | week_fact | **DEPRECATED** |
| `load_business_slice_month` | month_fact | **DEPRECATED** |
| `_RESOLVE_AND_AGG_WEEK_FROM_TEMP` | week_fact | **DEPRECATED** |
| `_RESOLVE_AND_AGG_FROM_TEMP` | month_fact | **DEPRECATED** |

---

## 3. LIMA GROWTH OWNERSHIP

| Table | Writer | Service | Type | Status |
|-------|--------|---------|------|:---:|
| `orders_raw` | `upsert_raw_orders` | yego_lima_growth_repository | CANONICAL | ACTIVE |
| `history_daily` | `bootstrap_history` | yego_lima_growth_history_service | CANONICAL | ACTIVE |
| `history_weekly` | auto-aggregation | SQL (from history_daily) | DERIVED | ACTIVE |
| `driver_state_snapshot` | `build_driver_state_snapshot` | yego_lima_driver_state_service | CANONICAL | ACTIVE |
| `program_eligibility` | `build_program_eligibility` | program_eligibility_service | CANONICAL | ACTIVE |
| `daily_opportunity_list` | `build_daily_opportunity_lists` | daily_opportunity_service | CANONICAL | ACTIVE |
| `prioritized_opportunity` | `build_prioritized_opportunities` | opportunity_policy_service | CANONICAL | ACTIVE |
| `assignment_queue` | `create_assignment_batch` | assignment_queue_service | CANONICAL | ACTIVE |
| `serving_fact` | `generate_all_serving_facts` | serving_facts_service | CANONICAL | ACTIVE |
| `intraday_signal` | `autonomous_tick` | scheduler_service (APScheduler 5min) | CANONICAL | ACTIVE |
| `scheduler_tick_log` | `autonomous_tick` | scheduler_service | CANONICAL | ACTIVE |
| `driver_list_history` | `snapshot_queue_to_history` | driver_list_history_service | CANONICAL | ACTIVE |

### Dead/Deprecated

| Table | Writer | Status |
|-------|--------|:---:|
| `driver_360_daily` | `stabilize_driver_360_day` | **DEAD** (R2.0) |
| `eligible_universe_daily` | `build_eligible_universe` | **DEAD** (R2.0) |
| `actionable_list_daily` | legacy | **DEPRECATED** |
| `hourly_snapshot` | legacy | **DEPRECATED** |

---

## 4. ORPHAN WRITERS DETECTED

| Writer | Table | Issue |
|--------|-------|-------|
| `loopcontrol_result_sync_service` | writes to `campaign_export.error_message` | Writing to wrong table. Orphaned `result_sync` table exists but unused. |

---

## 5. DOUBLE WRITERS DETECTED

**None found.** All tables have single-writer ownership after OV2-F.4A deprecation cleanup.

---

## FIRMA

```
CT-GOV-043 REFRESH OWNERSHIP REGISTRY
Date: 2026-06-08
Status: CANONICAL — 1 table = 1 writer enforced
```
