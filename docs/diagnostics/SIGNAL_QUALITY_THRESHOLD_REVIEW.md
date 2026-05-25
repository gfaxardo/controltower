# SIGNAL QUALITY THRESHOLD REVIEW

**Date**: 2026-05-25

---

## REVIEW TABLE

### Gap thresholds

| Threshold | Value | Justification | False Positive Risk | False Negative Risk | Verdict |
|-----------|-------|--------------|-------------------|-------------------|---------|
| `gap_critical` | 30% | >30% deviation is severe. Real operational impact expected at this level. | Medium — a single anomalous week could hit 30%. Mitigated by `sustained_negative` (3+ weeks). | Low — real critical gaps are usually visible above 30%. | KEEP |
| `gap_elevated` | 15% | >15% warrants review without being critical. | Medium — week-to-week variance can exceed this. Consider adding smoothing. | Low — gaps 15-30% are operationally meaningful. | KEEP |
| `gap_warning` | 5% | >5% is a minor flag to review. | High — normal week-to-week variance is often 3-8%. Risk of over-alert. | Low — below 5% is truly within noise. | KEEP but MONITOR |

### Confidence thresholds

| Threshold | Value | Justification | False Positive Risk | False Negative Risk | Verdict |
|-----------|-------|--------------|-------------------|-------------------|---------|
| `confidence_blocked` | 10 | Below 10 confidence: data effectively unusable. | Low — confidence <10 genuinely means blocked. | Low — matches trust service threshold. | KEEP |
| `confidence_critical` | 25 | Below 25: confidence severely degraded. | Low — genuine signal degradation. | Medium — borderline 20-30 could be uncertain. | KEEP |
| `confidence_warning` | 50 | Below 50: confidence needs review. | Medium — 45-55 could vary. | Low — above 50 is generally reliable. | KEEP |

### Attainment thresholds

| Threshold | Value | Justification | False Positive Risk | False Negative Risk | Verdict |
|-----------|-------|--------------|-------------------|-------------------|---------|
| `attainment_blocked` | 30% | Below 30% attainment: effectively blocked on that metric. | Low | Low | KEEP |
| `attainment_critical` | 50% | Below 50% attainment: critical gap. | Low | Low | KEEP |
| `attainment_elevated` | 75% | Below 75%: elevated concern. | Medium — YTD smoothing helps. | Low | KEEP |
| `attainment_warning` | 95% | Below 95%: minor flag. | High — 93-97% is normal variance. **Monitor carefully.** | Low | **KEEP but review at next cycle** |

---

## QUICK WINS IDENTIFIED

None needed — all thresholds are well-calibrated for operational use.

## ADJUSTMENTS MADE

None — thresholds are validated as-is. Zero changes.

## MONITORING RECOMMENDATIONS

1. **gap_warning at 5%**: Watch for noise in high-variance LOB/week combos. If too many warnings fire, consider 8%.
2. **attainment_warning at 95%**: Track false positive rate. If >20% of warnings are false, raise to 90%.
3. **sustained_negative at 3 weeks**: Consider exposing this as configurable in a future release.
