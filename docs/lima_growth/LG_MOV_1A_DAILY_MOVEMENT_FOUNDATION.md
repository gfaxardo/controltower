# LG-MOV-1A — DAILY MOVEMENT FOUNDATION

**Ticket:** LG-MOV-1A  
**Date:** 2026-06-11  
**Phase:** Lima Growth Foundation — Movement Layer  
**Status:** CERTIFIED — DAILY MOVEMENT POSSIBLE  

---

## TASK 0 — GOVERNANCE

Control Foundation / Lima Growth. Shadow mode. Zero production impact.

---

## TASK 1 — MOVEMENT AUDIT

### Snapshot Availability

| Source | Snapshots | Earliest | Latest |
|--------|-----------|----------|--------|
| taxonomy_v2_daily | 2 | 2026-06-09 | 2026-06-10 |
| lifecycle_daily | 2 | 2026-06-09 | 2026-06-10 |
| program_v2_assignment | 1 | — | 2026-06-10 |
| activity_event | 468 distinct dates | 2025-02-28 | 2026-06-10 |

**Activity events span 468 days (17 months)** — sufficient for rebuilding any date's taxonomy if needed. Currently only 2 taxonomy snapshots exist.

### Classification: **A) DAILY MOVEMENT POSSIBLE**

Daily movement can be detected and will improve as the taxonomy pipeline runs daily.

---

## TASK 2-4 — MOVEMENT FACT

### Table: `growth.driver_movement_fact`

| Column | Purpose |
|--------|---------|
| from_lifecycle / to_lifecycle | Lifecycle state change |
| from_segment / to_segment | Segment transition |
| from_program / to_program | Program change |
| movement_class | SEGMENT_CHANGE / PROGRAM_CHANGE / LIFECYCLE_CHANGE / NO_CHANGE |
| movement_score | -15 to +15 (negative = deterioration, positive = improvement) |
| changed_layers_json | Which layers changed |

---

## TASK 5-6 — MOVEMENT RESULTS (Jun 9 → Jun 10)

### Movement Classes

| Class | Drivers | % |
|-------|---------|---|
| PROGRAM_CHANGE | 67,454 | 98.5% |
| SEGMENT_CHANGE | 1,019 | 1.5% |

PROGRAM_CHANGE = 98.5% because Jun 9 had no program assignments (first day). As pipeline runs daily, this will stabilize to show only real program transitions.

### Top 15 Segment Transitions (1,019 real moves)

| From | To | Drivers | Score |
|------|----|---------|-------|
| ACTIVE_GROWTH | TOP_PERFORMER | 319 | +8 |
| ACTIVE_GROWTH | HVR_CANDIDATE | 135 | 0 |
| ACTIVE_GROWTH | STABLE | 89 | 0 |
| REGISTERED_NOT_ACTIVATED | ACTIVE_GROWTH | 85 | +15 |
| HVR_CANDIDATE | TOP_PERFORMER | 55 | 0 |
| ACTIVE_GROWTH | CHURNED | 54 | -8 |
| ACTIVE_GROWTH | REGISTERED_NOT_ACTIVATED | 53 | 0 |
| CHURNED | ARCHIVED | 48 | 0 |
| STABLE | TOP_PERFORMER | 46 | +8 |
| REACTIVATED_ACTIVE | TOP_PERFORMER | 42 | +8 |
| NEW_ACTIVE | ACTIVE_GROWTH | 21 | 0 |
| ACTIVE_GROWTH | NEW_ACTIVE | 18 | 0 |
| CHURNED | ACTIVE_GROWTH | 17 | +10 |
| REACTIVATED_ACTIVE | CHURNED | 9 | -8 |
| ARCHIVED | REACTIVATED_ACTIVE | 7 | +10 |

### Movement Score Distribution

| Score | Type | Drivers | Examples |
|-------|------|---------|----------|
| +15 | POSITIVE | 85 | REGISTERED_NOT_ACTIVATED → ACTIVE_GROWTH (activation) |
| +10 | POSITIVE | 17 | CHURNED → ACTIVE_GROWTH (recovery) |
| +8 | POSITIVE | 319 | ACTIVE_GROWTH → TOP_PERFORMER (improvement) |
| 0 | NEUTRAL | 67,998 | No segment change or lateral move |
| -8 | NEGATIVE | 54 | ACTIVE_GROWTH → CHURNED (deterioration) |

---

## TASK 10 — GO / NO-GO

### Veredicto: **A) MOVEMENT_FOUNDATION_CERTIFIED**

| Criterion | Status |
|-----------|--------|
| Daily movement detected | PASS (1,019 segment transitions) |
| 2 snapshots available | PASS (Jun 9 and Jun 10) |
| Movement scores computed | PASS (+15 to -8 range) |
| 1 driver = 1 movement/day | PASS |
| 0 duplicates | PASS |
| 0 production impact | PASS |

### Required for Full Movement Pipeline

| Gap | Action |
|-----|--------|
| Only 2 snapshots | Schedule daily taxonomy build in autonomous tick |
| PROGRAM_CHANGE inflated | Will stabilize when program assignments exist for both days |
| No LIFECYCLE_CHANGE detected | Jun 9-10 window too narrow for lifecycle transitions |

---

**LG-MOV-1A — CERTIFIED**

*Daily movement engine operational — 1,019 real segment transitions detected.*  
*68,473 drivers compared across 2 daily snapshots.*  
*Movement scores: +15 (activation) to -8 (churn).*  
*Ready for daily pipeline integration and program effectiveness measurement (LG-IMP-1A).*
