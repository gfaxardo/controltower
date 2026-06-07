# OV2-CX.1D — DATA PRESENCE RECONCILIATION

> **Date:** 2026-06-06
> **Motor:** Control Foundation / Diagnostic
> **Classification:** FRONTEND_ERROR — JS crash prevented data load

---

## 1. PIPELINE TRACE (2026-06-05)

| Stage | Rows/Cells | Status |
|-------|-----------|--------|
| **Source** (`ops.real_business_slice_day_fact`) | 6 rows, 15,073 trips | OK |
| **Repository** (`get_ct_matrix_data`) | 6 rows | OK |
| **ViewModel** (`build_matrix_response`) | 6 rows × 1 col = 6 cells | OK |
| **Endpoint** (`/ops/omniview-v2/matrix`) | 6 cells | OK |
| **Frontend hook** | CRASHED | FAIL |

---

## 2. ROOT CAUSE

**`ReferenceError: Cannot access 'handleCloseInspector' before initialization`**

In `OmniviewV2ShadowPage.jsx`, the `handleGoToLatestDate` callback referenced `handleCloseInspector` before it was defined. JavaScript `const` declarations are hoisted but not initialized, causing the TDZ (Temporal Dead Zone) error.

This crashed the entire OmniviewV2ShadowPage component during the initial render cycle, before any data fetching could complete. The OmniviewErrorBoundary caught the error and displayed the crash message instead of the shadow UI.

---

## 3. FIX

Reordered hooks: moved `handleCloseInspector` before `handleGoToLatestDate`.

```javascript
// BEFORE (broken)
const handleGoToLatestDate = useCallback(() => {
    handleCloseInspector();  // TDZ error
}, [handleCloseInspector]);

const handleCloseInspector = useCallback(() => { ... }, []);

// AFTER (fixed)
const handleCloseInspector = useCallback(() => { ... }, []);
const handleGoToLatestDate = useCallback(() => {
    handleCloseInspector();  // OK
}, [handleCloseInspector]);
```

---

## 4. VERIFICATION

| Check | 2026-06-05 | 2026-06-06 |
|-------|-----------|-----------|
| Source (DB) | 6 rows, 15,073 trips | 0 rows |
| Repository | 6 rows | NO_DATA |
| ViewModel | 6 cells | 0 cells, NO_DATA warning |
| view_status | READY | EMPTY |
| UI | Matrix with data | Empty state banner |

---

## 5. BUILD

| Check | Result |
|-------|--------|
| Build | PASS (6.9s) |
| Backend pipeline | Correct |
| Frontend hook order | Fixed |
| V1 intact | All chunks present |

---

## 6. DECISION

**GO** — Data pipeline is correct end-to-end. The frontend crash from hook ordering is resolved.
