# OPERATIONAL DEFAULTS + MOMENTUM AUTHORITY — PRECHECK GO / NO-GO

**Date**: 2025-05-25
**Phase**: 1H.4 — Operational Maturity Governance Layer
**Motor**: Control Foundation + Diagnostic Engine Temprano
**Foco**: Omniview Vs Proyección (viewMode='proyeccion')

---

## 1. ACTIVE PHASE

| Field | Value |
|---|---|
| Motor | Control Foundation |
| Phase | 1H.4 |
| Status | ACTIVE |
| Allowed | UX operacional, defaults, momentum visual authority, NaN cleanup, cell layout |
| Forbidden | New engines, AI loops, Evolution wiring |

## 2. WIRING VERIFICATION

| Target | Lives in | Status |
|---|---|---|
| `viewMode === 'proyeccion'` | `Matrix.jsx:319` | ✅ Active |
| `ProjectionCellRender` | `MatrixCell.jsx:200` | ✅ Active |
| `operationalMomentumEmphasis.js` | `utils/` | ✅ Pure functions, used by Evolution cell but reusable |
| `periodPop` in projection deltas | `projectionMatrixUtils.js` computeProjectionDeltas | ✅ Present |
| Deprecated ProjectionTable | NOT imported | ✅ Safe |
| Deprecated ProjectionCell | NOT imported | ✅ Safe |
| Evolution wiring | `MatrixCell.jsx:67-177` | ✅ Unchanged |

## 3. OMNIVIEW_MOMENTUM_CONTRACT.md

This file does not exist in the repo. The closest relevant docs are:
- `OMNIVIEW_MOMENTUM_REPORT.md` — Momentum Command Center phase report
- `OMNIVIEW_MOMENTUM_WIRING_REPORT.md` — Momentum wiring fixes
- `PROJECTION_PARITY_MIGRATION_REPORT.md` — Momentum absorbed by projection

The contract is implicit in `operationalMomentumEmphasis.js` (COMPARISON_CLASS, EMPHASIS_LEVEL).

## 4. SCOPE OF CHANGES

| Change | Scope | Risk |
|---|---|---|
| Default expanded cities | Remove `dailyDefaultCollapsed` logic in MatrixTable | LOW — pure UI state |
| User collapse governance | Add `userCollapsedRef` to track manual state | LOW — additive ref |
| Momentum color authority audit | Verify existing code, no logic changes | NONE — audit only |
| Cell dominant reading | Reorder cell rows: value+delta first, plan/gap small | LOW — pure visual |
| NaN cleanup | Add guards for edge cases | LOW — if-guards only |
| Current period authority | Verify existing, enhance if needed | LOW — visual only |

## 5. GO / NO-GO

### GO

| Check | Status |
|---|---|
| Wiring confirmed in Proyección | YES |
| No Evolution wiring touched | YES |
| No deprecated components used | YES |
| No core logic changes | YES |
| Build currently passes | YES |
| Phase 1H.4 allows these changes | YES |
| Sticky/virtualization/fullscreen safe | YES |

## VERDICT: **GO**

Proceed to PASO 1.
