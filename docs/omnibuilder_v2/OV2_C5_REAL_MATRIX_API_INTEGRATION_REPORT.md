# OV2-C.5 — REAL MATRIX API INTEGRATION REPORT

> **Date:** 2026-06-06
> **Motor:** Control Foundation / Matrix API Integration
> **Overall Status:** **PASS**

---

## 1. EXECUTIVE SUMMARY

The `/ops/omniview-v2/matrix` endpoint is implemented and responds with native MatrixResponse for both CT_TRIPS_2026 and YANGO_API_RAW sources. The frontend ShadowPage now consumes the real endpoint with automatic fallback to the shell adapter when unavailable.

---

## 2. GOVERNANCE

| Rule | Status |
|------|--------|
| Control Foundation | Active |
| No V1 touched | PASS |
| No serving productivo changed | PASS |
| YANGO_API_RAW canonical_ready=false | PASS |
| No Forecast/Suggestion/Decision/Action/AI | PASS |
| All additive | PASS |

---

## 3. FILES CREATED/MODIFIED

### Backend (4 files)
| File | Type |
|------|------|
| `app/repositories/omniview_v2_matrix_repository.py` | Created — 190 lines, CT + Yango raw queries |
| `app/services/omniview_v2_matrix_view_model_service.py` | Created — 300 lines, MatrixResponse builder |
| `app/routers/omniview_v2.py` | Modified — +1 endpoint /matrix |
| `scripts/audit_omniview_v2_matrix_api.py` | Created — audit script |

### Frontend (3 files)
| File | Type |
|------|------|
| `src/services/api.js` | Modified — +1 function `getOmniviewV2Matrix` |
| `hooks/useOmniviewV2Matrix.js` | Created — matrix data hook with fallback |
| `OmniviewV2ShadowPage.jsx` | Modified — uses real matrix + fallback banner |

---

## 4. ENDPOINT: GET /ops/omniview-v2/matrix

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| source_system | string | CT_TRIPS_2026 | Source system |
| grain | string | day | hour/day/week/month |
| date_from | string | null | ISO date |
| date_to | string | null | ISO date |
| country | string | peru | CT filter |
| city | string | lima | CT filter |

---

## 5. AUDIT RESULTS

| Test | Result | Detail |
|------|--------|--------|
| CT_TRIPS_2026 day | PASS | 6 rows × 1 col = 6 cells |
| YANGO_API_RAW day | PASS | 1 row × 1 col = 1 cell |
| Unsupported grain (Yango week) | PASS | GRAIN_NOT_SUPPORTED warning |

**Contract compliance:**
- All cells have row_id + column_id
- All cells have source_system + source_table
- canonical_ready correct per source
- warnings array always present
- Empty states handled gracefully

---

## 6. FRONTEND INTEGRATION

| Feature | Status |
|---------|--------|
| Matrix hook tries /matrix first | Active |
| Falls back to shell adapter on error | Active |
| Fallback banner visible | Active (amber "MATRIX_FALLBACK_ACTIVE") |
| MatrixShell receives real MatrixResponse | Active |
| No changes to visual system | PASS |
| Cell inspector works with real data | PASS |

---

## 7. BUILD QA

| Check | Result |
|-------|--------|
| Backend py_compile | PASS (all 3 new files) |
| Backend audit script | PASS (3/3) |
| Frontend build | PASS (6.8s, 194 modules) |
| Forbidden CSS patterns | 0 |
| Hardcoded hex in components | 0 |
| V1 chunks intact | All present |

---

## 8. RISKS

| Risk | Severity | Mitigation |
|------|----------|------------|
| `shellToMatrixResponse.js` still exists | LOW | Documented as TEMPORARY. Removed when happy path stable. |
| Matrix only returns orders metric currently | LOW | Multi-metric support planned for OV2-C.6 |
| Yango matrix has only 1 row (single park) | LOW | Expected. Multi-park coming in future. |

---

## 9. DECISION

**GO for OV2-C.6**

Conditions met:
- /ops/omniview-v2/matrix responds correctly
- CT_TRIPS_2026 day works
- YANGO_API_RAW day works
- MatrixShell consumes real MatrixResponse
- Fallback exists, banner visible when active
- Build clean
- V1 intact

---

## 10. NEXT PHASE

**OV2-C.6 — Multi-Metric Matrix & Compare UI**

Recommended:
1. Add revenue, drivers, TPD metrics to build_cells()
2. Wire compare mode in frontend using /matrix endpoint
3. Remove shellToMatrixResponse.js when matrix endpoint stable in production
4. Add error boundary for matrix-specific failures
5. Add grain support for Yango (hour)
