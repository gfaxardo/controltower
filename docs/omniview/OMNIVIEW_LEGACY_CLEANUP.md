# OMNIVIEW LEGACY CLEANUP — EXECUTED

**Date**: 2025-05-25
**Status**: DONE — SAFE ONLY

---

## Removed

### Dead Import (App.jsx)

| Line | Import | Reason |
|---|---|---|
| 44 (ex) | `import RealVsProjectionView from './components/RealVsProjectionView'` | Never rendered; route catches BacklogPlaceholder. Import was dead weight. |

### Dead API Functions (api.js)

| Function | Endpoint | Reason |
|---|---|---|
| `getPlanUnmappedSummary` | `/plan/unmapped-summary` | Zero imports in entire frontend |
| `getProjectionIntegrityAudit` | `/plan/projection-integrity-audit` | Zero imports; integrity read from omniview-project response |
| `getLobAliasCatalog` | `/plan/lob-alias-catalog` | Zero imports |
| `getPlanReconciliationAudit` | `/plan/reconciliation-audit` | Zero imports; reconciliation read from omniview-project response |
| `getRealVsProjectionOverview` | `/ops/real-vs-projection/overview` | Only imported by RealVsProjectionView (dead) |
| `getRealVsProjectionDimensions` | `/ops/real-vs-projection/dimensions` | Only imported by RealVsProjectionView (dead) |
| `getRealVsProjectionMappingCoverage` | `/ops/real-vs-projection/mapping-coverage` | Only imported by RealVsProjectionView (dead) |
| `getRealVsProjectionRealMetrics` | `/ops/real-vs-projection/real-metrics` | Only imported by RealVsProjectionView (dead) |
| `getRealVsProjectionTemplateContract` | `/ops/real-vs-projection/projection-template-contract` | Only imported by RealVsProjectionView (dead) |
| `getRealVsProjectionSystemSegmentation` | `/ops/real-vs-projection/system-segmentation-view` | Zero imports even inside RealVsProjectionView |
| `getRealVsProjectionProjectionSegmentation` | `/ops/real-vs-projection/projection-segmentation-view` | Zero imports even inside RealVsProjectionView |

### Dead Component Files

| File | Status |
|---|---|
| `BusinessSliceOmniviewProjectionTable.jsx` | **KEPT** — @deprecated tag preserved as documentation. Safe to delete in next phase. |
| `BusinessSliceOmniviewProjectionCell.jsx` | **KEPT** — @deprecated tag preserved as documentation. Safe to delete in next phase. |
| `RealVsProjectionView.jsx` | **KEPT** — referenced in registries as BACKLOG marker. Remove in FASE 4/6 with full tab cleanup. |

---

## NOT Removed

| Item | Reason |
|---|---|
| `BusinessSliceOmniviewProjectionTable.jsx` | Has `@deprecated` tag for traceability |
| `BusinessSliceOmniviewProjectionCell.jsx` | Has `@deprecated` tag for traceability |
| `RealVsProjectionView.jsx` component file | Registry still references it as BACKLOG |
| `operacion_omniview` legacy route | Hidden but safe — cleanup in FASE 4 |
| `/en-revision/*` routes | Contains multiple backlog views — cleanup in FASE 4 |
| `parseDateFromPeriodKey` debug in DEV | Development-only code, not in production build |

---

## Pending Cleanup (FASE 4/6)

- Delete 2 deprecated component files
- Remove `/en-revision` tab entirely
- Remove `RealVsProjectionView.jsx`
- Consolidate duplicated `getOmniviewProjection` fetch
