# YANGO LOYALTY SIGNAL QUALITY QA

**Date**: 2026-05-25

---

## VERIFICATION

| Check | Result | Notes |
|-------|--------|-------|
| No critical severity without strong signal | PASS | Only meets_oro=false + attainment <50% can trigger critical |
| Config incomplete → WARNING (not critical) | PASS | `has_any_targets: false` → WARNING via severity contract |
| Freshness blocked → BLOCKED | PASS | Mapped correctly in severity contract |
| No recommendations in explanation text | PASS | DiagnosticDominantFactor uses diagnostic engine, no prohibited language |
| No screen overload | PASS | Only shows when warnings exist; normal state shows nothing |
| City ranking PriorityStrip works | PASS | Shows severity counts per city category |
| Banners replaced by DiagnosticDominantFactor | PASS | Config/data warnings show as compact diagnostic explanation |
| City accordions still functional | PASS | No regression from diagnostic layer |

## OVER-ALERT CHECK

| Scenario | Expected Severity | Would Over-Alert? |
|----------|------------------|-------------------|
| All cities Oro, data complete | NORMAL | No — normal shows nothing |
| 2 cities Plata, config OK | WARNING | No — correct for non-Oro cities |
| No targets configured | WARNING | No — correct. Could be ELEVATED if blocking operations, but WARNING is appropriate |
| Data incomplete, 3 KPIs pending | WARNING | No — correct for incomplete data |

## VERDICT: GO

No over-alerting. Diagnostic explanations are appropriate.
