# LG-UX-0A — EXPLAINABILITY MAP

**Date:** 2026-06-11

---

## WHAT IS EXPLAINABLE TODAY

### 1. LIFECYCLE — "¿Por qué este lifecycle_status?"

| Element | Available | Source |
|---------|-----------|--------|
| Why ACTIVE? | YES | lifecycle_reason + evidence_json in driver_lifecycle_daily |
| Why AT_RISK? | YES | completed_trips_7d/14d/30d, days_since_last_completed_trip |
| Why CHURNED? | YES | days_since_last_completed_trip > 30, no trips |
| Why REACTIVATED? | YES | reactivated_flag, first_completed_trip_date |
| Why DECLINING? | YES | trip decline vs historical avg |
| Trace per driver | YES | lifecycle_event (48K rows) with previous → new status transitions |
| Version | YES | lifecycle_version column |

**Engine:** `yego_lima_driver_lifecycle_daily` + `yego_lima_driver_lifecycle_event`

### 2. SEGMENT / TAXONOMY — "¿Por qué este segmento?"

| Element | Available | Source |
|---------|-----------|--------|
| Why this operational_status? | YES | taxonomy_v2_explanation (342K rows) → matched_rules_json |
| Why this activity_status? | YES | matched_rules_json shows trip thresholds met |
| Why this value_tier? | YES | value_percentile calculation, evidence_json |
| Why this momentum_state? | YES | trip trend over 4-week windows |
| Why this operational_persona? | YES | Combined: all 5 layers with matched + failed rules |
| Which rules were checked? | YES | 18 rules in taxonomy_v2_config across 5 layers |
| Which rules PASSED? | YES | matched_rules_json per driver per layer |
| Which rules FAILED? | YES | failed_rules_json per driver per layer |

**Engine:** `growth.yego_lima_driver_taxonomy_v2_explanation` + `taxonomy_v2_config`

### 3. PROGRAM — "¿Por qué este programa?"

| Element | Available | Source |
|---------|-----------|--------|
| Why eligible? | YES | eligibility_reason in program_eligibility_daily |
| Why NOT eligible? | PARTIAL | Not directly stored; inferred from absent records |
| Why this priority? | YES | opportunity_score, final_rank in program_decision_trace |
| Why selected over others? | YES | selection_reason + eligible_programs_json in decision_trace |
| Program rules | YES | 4 active programs in program_registry |
| Decision trace | YES | program_decision_trace (5,558 decisions) |
| V2 explainability | YES | program_v2_registry (10 programs with config_json rules) |

**Engine:** `program_eligibility_daily` + `program_decision_trace` + `program_registry`

### 4. MOVEMENT — "¿Por qué se movió?"

| Element | Available | Source |
|---------|-----------|--------|
| State transitions | YES | state_transition_trace → trigger_reason, rule_delta_json |
| Program changes | YES | program_decision_trace → selection_reason |
| Entries/Exits | YES | transition_type (ENTERED / EXITED / STATE_CHANGE) |
| Membership | YES | driver_list_history → action_date, program_code, queue_status |
| V2 movement | PARTIAL | driver_movement_fact + program_v2_assignment_transition (shadow) |

**Engine:** `state_transition_trace` + `program_decision_trace` + `driver_list_history`

### 5. RNA — "¿Por qué no activó?"

| Element | Available | Source |
|---------|-----------|--------|
| RNA count | YES | Loyalty KPIs from ops.mv_driver_lifecycle_monthly_kpis |
| Contactability | YES | phone available via driver_data |
| Cancelled signals | YES | Cancelled trip events |
| Root causes | PARTIAL | Manual KPI table, not automated |
| City comparison | YES | Loyalty performance by city |

**Engine:** `yango_loyalty_*` services + `ops.*` views

### 6. EFFECTIVENESS — "¿Funcionó el contacto?"

| Element | Available | Source |
|---------|-----------|--------|
| Pre/post trips | YES | ops.driver_campaign_effectiveness → trips_before / trips_after |
| Reactivation | YES | reactivated_flag, days_to_first_trip_after |
| Campaign summary | YES | campaign_id, total_members, reactivated_count |
| V2 effectiveness | PARTIAL | V2 shadow table (0 rows, no active campaigns) |

**Engine:** `ops.driver_campaign_effectiveness` + `ops.driver_campaigns`

### 7. V2 SHADOW EXPLAINABILITY

| Element | Available | Source |
|---------|-----------|--------|
| Activity trend | YES | activity_trend in v2_activity_* tables (based on completed_trips thresholds) |
| Lifecycle churn risk | YES | churn_risk in v2_lifecycle_daily |
| Program classification | YES | eligibility_reason + program_name in v2_program_daily |
| Movement trigger | YES | trigger_reason in v2_movement_fact |

**Note:** V2 is shadow mode, not consumed by production UI.

---

## EXPLAINABILITY COVERAGE SUMMARY

| Domain | Explainable? | Coverage |
|--------|-------------|----------|
| Lifecycle | YES | lifecycle_reason + evidence_json per driver |
| Segment/Taxonomy | YES | matched_rules + failed_rules per layer, 342K explanations |
| Program | YES | eligibility_reason + selection_reason per driver |
| Movement | YES | trigger_reason + rule_delta per transition |
| RNA | PARTIAL | Counts exist, root causes are manual |
| Effectiveness | YES | Pre/post metrics per campaign member |
| **Why anything?** | **YES** | Most decisions have traceable evidence |

---

## "WHY" API

For any driver, the explainability chain is:

```
GET /driver-history/{driver_id}
  → lifecycle_state with lifecycle_reason
  → taxonomy segment with matched_rules (from explanation table)
  → program assignments with selection_reason (from decision trace)
  → movement history with trigger_reason (from transition trace)

GET /programs/status?date=
  → per-program eligibility counts

GET /governance/programs
  → program registry with descriptions and priorities
```
