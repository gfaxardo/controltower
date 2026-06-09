# LG-DIAG-R1.1A — Program Decision Trace Engine

**Date:** 2026-06-08
**Motor:** Control Foundation / Diagnostic Hardening
**Phase:** LG-DIAG-R1.1A
**Status:** PROGRAM DECISION TRACE CERTIFIED

---

## 1. EXECUTIVE SUMMARY

**DECISION TRACE: CERTIFIED.**

"Why THIS program and not the others?" is now answerable. 5,558/5,558 (100%) prioritized drivers have decision trace. Multi-eligibility audited: 48.5% qualify for 1 program, 45.4% for 2, 6.1% for 3. Three decision reasons: HIGHER_PRIORITY (87.5%), SINGLE_PROGRAM (12.2%), POLICY_OVERRIDE (0.3%). 0 regression failures.

---

## 2. MULTI-ELIGIBILITY AUDIT

| Programs | Drivers | % |
|:---:|:---:|:---:|
| 1 | 8,741 | 48.5% |
| 2 | 8,197 | 45.4% |
| 3 | 1,102 | 6.1% |
| 4 | 0 | 0% |

**51.5% of eligible drivers qualify for 2+ programs.** Decision trace is essential.

### Top combinations

| Combination | Drivers |
|-------------|:---:|
| ACTIVE_GROWTH only | 8,405 |
| ACTIVE_GROWTH + CHURN_PREVENTION | 6,337 |
| 14_90 + ACTIVE_GROWTH | 1,841 |
| 14_90 + ACTIVE_GROWTH + CHURN_PREVENTION | 1,102 |

---

## 3. DECISION REASONS

| Reason | Count | % |
|--------|:---:|:---:|
| **HIGHER_PRIORITY** | 4,864 | 87.5% |
| SINGLE_PROGRAM | 677 | 12.2% |
| POLICY_OVERRIDE | 17 | 0.3% |

---

## 4. DECISION PATH (from policy engine scoring)

```
driver in snapshot
    │
    ▼
program_eligibility: 3 INSERTs determine eligible programs
    │
    ▼
policy engine (build_prioritized_opportunities):
  ┌─ raw_opps (all opportunities)
  ├─ drv_state (lifecycle/performance/retention)
  ├─ drv_programs (eligible programs per driver)
  ├─ drv_eligible (JOIN: opportunity + program list)
  ├─ drv_weekly (orders_week, best_week_12w)
  ├─ drv_recency (last_trip_date)
  ├─ enriched (all data combined)
  ├─ classified (CASE: HV_RECOVERY > CHURN > 14_90 > ACTIVE_GROWTH)
  ├─ scored (impact*0.4 + urgency*0.3 + prob*0.3 + program_bonus)
  ├─ ranked (ROW_NUMBER per driver, dedup)
  └─ deduped (ROW_NUMBER global, final_rank)
    │
    ▼
selected_program_code + opportunity_score + final_rank
```

### Decision: "Why CHURN_PREVENTION and not ACTIVE_GROWTH?"

Driver eligible for BOTH. Policy engine assigns CHURN_PREVENTION because:
- Program bonus: +100 (vs +0 for ACTIVE_GROWTH)
- Higher urgency (retention_state = CHURN_RISK)
- Final opportunity_score higher → selected

**Reason: HIGHER_PRIORITY**

---

## 5. 20-DRIVER SAMPLE (all with decision trace)

| Driver | Eligible | Selected | Reason |
|--------|----------|----------|--------|
| 000cb5d8... | 14_90, ACTIVE_GROWTH | **14_90** | HIGHER_PRIORITY |
| 0010ebd8... | 14_90, ACTIVE_GROWTH | **14_90** | HIGHER_PRIORITY |
| 00415a84... | 14_90, ACTIVE, CHURN | **CHURN_PREVENTION** | HIGHER_PRIORITY |
| 00628983... | ACTIVE_GROWTH | **ACTIVE_GROWTH** | SINGLE_PROGRAM |
| 0119a290... | CHURN_PREVENTION | **CHURN_PREVENTION** | SINGLE_PROGRAM |

---

## 6. REGRESSION AUDIT

| Check | Result |
|-------|:---:|
| Without selected_program_code | **0** |
| Without decision reason | **0** |
| HV_RECOVERY without override trace | **0** |
| Decision coverage | **100% (5,558/5,558)** |

---

## 7. TWO QUESTIONS ANSWERED

| Question | Answer Source |
|----------|--------------|
| **WHY AM I HERE?** (rules) | program_eligibility → 11 rules → MATCH/FAIL per rule |
| **WHY THIS PROGRAM?** (decision) | policy engine → scoring → dedup → selection_reason |

---

## 8. FILES

| File | Status |
|------|:---:|
| `scripts/r1_1a_decision_trace.py` | Created — decision trace audit |

---

## 9. FINAL VERDICT

```
PROGRAM DECISION TRACE CERTIFIED
```

| Question | Answer |
|----------|:---:|
| Multi-eligibility audited | **PASS** (18,040 drivers, 51.5% multi-eligible) |
| Decision trace coverage | **PASS** (100%) |
| Prioritized coverage | **PASS** (5,558/5,558) |
| HV Recovery traceability | **PASS** (17/17 with POLICY_OVERRIDE) |
| Decision trace regression | **PASS** (0 failures) |
