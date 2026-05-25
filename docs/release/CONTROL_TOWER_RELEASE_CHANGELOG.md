# CONTROL TOWER — RELEASE CHANGELOG

**Date**: 2026-05-25
**Stages**: 4 through Momentum Release Hardening

---

## OMNIVIEW COMMAND CENTER

| File | Change |
|------|--------|
| `components/omniview/command/OmniviewCommandHeader.jsx` | NEW — Command header with health dots + attention |
| `components/omniview/command/OmniviewAttentionSummary.jsx` | NEW — Blocked/critical counts |
| `components/omniview/command/OmniviewModeSelector.jsx` | NEW — 4-mode segmented control |
| `BusinessSliceOmniviewMatrix.jsx` | MOD — Wrapped banner + mode state + weekdayFocus |

## MOMENTUM

| File | Change |
|------|--------|
| `utils/operationalMomentumEmphasis.js` | NEW — Comparison classification + emphasis levels |
| `utils/operationalMomentumPriority.js` | NEW — Priority engine (7 risk levels) |
| `components/omniview/momentum/OmniviewMomentumDrillChart.jsx` | NEW — Momentum drill chart |
| `components/omniview/momentum/OmniviewMomentumPriorityStrip.jsx` | NEW — Deterioration surface strip |
| `BusinessSliceOmniviewMatrixCell.jsx` | MOD — Momentum emphasis on delta rendering |
| `BusinessSliceOmniviewInspector.jsx` | MOD — Momentum/Evolution toggle |

## DRILL

| File | Change |
|------|--------|
| `services/api.js` | MOD — Added `getOmniviewMomentumDrill()` |

## BACKEND

| File | Change |
|------|--------|
| `services/omniview_momentum_drill_service.py` | NEW — Momentum drill endpoint service |
| `routers/ops.py` | MOD — Added `/business-slice/omniview-momentum-drill` endpoint |

## DECISION UX (Stage 4-7)

| File | Change |
|------|--------|
| `utils/operationalDecisionSeverity.js` | NEW — Severity contract |
| `utils/operationalAttentionRouting.js` | NEW — Attention routing |
| `utils/diagnosticExplanationEngine.js` | NEW — Diagnostic explanation |
| `components/operational/DecisionSeverityBadge.jsx` | NEW |
| `components/operational/DecisionPriorityStrip.jsx` | NEW |
| `components/operational/DecisionAttentionList.jsx` | NEW |
| `components/operational/DecisionAttentionHeader.jsx` | NEW |
| `components/operational/DecisionSignalTooltip.jsx` | NEW |
| `components/diagnostics/DiagnosticDominantFactor.jsx` | NEW |
| `components/diagnostics/DiagnosticFactorBadge.jsx` | NEW |
| `components/diagnostics/DiagnosticBreakdownTooltip.jsx` | NEW |
| `components/diagnostics/DiagnosticExplanationCard.jsx` | NEW |
| `components/diagnostics/DiagnosticReasonList.jsx` | NEW |
| `utils/__tests__/operationalDecisionSeverity.test.js` | NEW — 21 tests |
| `utils/__tests__/diagnosticExplanationEngine.test.js` | NEW — 17 tests |
| `utils/__tests__/diagnosticRegressionGuard.test.js` | NEW — 10 tests |

## UX FOUNDATION (Stage 1-3)

| File | Change |
|------|--------|
| `styles/ct-design-tokens.css` | MOD — Density, KPI compression, workbench, collapsible, momentum primitives |
| `components/KPICards.jsx` | MOD — Density reduction |
| `components/GlobalFreshnessBanner.jsx` | MOD — Font sizes |
| `components/MatrixExecutiveBanner.jsx` | MOD — Font sizes |
| `components/WeeklyPlanVsRealView.jsx` | MOD — ct-token colors + severity badges + explanation |
| `components/yangoLoyalty/YangoLoyaltyView.jsx` | MOD — Workbench header + severity strip + explanation |

## DOCS CREATED

| Directory | Files |
|-----------|-------|
| `docs/ui/` | 7 (audit, governance, workbench, density, decision UX, visual acceptance) |
| `docs/diagnostics/` | 16 (prechecks, audits, QA, governance, closure) |
| `docs/omniview/` | 20+ (command center, modes, momentum, drill, priority, visual acceptance) |
| `docs/release/` | 8 (precheck, changelog, backend/frontend QA, functional QA, release report) |
