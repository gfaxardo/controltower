# LG-UX-0A — DRIVER JOURNEY MAP

**Date:** 2026-06-11

---

## DRIVER LIFECYCLE THROUGH THE SYSTEM

```
                    ┌──────────────────────┐
                    │   Yango API Event     │
                    │  (first trip / order) │
                    └──────────┬───────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│ 1. INGESTION                                                     │
│                                                                   │
│ Driver appears in:                                                │
│   growth.yango_lima_orders_raw                                   │
│   → driver_profile_id, order_id, ended_at, price, mileage        │
│                                                                   │
│ Activity tracked in:                                              │
│   growth.yango_lima_driver_history_daily                         │
│   → date, driver_profile_id, completed_orders, gross_revenue     │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│ 2. STATE SNAPSHOT                                                │
│                                                                   │
│ Every 5 minutes, autonomous_tick builds:                          │
│   growth.yango_lima_driver_state_snapshot                        │
│                                                                   │
│ Driver now has:                                                   │
│   lifecycle_state:    ACTIVE / NEW / AT_RISK / DECLINING /       │
│                       CHURNED / REACTIVATED / INACTIVE           │
│   performance_state:  ABOVE_TARGET / BELOW_TARGET / NO_DATA      │
│   retention_state:    STABLE / DECLINING / NEW / UNKNOWN         │
│   completed_orders_day / week                                     │
│   supply_hours_day / week                                         │
│   avg_orders_4w / 12w                                             │
│   best_week_12w                                                   │
│   distance_to_weekly_target                                       │
│   new_driver_flag, reactivated_flag,                             │
│   recoverable_flag, declining_flag                               │
│                                                                   │
│ 18,545 unique drivers TODAY                                       │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│ 3. LIFECYCLE CLASSIFICATION (Daily)                              │
│                                                                   │
│   growth.yego_lima_driver_lifecycle_daily                        │
│                                                                   │
│ Driver classified into lifecycle_status:                          │
│   - NEW_ACTIVE: hired recently, building trips                   │
│   - ACTIVE: consistent trip activity                             │
│   - AT_RISK: trip decline detected                               │
│   - DECLINING: sustained downward trend                          │
│   - CHURNED: no trips > 30 days                                  │
│   - REACTIVATED: returned after churn                            │
│   - INACTIVE: registered, never completed trip                   │
│                                                                   │
│ Evidence:                                                         │
│   completed_trips_7d, completed_trips_14d, completed_trips_30d   │
│   days_since_last_completed_trip                                  │
│   lifecycle_reason, evidence_json                                │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│ 4. TAXONOMY CLASSIFICATION                                       │
│                                                                   │
│   growth.yego_lima_driver_taxonomy_v2_daily                      │
│                                                                   │
│ Driver gets multi-layer classification:                           │
│                                                                   │
│   Layer 1: OPERATIONAL STATUS                                     │
│     └── Based on lifecycle_status                                 │
│                                                                   │
│   Layer 2: ACTIVITY STATUS (sub-segment)                          │
│     └── Based on trip volumes: heavy/regular/occasional/light     │
│                                                                   │
│   Layer 3: VALUE OVERLAY (value_tier)                             │
│     └── Based on historical revenue percentile                    │
│                                                                   │
│   Layer 4: MOMENTUM (momentum_state)                              │
│     └── Based on trip trend direction: rising/falling/stable      │
│                                                                   │
│   Layer 5: OPERATIONAL PERSONA                                    │
│     └── Combined: "HIGH_VALUE_RISING_ACTIVE" etc.                │
│                                                                   │
│ EXPLAINABLE: driver_taxonomy_v2_explanation                       │
│   → matched_rules_json, failed_rules_json, evidence_json         │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│ 5. PROGRAM ELIGIBILITY                                           │
│                                                                   │
│   growth.yango_lima_program_eligibility_daily                    │
│                                                                   │
│ Driver checked against 4 programs:                                │
│                                                                   │
│   PROGRAM_HIGH_VALUE_RECOVERY (Priority 1)                        │
│     → Who: High historical value, recently inactive              │
│     → Why: Recovery of valuable drivers                          │
│                                                                   │
│   PROGRAM_CHURN_PREVENTION (Priority 2)                           │
│     → Who: Drivers at risk of churning                           │
│     → Why: Prevent loss before it happens                        │
│                                                                   │
│   PROGRAM_14_90 (Priority 3)                                      │
│     → Who: New/reactivated drivers in 14-90 day window           │
│     → Why: Stabilize new entrants                                 │
│                                                                   │
│   PROGRAM_ACTIVE_GROWTH (Priority 4)                              │
│     → Who: Active drivers below weekly target                    │
│     → Why: Boost productivity                                    │
│                                                                   │
│ Each driver may be eligible for 0-4 programs.                     │
│   TODAY: 28,128 eligibility records across 18,545 drivers         │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│ 6. PRIORITIZATION                                                │
│                                                                   │
│   growth.yango_lima_prioritized_opportunity_daily                │
│                                                                   │
│ Among eligible drivers, policy engine selects:                    │
│   → selected_program_code (highest priority match)               │
│   → opportunity_type (HIGH_VALUE / CHURN_RISK / ONBOARDING)     │
│   → priority (urgency score)                                     │
│   → value_tier, risk_tier                                        │
│   → is_actionable_today (boolean)                                │
│                                                                   │
│ Capacity limits per program:                                      │
│   HVR: priority 1, daily cap from policy_config                  │
│   Churn: priority 2                                               │
│   14_90: priority 3                                               │
│   Active Growth: priority 4                                       │
│                                                                   │
│   TODAY: 5,383 prioritized, subset are actionable                │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│ 7. QUEUE ASSIGNMENT                                              │
│                                                                   │
│   growth.yego_lima_assignment_queue                              │
│                                                                   │
│ Actionable drivers are assigned to channels:                      │
│   → channel: LoopControl (call center)                           │
│   → status: READY → EXPORTED                                     │
│   → priority_rank within program                                 │
│                                                                   │
│ Capacity-constrained:                                             │
│   → 3 channels, agents, capacity_per_agent                       │
│   → Unassigned drivers held with reason                          │
│                                                                   │
│   TODAY: 52 READY in queue                                        │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│ 8. EXPORT TO LOOPCONTROL                                         │
│                                                                   │
│   growth.yango_lima_loopcontrol_campaign_export                  │
│                                                                   │
│ READY drivers exported to LoopControl call center:                │
│   → campaign_id_external, contacts_sent                          │
│   → export_status: SUCCESS / PARTIAL / FAILED                    │
│                                                                   │
│   TOTAL: 54 exports on record                                     │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│ 9. CONTROL LOOP                                                  │
│                                                                   │
│   growth.yego_lima_control_loop_state                            │
│                                                                   │
│ After export, driver workflow tracked:                            │
│   ASSIGNED → CONTACTED → DONE                                    │
│                                                                   │
│   Per driver: agent, channel, notes, days_in_current_state       │
│                                                                   │
│   Intraday monitoring:                                            │
│     growth.yego_lima_intraday_driver_signal                       │
│     → Detects if contacted driver completed trips after contact  │
│     → reactivation_detected, activity_detected_today flags       │
│                                                                   │
│   TODAY: 668 drivers in control loop                              │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│ 10. HISTORY & OUTCOME                                            │
│                                                                   │
│   growth.yego_lima_driver_list_history                           │
│                                                                   │
│ Complete audit trail per driver:                                  │
│   → program_code, priority_rank, queue_status                    │
│   → assigned_channel, exported_at                                │
│   → action_status (CONTACTED / DONE / EXPIRED)                   │
│                                                                   │
│   TODAY: 1,104 history records                                    │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│ 11. MOVEMENT DETECTION                                           │
│                                                                   │
│   growth.yego_lima_state_transition_trace                        │
│   growth.yego_lima_program_decision_trace                        │
│                                                                   │
│ Driver movement between states tracked:                           │
│   → ENTERED program, EXITED program, STATE_CHANGE                │
│   → trigger_reason, rule_delta_json                              │
│                                                                   │
│   TOTAL: 1,205 transitions + 5,558 decisions                     │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│ 12. RNA (Registered Not Activated) — Yango Loyalty              │
│                                                                   │
│   ops.mv_driver_lifecycle_monthly_kpis                           │
│   public.trips_2026                                              │
│                                                                   │
│ RNA drivers: registered on platform, never completed a trip       │
│   → N (new registrations) + R (reactivatable = churned >30d)    │
│   → Contactability: phone available?                             │
│   → Cancelled signals: drivers who cancelled after contact       │
│   → Root causes: onboarding friction, payment, trust             │
│                                                                   │
│ Separate system: Yango Loyalty endpoints                          │
└──────────────────────────────────────────────────────────────────┘
```

## DRIVER JOURNEY SUMMARY

```
Yango API Event
  → Ingestion (every 5 min)
    → State Snapshot (every 5 min, TODAY data)
      → Lifecycle Classification (daily, T-1 data)
        → Taxonomy (daily, 5-layer persona)
          → Program Eligibility (every 5 min, 4 programs)
            → Prioritization (policy engine, daily capacity)
              → Queue Assignment (channel, status)
                → Export to LoopControl (call center)
                  → Control Loop (ASSIGNED → CONTACTED → DONE)
                    → History & Outcome
                      → Movement Detection
                        → (RNA path: Loyalty system, separate)
```
