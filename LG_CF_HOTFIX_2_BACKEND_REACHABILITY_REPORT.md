# LG-CF-HOTFIX-2 — Backend Reachability Root Cause Report

**Date**: 2026-06-09  
**Status**: RESOLVED  
**Classification**: B) Puerto incorrecto  
**Affected Phase**: Control Foundation (REOPENED/P0)

---

## TAREA 0 — Phase Context

- **Active phase**: Control Foundation — Omniview P0 Recovery (REOPENED 2026-06-03)
- **Constraint**: Diagnostic Engine PAUSED. No touching programs, priorización, queue, intraday, capacity.
- **Architectural rule**: Reliability before prediction. Serving-first architecture.

---

## TAREA 1 — Frontend Audit

### URL Resolution Chain

| Layer | File | Line | Value |
|---|---|---|---|
| Env variable | `frontend\.env.local` | 2 | `VITE_API_URL=http://127.0.0.1:8001` (historical, now corrected) |
| Vite proxy target | `frontend\vite.config.js` | 32 | `target: env.VITE_API_URL \|\| 'http://127.0.0.1:8000'` |
| Axios baseURL (DEV) | `frontend\src\services\api.js` | 5 | `'/api'` (proxied by Vite) |
| Axios baseURL (PROD) | `frontend\src\services\api.js` | 4-5 | `VITE_API_URL \|\| '/api'` |

### Critical API Calls

| Call | File | Line | Effective URL (DEV) |
|---|---|---|---|
| operational-date | `LimaGrowthDashboardV2.jsx` | 31 | `GET /api/yego-lima-growth/refresh/operational-date` |
| governance-status | `LimaGrowthDashboardV2.jsx` | 49 | `GET /api/yego-lima-growth/refresh/governance-status` |

In DEV mode, axios baseURL is always `/api`. Vite handles the proxy rewrite:
```
Browser → GET /api/yego-lima-growth/refresh/operational-date
Vite   → rewrite /api → /, forward to VITE_API_URL (from .env.local)
Target → GET http://127.0.0.1:{port}/yego-lima-growth/refresh/operational-date
```

---

## TAREA 2 — Backend Audit

### Router Registration

Both endpoints are served by the same router:

| Registration | File | Line |
|---|---|---|
| Router import | `backend\app\main.py` | 8 |
| Router registration | `backend\app\main.py` | 156 |

### Endpoint Definitions

| Endpoint | Router File | Lines | Handler |
|---|---|---|---|
| `GET /yego-lima-growth/refresh/operational-date` | `yego_lima_daily_refresh.py` | 38-40 | `detect_latest_closed_data_date()` |
| `GET /yego-lima-growth/refresh/governance-status` | `yego_lima_daily_refresh.py` | 43-45 | `get_governance_status()` |

Router prefix: `/yego-lima-growth/refresh` (line 14-16)

**Verdict**: Both endpoints are properly defined and registered. No routing issue.

---

## TAREA 3 — Endpoint Verification (Port 8000)

| Endpoint | URL | Status | Payload |
|---|---|---|---|
| `/docs` | `http://127.0.0.1:8000/docs` | **200 OK** | Swagger UI |
| `governance-status` | `http://127.0.0.1:8000/yego-lima-growth/refresh/governance-status` | **200 OK** | `{"operational_data_date":"2026-06-09","operability":"OPERABLE_STALE_WARNING",...}` |
| `operational-date` | `http://127.0.0.1:8000/yego-lima-growth/refresh/operational-date` | **200 OK** | `{"operational_data_date":"2026-06-09","is_fresh":true}` |

Backend responds correctly on port 8000. Zero errors.

---

## TAREA 4 — Root Cause Classification

**Category**: **B) Puerto incorrecto**

### Evidence Table

| Component | Expected | Actual | Result |
|---|---|---|---|
| Backend port | 8000 | 8000 ✓ | Responds 200 |
| `.env.local` VITE_API_URL (bug) | `http://127.0.0.1:8000` | `http://127.0.0.1:8001` ✗ | Vite forwards all requests to 8001 |
| Vite proxy fallback | `http://127.0.0.1:8000` | `http://127.0.0.1:8000` ✓ | Unused — .env.local has priority |
| Backend on port 8001 | Running | NOT running | ECONNREFUSED |

### How Vite priority works

```
Vite's loadEnv(mode, cwd, '') loads variables in order:
  1. .env.local            ← highest priority (CONTAINS THE BUG)
  2. .env.development
  3. .env
  4. env fallback in code  ← never reached
```

### Categories Eliminated

| Category | Reason |
|---|---|
| A) Backend caído | Backend responde 200 OK en `http://127.0.0.1:8000` |
| C) Router no registrado | `yego_lima_daily_refresh.router` registrado en `main.py:156` |
| D) Endpoint roto | Ambos endpoints devuelven 200 con payload válido |
| E) CORS | Error real es `ECONNREFUSED`, no CORS. CORS configurado en `main.py:71-77` |
| F) Proxy Vite | Proxy funciona correctamente; el target era el puerto equivocado |

---

## TAREA 5 — Fix Applied

**File**: `frontend\.env.local`  
**Line**: 2  
**Before**: `VITE_API_URL=http://127.0.0.1:8001`  
**After**: `VITE_API_URL=http://127.0.0.1:8000`

**Action required after fix**: Restart Vite dev server (Vite reads `.env.local` at startup only).

---

## TAREA 6 — QA Verification

### Direct backend tests (port 8000)

```
GET /docs                                               → 200 OK
GET /yego-lima-growth/refresh/governance-status         → 200 OK (payload: operational_data_date=2026-06-09)
GET /yego-lima-growth/refresh/operational-date          → 200 OK (payload: operational_data_date=2026-06-09)
```

### Proxy-through-Vite tests (port 5173 → backend 8000)

```
GET http://[::1]:5173/api/yego-lima-growth/refresh/operational-date   → 200 OK
GET http://[::1]:5173/api/yego-lima-growth/refresh/governance-status  → 200 OK
```

### Expected UI behavior after fix

| Check | Expected |
|---|---|
| Red error banner "Backend unreachable" | Desaparece |
| Operational date display | Muestra `2026-06-09` |
| Governance status | Carga correctamente |
| READY/HELD counters | Cargan con datos reales |
| Sections (Today's Action Plan, Programs, etc.) | Cargan sin errores 422 |

---

## Conclusion

**Single root cause**: `.env.local:2` had `VITE_API_URL=http://127.0.0.1:8001`, overriding Vite's proxy target. The backend was running on port 8000. No code changes needed — only a configuration value correction.

**Affected scope**: All frontend-to-backend communication. Not a backend bug, not a router issue, not a code defect.

**Fix**: Change `VITE_API_URL` in `.env.local` from `http://127.0.0.1:8001` to `http://127.0.0.1:8000`. Restart Vite dev server.
