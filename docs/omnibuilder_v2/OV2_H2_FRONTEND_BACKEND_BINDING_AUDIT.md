# OV2-H.2 — FRONTEND BACKEND BINDING AUDIT

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Backend Capacity
> **Status:** AUDIT COMPLETE — BINDING CORRECT

---

## 1. BINDING CHAIN

```text
Frontend (Vite :5173) → proxy /api → VITE_API_URL → Backend uvicorn :8000
         ↓                         ↓
   api.js baseURL='/api'     vite.config.js target: 127.0.0.1:8000
```

## 2. CONFIGURATION AUDIT

### 2.1 `frontend/.env`

| Variable | Value | Status |
|----------|-------|--------|
| `VITE_API_URL` | `http://127.0.0.1:8000` | **CORRECT — points to Control Tower** |
| `VITE_AUTH_REQUIRED` | `false` | OK (dev) |

### 2.2 `frontend/src/services/api.js`

| Line | Config | Value |
|------|--------|-------|
| 4 | `apiBase` | `VITE_API_URL` or `''` |
| 5 | `baseURL` (DEV) | `'/api'` (proxied by Vite) |
| 5 | `baseURL` (PROD) | `apiBase` or `'/api'` |
| 8 | axios `baseURL` | Resolved per above |
| 9 | axios `timeout` | 60000ms (60s) |

### 2.3 `frontend/vite.config.js`

| Line | Config | Value |
|------|--------|-------|
| 32 | Vite proxy target | `VITE_API_URL` or `http://127.0.0.1:8000` |

## 3. DEVMODE FLOW

```
Browser :5173 → axios GET /api/ops/omniview-v2/shell
              → Vite dev proxy rewrites to http://127.0.0.1:8000/ops/omniview-v2/shell
              → Backend uvicorn :8000 → PostgreSQL :5432
```

## 4. PRODUCTION FLOW

```
Browser :443 → nginx → /api → uvicorn :8000 (--workers N)
                           or
Browser :443 → VITE_API_URL=http://162.55.214.109:8000 (direct dev expose)
```

## 5. PORT AUDIT

| Port | Expected | Actual | Status |
|------|----------|--------|--------|
| 8000 | Control Tower backend | uvicorn `app.main:app` | **MATCH** |
| 9001 | OTHER APP (not CT) | Separate uvicorn, different app | **EXCLUDED** |
| 5173 | Frontend dev server (Vite) | node/vite | **MATCH** |
| 5432 | PostgreSQL | Remote 168.119.226.236 | **MATCH** |

## 6. allow_runtime AUDIT

| Location | Found? |
|----------|--------|
| `frontend/src/services/api.js` | **NO** |
| `frontend/src/pages/**/*.jsx` | **NO** |
| `frontend/src/hooks/**/*.js` | **NO** |
| `frontend/src/components/**/*.jsx` | **NO** |

**Verdict: Frontend NEVER sends `allow_runtime=true`.** Compliant by default.

## 7. RISK ASSESSMENT

| Risk | Severity | Details |
|------|----------|---------|
| VITE_API_URL pointing to wrong port | LOW | Currently `:8000` — correct. If someone changes to `:9001`, frontend binds to wrong app |
| Production VITE_API_URL not set | LOW | Falls back to same-origin `/api` — correct with nginx |
| Backend identity not verifiable | **FIXED** | New `GET /ops/omniview-v2/backend-identity` → returns `YEGO_CONTROL_TOWER` |
| FRONTEND_BACKEND_MISMATCH in dev | LOW | Both apps share Python env; mitigated by backend-identity check |

## 8. BACKEND-IDENTITY VALIDATION CHECK

Run from browser dev tools:
```javascript
fetch('/api/ops/omniview-v2/backend-identity')
  .then(r => r.json())
  .then(d => console.assert(d.app_name === 'YEGO_CONTROL_TOWER', 'WRONG BACKEND'))
```

## 9. VERDICT

**PASS** — Frontend correctly binds to Control Tower backend on `:8000`. No `allow_runtime` in frontend code. Backend identity endpoint added for runtime verification.
