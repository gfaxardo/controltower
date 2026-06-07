# OV2-C.4 — V1 REGRESSION QA

> **Date:** 2026-06-06
> **Motor:** Control Foundation / Shadow UI Hardening
> **Status:** PASS

---

## 1. V1 ROUTE INTEGRITY

| Route | Status |
|-------|--------|
| `/operacion/omniview-matrix` | Active — V1 matrix loads |
| `/operacion/omniview` | Active — V1 classic view |
| `/operacion/business-slice` | Active — business slice view |
| `/performance/*` | Active — all performance routes |
| `/drivers/*` | Active — all driver routes |
| `/lima-growth` | Active — Lima Growth dashboard |

**OV2 routes are ADDITIVE only:**
- `/operacion/omniview-v2-matrix-sandbox` — new
- `/operacion/omniview-v2-shadow` — new

Zero V1 routes modified or removed.

---

## 2. BUILD CHUNK INTEGRITY

All V1 chunks present in build output:

| Chunk | Size | Present? |
|-------|------|----------|
| BusinessSliceOmniviewMatrix | 328 KB | YES |
| SupplyView | 71 KB | YES |
| YegoProProfitabilityPage | 138 KB | YES |
| LimaGrowthDashboardV2 | 51 KB | YES |
| echarts vendor | 695 KB | YES |
| React vendor | 176 KB | YES |

OV2 chunks are separate:
| Chunk | Size |
|-------|------|
| OmniviewV2ShadowPage | 12 KB |
| OmniviewV2MatrixSandbox | (in shadow bundle) |

---

## 3. API.JS INTEGRITY

| # | Check | Result |
|---|-------|--------|
| A1 | All V1 API functions intact | PASS — 0 V1 functions modified |
| A2 | New functions added at end | PASS — after Lima Growth functions |
| A3 | `export default api` preserved | PASS |
| A4 | No break in V1 endpoint calls | PASS — V1 functions unchanged |

V1 functions verified untouched (sample):
- `getBusinessSliceMonthly()` — unchanged
- `getBusinessSliceWeekly()` — unchanged
- `getBusinessSliceDaily()` — unchanged
- `getOmniviewProjection()` — unchanged

---

## 4. IMPORT ISOLATION

| # | Check | Result |
|---|-------|--------|
| I1 | No OV2 imports in V1 components | PASS — V1 components have zero OV2 imports |
| I2 | No V1 imports broken by OV2 | PASS — `App.jsx` import added, not replaced |
| I3 | OV2 CSS scoped to `.ov2-*` classes | PASS — no global style pollution |

---

## 5. CSS ISOLATION

| # | Check | Result |
|---|-------|--------|
| C1 | OV2 uses `.ov2-` prefixed classes | PASS — all classes prefixed |
| C2 | OV2 uses `--ov2-` CSS variables | PASS — no conflict with V1 `--ct-` variables |
| C3 | No `!important` in OV2 CSS | PASS |
| C4 | V1 styles unaffected | PASS — confirmed via build |

---

## 6. NAVIGATION REGISTRY

| # | Check | Result |
|---|-------|--------|
| N1 | V1 navigation items unchanged | PASS — controlTowerNavigationRegistry.js untouched |
| N2 | OV2 routes in ROUTE_MAP only | PASS — added as new entries |
| N3 | No OV2 route is default | PASS — `/` still maps to `operacion_omniview_matrix` |

---

## 7. VERDICT

**V1 REGRESSION QA: PASS** — Zero V1 files modified (except additive App.jsx + api.js additions). Zero V1 routes touched. Zero style conflicts. All V1 chunks in build output.
