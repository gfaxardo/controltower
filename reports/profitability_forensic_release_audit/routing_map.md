# Routing Map — Yego Pro Profitability

## Route Definition

```
Path:     /fleet-project/yego-pro/profitability
Tab:      TAB_FLEET_PROJECT ("Fleet Project")
Sub:      fleet_yegopro_profitability
File:     App.jsx line 166
```

## Import Chain

```
App.jsx:52
  const YegoProProfitabilityPage = lazy(() => import('./components/YegoProProfitabilityPage'))
                                                      └── resolves to src/components/YegoProProfitabilityPage.jsx

App.jsx:545
  {fleetProjectSubTab === 'fleet_yegopro_profitability' &&
    <YegoProProfitabilityPage key={`yegopro-profitability-${refreshKey}`} />}
```

## Component Resolution

- **Single source file**: `frontend/src/components/YegoProProfitabilityPage.jsx`
- **No duplicate**: Only one file named `YegoProProfitabilityPage.jsx` exists
- **No barrel export**: Direct import, no index.js re-export
- **No alias conflict**: Vite config has no path aliases redirecting this import
- **No lazy fallback component**: React.lazy() imports the correct file

## Lazy Loading

The component is loaded via `React.lazy()` + `<Suspense>`. During loading, a spinner is shown. If the component fails to load, React's ErrorBoundary would catch it. No error boundary wrapping this specific route was found, meaning an import failure would crash the entire app (not silently fallback to old code).

## Vite Dev Server Config

```
server.port: 5173
server.proxy: /api → http://127.0.0.1:8000
```

In dev mode, Vite serves the frontend on port 5173 and proxies `/api/*` requests to the backend on port 8000.

## ALL Profitability-related Files Found

```
frontend/src/components/YegoProProfitabilityPage.jsx  — main component (2,709 lines)
frontend/src/services/api.js                           — profitability API functions
backend/app/routers/yego_pro_profitability.py          — FastAPI router
backend/app/services/yego_pro_profitability_service.py — business logic
```

**No other YegoPro profitability files exist in the codebase.**
