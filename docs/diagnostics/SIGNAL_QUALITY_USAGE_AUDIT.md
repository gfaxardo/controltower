# SIGNAL QUALITY USAGE AUDIT

**Date**: 2026-05-25

---

## CONSUMPTION MAP

### Views consuming severity/diagnostic

| View | Imports | Usage |
|------|---------|-------|
| WeeklyPlanVsRealView | DecisionSeverityBadge, DecisionPriorityStrip, getDecisionSeverity, DiagnosticDominantFactor | Per-alert severity + explanation |
| YangoLoyaltyView | DecisionPriorityStrip, getDecisionSeverity, DiagnosticDominantFactor | City ranking strip + config/data explanation |

### Components consuming internally

| Component | Imports | Notes |
|-----------|---------|-------|
| DecisionSeverityBadge | getDecisionSeverity, getDecisionTone, getDecisionLabel | Pure badge rendering |
| DecisionPriorityStrip | getAttentionSummary | Summary counts |
| DecisionAttentionList | stablePrioritySort, getDecisionSeverity | Sorting/filtering |
| DiagnosticDominantFactor | buildDiagnosticExplanation, DiagnosticFactorBadge | 1-line explanation |
| DiagnosticBreakdownTooltip | buildDiagnosticExplanation, summarizeDiagnosticSignals | Expandable tooltip |
| DiagnosticExplanationCard | buildDiagnosticExplanation, summarizeDiagnosticSignals | Structured panel |
| DiagnosticFactorBadge | FACTOR_LABEL (constant) | Badge rendering |
| DecisionSignalTooltip | explainDecisionSeverity | Self-contained |

### No consumption: 0 untracked uses

---

## SIGNAL EXTRACTORS

### Weekly View (`alertSignalExtractor`)
```js
alert => ({
  gap_revenue_pct: alert.gap_revenue_pct * 100,  // 0-1 → 0-100 conversion
  gap_trips_pct: alert.gap_trips_pct * 100,
  gap_unitario_pct: alert.gap_unitario_pct * 100,
  unit_alert: alert.unit_alert,
})
```

**Note**: Backend returns `gap_*_pct` as 0-1 range. Extractor multiplies by 100 to match `DECISION_THRESHOLDS` (which use percentages). This is correct.

### Yango Loyalty (city ranking)
```js
city => ({
  meets_oro: city.cat?.category === 'ORO',
  data_complete,
  has_any_targets,
  attainment_pct: city.avgScore,
})
```

---

## DUPLICATES FOUND

| Signal | Produced by | Normalized by | Status |
|--------|-----------|---------------|--------|
| `getDecisionSeverity` | operationalDecisionSeverity.js | — (canonical source) | OK |
| `buildDiagnosticExplanation` | diagnosticExplanationEngine.js | Calls getDecisionSeverity internally | OK |
| `attainment_pct` | Yango (`avgScore`) + Matrix (`attainment_pct`) | Different sources, same concept | Consistent |

No duplicated thresholds found.

---

## INCONSISTENCIES

| Issue | Severity | Fix |
|-------|----------|-----|
| `require()` in DecisionAttentionList.jsx | Low | Fixed — converted to ES import |
| `gap_*_pct` values in Weekly backend (0-1) vs thresholds (0-100) | None (extractor handles it) | Already correct |

---

## VISUAL NOISE RISK

| Risk | Probability | Mitigation |
|------|------------|------------|
| All alerts get DiagnosticDominantFactor | Low | Only shows for blocked/critical/elevated/warning; normal returns null |
| PriorityStrip shows 0 counts | Low | Returns null when no items or all counts are 0 |
| YangoLoyalty: explanation replaces banners | Low | DiagnosticDominantFactor is used only when warnings exist, not for normal state |
