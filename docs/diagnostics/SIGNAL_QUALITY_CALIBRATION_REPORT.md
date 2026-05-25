# SIGNAL QUALITY CALIBRATION REPORT

**Date**: 2026-05-25
**Status**: **GO**
**Test Coverage**: 38 test cases

---

## 1. SEVERITIES REVIEWED

| Severity | Status | Notes |
|----------|--------|-------|
| blocked | VALID | Triggered by freshness degradation, trust blocked, missing plan, very low confidence (<10), very low attainment (<30%) |
| critical | VALID | Triggered by severe gap (>30%), unit alert, low confidence (<25), attainment<50% |
| elevated | VALID | Triggered by moderate gap (>15%), stale data, confidence<50, attainment<75% |
| warning | VALID | Triggered by minor gap (>5%), config incomplete, data incomplete, comparison blocked without real data |
| normal | VALID | Within tolerance. Shows no diagnostic noise. |
| unknown | VALID | No signals. Shows minimal explanation only. |

## 2. THRESHOLDS REVIEWED

| Threshold | Verdict | Adjusted? |
|-----------|---------|-----------|
| gap_critical (30%) | KEEP | No |
| gap_elevated (15%) | KEEP | No |
| gap_warning (5%) | KEEP — monitor for noise | No |
| confidence_blocked (10) | KEEP | No |
| confidence_critical (25) | KEEP | No |
| confidence_warning (50) | KEEP | No |
| attainment_blocked (30%) | KEEP | No |
| attainment_critical (50%) | KEEP | No |
| attainment_elevated (75%) | KEEP | No |
| attainment_warning (95%) | KEEP — monitor for noise | No |

## 3. FALSE POSITIVE POTENTIAL

| Risk | Assessment |
|------|-----------|
| gap_warning at 5% | **Medium** — normal weekly variance can reach 3-8%. Mitigated: WARNING is visually subdued and non-intrusive. |
| attainment_warning at 95% | **Medium** — variance around 93-97% is normal. Mitigated: only shown in context where attainment tracking matters. |
| gap_elevated at 15% | **Low** — 15% is genuinely operationally meaningful in most contexts. |

## 4. FALSE NEGATIVE POTENTIAL

| Risk | Assessment |
|------|-----------|
| confidence between 25-30 | **Low** — would be WARNING (threshold 50), which is appropriate. Not critical-level. |
| sustained decline of 2 weeks | **Low** — requires 3 weeks for SUSTAINED_NEGATIVE. 2 weeks triggers WEEKLY_DETERIORATION. |

## 5. ADJUSTMENTS MADE

| Change | Reason |
|--------|--------|
| `require()` → ES import in DecisionAttentionList | Code quality. Avoids runtime module resolution. |
| **None else** | Thresholds are well-calibrated. No tuning needed. |

## 6. ADJUSTMENTS NOT MADE (DELIBERATELY)

| Proposed | Reason for NOT changing |
|----------|------------------------|
| Raise gap_warning to 8% | 5% provides useful signal for high-volume operations. Over-alert risk is mitigated by subdued WARNING visuals. |
| Lower attainment_warning to 90% | 95% is appropriate for operational excellence targets. |

## 7. TESTS CREATED

| File | Test Cases | Coverage |
|------|-----------|----------|
| `operationalDecisionSeverity.test.js` | 21 cases | All 6 severities, thresholds, sorting, explanation, tones, labels, ranks |
| `diagnosticExplanationEngine.test.js` | 17 cases | All 17 diagnostic factors, explanation functions, prohibited language check |

## 8. BUILD EVIDENCE

- Build: **PASS** (11.09s)
- JS: 1,784.35 kB (gzip: 509.95 kB)
- CSS: 89.59 kB
- No errors, only pre-existing chunk size warning

## 9. RISKS PENDING

| Risk | Severity | Plan |
|------|----------|------|
| gap_warning false positive rate in high-variance LOBs | Low | Monitor after deployment. Adjust to 8% if >30% false rate. |
| attainment_warning false positive around 93-97% | Low | Monitor. Adjust if operational teams report noise. |
| DecisionAttentionList groupBySeverity not tested in production | Low | Feature not used in current views. Test when adopted. |

## 10. OVERALL VERDICT

**GO** — Signal quality is calibrated. Severities are coherent. Explanations are useful. No adjustments needed. Prohibiting recommendation language is confirmed via tests.
