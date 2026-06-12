# LG-UX-0A — DECISION MAP

**Date:** 2026-06-11

---

## DECISIONS THE SYSTEM ENABLES TODAY

### 1. CONTACTAR (Contact)

| Attribute | Value |
|-----------|-------|
| **Decision** | ¿A quién contactar hoy? |
| **Data** | prioritized_opportunity_daily → is_actionable_today = true |
| **Logic** | Policy engine: weekly_target=42 trips, capacity per program, priority scoring |
| **Evidence** | driver_state: distance_to_weekly_target, completed_orders_week, lifecycle_state |
| **Action** | Export to LoopControl call center |
| **Endpoint** | POST /assignment-queue/build → POST /assignment-queue/export |

### 2. RECUPERAR (Recover)

| Attribute | Value |
|-----------|-------|
| **Decision** | ¿Qué drivers de alto valor están inactivos? |
| **Data** | program_eligibility_daily → PROGRAM_HIGH_VALUE_RECOVERY |
| **Logic** | High historical value + recently inactive (no trips in window) |
| **Evidence** | driver_state: value_tier, completed_orders_30d, best_week_12w |
| **Action** | Assign to HVR program, prioritize for contact |
| **Endpoint** | GET /programs/status → HVR counts |

### 3. ACTIVAR (Activate)

| Attribute | Value |
|-----------|-------|
| **Decision** | ¿Qué nuevos drivers necesitan impulso? |
| **Data** | program_eligibility_daily → PROGRAM_14_90 |
| **Logic** | New or reactivated drivers within 14-90 day window |
| **Evidence** | driver_state: new_driver_flag, reactivated_flag, days_since_first_trip |
| **Action** | Assign to 14_90 program, prioritize onboarding contact |
| **Endpoint** | GET /programs/status → 14_90 counts |

### 4. PRIORIZAR (Prioritize)

| Attribute | Value |
|-----------|-------|
| **Decision** | ¿En qué orden contactar? |
| **Data** | prioritized_opportunity_daily → priority, final_rank |
| **Logic** | Multi-factor: value_tier × risk_tier × opportunity_score × program priority |
| **Evidence** | priority_score components from policy_config |
| **Action** | Queue ordered by priority_rank, exported in order |
| **Endpoint** | GET /assignment-queue/summary → priority distribution |

### 5. MONITOREAR (Monitor)

| Attribute | Value |
|-----------|-------|
| **Decision** | ¿El sistema está sano? |
| **Data** | freshness_registry + serving_fact + scheduler_status |
| **Logic** | Component-level freshness vs SLA thresholds |
| **Evidence** | latency_minutes, max_data_date, tick_count, success_count |
| **Action** | Alert if CRITICAL, verify scheduler running |
| **Endpoint** | GET /growth/health → system_status |

### 6. SEGUIMIENTO (Follow-up)

| Attribute | Value |
|-----------|-------|
| **Decision** | ¿Se contactó? ¿Mejoró? |
| **Data** | control_loop_state (current_state) + intraday_driver_signal (activity_detected) |
| **Logic** | If CONTACTED and activity_detected_today → positive outcome |
| **Evidence** | trips_after_action, first_trip_after_action_at, reactivation_detected |
| **Action** | Mark DONE in control loop, record in list_history |
| **Endpoint** | GET /governance/health → loop status |

### 7. RETENER (Retain)

| Attribute | Value |
|-----------|-------|
| **Decision** | ¿Qué drivers activos están en riesgo de irse? |
| **Data** | program_eligibility_daily → PROGRAM_CHURN_PREVENTION |
| **Logic** | Active drivers showing trip decline below threshold |
| **Evidence** | driver_state: declining_flag, completed_orders_7d vs avg_orders_4w |
| **Action** | Assign to Churn Prevention, contact before they leave |
| **Endpoint** | GET /programs/status → Churn Prevention counts |

### 8. CRECER (Grow)

| Attribute | Value |
|-----------|-------|
| **Decision** | ¿Qué drivers activos pueden producir más? |
| **Data** | program_eligibility_daily → PROGRAM_ACTIVE_GROWTH |
| **Logic** | Active drivers below weekly_trips_target (42 trips) |
| **Evidence** | driver_state: completed_orders_week, distance_to_weekly_target, supply_hours |
| **Action** | Assign to Active Growth, contact to boost volume |
| **Endpoint** | GET /programs/status → Active Growth counts |

### 9. ENTENDER (Understand)

| Attribute | Value |
|-----------|-------|
| **Decision** | ¿Por qué este driver está en este programa/segmento? |
| **Data** | taxonomy_v2_explanation + program_decision_trace |
| **Logic** | matched_rules_json shows which rules triggered classification |
| **Evidence** | evidence_json, selection_reason, trigger_reason |
| **Action** | Display "Why" in driver detail view |
| **Endpoint** | GET /driver-history/{driver_id} → explainability data |

## DECISION FLOW SUMMARY

```
Universe (18,545 drivers)
  → Eligible (28,128 eligibility records, drivers may be in 0-4 programs)
    → Prioritized (5,383 opportunities, ranked)
      → Actionable (subset within daily capacity)
        → Assigned to Queue (52 READY today)
          → Exported to LoopControl (54 total exports)
            → CONTACTED (control loop: 668 in workflow)
              → DONE / IMPROVED / NO_CHANGE / WORSE
                → History recorded (1,104 records)
```
