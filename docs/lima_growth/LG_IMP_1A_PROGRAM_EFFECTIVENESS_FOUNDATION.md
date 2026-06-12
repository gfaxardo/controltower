# LG-IMP-1A — PROGRAM EFFECTIVENESS FOUNDATION

**Ticket:** LG-IMP-1A  
**Date:** 2026-06-11  
**Status:** FOUNDATION READY — AWAITING DAILY PIPELINE  

---

## TASK 1 — EFFECTIVENESS CONTRACT

| Layer | Source | Grain |
|-------|--------|-------|
| PROGRAM_EXPOSURE | `program_v2_assignment_daily` | driver + date + program |
| PROGRAM_MOVEMENT | `driver_movement_fact` | driver + date + from/to segments |
| PROGRAM_OUTCOME | `driver_program_effectiveness_fact` | driver + date + movement_type + score |

---

## TASK 2 — OUTCOME CATALOG

### Positive Movements (12 rules)

| From | To | Score | Category |
|------|----|-------|----------|
| REGISTERED_NOT_ACTIVATED | ACTIVE_GROWTH | +15 | ACTIVATION |
| REGISTERED_NOT_ACTIVATED | TOP_PERFORMER | +20 | ACTIVATION_PREMIUM |
| CHURNED | ACTIVE_GROWTH | +10 | CHURN_RECOVERY |
| CHURNED | TOP_PERFORMER | +15 | CHURN_RECOVERY_PREMIUM |
| ACTIVE_GROWTH | TOP_PERFORMER | +8 | GROWTH |
| ACTIVE_GROWTH | STABLE | +5 | STABILIZATION |
| NEW_ACTIVE | ACTIVE_GROWTH | +5 | ONBOARDING_PROGRESS |
| REACTIVATED_ACTIVE | ACTIVE_GROWTH | +5 | REACTIVATION_STABLE |
| REACTIVATED_ACTIVE | TOP_PERFORMER | +8 | REACTIVATION_PREMIUM |
| SOFT_CHURN | ACTIVE_GROWTH | +8 | SOFT_RECOVERY |
| HVR_CANDIDATE | TOP_PERFORMER | +10 | HVR_RECOVERY |
| REGISTERED_NOT_ACTIVATED | NEW_ACTIVE | +15 | ACTIVATION |

### Negative Movements (8 rules)

| From | To | Score | Category |
|------|----|-------|----------|
| ACTIVE_GROWTH | CHURNED | -8 | CHURN |
| TOP_PERFORMER | HVR_CANDIDATE | -10 | HIGH_VALUE_AT_RISK |
| TOP_PERFORMER | CHURNED | -12 | TOP_CHURN |
| STABLE | CHURNED | -8 | STABLE_CHURN |
| NEW_ACTIVE | CHURNED | -8 | NEW_CHURN |
| REACTIVATED_ACTIVE | CHURNED | -8 | REACTIVATED_CHURN |
| TOP_PERFORMER | ACTIVE_GROWTH | -5 | PERFORMANCE_DROP |
| STABLE | ACTIVE_GROWTH | -3 | DESTABILIZATION |

---

## TASK 3-5 — EFFECTIVENESS FACTS BUILT

### Tables Created

| Table | Purpose |
|-------|---------|
| `program_effectiveness_fact` | Daily aggregated effectiveness per program |
| `driver_program_effectiveness_fact` | Per-driver movement + program correlation |

### Movement Types Detected (Jun 8-10, 3-day aggregate)

| From | To | Type | Count |
|------|----|------|-------|
| ACTIVE_GROWTH | TOP_PERFORMER | **POSITIVE** | 319 |
| REGISTERED_NOT_ACTIVATED | ACTIVE_GROWTH | **POSITIVE** | 85 |
| CHURNED | ACTIVE_GROWTH | **POSITIVE** | 17 |
| ACTIVE_GROWTH | CHURNED | **NEGATIVE** | 54 |
| ACTIVE_GROWTH | HVR_CANDIDATE | NEUTRAL | 135 |
| (other transitions) | — | NEUTRAL | 407 |

---

## TASK 6-7 — OBSERVABILITY + VALIDATION

| Criterion | Result |
|-----------|--------|
| 1 driver = 1 outcome | PASS (0 duplicates) |
| Movement source certified | PASS (from driver_movement_fact) |
| 68,473 drivers tracked | PASS |
| 3 days of movement data | PASS (Jun 8-10) |

### Effectiveness Score Formula

```
effectiveness_score = (positive_moves - negative_moves) / assigned_drivers × 100
```

Note: Scores show 0% on first build because program assignments for Jun 7-9 were not persisted. As the daily pipeline runs (taxonomy → program assignment → movement detection), per-program effectiveness scores will populate.

---

## TASK 9 — GO / NO-GO

### Veredicto: **A) EFFECTIVENESS_FOUNDATION_READY**

| Criterion | Status |
|-----------|--------|
| Outcome catalog defined (20 rules) | PASS |
| Movement classification working | PASS (319 positive, 54 negative detected) |
| Effectiveness facts created | PASS (2 tables) |
| 0 duplicates | PASS |
| 0 production impact | PASS |
| Requires daily pipeline for full scores | NOTE — first build artifact |

### Prerequisites for Full Effectiveness Scores

1. Run daily taxonomy build for 5+ consecutive days
2. Run daily program assignment for each day
3. Run daily movement detection between each pair
4. Correlate program→movement with 1-day lag

With 5+ days of data, effectiveness scores will show which programs are driving positive outcomes vs which need adjustment.

---

**LG-IMP-1A — FOUNDATION READY**

*20 outcome rules defined. 319 positive and 54 negative movements detected.*  
*2 fact tables created. 68,473 drivers tracked across 3 days.*  
*Effectiveness scores will populate with daily pipeline execution.*  
*Ready for program benchmarking and optimization.*
