# LG-UX-0A — WORKFLOW MAP

**Date:** 2026-06-11

---

## COMPLETE OPERATIONAL WORKFLOW

### INPUT → PROCESS → OUTPUT → DECISION

```
┌─────────────────────────────────────────────────────────────────┐
│                        YANGO API                                 │
│  orders_raw, driver_profiles_raw, supply_api, productivity_api  │
│  (Every 5 min via autonomous_tick)                              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    INGESTION LAYER                               │
│                                                                  │
│  INPUT:  Yango API raw data                                     │
│  PROCESS: Incremental upsert into growth.yango_lima_*           │
│  OUTPUT:  driver_history_daily (520K rows, rolling)             │
│           driver_history_weekly (135K rows, W22)                │
│           orders_raw (12K rows, last Jun 9)                     │
│  WRITER:  autonomous_tick (every 5 min)                         │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    STATE LAYER                                   │
│                                                                  │
│  INPUT:  driver_history_daily + Yango API                       │
│  PROCESS: build_driver_state_snapshot(date)                      │
│  OUTPUT:  driver_state_snapshot (148K rows, TODAY)              │
│           Per driver: lifecycle_state, performance_state,       │
│           retention_state, completed_orders, supply_hours,      │
│           weekly_target, distance_to_target, flags              │
│  WRITER:  autonomous_tick (every 5 min)                         │
│  DECISION: ¿Está activo? ¿Está en riesgo? ¿Es recuperable?     │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   LIFECYCLE LAYER                                │
│                                                                  │
│  INPUT:  driver_state_snapshot + historical orders              │
│  PROCESS: classify lifecycle_status per driver                  │
│  OUTPUT:  driver_lifecycle_daily (273K rows, T-1)              │
│           lifecycle_event (48K rows)                            │
│           Statuses + anchor dates + trip windows                │
│  WRITER:  autonomous_tick (daily pipeline)                      │
│  EXPLAIN: lifecycle_reason, evidence_json per driver            │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   TAXONOMY LAYER                                 │
│                                                                  │
│  INPUT:  driver_lifecycle_daily                                  │
│  PROCESS: taxonomy classification (18 rules, 5 layers)          │
│  OUTPUT:  driver_taxonomy_v2_daily (273K rows)                  │
│           Per driver: operational_status, segment, value_tier,  │
│           momentum_state, operational_persona                   │
│  EXPLAIN: driver_taxonomy_v2_explanation (342K rows)            │
│           matched_rules_json, failed_rules_json, evidence_json  │
│  DECISION: ¿Qué tipo de driver es? ¿Cuál es su valor?          │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   PROGRAM LAYER                                  │
│                                                                  │
│  INPUT:  driver_state_snapshot                                  │
│  PROCESS: build_program_eligibility(date)                        │
│           Each driver checked against 4 program rules           │
│  OUTPUT:  program_eligibility_daily (226K rows, TODAY)          │
│           Per driver: program_code, eligible_flag, reason       │
│  WRITER:  autonomous_tick                                       │
│  EXPLAIN: eligibility_reason per driver per program             │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                PRIORITIZATION LAYER                              │
│                                                                  │
│  INPUT:  program_eligibility_daily + policy_config              │
│  PROCESS: build_prioritized_opportunities(date)                 │
│           Policy: weekly_target=42, capacity limits per program │
│  OUTPUT:  prioritized_opportunity_daily (44K rows, TODAY)       │
│           Per driver: selected_program, opportunity_type,       │
│           priority, value_tier, risk_tier                       │
│           ACTIONABLE: is_actionable_today flag                  │
│  DECISION: ¿A quién contactar hoy? ¿En qué orden?              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   QUEUE LAYER                                    │
│                                                                  │
│  INPUT:  prioritized_opportunity_daily + capacity_config        │
│  PROCESS: create_assignment_batch(date)                          │
│           Capacity: 3 channels, agents, limits                  │
│  OUTPUT:  assignment_queue (2,104 rows, TODAY)                  │
│           Per driver: program, priority, channel, status        │
│           Status: READY (52), HELD, EXPORTED                    │
│  WRITER:  daily_refresh_service                                 │
│  DECISION: ¿Qué se envió a LoopControl? ¿Qué quedó pendiente?  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   EXPORT LAYER                                   │
│                                                                  │
│  INPUT:  assignment_queue (READY drivers)                       │
│  PROCESS: export_from_contacts() → LoopControl API              │
│  OUTPUT:  loopcontrol_campaign_export (54 rows)                 │
│           loopcontrol_export_job_run (3 runs)                   │
│  DECISION: ¿Se entregaron los contactos al call center?        │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                CONTROL LOOP LAYER                                │
│                                                                  │
│  INPUT:  assignment_queue + loopcontrol_result_sync             │
│  PROCESS: Track ASSIGNED → CONTACTED → DONE workflow            │
│  OUTPUT:  control_loop_state (668 rows)                         │
│           Per driver: current_state, agent, channel, notes      │
│           intraday_driver_signal (310) for activity detection   │
│  DECISION: ¿Se contactó? ¿Qué resultado? ¿Requiere seguimiento?│
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                  SERVING LAYER                                   │
│                                                                  │
│  INPUT:  All above outputs                                      │
│  PROCESS: generate_all_serving_facts(date)                      │
│  OUTPUT:  serving_fact (48 rows, TODAY, 8 fact types)           │
│           Types: operational_summary, today_action_plan,        │
│           programs_summary, driver_state_summary,               │
│           queue_summary, allocation_trace, policy, refresh      │
│  SERVES:  Overview, Segments, Programs, Queue, Action Plan     │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    UI LAYER                                      │
│                                                                  │
│  CONSUMES:  serving_fact OR direct DB queries                   │
│  ENDPOINTS: 21 Lima Growth endpoints                            │
│  PAGES:     Overview, Segments, Programs, Queue, Movement,      │
│             Today Action Plan, Operational Truth, Governance    │
│  AUTH:      No auth required (internal tool)                    │
└─────────────────────────────────────────────────────────────────┘
```

## V2 SHADOW PIPELINE (Parallel, Not Production)

```
Activity Event → Lifecycle → Taxonomy V2 → Program V2 → Movement → Observability → Effectiveness
(9 steps, daily 04:45, writes to growth.yego_lima_v2_* shadow tables)
Status: CERTIFIED, operational, 0 UI consumption
```

## KEY DECISION POINTS

| # | Decision | Data Source | Consumer |
|---|----------|------------|----------|
| 1 | ¿Está activo? | driver_state_snapshot lifecycle_state | Operations |
| 2 | ¿Está en riesgo? | driver_state_snapshot declining_flag | Operations |
| 3 | ¿Es recuperable? | driver_state_snapshot recoverable_flag | Operations |
| 4 | ¿Qué programa? | program_eligibility_daily | Operations |
| 5 | ¿A quién contactar hoy? | prioritized_opportunity_daily is_actionable_today | Agent |
| 6 | ¿Qué canal? | assignment_queue assigned_channel | Agent |
| 7 | ¿Se contactó? | control_loop_state current_state | Supervisor |
| 8 | ¿Mejoró? | driver_list_history + intraday_signal | Impact analysis |
| 9 | ¿Sistema sano? | freshness_registry + serving_fact | Ops manager |
