# BEHAVIORAL MVP VALIDATION

**Date**: 2025-05-25
**Status**: FRAMEWORK — awaiting operational sessions

---

## 1. Classification Accuracy

### 7 Statuses to validate

| Status | Threshold | Validation method |
|---|---|---|
| `churned` | days_since_last ≥ 30 | Compare against known churned driver list |
| `inactive_risk` | days_since_last ≥ 14 | Track if these drivers actually churn within 30 days |
| `at_risk` | delta_pct ≤ -40% | Verify with city managers — "Is this driver really at risk?" |
| `declining` | delta_pct ≤ -25% | Check if decline is temporary (holiday) or sustained |
| `top` | trips_per_day ≥ 5 AND active ≥ 30% days | Compare against known top drivers list |
| `growing` | delta_pct ≥ +25% | Verify growth is real (not returning from absence) |
| `stable` | default | Is "stable" too broad? Does it hide problems? |

---

## 2. Questions for Operators

### Classification sense
- Q1: "Do the 'at_risk' drivers match who you'd flag manually?" → Expected: >80% match
- Q2: "Are there drivers you'd flag as at_risk but the system says 'stable'?" → Document each case
- Q3: "Is the 'churned' classification too late at 30 days?" → Should it be earlier?

### Dominant factor clarity
- Q4: "Does the explanation (e.g. 'Caida severa de viajes (-45%)') make sense?" → Expected: "Yes, I understand why"
- Q5: "Would you prefer more detail in the explanation?" → What detail?

### Signal gaps
- Q6: "What ONE missing signal would make this most useful?" → Record top-3 answers
- Q7: "Would 'revenue per driver' change your decisions?" → Decision impact assessment

---

## 3. False Positive Audit

### Known risk patterns
| Pattern | Expected frequency | Actual frequency (fill) |
|---|---|---|
| Holiday drop classified as "declining" | Weekly (seasonal) | _ |
| New driver growth spike classified as "growing" | Daily | _ |
| Weekend-only driver classified as "inactive_risk" (5 days since last weekday) | ~10% of weekend drivers | _ |
| Top driver temporary absence (vacation) classified as at_risk | Occasional | _ |
| Park switch causing "declining" in old park | During rebalancing | _ |

---

## 4. False Negative Audit

### Should have been detected but wasn't
| Missing case | Why system missed it |
|---|---|
| Driver with stable trips but deteriorating acceptance | No acceptance signal |
| Driver earning less despite same trips (price changes) | No revenue signal |
| Driver working same days but fewer peak hours | No trip_hour signal |
| Driver switching from premium to economy zones | No zone signal |

---

## 5. Severity Calibration

| Current | Question |
|---|---|
| `at_risk` → severity: critical | Is "critical" alarming? Should it be "elevated"? |
| `declining` → severity: elevated/warning | Is the -35% threshold for "elevated" correct? |
| `inactive_risk` → severity: warning | Should it be higher? Inactivity is precursor to churn. |

---

## Validation Matrix (to be filled)

| Metric | Value |
|---|---|
| Classification accuracy (operator match) | _ / 100 |
| False positive rate | _ % |
| False negative rate (missing cases) | _ cases |
| Most useful status for operators | _ |
| Least useful status | _ |
| Most requested missing signal | _ |
| Panel load time (seconds) | _ |
