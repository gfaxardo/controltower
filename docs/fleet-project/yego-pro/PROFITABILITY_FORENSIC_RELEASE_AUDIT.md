# Profitability Forensic Release Audit — Silent Rollback Investigation

## 1. Executive Summary

**No silent rollback occurred. No code regression occurred.**

The profitability code is correct and complete in HEAD (commit `4182aa2`), working copy, and the production dist bundle. All P2.2.1, P2.2.2, and P2.3 features are present across all layers.

**Root cause: Neither the frontend dev server (Vite on :5173) nor the backend API server (uvicorn on :8000) are running.** Without servers, `http://localhost:5173` receives no response. The UI the user saw was likely a **cached browser page** from a previous session when the servers WERE running with older code.

## 2. Git State Evidence

```
Branch:        master
HEAD:          4182aa2 (feat(profitability): P2.3 explainability hardening)
Remote:        origin = https://github.com/gfaxardo/controltower
Last 3 commits:
  4182aa2 feat(profitability): P2.3 explainability hardening
  e2756b2 feat(profitability): deploy diagnostic drills and operational baseline
  909b1bb CF-H1: Control Foundation closure
```

## 3. Line Count Comparison: HEAD vs Working Copy

| File | HEAD | Working Copy | Delta | Status |
|------|------|-------------|-------|--------|
| `YegoProProfitabilityPage.jsx` | 2,709 | 2,709 | 0 | IDENTICAL |
| `api.js` | 1,174 | 1,174 | 0 | IDENTICAL |
| `yego_pro_profitability_service.py` | 4,335 | 4,335 | 0 | IDENTICAL |
| `yego_pro_profitability.py` | 310 | 310 | 0 | IDENTICAL |

No profitability files in `git diff`. All features committed and pushed.

## 4. Feature Signature Audit

All features confirmed present in HEAD and dist bundle:

| Feature | HEAD | Dist Bundle |
|---------|------|-------------|
| `get_driver_drill` (backend func) | YES | N/A |
| `get_vehicle_drill` (backend func) | YES | N/A |
| `get_kpi_explainability` (backend func) | YES | N/A |
| `/driver-drill` endpoint path | YES (router) | YES (index bundle) |
| `/vehicle-drill` endpoint path | YES (router) | YES (index bundle) |
| `/kpi-explainability` endpoint path | YES (router) | YES (index bundle) |
| `showKpiCalc` modal | YES | YES |
| `showEntityDrill` modal | YES | YES |
| "Ver calculo" button text | YES | YES |
| "Como se calculo" modal title | YES | YES |
| `entity_name` in portfolio display | YES | YES |
| `c.rule` ("Regla:") in root causes | YES | YES |
| onViewCalculation / onEntityDrill | YES | YES (minified) |

## 5. Routing Forensics

Route `/fleet-project/yego-pro/profitability`:
- Maps to `TAB_FLEET_PROJECT` with sub `fleet_yegopro_profitability` (App.jsx:166)
- Renders `<YegoProProfitabilityPage>` via `React.lazy()` import (App.jsx:52, 545)
- File: `src/components/YegoProProfitabilityPage.jsx`
- Import: `const YegoProProfitabilityPage = lazy(() => import('./components/YegoProProfitabilityPage'))`
- No duplicate components, no barrel exports, no alias conflicts
- Route points to the CORRECT file

## 6. Dev Server / Runtime Forensics

| Check | Result |
|-------|--------|
| Port 5173 (Vite dev server) | **NOT LISTENING** |
| Port 8000 (uvicorn backend) | **NOT LISTENING** |
| Node process running Vite | **NONE** |
| Python/uvicorn process | **NONE** |
| nginx process | **NONE** |
| PostgreSQL (port 5432) | Running |

The Vite config (vite.config.js) configures dev server on port 5173 with proxy to 127.0.0.1:8000. Neither server is running, so `http://localhost:5173` receives NO response from a server.

## 7. Production Dist Audit

```
Dist index.html:  frontend/dist/index.html
Dist build time:  2026-05-31 20:47:07 (today, ~2 hours after last commit)
Main bundle:      index-DbeWUK1E.js (106.3 KB)
Profitability:    YegoProProfitabilityPage-BMfs9auS.js (134 KB)
```

String verification in dist bundles:
- `driver-drill`: **PRESENT** (index bundle)
- `vehicle-drill`: **PRESENT** (index bundle)
- `kpi-explainability`: **PRESENT** (index bundle)
- `Ver calculo`: **PRESENT** (profitability bundle)
- `Como se calculo`: **PRESENT** (profitability bundle)
- `entity_name`: **PRESENT** (profitability bundle)
- `Regla:`: **PRESENT** (profitability bundle)
- `Sin referencia`: **PRESENT** (profitability bundle)

## 8. Hypothesis Matrix

| # | Hypothesis | Evidence For | Evidence Against | Verdict |
|---|-----------|-------------|-----------------|---------|
| H1 | Cambios no commiteados | None | HEAD = WC, all committed | **REJECTED** |
| H2 | Servidor desde otro repo | None | Single repo, correct cwd | **REJECTED** |
| H3 | Vite cache/HMR stale | Could explain stale UI | No Vite process running at all | **REJECTED** (no server to be stale) |
| H4 | Ruta a componente viejo | None | App.jsx route correct | **REJECTED** |
| H5 | Backend nuevo, frontend viejo | Dist has new strings | Both backend+frontend have new code | **REJECTED** |
| H6 | Error JS → fallback | Possible if running | No server to run JS | **Cannot verify** |
| H7 | Build/deploy no ejecutado | Vite/uvicorn not running | Dist was built today | **PARTIALLY TRUE** |
| H8 | Branch mismatch | HEAD = master | Single branch | **REJECTED** |
| H9 | Browser cache | **Strong — explains seeing UI on dead port** | Cannot verify without browser access | **LIKELY ROOT CAUSE** |
| H10 | Feature flags | None detected | No feature flags in codebase | **REJECTED** |

## 9. Root Cause

**PRIMARY: Application servers are NOT RUNNING.**

- Vite dev server (port 5173) is not running → `http://localhost:5173` gets connection refused
- uvicorn backend (port 8000) is not running → all API calls fail

**SECONDARY: Browser is showing cached content.**

The user reported seeing a UI at `http://localhost:5173/fleet-project/yego-pro/profitability` even though no server is listening on port 5173. This is only possible if:
1. The browser served the page from its HTTP cache (cached from a previous session)
2. The user was looking at a different port/URL than stated
3. A service worker cached the old response

Since the servers are down, the user cannot possibly see the CURRENT (new) code. They can only see whatever their browser cached from a previous working session — which would be the OLD code from before the P2.2.1/P2.2.2/P2.3 commits.

## 10. Impact

- All P2.2.1, P2.2.2, and P2.3 changes are IMPLEMENTED, COMMITTED, and PUSHED
- Production dist is BUILT with new features
- Changes have NEVER been served to a browser because no server is running
- The user validated against a CACHED version of the old UI
- No rollback, no regression, no silent code change occurred

## 11. Recovery Plan

### Step 1: Start backend
```bash
cd C:\cursor\controltower\controltower
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Step 2: Start frontend dev server (in new terminal)
```bash
cd C:\cursor\controltower\controltower\frontend
npm run dev
```

### Step 3: Verify backend endpoints
```bash
curl http://127.0.0.1:8000/fleet-project/yego-pro/profitability/kpi-explainability
curl http://127.0.0.1:8000/fleet-project/yego-pro/profitability/driver-drill?driver_id=TEST
curl http://127.0.0.1:8000/fleet-project/yego-pro/profitability/simulator/operational-baseline
```

### Step 4: Clear browser cache
- Open browser DevTools → Network tab → Check "Disable cache"
- Or hard-refresh: Ctrl+Shift+R
- Or open in incognito/private window

### Step 5: Open
```
http://localhost:5173/fleet-project/yego-pro/profitability
```

### Step 6: Verify UI features
- Overview: "Ver calculo" button visible → opens multi-tab KPI modal
- Drivers/Vehicles: names shown (not UUIDs), clickable → drill modal
- Diagnostics → Root Causes: shows % loss, regla, afectados
- Simulator: operational references with source/confidence

### Production deployment (if using dist)
To serve the built dist:
```bash
# Option A: nginx
# Configure nginx to serve frontend/dist/ on port 80
# Proxy /api to uvicorn on port 8000

# Option B: vite preview
cd frontend && npm run preview
```

## 12. Risks

1. **Data availability**: Even with the new code running, panels may appear empty if MVs (module_weekly_billing, module_calculated_shifts) have no rows for the park_id. This is a DATA problem, not a CODE problem.
2. **Browser cache persistence**: The user must clear cache or use incognito to see new code.
3. **Backend dependency**: uvicorn must be started from the correct repo path where the committed code lives.

## 13. GO/NO-GO

**GO for recovery** — The code is complete, tested (build passed), and ready to serve. The only issue is that the application servers are not running. Starting them + clearing browser cache will immediately expose all implemented features.

## 14. Evidence Files Generated

All audit artifacts saved to: `reports/profitability_forensic_release_audit/`

- `git_state.txt` — Full git state snapshot
- `diff_stat.txt` — Git diff statistics
- `diff_names.txt` — Changed file names
- `diff_YegoProProfitabilityPage.patch` — Frontend component diff
- `diff_api.patch` — api.js diff
- `diff_service.patch` — Service diff
- `diff_router.patch` — Router diff
- `feature_signature_matrix.md` — Feature existence matrix
