# DIAGNOSTIC LAYER — Architecture Map

**Date**: 2026-05-25
**Status**: STABLE — CLOSED

---

## Layer Stack

```
┌────────────────────────────────────────────────┐
│  VIEW LAYER (consumers)                        │
│  WeeklyPlanVsRealView  YangoLoyaltyView        │
├────────────────────────────────────────────────┤
│  VISUAL COMPONENTS (diagnostics/)              │
│  DiagnosticDominantFactor                      │
│  DiagnosticBreakdownTooltip                    │
│  DiagnosticExplanationCard                     │
│  DiagnosticFactorBadge                         │
│  DiagnosticReasonList                          │
├────────────────────────────────────────────────┤
│  VISUAL COMPONENTS (operational/)              │
│  DecisionSeverityBadge                         │
│  DecisionPriorityStrip                         │
│  DecisionAttentionList                         │
│  DecisionAttentionHeader                       │
│  DecisionSignalTooltip                         │
├────────────────────────────────────────────────┤
│  UTILITIES                                      │
│  diagnosticExplanationEngine.js                │
│  operationalAttentionRouting.js                │
│  operationalDecisionSeverity.js                │
├────────────────────────────────────────────────┤
│  EXISTING DATA (read-only)                     │
│  Phase2B weekly alerts  Yango Loyalty API      │
│  Freshness service   Trust/Confidence service  │
└────────────────────────────────────────────────┘
```

---

## Severity Contract (`operationalDecisionSeverity.js`)

| Constant | Values |
|----------|--------|
| `DECISION_SEVERITY` | blocked, critical, elevated, warning, normal, unknown |
| `DECISION_PRIORITY_ORDER` | 0→blocked, 1→critical, 2→elevated, 3→warning, 4→normal, 5→unknown |
| `DECISION_THRESHOLDS` | gap_* (30/15/5), confidence_* (10/25/50), attainment_* (30/50/75/95) |

### Pure functions
- `normalizeDecisionSignal(input)` → canonical severity
- `getDecisionSeverity(entity)` → severity
- `getDecisionTone(severity)` → color object
- `getDecisionLabel(severity)` → "Blocked" etc.
- `getDecisionRank(severity)` → numeric rank
- `sortByDecisionPriority(items)` → sorted array
- `explainDecisionSeverity(input)` → {severity, label, reasons}

---

## Attention Routing (`operationalAttentionRouting.js`)

- `partitionBySeverity(items)` → {blocked, critical, elevated, warning, normal, unknown}
- `stablePrioritySort(items)` → ordered array
- `getAttentionSummary(items)` → counts per severity
- `getAttentionRatio(items)` → % needing attention

---

## Explanation Engine (`diagnosticExplanationEngine.js`)

### 17 Official Diagnostic Factors

**System Integrity**: freshness_degraded, trust_degraded, missing_serving, blocked_comparison, missing_comparable, missing_plan, projection_missing, stale_data, confidence_degraded

**Operational**: severe_gap, unit_alert_triggered, attainment_gap

**Trend**: sustained_negative, weekly_deterioration, monthly_deterioration

**Config/Data**: config_incomplete, data_incomplete

**Fallback**: insufficient_signal

### Functions
- `extractDiagnosticFactors(signals)` → [{factor, detail}]
- `extractDominantDiagnosticFactor(signals)` → {factor, detail}
- `buildDiagnosticExplanation(signals)` → {severity, dominantFactor, secondaryFactors, allFactors, summary}
- `explainBlockedState / explainCriticalState / explainElevatedState / explainUnknownState`
- `summarizeDiagnosticSignals(signals)` → compact string

---

## Components

| Component | File | Purpose |
|-----------|------|---------|
| DecisionSeverityBadge | operational/DecisionSeverityBadge.jsx | Dot or badge showing severity |
| DecisionPriorityStrip | operational/DecisionPriorityStrip.jsx | Strip: "2 blocked, 1 critical" |
| DecisionAttentionList | operational/DecisionAttentionList.jsx | Sort/filter by priority |
| DecisionAttentionHeader | operational/DecisionAttentionHeader.jsx | Section header with attention % |
| DecisionSignalTooltip | operational/DecisionSignalTooltip.jsx | Hover tooltip explaining severity |
| DiagnosticDominantFactor | diagnostics/DiagnosticDominantFactor.jsx | 1-line: "Critical due to..." |
| DiagnosticFactorBadge | diagnostics/DiagnosticFactorBadge.jsx | Chip badge per factor |
| DiagnosticBreakdownTooltip | diagnostics/DiagnosticBreakdownTooltip.jsx | Expandable diagnostic detail |
| DiagnosticExplanationCard | diagnostics/DiagnosticExplanationCard.jsx | Structured explanation panel |
| DiagnosticReasonList | diagnostics/DiagnosticReasonList.jsx | Compact factor list |

---

## Views Consuming

| View | Components Used | Signals Consumed |
|------|----------------|-----------------|
| WeeklyPlanVsRealView | DecisionSeverityBadge, DecisionPriorityStrip, DiagnosticDominantFactor | gap_*_pct, unit_alert |
| YangoLoyaltyView | DecisionPriorityStrip, DiagnosticDominantFactor | meets_oro, data_complete, has_any_targets, attainment_pct |

---

## Limits Before Suggestion Engine

| This layer DOES | Suggestion Engine WOULD |
|----------------|------------------------|
| Explain WHY something is critical | Recommend WHAT to do about it |
| Decompose causal factors | Prioritize response actions |
| Show dominant diagnostic factor | Show expected impact of actions |
| Summarize diagnostic signals | Generate action playbooks |
| Route attention visually | Escalate and assign tasks |

---

## Prohibited Boundaries

- ❌ Recommending actions
- ❌ "Haz X", "Llama a...", "Ejecuta campaña"
- ❌ Inferring external causality (market, competition)
- ❌ ML/AI-driven diagnosis
- ❌ New backend endpoints or serving facts
- ❌ Modifying existing data

---

## Tests

| File | Cases | Coverage |
|------|-------|----------|
| `operationalDecisionSeverity.test.js` | 21 | All severities, thresholds, sorting, explanations |
| `diagnosticExplanationEngine.test.js` | 17 | All factors, explanation functions, prohibited language |
| `diagnosticRegressionGuard.test.js` | ~10 | Constants integrity, threshold centralization, text compliance |
