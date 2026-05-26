# VIEWPORT DOMINANCE — PRECHECK GO / NO-GO

**Date**: 2025-05-25
**Phase**: 1H.4 — Operational Maturity Governance Layer
**Motor**: Control Foundation
**Foco**: Omniview Vs Proyección (NO Evolution)

---

## 1. ACTIVE PHASE

| Field | Value |
|---|---|
| Motor | Control Foundation |
| Phase | 1H.4 |
| Status | ACTIVE |
| Allowed | UX operacional, scroll governance, visual hardening, empty states, Omniview focus mode, fullscreen drill |
| Forbidden | New engines, AI loops, heavy runtime fallback |

## 2. READY NEXT

Diagnostic Engine — Phase 2A.3 (blocked until Serving Governance Foundation stabilized).

## 3. WIRING VERIFICATION: PROYECCIÓN vs EVOLUCIÓN

| Target | Lives in | Active route |
|---|---|---|
| `BusinessSliceOmniviewMatrix` (root) | `App.jsx:365` | `/operacion/omniview-matrix` |
| `viewMode === 'proyeccion'` | `Matrix.jsx:319` | Toggle in controls |
| `ProjectionCellRender` | `MatrixCell.jsx:197` | `mode='projection'` |
| `displayProjMatrix` | `Matrix.jsx:919` | Filtered projection matrix |
| Evolution mode | `viewMode === 'evolucion'` | Secondary legacy |
| Evolution wiring | `MatrixCell.jsx:67-177` (e-mode) | Unchanged |

**All changes will target projection mode exclusively.** Evolution wiring untouched.

## 4. SCROLL OWNERSHIP RISKS (preliminary)

| Risk | Severity | Description |
|---|---|---|
| Nested `overflow-hidden` + `overflow-auto` | HIGH | Outer `.overflow-hidden` on table wrapper + inner `.overflow-x-auto` creates scroll containment conflict |
| `overflow-x-hidden` on root div | MEDIUM | Line 1268 of Matrix.jsx clips horizontal overflow, preventing natural scroll |
| Zoom transform wrapper with `min-w-0` | LOW | scale() transform changes coordinate system; scroll calculations unaware |
| Fullscreen uses `overflow-y-auto` on overlay | LOW | Separate scroll context, isolated from matrix scroll |

## 5. VIRTUALIZATION RISKS

| Risk | Status |
|---|---|
| No virtualization library used | Not a risk — hand-rolled column windowing is lightweight |
| Column visibility tracking via scroll event | `visibleColRange` state (Table line 182-197) — passive listener, stable |
| No re-render storms | `passive: true` on scroll listener |

## 6. STICKY RISKS

| Element | Type | Risk |
|---|---|---|
| Total row | `position: sticky, top: headerH` | None — inside scroll container |
| City header row | `position: sticky, left: 0` with z-index 10 | None |
| Line name column | `position: sticky, left: COL1_W` with z-index 10 | None |
| Sticky + nested overflow | All sticky elements inside single scroll div | **Safe** |

## 7. AUTO-FOCUS BUGS FOUND

| Bug | Severity | Description |
|---|---|---|
| `scrollToCurrentPeriod` uses `matrix.allPeriods` (Evolution) only | **CRITICAL** | Projection mode has no auto-scroll at all |
| Auto-scroll guard checks `rows.length` (Evolution rows only) | **CRITICAL** | Projection mode never triggers auto-scroll |
| "Ir a hoy" button hidden for `isProjectionMode` | HIGH | Operator has no manual fallback |
| Fullscreen projection renders `projMatrix` not `displayProjMatrix` | MEDIUM | Wrong matrix reference but functionally similar |

## 8. GO / NO-GO VERDICT

### GO

| Check | Status |
|---|---|
| Wiring confirmed in Proyección | YES |
| Evolution not affected | YES |
| Phase 1H.4 allows these changes | YES |
| Build currently passes | YES |
| Scroll ownership can be unified | YES |
| Sticky/virtualization safe | YES |
| No core logic changes needed | YES |

### Residual Risks

- None. All changes are UX/visual/scroll governance within the projection viewport.

## VERDICT: **GO**

Proceed to PASO 1 — Scroll Ownership Audit.
