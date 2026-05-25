# Omniview Real Render Path Audit

**Date**: 2025-05-25
**Status**: Verified

## Route Resolution

| Path | Component | Status |
|---|---|---|
| `/operacion/omniview-matrix` | `BusinessSliceOmniviewMatrix.jsx` | **ACTIVE** |
| `/operacion/omniview` | `BusinessSliceOmniview.jsx` | Hidden (LEGACY) |

## Component Chain

```
App.jsx (line 365)
  └─ OmniviewErrorBoundary
     └─ BusinessSliceOmniviewMatrix.jsx  (3799 lines)
        ├─ OmniviewCommandHeader
        │  ├─ MatrixExecutiveBanner
        │  └─ OperationalModeSelector
        ├─ OmniviewMomentumPriorityStrip    <-- FIXED
        ├─ Controls (grain, filters, weekdayFocus, zoom)
        ├─ OperationalStatusBar
        ├─ BusinessSliceOmniviewMatrixTable
        │  └─ BusinessSliceOmniviewMatrixCell
        ├─ BusinessSliceOmniviewInspector
        └─ BusinessSliceInsightsPanel
```

## Mode Routing

- **Evolución**: `viewMode === 'evolucion'` — renders real-time matrix
- **Vs Proyección**: `viewMode === 'proyeccion'` — renders ProjectionCellRender cells

Both modes use the **same** `BusinessSliceOmniviewMatrix` component. Cell rendering diverges at `BusinessSliceOmniviewMatrixCell.jsx:68` where `mode === 'projection'` switches to `ProjectionCellRender`.

## Feature Flags

| Flag | Value | Effect |
|---|---|---|
| `VITE_OMNIVIEW_MATRIX_MANUAL_LOAD` | Dev only | Defers heavy queries until "Cargar datos" |
| Maturity: `operacion_omniview_matrix` | `STABLE / experimental: false` | Always visible |
| Maturity: `operacion_omniview` | `LEGACY / visible: false` | Hidden |

## Conclusion

The real UI component is **confirmed**: `BusinessSliceOmniviewMatrix.jsx`. There is no wrapper, no legacy override, and no feature flag blocking the active path.
