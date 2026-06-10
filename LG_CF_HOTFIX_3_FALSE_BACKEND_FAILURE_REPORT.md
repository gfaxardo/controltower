# LG-CF-HOTFIX-3 — False Backend Failure Report

**Date**: 2026-06-10  
**Status**: RESOLVED  
**Classification**: ESM default vs named export mismatch  
**Affected File**: `frontend/src/pages/LimaGrowthDashboardV2.jsx`

---

## TAREA 1 — Audit

### Audited Files

| File | Role |
|---|---|
| `frontend/src/pages/LimaGrowthDashboardV2.jsx` | Dashboard component, fetches operational-date + governance-status on mount |
| `frontend/src/services/api.js` | Axios instance + API function exports |
| `frontend/src/pages/lima-growth-v2/hooks/useLimaGrowthData.js` | Data hook (static imports, no bug) |

### Fetch Chain

```
LimaGrowthDashboardV2.jsx:28-58 (useEffect [])
  ├── import('../services/api.js').then(m => m.api.get('/...'))
  │   └── Line 31: operational-date
  └── import('../services/api.js').then(m => m.api.get('/...'))
      └── Line 49: governance-status
```

---

## TAREA 2 — Exact Registration

| Detail | Value |
|---|---|
| **URL called** | `/yego-lima-growth/refresh/operational-date` |
| **Backend response (raw)** | `{"operational_data_date":"2026-06-09","is_fresh":true}` — **200 OK** |
| **URL called** | `/yego-lima-growth/refresh/governance-status` |
| **Backend response (raw)** | `{"operational_data_date":"2026-06-09","operability":"OPERABLE_STALE_WARNING",...}` — **200 OK** |
| **Exception thrown in browser** | `TypeError: Cannot read properties of undefined (reading 'get')` |
| **Error shown to user** | "Backend unreachable: operational-date endpoint failed" / "Governance status endpoint failed" |

The endpoints **respond correctly** (200 OK, valid JSON). The error is **100% client-side**. The request never reaches the network.

---

## TAREA 3 — Verification

| Check | Result |
|---|---|
| Endpoint returns 200? | Yes — verified via PowerShell direct to backend + proxy |
| Parser breaks? | No — `.then(resp => resp.data)` never executes; error is before `.then()` |
| Shape mismatch? | No — fetch never completes |
| `undefined` access? | **YES — `m.api` is `undefined`** |
| `Promise.all` rejection? | N/A — chains are separate |
| Error post-fetch? | No — error is pre-fetch (synchronous on the import resolution) |

### Root Cause: ESM Default vs Named Export

**`api.js` export structure** (verified):

```javascript
// api.js line 7
const api = axios.create({...})

// api.js line 1709
export default api

// Named exports (working correctly):
export const getLimaGrowthTodayActionPlan = ...
export const getLimaGrowthOperationalSummary = ...
// etc.
```

In ESM dynamic imports, the module namespace object assigns:
- `m.default` → the default export (`api` axios instance)  
- `m.namedExport` → any named export

**Bug** (`LimaGrowthDashboardV2.jsx:31,49`):

```javascript
import('../services/api.js').then(m => {
    return m.api.get('/yego-lima-growth/refresh/operational-date') // BUG
//         ^^^^^^ undefined
})
```

`m.api` resolves to `undefined` because there is **no named export called `api`**.  
`m.api.get(...)` throws `TypeError: Cannot read properties of undefined (reading 'get')`.  
Caught by `.catch()` → sets `dateError` / `governanceError` → false "Backend unreachable".

**Why handleRetryAll works** (lines 61-67):

```javascript
import('../services/api.js').then(m => m.getLimaGrowthTodayActionPlan(operationalDate))
//                                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
//                                      This IS a named export → works correctly
```

---

## TAREA 4 — Fix Applied

**File**: `frontend/src/pages/LimaGrowthDashboardV2.jsx`

| Line | Before | After |
|---|---|---|
| 31 | `m.api.get('/yego-lima-growth/refresh/operational-date')` | `m.default.get('/yego-lima-growth/refresh/operational-date')` |
| 49 | `m.api.get('/yego-lima-growth/refresh/governance-status')` | `m.default.get('/yego-lima-growth/refresh/governance-status')` |

**No other files affected**. Global grep for `m.api.` pattern in dynamic imports: **0 other matches**.

**Scope**: 2 lines changed. No backend changes. No endpoint changes. No program changes.

---

## TAREA 5 — QA Verification

### Backend endpoints (direct)

```
GET /yego-lima-growth/refresh/operational-date   → 200 OK  {"operational_data_date":"2026-06-09"}
GET /yego-lima-growth/refresh/governance-status  → 200 OK  {"operability":"OPERABLE_STALE_WARNING"}
```

### Vite proxy (through frontend)

```
GET http://[::1]:5173/api/yego-lima-growth/refresh/operational-date   → 200 OK
```

### Expected UI behavior after HMR/vite reload

| Check | Expected |
|---|---|
| Red banner "Backend unreachable" | **Desaparece** |
| Operational date | Muestra `2026-06-09` en header |
| Governance status | Carga (yellow/OPERABLE_STALE_WARNING banner) |
| Governance summary bar | Renderiza (Refresh Governance, facts OK/STALE, etc.) |
| READY/HELD/Universo counters | Cargan con datos de `data.todayActionPlan` |
| Sections render | Today's Action Plan, Programs, etc. cargan sin false errors |

---

## Conclusion

**False backend failure**: The backend always responded correctly. The frontend never sent a network request because the dynamic ESM import accessed `m.api` (non-existent named export) instead of `m.default` (the actual axios instance). The `TypeError` was caught and surfaced as "Backend unreachable", misleading the user.

**Root cause type**: ESM module namespace access mismatch (default export accessed as named export).

**Fix**: Change `m.api.get()` to `m.default.get()` (2 lines).
