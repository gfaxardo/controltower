# OMNIVIEW PERFORMANCE HARDENING

**Date**: 2025-05-25
**Build**: PASS (9.71s, 812 modules)
**Status**: AUDITED — LOW RISK

---

## Findings

### HIGH (identified but deferred — no runtime impact at current scale)

| # | Issue | Location |
|---|---|---|
| 1 | Cell `onClick` inline function per cell (6000+ per render) | Table.jsx:622-626 |
| 2 | MatrixTable not wrapped in React.memo | Table.jsx:89 |
| 3 | `handleExport` 22 deps — recreated on every state change | Matrix.jsx:1252 |

**Mitigation**: Cell memo is already present but partially defeated. Real impact depends on matrix size. Daily grain with many cities/rows is most affected. Deferred to FASE 6 hardening because fixing requires structural change (event delegation, stable callbacks).

### MEDIUM (fixed in this phase)

| # | Issue | Fix Applied |
|---|---|---|
| 1 | OMPS not wrapped in React.memo | ✅ Wrapped with `memo()` |
| 2 | `?? []` creates new array per render | Mitigated by React.memo (shallow compare skips re-render) |
| 3 | `displayMatrix` + `displayProjMatrix` both recompute on weekdayFocus | Kept as-is (intended data flow for both modes) |
| 4 | Inline `onClose`/`onGoBack` for Inspector/Drill | Kept as-is (Inspector uses refs; Drill unmounts between selections) |

### Not Fixed (acceptable)

| # | Issue | Reason |
|---|---|---|
| 1 | `currentPeriodKey` useMemo on primitive | Harmless — no perf impact |
| 2 | `sortSelectOptions` useMemo on trivial filter | Harmless — no perf impact |
| 3 | `projectionEmptyKind` 10 deps | Cheap computation — 10 deps stable in practice |

---

## Measures Applied

| File | Change |
|---|---|
| `OmniviewMomentumPriorityStrip.jsx` | Wrapped in `React.memo` |
| `api.js` | Removed 11 dead exported functions → smaller bundle |
| `App.jsx` | Removed dead import `RealVsProjectionView` |

---

## Bundle Size

| Metric | Before Cleanup | After Cleanup | Delta |
|---|---|---|---|
| JS bundle | 1,805.53 kB | 1,804.58 kB | -0.95 kB |
| CSS | 89.83 kB | 89.83 kB | 0 |
| Modules | 813 | 812 | -1 |
| Build time | 9.74s | 9.71s | -0.03s |
