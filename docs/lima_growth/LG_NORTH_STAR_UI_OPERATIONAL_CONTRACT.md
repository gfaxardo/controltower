# Lima Growth Machine — UI Operational North Star

**Version:** 1.0.0
**Date:** 2026-06-14
**Status:** DEFINITIVE
**Reference:** LG-UI-NORTH-1A

---

## 1. Core Principle

Lima Growth Machine backend core is certified closed. But the product is NOT complete until the operator can see, understand, and act on the lists through a UI — without SQL, without CSV, without terminal commands.

**The product = lists + explainability + export + UI visibility + action context.**

---

## 2. Minimum UI Requirements

### 2.1 Daily Universe Overview

The operator must see at a glance:
- Total drivers
- Exportable drivers
- Non-exportable drivers
- Count by universe (9 universes)
- Freshness date (generated_date)
- Active Control Loop batch ID

### 2.2 Actionable Lists

Universes to work:
1. NEW_REACTIVATED_0_14_TO_50
2. RAMP_UP_15_45_TO_100W
3. CONSOLIDATION_46_90_TO_100W
4. ACTIVE_GROWTH_90_PLUS_BAND_UP
5. RECOVERY_RECENT_INACTIVE_HIGH_VALUE
6. RECOVERY_RECENT_INACTIVE_LOW_VALUE

Do NOT work:
- CEMETERY_LONG_CHURNED
- PROTECTED_ALREADY_MEETING_GOAL
- NO_DATA_OR_NO_ACTION

### 2.3 Driver Table

Each row must show minimum:
- driver_profile_id / driver_id
- name/phone if contract allows
- assigned_universe_v1
- reason_text (human-readable why)
- recommended_action_category
- weekly_trips
- gap_to_target
- productivity_band
- value_tier
- Control Loop status
- latest generated_date

### 2.4 Driver Drilldown

On click:
- Profile: age, inactivity, value, band, trend
- Evidence: evidence_json, reason_code, objective
- Target: target_metric, baseline_metric, gap
- Exit: exit_condition, movement_hint
- History: transition types, dates, previous/current universes
- Actions: Control Loop action entries (agent, date, status, notes)

### 2.5 Movement Dashboard

Transition summary:
- STAYED_IN_LIST
- PROTECTED_GOAL_MET
- EXITED_GOAL_MET
- MOVED_UP_BAND / MOVED_DOWN_BAND
- MOVED_TO_RECOVERY / MOVED_TO_CEMETERY
- RECOVERED_TO_ACTIVE
- BECAME_EXPORTABLE / NO_LONGER_EXPORTABLE

### 2.6 Alerts

UI must alert when:
- Worklist is stale (generated_date behind)
- Transition fact is stale
- Control Loop batch does not match current date
- Goal attainment violations exist
- reason_text or evidence_json is missing
- Exportable drivers have no Control Loop status

### 2.7 Action Evidence Readback

Read-only access to Control Loop actions taken:
- Agent assigned
- Action date
- State (READY, CONTACTED, DONE, etc.)
- Notes
- Outcome

This is NOT the Action Engine. It is visibility of actions already taken.

---

## 3. What This Does NOT Open

- Action Engine (write/automation)
- Diagnostic Engine
- Forecast/Suggestion/Decision/AI/Learning
- Program Registry V3
- State Machine completa
- New assignment rules or thresholds

---

*UI is not optional. The product is not complete until the operator can see it.*
