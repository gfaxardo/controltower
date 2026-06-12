# LG-UX-0A — SYSTEM INVENTORY

**Date:** 2026-06-11  
**Phase:** LG-UX-0A / Workflow Mapping

---

## COMPLETE SYSTEM INVENTORY

### DATA LAYER

| Layer | Tables | Rows | Status |
|-------|--------|------|--------|
| Raw Ingestion | raw_yango.*, growth.yango_lima_orders_raw | 12,322 | Max 2026-06-09 |
| Driver State | growth.yango_lima_driver_state_snapshot | 148,167 | FRESH TODAY |
| Driver History | growth.yango_lima_driver_history_daily | 520,340 | Rolling |
| Lifecycle | growth.yego_lima_driver_lifecycle_daily + event | 273,908 + 48,611 | T-1 |
| Taxonomy V2 | growth.yego_lima_driver_taxonomy_v2_daily | 273,908 | T-1 |
| Program Eligibility | growth.yango_lima_program_eligibility_daily | 226,432 | FRESH TODAY |
| Prioritized Opportunity | growth.yango_lima_prioritized_opportunity_daily | 44,367 | FRESH TODAY |
| Assignment Queue | growth.yego_lima_assignment_queue | 2,104 | FRESH TODAY |
| Control Loop | growth.yego_lima_control_loop_state | 668 | FRESH TODAY |
| Serving Facts | growth.yego_lima_serving_fact | 48 | FRESH TODAY |
| Movement Trace | growth.yego_lima_state_transition_trace + program_decision_trace | 1,205 + 5,558 | STALE (Jun 5) |
| List History | growth.yego_lima_driver_list_history | 1,104 | FRESH TODAY |
| Freshness Registry | growth.yego_lima_freshness_registry | 7 | FRESH |
| V2 Shadow | growth.yego_lima_v2_* (9 tables) | 822K total | Shadow, not production |

### PROGRAM LAYER

| Code | Name | Drivers Today |
|------|------|--------------|
| PROGRAM_ACTIVE_GROWTH | Active Growth | 17,685 |
| PROGRAM_CHURN_PREVENTION | Churn Prevention | 7,774 |
| PROGRAM_14_90 | Programa 14/90 | 2,669 |

### SCHEDULER LAYER

| Scheduler | Frequency | Status | Last Tick |
|-----------|-----------|--------|-----------|
| lima_growth_autonomous_tick | Every 5 min | RUNNING | 3.8m ago |
| lima_growth_v2_daily_pipeline | Daily 04:45 | REGISTERED | Shadow |
| serving_fact_daily_refresh | Daily 05:00 | REGISTERED | — |
| omniview_cascade_refresh | Daily 04:00 | REGISTERED | — |

### API LAYER (Lima Growth only)

| Endpoint Group | # Endpoints | Pattern | Tables Read |
|---------------|------------|---------|------------|
| Operational Summary | 1 | Serving-first | driver_state, eligibility, prioritized, queue, loopcontrol, capacity |
| Driver State Summary | 1 | Serving-first | driver_state |
| Programs Status | 1 | Direct DB | eligibility, prioritized, queue |
| Queue Operational | 1 | Direct DB | queue, queue_build_log, policy |
| Queue Summary | 1 | Serving-first | queue, loopcontrol, capacity |
| Today Action Plan | 1 | Serving-first | 4 composed services |
| Movement | 3 | Direct DB | state_transition, program_decision, list_history |
| Operational Truth | 1 | Direct DB | 7 tables |
| Governance | 4 | Direct DB | registry, runs, freshness, health |
| Growth Health | 3 | Aggregated | freshness_fact, governance, chain, v2_pipeline |
| V2 Pipeline | 2 | Shadow | V2 shadow tables |

### UNIQUE DRIVERS TODAY

```
18,545 unique drivers in driver_state_snapshot for 2026-06-11
```

### MOVEMENT SUMMARY

```
State transitions: 1,205 total records (last: 2026-06-05)
Program decisions: 5,558 total records (last: 2026-06-05)
List history: 1,104 records (last: 2026-06-11)
```

### RNA / LOYALTY

```
Yango Loyalty endpoints: 16 endpoints
Tables: ops.mv_driver_lifecycle_monthly_kpis, ops.yango_loyalty_*, public.trips_2026
```

### OBSERVABILITY

```
ops.v_observability_module_status: 6 modules tracked
ops.observability_refresh_log: 28 entries
```

### EFFECTIVENESS

```
ops.driver_campaigns: available
ops.driver_campaign_effectiveness: available
V2 effectiveness: 0 rows (no active campaigns for target period)
```
