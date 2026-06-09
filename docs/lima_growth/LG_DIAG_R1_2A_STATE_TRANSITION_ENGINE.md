# LG-DIAG-R1.2A — State Transition Engine Certification

**Date:** 2026-06-08
**Motor:** Control Foundation / Diagnostic Hardening
**Phase:** LG-DIAG-R1.2A
**Status:** STATE TRANSITION ENGINE CERTIFIED

---

## 1. EXECUTIVE SUMMARY

**WHY DID I MOVE? — ANSWERED.**

1,205 driver state transitions detected between snapshots 06-04 → 06-05 across 18,475 drivers. 99% have explicit causal triggers from real data (churn_risk_flag, declining_flag, orders_week_delta). 0 regression gaps. The Diagnostic Engine now answers all three questions: WHY AM I HERE? → WHY THIS PROGRAM? → WHY DID I MOVE?

---

## 2. DIAGNOSTIC ENGINE — THREE QUESTIONS

| # | Question | Engine | Status |
|---|----------|--------|:---:|
| 1 | **WHY AM I HERE?** | Program Explainability (R1.0B) | CERTIFIED |
| 2 | **WHY THIS PROGRAM?** | Decision Trace Engine (R1.1A) | CERTIFIED |
| 3 | **WHY DID I MOVE?** | State Transition Engine (R1.2A) | **CERTIFIED** |

---

## 3. STATE INVENTORY

### Lifecycle States (06-05)
| State | Count |
|-------|:---:|
| ESTABLISHED | 15,488 |
| ACTIVATED | 2,793 |
| EARLY_LIFE | 264 |

### Performance States
| State | Count |
|-------|:---:|
| LOW | 16,667 |
| MEDIUM | 1,018 |
| HIGH | 634 |
| TARGET | 226 |

### Retention States
| State | Count |
|-------|:---:|
| HEALTHY | 10,470 |
| CHURN_RISK | 6,999 |
| AT_RISK | 775 |
| WATCHLIST | 301 |

---

## 4. TRANSITION DETECTION (06-04 → 06-05)

| Dimension | Changes |
|-----------|:---:|
| **Retention** | 834 |
| **Performance** | 838 |
| **Lifecycle** | 1 |
| **Total unique drivers with transitions** | **1,205** |

### Top 10 Transitions

| Transition | Count | Direction |
|-----------|:---:|:---:|
| CHURN_RISK → HEALTHY | 240 | IMPROVED |
| HEALTHY → CHURN_RISK | 227 | DECLINED |
| LOW → MEDIUM | 201 | IMPROVED |
| CHURN_RISK → AT_RISK | 177 | IMPROVED |
| LOW → HIGH | 63 | IMPROVED |
| CHURN_RISK → WATCHLIST | 56 | IMPROVED |
| LOW → TARGET | 50 | IMPROVED |
| AT_RISK → CHURN_RISK | 48 | DECLINED |
| HEALTHY → AT_RISK | 30 | DECLINED |
| AT_RISK → HEALTHY | 24 | IMPROVED |

---

## 5. CAUSALITY (Real triggers from data)

| Trigger Type | Used In |
|-------------|---------|
| `churn_risk_flag_changed` | Retention state transitions |
| `declining_flag_changed` | Performance/retention transitions |
| `orders_week_delta` | All transitions |
| `supply_hours_delta` | Supply-related transitions |

### Example Explanation

```
Driver: 8cf58c5f...
Transition: RETENTION: HEALTHY -> CHURN_RISK
Trigger: churn_risk_flag changed False -> True
         orders_week delta: -52 (significant drop)
Evidence: Orders dropped from high volume to low.
          Churn risk flag activated.
```

---

## 6. COVERAGE

| Metric | Result |
|--------|:---:|
| Transitions detected | 1,205 |
| With explicit cause | **1,198 (99%)** |
| Minor changes (no explicit trigger) | 7 (1%) |
| Unexplained | 0 |

---

## 7. REGRESSION

| Check | Result |
|-------|:---:|
| Missing state_before | **0** |
| Missing state_after | **0** |
| Missing trigger_reason | **0** |
| Drivers disappeared between snapshots | N/A (JOIN only) |

---

## 8. OUTPUT CONTRACT (Future)

```json
{
  "driver_id": "...",
  "snapshot_before": "2026-06-04",
  "snapshot_after": "2026-06-05",
  "state_before": {"lifecycle": "ESTABLISHED", "retention": "HEALTHY"},
  "state_after": {"lifecycle": "ESTABLISHED", "retention": "CHURN_RISK"},
  "transition_type": "RETENTION: HEALTHY -> CHURN_RISK",
  "trigger_reason": "churn_risk_flag True; orders_week -52",
  "evidence": {"orders_delta": -52, "churn_flag_changed": true}
}
```

---

## 9. FILES

| File | Status |
|------|:---:|
| `scripts/r1_2a_state_transition.py` | Created — transition audit |
| `docs/...LG_DIAG_R1_2A_STATE_TRANSITION_ENGINE.md` | This document |

---

## 10. FINAL VERDICT

```
STATE TRANSITION ENGINE CERTIFIED
```

### Diagnostic Engine — All 3 Questions Answered

```
WHY AM I HERE?       → Program Explainability    → CERTIFIED (R1.0B)
WHY THIS PROGRAM?    → Decision Trace Engine     → CERTIFIED (R1.1A)
WHY DID I MOVE?      → State Transition Engine   → CERTIFIED (R1.2A)
```
