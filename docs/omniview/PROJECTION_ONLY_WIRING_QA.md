# PROJECTION-ONLY WIRING QA

**Date**: 2026-05-25

---

## ACTIVE WIRING (Proyección)

| Component | File:Line | Mode |
|---|---|---|
| `BusinessSliceOmniviewMatrix` toggle | `Matrix.jsx` → `viewMode === 'proyeccion'` | Proyección |
| `ProjectionCellRender` | `MatrixCell.jsx:202` | Proyección |
| `buildProjectionCellDisplay` | `projectionCellDisplayModel.js:21` | Proyección |
| `buildComparableDelta` | `comparableDeltaDisplay.js` → imported by display model | Proyección |
| `resolveClosedPeriodAnchor` | `projectionClosedPeriodEngine.js` → `Matrix.jsx` | Proyección |
| `computeProjectionDeltas` | `projectionMatrixUtils.js:572` | Proyección |
| `OmniviewProjectionDrill` | sidebar + drill panel | Proyección |
| `OmniviewMomentumPriorityStrip` | recibe `projMatrix` | Proyección |

## DEPRECATED (no tocado)

| Component | Estado |
|---|---|
| `BusinessSliceOmniviewProjectionTable` | Deprecated, no wiring |
| `BusinessSliceOmniviewProjectionCell` | Deprecated, no wiring |
| `OmniviewTopDeviations` | Deprecated, no wiring |
| `RealVsProjectionView` | Stale, no wiring |

## EVOLUTION (sin cambios)

| Check | Status |
|---|---|
| Evolution cell render path | Intacto, sin cambios |
| Evolution delta computation | Intacto, sin cambios |
| Evolution auto-scroll | Intacto, sin cambios |
| `BusinessSliceOmniviewInspector` | Intacto, sin cambios |

## VERDICT: PASS — Proyección es el cerebro principal. Evolution es legacy secundario sin regresiones.
