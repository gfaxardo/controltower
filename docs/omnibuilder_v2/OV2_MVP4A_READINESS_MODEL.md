# OV2-MVP.4A — READINESS MODEL

> **Fase:** OV2-MVP.4A — Deprecation Preparation
> **Sub-document:** Readiness Model
> **Fecha:** 2026-06-12

---

## 1. CLASSIFICATION

| Level | Definition | Action |
|-------|-----------|--------|
| **NOT_READY** | Trial not completed or score < 70 | Continue build/trial. No cutover. |
| **READY_WITH_GAPS** | Trial completed, score 70-84 | Proceed with cutover but keep V1 highly visible. |
| **READY_FOR_CUTOVER** | Trial completed, score ≥ 85, all criteria met | Execute cutover. Activate V1_LEGACY_MODE. |

---

## 2. VARIABLES

| Variable | Source | Weight | Target |
|----------|--------|--------|--------|
| `acceptance_score` | ov2_mvp3a_compute_acceptance_score.py | — | ≥ 85 |
| `v2_v1_ratio` | /ops/omniview-v2/usage-metrics | — | ≥ 3:1 |
| `confidence_score` | Operator survey | — | ≥ 4.0 |
| `open_p0` | Friction log | — | 0 |
| `open_p1` | Friction log | — | ≤ 5 |
| `rollback_ready` | Rollback runbook tested | — | YES |
| `source_ready` | CF-H2H status | — | Not required (V2 uses CT) |
| `training_complete` | Training session done | — | YES |
| `trial_executed` | Trial completed 2 weeks | — | YES |

---

## 3. READINESS FORMULA

```
readiness = (
    (acceptance_score >= 85) AND
    (v2_v1_ratio >= 3.0) AND
    (confidence_score >= 4.0) AND
    (open_p0 == 0) AND
    (open_p1 <= 5) AND
    (rollback_ready == YES) AND
    (training_complete == YES) AND
    (trial_executed == YES)
)

IF readiness:
    classification = READY_FOR_CUTOVER
ELIF acceptance_score >= 70 AND trial_executed:
    classification = READY_WITH_GAPS
ELSE:
    classification = NOT_READY
```

---

## 4. CURRENT STATE (pre-trial)

| Variable | Current | Target | Status |
|----------|---------|--------|--------|
| acceptance_score | 90.1 (pre-trial estimate) | ≥ 85 | ✓ |
| v2_v1_ratio | 0 (trial not started) | ≥ 3:1 | ✗ |
| confidence_score | 0 (not surveyed) | ≥ 4.0 | ✗ |
| open_p0 | 0 | 0 | ✓ |
| open_p1 | 0 | ≤ 5 | ✓ |
| rollback_ready | Design done, not tested | YES | ✗ |
| source_ready | N/A (CT is default) | N/A | ✓ |
| training_complete | Guide created, session pending | YES | ✗ |
| trial_executed | NOT STARTED | YES | ✗ |

**Current classification: NOT_READY (trial not executed)**

---

## 5. EXPECTED PROGRESSION

| Milestone | Expected Date | Classification |
|-----------|--------------|----------------|
| Trial starts | 2026-06-16 | NOT_READY |
| Trial week 1 complete | 2026-06-20 | NOT_READY → READY_WITH_GAPS |
| Trial week 2 complete | 2026-06-27 | READY_WITH_GAPS → READY_FOR_CUTOVER |
| Cutover checklist complete | 2026-06-30 | READY_FOR_CUTOVER |
| V1_LEGACY_MODE active | TBD (post-approval) | CUTOVER EXECUTED |

---

## 6. GATE DECISIONS

| Gate | Decision Point | Criteria |
|------|---------------|----------|
| G1: Open trial | NOW | Trial infra ready |
| G2: End week 1 | 2026-06-20 | score ≥ 80, ratio ≥ 2:1 |
| G3: End trial | 2026-06-27 | score ≥ 85, ratio ≥ 3:1, conf ≥ 4.0 |
| G4: Cutover | 2026-06-30 | All checklist items YES |
| G5: V1 removal | 30 days post-cutover | 0 V1 usage, 0 regressions |

---

## 7. ANSWER TO "WHAT'S MISSING?"

| # | Gap | Phase |
|---|-----|-------|
| 1 | Trial execution (2 weeks) | OV2-MVP.3A (in progress) |
| 2 | V1_LEGACY_MODE implementation | OV2-MVP.4 |
| 3 | Rollback test | OV2-MVP.4 |
| 4 | Training session | OV2-MVP.4 |
| 5 | Cutover signoffs | OV2-MVP.4 |
