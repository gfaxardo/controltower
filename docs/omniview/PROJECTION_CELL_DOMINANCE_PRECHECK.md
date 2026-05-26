# PROJECTION CELL DOMINANCE — PRECHECK GO / NO-GO

**Date**: 2026-05-25
**Phase**: 1H.4 — Operational Maturity Governance Layer
**Motor**: Control Foundation
**Foco**: Omniview Vs Proyección — Cell Visual Dominance Tuning

---

## 1. ACTIVE PHASE

| Field | Value |
|---|---|
| Motor | Control Foundation |
| Phase | 1H.4 |
| Status | ACTIVE |
| Allowed | UX operacional, cell rendering, visual hierarchy tuning, delta comparable isolation |
| Forbidden | New engines, AI loops, backend changes, Evolution wiring |

## 2. READY NEXT

Diagnostic Engine — Phase 2A.3 (blocked until Serving Governance Foundation stabilized).

## 3. WIRING VERIFICATION

| Target | Lives in | Active? |
|---|---|---|
| `ProjectionCellRender` | `BusinessSliceOmniviewMatrixCell.jsx:202` | ✅ |
| `buildProjectionCellDisplay` | `projectionCellDisplayModel.js:38` | ✅ |
| `computeProjectionDeltas` | `projectionMatrixUtils.js:572` | ✅ |
| `periodPop` (momentum data) | `projectionMatrixUtils.js:613` | ✅ |
| Cell rendering callsite | `BusinessSliceOmniviewMatrixTable.jsx:634` | ✅ |

**All changes target Proyección exclusively. Evolution zero changes.**

## 4. CURRENT AMBIGUITIES FOUND

| Ambiguity | Location | Severity |
|---|---|---|
| `comparableLabel` = "vs domingo comparable" is vague | `projectionCellDisplayModel.js:31-34` | MEDIUM |
| `isPlanFallback` shows attainment as delta substitute | `projectionCellDisplayModel.js:70-71` | HIGH — confuses plan with momentum |
| `attainmentStr` shown below momentum in same cell | `MatrixCell.jsx:377-380` | MEDIUM — two numeric contexts in one cell |
| No explicit `comparableType` enum in display model | `projectionCellDisplayModel.js:109-132` | LOW — implicit via `deriveMomentumLabel` |
| `periodPopLabel` from backend may override grain-derived label | `projectionCellDisplayModel.js:68` | LOW — backend may send wrong label |
| No YTD isolation from delta pathway | Entire model | MEDIUM — YTD lives in tooltip only, but no explicit guard |

## 5. CONFIRMED: NO EVOLUTION CHANGES

| Check | Status |
|---|---|
| Evolution wiring unchanged | ✅ |
| Evolution cell render path untouched | ✅ |
| Evolution delta computation untouched | ✅ |
| Proyección as primary brain | ✅ |

## 6. GO / NO-GO VERDICT

### GO

| Check | Status |
|---|---|
| Wiring confirmed in Proyección | ✅ |
| Evolution not affected | ✅ |
| Phase 1H.4 allows visual tuning | ✅ |
| Build currently passes | ✅ |
| No new engines needed | ✅ |
| No backend changes needed | ✅ |
| `periodPop` data already available | ✅ |

### Residual Risks

| Risk | Mitigation |
|---|---|
| `periodPop` may be null for periods without comparable | Guard with `hasComparable` boolean |
| Backend may send plan-driven data as `periodPop` | DERIVE from grain, validate against `periodPopKind` |
| Attainment fallback may still be needed for new cities/lines | Show as muted context, never as delta substitute |

## VERDICT: **GO**

Proceed to PASO 1 — Field Separation Audit.
