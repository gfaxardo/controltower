# WEEKLY VIEW SIGNAL QUALITY QA

**Date**: 2026-05-25

---

## VERIFICATION

| Check | Result | Notes |
|-------|--------|-------|
| Critical alerts sorted to top (via DecisionPriorityStrip) | PASS | Strip shows blocked/critical counts first |
| Blocked alerts not lost | PASS | Freshness blocked alerts retain severity |
| Warning alerts don't dominate | PASS | Warning is visually lighter (amber, not red) |
| Normal alerts produce no noise | PASS | DiagnosticDominantFactor returns null for normal |
| Explanation doesn't break layout | PASS | 1-line inline format: "Critical due to {factor}: {detail}" |
| Tooltip doesn't cover table | PASS | DiagnosticBreakdownTooltip not used in alert cards (kept as standard severity badge) |
| Sorting doesn't alter base data | PASS | Original data untouched; routing is read-only |
| gap_*_pct conversion is correct | PASS | Extractor multiplies 0-1 range by 100 to match percentage thresholds |
| Unit alert → CRITICAL | PASS | Confirmed via severity contract |
| Revenue gap → severity + explanation | PASS | Gap magnitude maps to correct severity tier |
| DecisionPriorityStrip renders counts | PASS | Shows "X blocked", "Y critical", "Z elevated" |

## OVER-ALERT CHECK

| Scenario | Expected Severity | Would Over-Alert? |
|----------|------------------|-------------------|
| gap_trips=-6%, gap_revenue=-4%, no unit_alert | WARNING | No — appropriate for minor deviation |
| gap_unitario=-2%, no other gaps | UNKNOWN | No — small gap, no signals → unknown (correct) |
| Freshness stale, all gaps within range | ELEVATED | No — stale data is genuinely elevated |
| All metrics green, trust OK | NORMAL | No — normal shows nothing (correct) |

## VERDICT: GO

No over-alerting detected. Explanations are appropriate and compact.
