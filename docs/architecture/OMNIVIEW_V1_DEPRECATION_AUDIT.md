# OMNIVIEW V1 — DEPRECATION AUDIT

**Version:** 1.0.0
**Date:** 2026-06-13
**Status:** READ-ONLY AUDIT — No deletions executed
**Phase:** V1-D0 Audit

---

## 0. Executive Decision

**GO: V1 CAN BE SOFT-DEPRECATED**

V1 can be hidden from the main menu. Routes must remain accessible as fallback. V1 endpoints shared with V2 (reports, filters, freshness) must NOT be removed. V1-only components can be flagged for removal after 30-day observation window.

---

## 1. Route Inventory

| Route | Component | Version | Status | Menu Default? |
|-------|-----------|---------|--------|---------------|
| `/` (root) | → `operacion_omniview_matrix` | V1 | **ACTIVE default** | YES |
| `/operacion` | → `operacion_omniview_matrix` | V1 | **ACTIVE** | YES |
| `/operacion/omniview` | `BusinessSliceOmniview` (legacy) | V1 | LEGACY | NO |
| `/operacion/omniview-matrix` | `BusinessSliceOmniviewMatrix` | V1 | **ACTIVE** | YES (default) |
| `/operacion/omniview-v2-professional` | `OmniviewV2ProfessionalPage` | V2 | **DEFAULT** | YES (via sub-tab) |
| `/operacion/omniview-v2-shadow` | `OmniviewV2ShadowPage` | V2 | FALLBACK | NO |
| `/operacion/omniview-v2-matrix-sandbox` | `OmniviewV2MatrixSandbox` | V2 | DEV | NO |
| `/operacion/reportes` | `BusinessSliceOmniviewReports` | V1 | ACTIVE | NO |

**Key finding:** The root route `/` and `/operacion` default to V1 matrix (`operacion_omniview_matrix`). V2 professional is accessible via sub-tab but V1 remains the landing experience.

---

## 2. Component Inventory

| Component | Path | Endpoints Used | Shared With V2? | Deprecation |
|-----------|------|---------------|-----------------|-------------|
| `BusinessSliceOmniviewMatrix` | `components/BusinessSliceOmniviewMatrix.jsx` | 17 (all V1-specific) | No | SAFE_TO_REMOVE_LATER |
| `BusinessSliceOmniview` (legacy) | `components/BusinessSliceOmniview.jsx` | omniview legacy endpoints | No | SAFE_TO_REMOVE_LATER |
| `BusinessSliceOmniviewReports` | `components/BusinessSliceOmniviewReports.jsx` | V1 filters/coverage | **SHARED** (filters endpoint) | KEEP_TEMPORARILY |
| `BusinessSliceOmniviewMatrixTable` | `components/` | None (renders data) | No | SAFE_TO_REMOVE_LATER |
| `BusinessSliceOmniviewMatrixCell` | `components/` | None (renders data) | No | SAFE_TO_REMOVE_LATER |
| `BusinessSliceOmniviewMatrixHeader` | `components/` | None (renders data) | No | SAFE_TO_REMOVE_LATER |
| `BusinessSliceOmniviewInspector` | `components/` | trust/issue endpoints | No | SAFE_TO_REMOVE_LATER |
| `BusinessSliceOmniviewKpis` | `components/` | None | No | SAFE_TO_REMOVE_LATER |
| `BusinessSliceOmniviewSidebar` | `components/` | None | No | SAFE_TO_REMOVE_LATER |
| `OmniviewPriorityPanel` | `components/` | None | No | SAFE_TO_REMOVE_LATER |
| `OmniviewTopDeviations` | `components/` | None | No | SAFE_TO_REMOVE_LATER |
| `OmniviewProjectionDrill` | `components/` | projection endpoints | No | SAFE_TO_REMOVE_LATER |
| `OmniviewErrorBoundary` | `components/` | None | **SHARED** (V2 uses it) | DO_NOT_TOUCH |

**14 V1 components.** 11 are V1-only. 1 is shared (ErrorBoundary). 1 is shared via endpoints (Reports).

---

## 3. Endpoint Inventory

| Endpoint | V1 | V2 | Shared? | Deprecation |
|----------|----|----|---------|-------------|
| `/ops/business-slice/monthly` | YES | NO | NO | SAFE_TO_DEPRECATE |
| `/ops/business-slice/weekly` | YES | NO | NO | SAFE_TO_DEPRECATE |
| `/ops/business-slice/daily` | YES | NO | NO | SAFE_TO_DEPRECATE |
| `/ops/business-slice/omniview` | YES | NO | NO | SAFE_TO_DEPRECATE |
| `/ops/business-slice/filters` | YES | NO | NO | SAFE_TO_DEPRECATE (check Reports) |
| `/ops/business-slice/coverage-summary` | YES | NO | NO | SAFE_TO_DEPRECATE |
| `/ops/business-slice/real-freshness` | YES | **YES** | SHARED | DO_NOT_TOUCH |
| `/ops/business-slice/matrix-operational-trust` | YES | NO | NO | SAFE_TO_DEPRECATE |
| `/ops/business-slice/matrix-issue-action` | YES (POST) | NO | NO | SAFE_TO_DEPRECATE |
| `/ops/omniview/refresh` | YES (POST) | NO | NO | **ALREADY FAIL-CLOSED** |
| `/ops/business-slice/backfill` | YES (POST) | NO | NO | **ALREADY FAIL-CLOSED** |
| `/ops/business-slice/real-refresh-omniview` | YES (POST) | NO | NO | **ALREADY FAIL-CLOSED** |
| `/ops/business-slice/omniview-projection` | YES | NO | NO | SAFE_TO_DEPRECATE |
| `/ops/business-slice/fact-status` | YES | NO | NO | SAFE_TO_DEPRECATE |
| `/ops/business-slice/coverage` | YES | NO | NO | SAFE_TO_DEPRECATE |

**15 V1 endpoints.** 3 already fail-closed (Phase C.2). 1 shared (freshness). 11 V1-only safe to deprecate when V1 components removed.

---

## 4. Shared Assets

| Asset | V1 | V2 | Risk If Removed |
|-------|----|----|-----------------|
| `OmniviewErrorBoundary` | YES | YES | V2 would lose error boundary |
| `omniviewExport.js` | YES | Partially (V2 has own) | V1 export would break, V2 not affected |
| `omniviewMatrixUtils.js` | YES | NO | V1 only — safe |
| `projectionMatrixUtils.js` | YES | NO | V1 only — safe |
| `omniviewUtils.js` | YES | NO | V1 only — safe |
| `/ops/business-slice/real-freshness` | YES | YES | DO NOT REMOVE — V2 uses it |
| `BusinessSliceOmniviewReports` | YES | NO | V1 only — safe (but shares filters endpoint) |

**1 critical shared asset:** `OmniviewErrorBoundary`. Must not be removed.

---

## 5. Deprecation Decision Matrix

| Item | Type | Recommendation | Reason | Risk |
|------|------|---------------|--------|------|
| Root `/` → V1 matrix | Route | CHANGE default to V2 professional | V2 is certified, V1 is legacy | LOW |
| `/operacion/omniview` | Route | HIDE_FROM_MENU | Legacy Omniview, unused | LOW |
| `/operacion/omniview-matrix` | Route | HIDE_FROM_MENU | V1 matrix, V2 is default | LOW |
| `/operacion/reportes` | Route | KEEP_AS_FALLBACK | No V2 equivalent yet | MEDIUM |
| `BusinessSliceOmniview` (legacy) | Component | REMOVE_AFTER_30_DAYS | Unused, deprecated by OMNI-P0 | LOW |
| `BusinessSliceOmniviewMatrix` | Component | REMOVE_AFTER_30_DAYS | 12K lines, V2 certified | MEDIUM |
| `BusinessSliceOmniviewReports` | Component | KEEP_TEMPORARILY | No V2 reports yet | MEDIUM |
| `OmniviewErrorBoundary` | Component | DO_NOT_TOUCH | Shared with V2 | HIGH |
| V1-only endpoints (11) | Endpoint | DEPRECATE_AFTER_COMPONENT_REMOVAL | Safe after V1 components gone | LOW |
| V1-shared endpoints (3 POST) | Endpoint | ALREADY_BLOCKED | Phase C.2 fail-closed | NONE |

---

## 6. Phased Deprecation Plan

### V1-D0: Audit Complete (THIS PHASE)
- Read-only audit. No code changes.

### V1-D1: Root Route Switch + Menu Hide
- Change root `/` and `/operacion` default to V2 professional (`operacion_omniview_v2`)
- Hide `/operacion/omniview` (legacy) from menu
- Hide `/operacion/omniview-matrix` from menu (keep route accessible)
- Show "Legacy V1" warning banner on V1 routes
- **Risk: LOW.** V2 professional is certified and smoke-verified.

### V1-D2: 30-Day Observation
- Monitor for V1 route access
- Confirm no operational dependency
- Keep all routes accessible

### V1-D3: Component Removal
- Remove V1-only components (11 files)
- Remove V1 CSS not shared
- Remove V1-only helpers (omniviewMatrixUtils, projectionMatrixUtils, omniviewUtils)

### V1-D4: Endpoint Cleanup
- Deprecate V1-only endpoints after component removal confirmed safe
- Keep shared endpoints (freshness, filters)

### V1-D5: Reports Migration (if needed)
- Build V2 reports equivalent before removing `BusinessSliceOmniviewReports`
- Or accept as final V2 scope limitation

---

## 7. What Was Not Changed

- No code modified
- No routes changed
- No components deleted
- No endpoints removed
- No backend, DB, refresh, Growth, Diagnostic, or Forecast changes

---

## 8. Next Prompt

> "V1-D1 Soft Deprecation: switch root/default route from V1 matrix to V2 professional. Hide V1 legacy/Omniview routes from menu. Keep all routes accessible. Add legacy warning banner on V1 routes. No backend/DB changes."

---

*Read-only audit complete. V1 can be soft-deprecated. V2 professional is ready.*