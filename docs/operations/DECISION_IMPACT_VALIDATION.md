# DECISION IMPACT VALIDATION

**Date**: 2025-05-25
**Purpose**: Separate insights that drive real decisions from decorative information

---

## 1. DECISION IMPACT FRAMEWORK

Each insight/feature is classified:

| Impact Level | Definition |
|---|---|
| **DECISION** | Directly triggers an operational action (call, rebalance, investigate) |
| **AWARENESS** | Increases understanding but doesn't trigger immediate action |
| **DECORATION** | Present but never acted upon; could be removed without operational loss |

---

## 2. FEATURE IMPACT CLASSIFICATION

### Momentum
| Feature | Expected Impact | Actual (fill) |
|---|---|---|
| DoD same-weekday | DECISION — "Friday down → check Saturday staffing" | _ |
| WoW | AWARENESS — "Trend is negative" | _ |
| MoM | AWARENESS — "Seasonal pattern" | _ |
| Priority strip top-5 | DECISION — "Top 3 cities need attention" | _ |
| Consecutive decline | DECISION — "3 weeks declining → escalation" | _ |
| Momentum drill chart | AWARENESS — "Visual trend confirmation" | _ |

### Projection (Plan vs Real)
| Feature | Expected Impact | Actual (fill) |
|---|---|---|
| Attainment % | DECISION — "At 72% → need more drivers" | _ |
| Gap value | DECISION — "Short by 50 trips → adjust targets" | _ |
| YTD summary | AWARENESS — "Year outlook" | _ |
| Integrity banner | DECISION — "Data is broken → don't trust" | _ |
| Projection drill | AWARENESS — "Root cause analysis" | _ |

### Behavioral MVP
| Feature | Expected Impact | Actual (fill) |
|---|---|---|
| at_risk classification | DECISION — "Flag this driver for attention" | _ |
| declining classification | AWARENESS — "Monitor this driver" | _ |
| top classification | AWARENESS — "Benchmark reference" | _ |
| inactive_risk | DECISION — "Contact driver before churn" | _ |
| dominant_factor | AWARENESS — "Why this driver is declining" | _ |

---

## 3. DECISION TRIGGER EXAMPLES

### High-value decision triggers (to validate)

| Trigger | Expected decision | Reality (fill) |
|---|---|---|
| City trips DoD ▼ > 15% | Call city manager | _ |
| Driver at_risk with 3 consecutive declines | Contact driver / incentive review | _ |
| Attainment < 75% for current week | Rebalance supply to city | _ |
| Integrity BROKEN status | Stop using data; contact data team | _ |
| 5+ inactive_risk drivers in same city | Investigate city supply issue | _ |

### Low-value (likely decorative)

| Feature | Why likely decorative |
|---|---|
| Zoom control | Changed once, never again |
| Focus mode dimming | Looks cool, not operationally needed |
| Density toggle | Set once, forgotten |
| FACT tables panel | Technical detail, not operational |

---

## 4. INSIGHT UTILITY MATRIX

After 3+ sessions, classify each feature:

```
FEATURE                  USED?    TRIGGERED ACTION?    KEEP?    NOTES
─────────────────────────────────────────────────────────────────────
DoD same-weekday          Y/N         Y/N              Y/N      ...
WoW                        Y/N         Y/N              Y/N      ...
MoM                        Y/N         Y/N              Y/N      ...
Priority strip             Y/N         Y/N              Y/N      ...
Attainment %               Y/N         Y/N              Y/N      ...
Gap value                  Y/N         Y/N              Y/N      ...
Momentum drill             Y/N         Y/N              Y/N      ...
Projection drill           Y/N         Y/N              Y/N      ...
Behavioral panel           Y/N         Y/N              Y/N      ...
Weekday focus              Y/N         Y/N              Y/N      ...
Fullscreen                 Y/N         Y/N              Y/N      ...
Zoom                       Y/N         Y/N              Y/N      ...
Focus mode                 Y/N         Y/N              Y/N      ...
Insight mode               Y/N         Y/N              Y/N      ...
```

---

## Validation Summary (to be filled)

| Metric | Value |
|---|---|
| Features classified as DECISION | _ |
| Features classified as AWARENESS | _ |
| Features classified as DECORATION | _ |
| % of critical alerts that triggered action | _ |
| Most actionable feature | _ |
| Least useful feature | _ |
