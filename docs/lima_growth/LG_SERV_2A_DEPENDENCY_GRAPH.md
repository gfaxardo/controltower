# LG-SERV-2A — DEPENDENCY GRAPH

**Date:** 2026-06-11  
**Source:** `serving_operability_service.py:DEPENDENCY_GRAPH`

---

## Canonical Dependency Graph

```
Yango API / raw_yango.orders_raw
  └── RNA_serving (yango_lima_driver_history_daily)
        └── driver_state_snapshot
              ├── program_assignment (program_eligibility_daily)
              │     └── serving_driver_explorer (serving_fact)
              └── (lifecycle pipeline)

ops.driver_daily_activity_fact
  ├── activity_daily
  ├── activity_weekly
  └── activity_monthly

growth.yego_lima_driver_lifecycle_daily
  ├── lifecycle_daily (V2 shadow)
  │     ├── taxonomy_v2
  │     └── program_v2
  ├── taxonomy_v2
  │     └── movement_fact
  └── program_v2
        ├── movement_fact
        └── program_assignment (indirect via autonomous tick)

state_transition_trace + program_decision_trace
  └── movement_fact
        └── observability_fact
              └── RNA_serving

ops.driver_campaigns + effectiveness
  └── effectiveness_fact (standalone)

ops.v_observability_module_status
  └── observability_fact
```

## Critical Chains

### Chain A: Yango API → Explorer (CRITICAL)

```
raw_orders → RNA_serving(6h SLA) → driver_state_snapshot(5h) → program_assignment(5h) → serving_explorer(5h)
```

Currently BROKEN: raw_orders max 2026-06-09 → RNA_serving 194h old → driver_state marked WARNING → chain stale.

### Chain B: Activity → Movement (HEALTHY but stale)

```
activity_fact → activity_daily/weekly/monthly → lifecycle → taxonomy_v2 → program_v2 → movement → observability
```

Currently DEGRADED: activity_fact ends 2026-05-21 → V2 pipeline output 50h old → chain 2 days behind.

### Chain C: Observability (standalone, HEALTHY)

```
v_observability_module_status → observability_fact
```

6 modules tracked, fresh to 2026-06-10.

## Freshness Propagation Rules

- If `raw_orders` is stale → `RNA_serving` degrades → `driver_state` degrades → cascade
- If `driver_lifecycle_daily` is stale → `lifecycle_daily`, `taxonomy_v2`, `program_v2` all degrade  
- If `state_transition_trace` is stale → `movement_fact` degrades → `observability_fact` degrades
- Each degraded asset's age propagates downstream: upstream age = minimum of all dependency ages

## Code Reference

Dependency graph is defined in:
- `backend/app/services/serving_operability_service.py:35-49` (DEPENDENCY_GRAPH dict)
- `backend/app/services/yego_lima_freshness_chain_service.py:13-23` (LINEAGE_SOURCE dict)
