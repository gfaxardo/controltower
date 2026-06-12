# LG-TRUTH-1A — UI SOURCE OF TRUTH LINEAGE

**Date:** 2026-06-11

---

## CANONICAL UI DATA CHAIN

```
Yango API (ingested by autonomous tick, every 5 min)
  └── growth.yango_lima_driver_history_daily (rolling)
        └── growth.yango_lima_driver_state_snapshot (TODAY)
              ├── growth.yango_lima_program_eligibility_daily (TODAY)
              │     └── growth.yango_lima_prioritized_opportunity_daily (TODAY)
              │           └── growth.yego_lima_assignment_queue (TODAY)
              ├── growth.yego_lima_capacity_config
              └── growth.yego_lima_serving_fact (TODAY, 8 fact types)
```

## UI PAGE → ENDPOINT → TABLE MAP

| UI Page | Endpoint | Primary Tables | Fresh Today? |
|---------|----------|---------------|-------------|
| **Overview** | `/operational-summary` | driver_state_snapshot, eligibility, prioritized, queue, capacity, loopcontrol | YES |
| **Segments** | `/driver-state/summary` | driver_state_snapshot | YES |
| **Programs** | `/programs/status` | eligibility, prioritized, queue | YES |
| **Queue** | `/assignment-queue/summary` | assignment_queue, loopcontrol, capacity | YES |
| **Today Action Plan** | `/today-action-plan` | ALL (composes 4 services) | YES |
| **Movement** | `/movement/summary` | state_transition_trace, program_decision_trace, list_history | PARTIAL |
| **Governance** | `/governance/*` | freshness_registry, refresh_run_log, program_registry | YES |
| **Operational Truth** | `/operational-truth` | driver_state, eligibility, prioritized, queue, loopcontrol, policy | YES |
| **RNA** | `/yango-loyalty/*` | ops.* loyalty tables, public.trips_* | YES |

## Tables NOT Consumed by UI

| Table | Why Not? |
|-------|---------|
| growth.yego_lima_v2_* (all 9) | V2 SHADOW — pipeline certification, not production |
| growth.driver_movement_fact | Autonomous tick shadow — separate from UI movement endpoint |
| growth.yango_lima_driver_history_weekly | Weekly aggregation, not consumed by any UI endpoint directly |
| ops.driver_daily_activity_fact | Omniview source, not Lima Growth UI source |

## Freshness Reality (2026-06-11 21:25 Lima)

| Table | Max Date | Age | UI Impact? |
|-------|----------|-----|-----------|
| driver_state_snapshot | 2026-06-11 | 0h | HIGH — Overview, Segments |
| program_eligibility | 2026-06-11 | 0h | HIGH — Programs, Overview |
| prioritized_opportunity | 2026-06-11 | 0h | HIGH — Programs, Overview |
| assignment_queue | 2026-06-11 | 0h | HIGH — Queue, Overview |
| serving_fact | 2026-06-11 | 0h | HIGH — Serving-first cache |
| lifecycle_daily | 2026-06-10 | ~30h | LOW — Indirect via state snapshot |
| raw_orders | 2026-06-09 | ~54h | LOW — Intermediate, not UI-facing |
| driver_history_weekly | 2026-06-01 | ~240h | NONE — No UI consumption |
