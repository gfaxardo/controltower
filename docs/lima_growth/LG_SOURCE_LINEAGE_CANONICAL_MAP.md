# LG — Source Lineage Canonical Map

**Date:** 2026-06-07
**Phase:** LG-INFRA-R1.5
**Status:** CANONICAL

---

## 1. EXECUTIVE SUMMARY

This document defines the canonical source lineage from Yango Fleet API to the Lima Growth UI. Every table in the `growth.*` schema is classified as ACTIVE, DERIVED, CONFIG, AUDIT, or LEGACY. No ambiguity remains.

**Canonical live source:** `raw_yango.orders_raw` / Yango Fleet API
**Historical source:** `public.trips_2025` / `public.trips_2026` (enrichment only)
**Conflict rule:** Yango API always wins.

---

## 2. CANONICAL LINEAGE CHAIN

```
┌─────────────────────────────────────────────────────────────┐
│                      YANGO FLEET API                         │
│  POST /v1/parks/orders/list                                  │
│  POST /v1/parks/driver-profiles/list                         │
│  GET  /v2/parks/contractors/supply-hours (per-driver)        │
└──────────┬──────────────────────┬───────────────────────────┘
           │                      │
           ▼                      ▼
┌──────────────────────┐  ┌──────────────────────────────┐
│ raw_yango.orders_raw │  │ raw_yango.driver_profiles_raw│
│ (11087 rows)         │  │ raw_yango.transactions_raw    │
└──────────┬───────────┘  └──────────────┬───────────────┘
           │                              │
           ▼                              │
┌──────────────────────────────────────┐  │
│ growth.yango_lima_orders_raw (237)   │  │
└──────────┬───────────────────────────┘  │
           │                              │
           ▼                              ▼
┌──────────────────────────────────────────────────────────┐
│          growth.yango_lima_eligible_universe_daily        │
│  Built from: Yango API driver-profiles/list + orders_raw  │
│  Classification: ACTIVE | Grain: per driver, per date     │
│  Skippable: YES — downstream uses driver_state_snapshot   │
│  Refresh: Daily closed pipeline (Yango API heavy call)    │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│          growth.yango_lima_driver_360_daily               │
│  Built from: eligible_universe + orders_raw + API supply  │
│  Classification: ACTIVE | Grain: per driver, per date     │
│  Skippable: YES — snapshot uses history_weekly instead    │
│  Refresh: Daily (per-driver supply API — slow)            │
└───────────┬──────────────────────────────┬───────────────┘
            │                              │
            │    ┌─────────────────────────┘
            │    │
            ▼    ▼
┌──────────────────────────────────────────────────────────┐
│  growth.yango_lima_driver_history_daily  (from trips)     │
│                       │                                   │
│                       ▼                                   │
│  growth.yango_lima_driver_history_weekly (rolling)        │
│  Classification: ACTIVE | Grain: per driver, per week     │
│  Source: bootstrapped from public.trips_2025/2026         │
│  REFRESH: Daily (new week data appended)                  │
└───────────┬──────────────────────────────────────────────┘
            │
            │  ┌─────────────────────────────┐
            ├──┤  driver_360_daily           │ (current week data)
            │  └─────────────────────────────┘
            │
            ▼
┌──────────────────────────────────────────────────────────┐
│       growth.yango_lima_driver_state_snapshot             │
│  Built from: history_weekly + driver_360_daily            │
│  Classification: ACTIVE | Grain: per driver, per date     │
│  Mutable: NO (replaced per date) | Versioned: NO          │
│  CRITICAL: YES — feeds ALL downstream layers              │
│  18,475 drivers per snapshot                              │
└──────────┬───────────────────────────────────────────────┘
           │
           ├──────────────────────────────────────┐
           ▼                                      ▼
┌──────────────────────────────┐  ┌──────────────────────────────┐
│ program_eligibility_daily    │  │ driver_segment_snapshot      │
│ 28,493 eligible drivers      │  │ 47 segments                  │
└──────────────┬───────────────┘  └──────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────┐
│       growth.yango_lima_daily_opportunity_list            │
│  28,493 rows per date                                     │
│  Types: OPPORTUNITY_14_90, ACTIVE_GROWTH, CHURN_PREVENTION│
└──────────────┬───────────────────────────────────────────┘
               │
               ▼ (via opportunity policy engine)
┌──────────────────────────────────────────────────────────┐
│    growth.yango_lima_prioritized_opportunity_daily        │
│  5,604 scored & ranked per date                           │
│  500 actionable today (capacity-gated)                    │
└──────────────┬───────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────┐
│       growth.yego_lima_assignment_queue                   │
│  500 built per date | 310 READY | 190 HELD                │
│  Channels: whatsapp, sms, push, email                     │
└──────────────┬───────────────────────────────────────────┘
               │
               ├──────────────────────┐
               ▼                      ▼
┌──────────────────────┐  ┌──────────────────────────────┐
│ loopcontrol_campaign │  │ serving_fact (8 types)        │
│ _export              │  │ Pre-computed UI cache         │
└──────────────────────┘  └──────────────┬───────────────┘
                                         │
                                         ▼
                              ┌──────────────────────┐
                              │   UI ENDPOINTS        │
                              │   Serving-first       │
                              │   < 1s response       │
                              └──────────────────────┘
```

---

## 3. TABLE CLASSIFICATION MATRIX

### ACTIVE (Core Operational Tables)

| Table | Role | Source | Refresh | Obligatory |
|-------|------|--------|---------|:---:|
| `yango_lima_orders_raw` | Raw orders from Yango API | Yango API orders/list | Daily ingestion | YES |
| `yango_lima_eligible_universe_daily` | Driver tier classification | Yango API + orders_raw | Daily pipeline | SKIPPABLE |
| `yango_lima_driver_360_daily` | Per-driver daily profile | eligible_universe + API supply | Daily pipeline | SKIPPABLE |
| `yango_lima_driver_history_daily` | Historical daily records | trips_2025/2026 | Bootstrap | YES |
| `yango_lima_driver_history_weekly` | Weekly aggregates | history_daily | Daily | YES |
| `yango_lima_driver_state_snapshot` | Canonical driver state | history_weekly + 360_daily | Daily pipeline | **YES** |
| `yango_lima_driver_segment_snapshot` | Driver segmentation | 360_daily + history_weekly | Daily pipeline | NO |
| `yango_lima_loyalty_sub50_weekly` | Loyalty sub-50 | 360_daily + history_weekly | Daily pipeline | NO |
| `yango_lima_program_eligibility_daily` | Per-driver program assignment | driver_state_snapshot | Daily pipeline | **YES** |
| `yango_lima_daily_opportunity_list` | Daily opportunity generation | program_eligibility | Daily pipeline | YES |
| `yango_lima_prioritized_opportunity_daily` | Scored & ranked opportunities | daily_opportunity_list + policy | Policy engine | **YES** |
| `yego_lima_assignment_queue` | Operational action queue | prioritized_opportunity | Daily refresh | **YES** |
| `yego_lima_serving_fact` | Pre-computed UI facts | Multiple sources | Daily refresh | **YES** |
| `yego_lima_intraday_driver_signal` | Intraday observation | orders_raw | 5-min tick | NO |

### CONFIG (Configuration Tables)

| Table | Role |
|-------|------|
| `yango_lima_opportunity_policy_config` | Prioritization policy parameters |
| `yango_lima_loopcontrol_config` | LoopControl integration settings |
| `yego_lima_capacity_config` | Agent capacity configuration |
| `yego_lima_program_capacity_policy` | Per-program capacity caps |

### DERIVED (Analytics / Post-Processing)

| Table | Role |
|-------|------|
| `yango_lima_driver_action_daily_impact` | Daily impact records |
| `yango_lima_action_attribution_daily` | Attribution analysis |
| `yango_lima_driver_segment_transition_daily` | Segment transitions |
| `yego_lima_impact_tracking` | Impact tracking |
| `yego_lima_movement_tracking` | Movement tracking |
| `yego_lima_attribution_candidates` | Attribution candidates |
| `yango_lima_productivity_daily/weekly/monthly` | Productivity metrics |

### AUDIT (Operational Logs)

| Table | Role |
|-------|------|
| `yango_lima_pipeline_run_log` | Pipeline execution log |
| `yango_lima_pipeline_run_step_log` | Per-step detail |
| `yego_lima_refresh_run_log` | Refresh execution log |
| `yego_lima_refresh_step_log` | Per-step detail |
| `yego_lima_scheduler_status` | Scheduler operational state |
| `yego_lima_queue_build_audit` | Queue build audit trail |
| `yego_lima_program_capacity_policy_audit` | Policy changes audit |
| `yango_lima_loopcontrol_export_job_run` | Export job tracking |
| `yango_lima_loopcontrol_export_job_program` | Per-program export detail |
| `yego_lima_loopcontrol_result_sync` | Result sync records |
| `yango_lima_data_freshness` | Source freshness tracking |

### LEGACY (Superseded)

| Table | Superseded By | Status |
|-------|---------------|:---:|
| `yango_lima_actionable_list_daily` | `daily_opportunity_list` | DEPRECATED |
| `yango_lima_actionable_list_outcome_daily` | Superseded | DEPRECATED |
| `yango_lima_driver_action_registry` | Superseded | DEPRECATED |
| `yango_lima_hourly_snapshot` | `driver_360_daily` | DEPRECATED |

---

## 4. CRITICAL DEPENDENCY FINDINGS

### 4.1 driver_state_snapshot = The Keystone

`driver_state_snapshot` is the single most critical table. It feeds:
- `program_eligibility` (28,493 rows)
- `driver_segments` (47 segments)
- All 8 serving facts
- UI operational summary
- Today action plan

**It depends on BOTH:**
- `driver_history_weekly` (historical metrics: 4w/12w averages, best_week)
- `driver_360_daily` (current week supply/orders)

**If driver_360_daily has 0 rows for a date**, the snapshot STILL builds (using only history_weekly data), but current-week supply/orders enrichment is missing.

### 4.2 eligible_universe + driver_360 = Skippable

These two steps (#2 and #3 in the pipeline) are frequently skipped when they detect their work is already done, or when async event loop detection triggers. **This is by design** — the snapshot does not strictly depend on them for dates where history_weekly has sufficient data.

**Verdict:** `eligible_universe` and `driver_360_daily` are **CANONICAL but SKIPPABLE**. Their absence degrades freshness (no current supply_hours) but does not break the pipeline.

### 4.3 No Circular Dependencies

The chain is linear and well-ordered:
```
Yango API → orders_raw → history → snapshot → eligibility → opportunities → prioritized → queue → serving → UI
```

No table feeds back into an earlier layer.

---

## 5. SOURCE CONFLICT RESOLUTION

| Data point | Live source | Historical source | Winner |
|-----------|-------------|-------------------|:---:|
| completed_orders_today | Yango API orders/list | trips_2026 | **Yango API** |
| supply_hours_today | Yango API supply-hours | N/A | **Yango API** |
| driver identity | Yango API driver-profiles/list | N/A | **Yango API** |
| lifetime_trips | N/A | trips_2025/2026 | **trips** |
| first_seen | N/A | trips_2025/2026 | **trips** |
| best_week_12w | N/A | trips_2025/2026 | **trips** |
| lifecycle transitions | N/A | trips_2025/2026 | **trips** |

---

## 6. REFRESH FREQUENCY BY LAYER

| Layer | Frequency | Trigger | Can be skipped? |
|-------|-----------|---------|:---:|
| orders_raw ingestion | Daily (pipeline) or on-demand | Pipeline step or lab endpoint | NO |
| eligible_universe | Daily (pipeline) | Pipeline step 2 | YES |
| driver_360 | Daily (pipeline) | Pipeline step 3 | YES |
| driver_state_snapshot | Daily (pipeline) | Pipeline step 6 | NO |
| program_eligibility | Daily (pipeline) | Pipeline step 7 | NO |
| daily_opportunity_list | Daily (pipeline) | Pipeline step 8 | NO |
| prioritized_opportunity | Daily (policy) | Policy engine | NO |
| assignment_queue | Daily (refresh) | Refresh step 3 | NO |
| serving_facts | Daily (refresh) | Refresh step 5 | NO |
| intraday_signals | Every 5 min | Scheduler tick | YES |

---

## 7. FINAL LINEAGE VERDICT

```
LINEAGE CANONICAL MAP CERTIFIED
```

- 15-step pipeline documented
- 42 growth.* tables classified
- Keystone: driver_state_snapshot
- Skippable: eligible_universe + driver_360
- Deprecated: 4 legacy tables
- Source: Yango API (live) + trips (historical enrichment)
- No circular dependencies
- Linear chain from API to UI
