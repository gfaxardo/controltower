# PROJECTION PARITY MIGRATION — PRECHECK

**Date**: 2025-05-25
**Phase**: FASE 2 — Momentum Absorption into Proyección
**Motor**: Control Foundation + Diagnostic Engine Temprano

---

## 1. ACTIVE PHASE CONFIRMATION

| Item | Value |
|---|---|
| Current Phase | 1H.4 Operational Maturity Governance |
| Engine | Control Foundation (GO) |
| Next Engine | Diagnostic Engine (2A.3, READY NEXT) |
| Forecast Engine | PROTOTYPE ONLY — NOT ACTIVE |

**Check**: Migration is within Control Foundation scope — no engine change required.

---

## 2. ALLOWED vs FORBIDDEN

### ALLOWED
- Omniview hardening (focus mode, fullscreen drill) → **YES**
- UX operacional → **YES**
- Eliminación de redundancias → **YES**
- Claridad visual, reducción de ruido → **YES**

### FORBIDDEN
- Activar Forecast Engine → **N/A** (no estamos activando forecast)
- Suggestion/Decision/Action engines → **N/A**
- AI automation loops → **N/A**
- Heavy runtime fallback → **N/A** (no new backend queries; reusing existing `period_over_period` data)

---

## 3. WIRING VIVO DETECTADO

| Wiring Target | Status | File:Line |
|---|---|---|
| `BusinessSliceOmniviewMatrix` | **ALIVE** — renders `/operacion/omniview-matrix` | `App.jsx:365` |
| `ProjectionCellRender` (inline) | **ALIVE** — activated by `mode='projection'` | `BusinessSliceOmniviewMatrixCell.jsx:198` |
| `displayProjMatrix` | **ALIVE** — passes to MatrixTable | `BusinessSliceOmniviewMatrix.jsx:919` |
| `OmniviewProjectionDrill` | **ALIVE** — side panel for projection selection | `BusinessSliceOmniviewMatrix.jsx:1897` |
| `OmniviewMomentumPriorityStrip` | **ALIVE** — currently only for evolution | `BusinessSliceOmniviewMatrix.jsx:1305` |
| `OmniviewMomentumDrillChart` | **ALIVE** — standalone drill chart | `momentum/OmniviewMomentumDrillChart.jsx` |
| `operationalMomentumEmphasis.js` | **ALIVE** — shared utility | `utils/operationalMomentumEmphasis.js` |
| `operationalMomentumPriority.js` | **ALIVE** — shared utility (recently rewired) | `utils/operationalMomentumPriority.js` |

---

## 4. LEGACY / DEAD CODE DETECTADO

| Code | Status |
|---|---|
| `BusinessSliceOmniviewProjectionTable.jsx` | DEAD (@deprecated, zero imports) |
| `BusinessSliceOmniviewProjectionCell.jsx` | DEAD (@deprecated, zero imports) |
| `RealVsProjectionView.jsx` | LEGACY (imported in App.jsx:44, never rendered) |
| 6 dead API functions | DEAD (defined, never called) |

**Confirmation**: NO new code will touch any of these dead components.

---

## 5. EXISTING MOMENTUM INFRASTRUCTURE

| File | Functions | Ready for Proyección? |
|---|---|---|
| `operationalMomentumEmphasis.js` | `classifyComparison`, `getMomentumEmphasis`, `getMomentumStyle`, `getComparisonLabel`, `isMomentumComparison` | **YES** — pure functions, grain-aware |
| `operationalMomentumPriority.js` | `extractMomentumPriorityFromMatrix`, `classifyMomentumRisk`, `sortMomentumAttention` | **YES** — recent rewired to accept matrix structure |
| `OmniviewMomentumPriorityStrip.jsx` | Priority strip component | **YES** — recent rewired to accept cities + allPeriods |
| `OmniviewMomentumDrillChart.jsx` | Momentum drill chart | **YES** — standalone, calls `getOmniviewMomentumDrill` API |
| `insightEngine.js` | `detectInsights`, `buildInsightCellMap` | **PARTIAL** — currently only used in Evolution mode; needs adaptation for projection matrix |

---

## 6. PROJECTION DATA AVAILABILITY FOR MOMENTUM

Projection rows contain `period_over_period` data:
- `periodPopComparable` (boolean) — whether period-over-period comparison is valid
- `periodPopLabel` (string) — "DoD", "WoW", "MoM"
- `periodPop` (number) — variation value
- Available via `cell.raw?.period_over_period` in `projectionMatrixUtils.js:582`

**This is already partially rendered** in `ProjectionCellRender` at lines 410-418, but with subtle styling. The data EXISTS; it just needs proper momentum emphasis.

---

## 7. RISK ASSESSMENT

| Risk | Severity | Mitigation |
|---|---|---|
| Breaking projection cell layout | MEDIUM | Incremental changes, preserve existing rows |
| Duplicating momentum logic | LOW | Reuse existing `operationalMomentumEmphasis.js` and `operationalMomentumPriority.js` |
| Performance regression | LOW | No new API calls needed; `period_over_period` data already in response |
| Sticky/scroll breakage | LOW | Not touching table layout or sticky logic |
| Legacy wiring | NONE | All targets confirmed ALIVE |

---

## 8. GO / NO-GO

| Criteria | Status |
|---|---|
| Active phase allows Omniview hardening | **YES** |
| All wiring targets are ALIVE | **YES** |
| No forecast/suggestion/decision engines activated | **YES** |
| Momentum infrastructure already exists and works | **YES** |
| Projection data already has period_over_period | **YES** |
| No new backend endpoints needed | **YES** |
| No heavy runtime fallback | **YES** |
| Deterministic logic only | **YES** |

---

## VERDICT: **GO** — READY FOR IMPLEMENTATION

Proyección can absorb momentum without:
- New engines
- New endpoints
- Duplicated logic
- Legacy wiring
- Matrix breakage
