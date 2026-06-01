# Dev Server Audit — Yego Pro Profitability Forensic

## Port Audit

| Port | Service | Status |
|------|---------|--------|
| 5173 | Vite dev server | **NOT LISTENING** |
| 8000 | uvicorn backend | **NOT LISTENING** |
| 5432 | PostgreSQL | Listening |

## Process Audit

| PID | Name | Purpose |
|-----|------|---------|
| 14024 | node | PowerShell child (not Vite) |
| 8040 | postgres | PostgreSQL database |

No Vite, uvicorn, or nginx processes found.

## Vite Configuration

```
Port: 5173
Proxy: /api → http://127.0.0.1:8000
HistoryApiFallback: Enabled
Base: /
```

## Production Build

```
Dist path:    frontend/dist/
Index:        frontend/dist/index.html → references index-DbeWUK1E.js
Build time:   2026-05-31 20:47:07
Bundle size:  106.3 KB (index), 134 KB (profitability chunk)
```

## Commands to Start

```bash
# Terminal 1 — Backend
cd C:\cursor\controltower\controltower
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2 — Frontend (dev)
cd C:\cursor\controltower\controltower\frontend
npm run dev
```

## Verification

After starting both servers:
1. `http://localhost:5173/fleet-project/yego-pro/profitability` → renders YegoProProfitabilityPage
2. `http://127.0.0.1:8000/fleet-project/yego-pro/profitability/kpi-explainability` → returns JSON
3. `http://127.0.0.1:8000/fleet-project/yego-pro/profitability/driver-drill?driver_id=xxx` → returns JSON
