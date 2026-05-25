# PROJECTION LEGACY SAFETY AUDIT

**Date**: 2025-05-25
**Status**: MARKED FOR CLEANUP — NOT YET CLEANED

---

## DEAD COMPONENTS (safe to delete later)

| File | Reason | Zero Imports? |
|---|---|---|
| `components/BusinessSliceOmniviewProjectionTable.jsx` | `@deprecated FASE 3.1B` — absorbed into `BusinessSliceOmniviewMatrixTable` | ✅ Yes |
| `components/BusinessSliceOmniviewProjectionCell.jsx` | `@deprecated FASE 3.1B` — absorbed into `ProjectionCellRender` | ✅ Yes |

## DEAD IMPORTS

| File | Line | Import | Action |
|---|---|---|---|
| `App.jsx` | 44 | `import RealVsProjectionView` | Remove (never rendered, BACKLOG) |

## DEAD API FUNCTIONS (api.js)

| # | Function | Endpoint |
|---|---|---|
| 1 | `getPlanUnmappedSummary` | `/plan/unmapped-summary` |
| 2 | `getProjectionIntegrityAudit` | `/plan/projection-integrity-audit` |
| 3 | `getLobAliasCatalog` | `/plan/lob-alias-catalog` |
| 4 | `getPlanReconciliationAudit` | `/plan/reconciliation-audit` |
| 5 | `getRealVsProjectionSystemSegmentation` | `/ops/real-vs-projection/system-segmentation-view` |
| 6 | `getRealVsProjectionProjectionSegmentation` | `/ops/real-vs-projection/projection-segmentation-view` |

## DUPLICATED FETCHES (to consolidate later)

| Component | Duplication |
|---|---|
| `OperationalOpportunitiesView` | Fetches `getOmniviewProjection` independently from Matrix |
| Plan versions fetch | `getPlanVersions` + `getControlLoopPlanVersions` called in 3 separate places |

## UNUSED IMPORT (cleaned in this phase)

| File | Change |
|---|---|
| `BusinessSliceOmniviewMatrixCell.jsx:16` | Removed `fmtPeriodPop` — no longer used after momentum absorption |

## LEGACY ROUTES (not touched)

| Route | Status |
|---|---|
| `/en-revision/real-vs-proyeccion` | Dead (always renders BacklogPlaceholder) |
| `/operacion/omniview` | Hidden (LEGACY, replaced by Matrix) |

---

## SAFETY RULE

**Cleanup will be executed in FASE 4 (Evolution Deprecation Precheck) or FASE 6 (Final Hardening).** Do NOT clean in this phase to avoid unintended breakage and to keep rollback simple.
