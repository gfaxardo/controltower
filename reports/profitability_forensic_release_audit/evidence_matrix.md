# Profitability Evidence Audit — Endpoint-by-Endpoint

All data captured at runtime from running servers (uvicorn:8000 + Vite:5173).

## Evidence Matrix

| Tab | Endpoint | HTTP | Backend Rows | API Key | TabularPanel reads | Rows Extracted | Renders |
|-----|----------|------|-------------|---------|-------------------|---------------|---------|
| **Overview** | `/overview` | 200 | 17 KPIs | `kpis` | N/A (uses DiagnosticHeader) | 17 via getMetricValue | **YES** |
| **Weekly** | `/weekly` | 200 | 1 week | `weeks` | `data.rows \|\| data.data \|\| Array.isArray` | **null** | **EMPTY** |
| **Daily** | `/daily` | 200 | 30 days | `days` | `data.rows \|\| data.data \|\| Array.isArray` | **null** | **EMPTY** |
| **Drivers** | `/drivers` | 200 | 26 drivers | `drivers` | `data.rows \|\| data.data \|\| Array.isArray` | **null** | **EMPTY** |
| **Vehicles** | `/vehicles` | 200 | 102 vehicles | `vehicles` | `data.rows \|\| data.data \|\| Array.isArray` | **null** | **EMPTY** |

## Root Cause

`TabularPanel` (line 2510) does NOT use `extractRows()`. It has its own hardcoded extraction:

```js
// TabularPanel — BROKEN for profitability API responses
const rows = data.rows || data.data || (Array.isArray(data) ? data : null)
```

But the profitability API returns responses with different keys:
- `/weekly` → `{weeks: [...], total_weeks: 1}`
- `/daily` → `{days: [...], total_days: 30}`
- `/drivers` → `{drivers: [...], summary: {...}}`
- `/vehicles` → `{vehicles: [...], limitation: "..."}`

None of these have a `rows` or `data` key, so `TabularPanel` gets `null`, which triggers:
```js
if (!rows || rows.length === 0) return <><GuideBlock tabId={tabId} /><EmptyState tabId={tabId} /></>
```

The `extractRows()` helper at line 205 already handles nested arrays:
```js
function extractRows(data) { return data?.rows || data?.data || (Array.isArray(data) ? data : []) }
```

But this helper is only used inside `OverviewDiagnostic` sub-components (DiagnosticHeader, DriverLeaderboard, TopRankedCard, etc.) — NOT in TabularPanel.

## Evidence: Overview renders data (uses different path)

Overview DOES render because it goes through `OverviewDiagnostic` → `DiagnosticHeader` which reads from `diagData.overview` and `diagData.drivers`/`diagData.vehicles` directly via `extractRows()`.

## Confirmation

To prove this with no code changes, here's the exact chain:

### Weekly tab (EMPTY)
1. `loadTab('weekly')` → `getYegoProProfitabilityWeekly()` → returns `{weeks: [{week_start:'2026-05-18',...}], total_weeks:1}`
2. `setTabData(result)` → tabData = `{weeks: [...], ...}`
3. Render: `!tabLoading && !tabError && tabData && renderTabPanel('weekly', tabData)`
4. `renderTabPanel('weekly', data)` → `TabularPanel({data})` 
5. `TabularPanel`: `data.rows`=undefined, `data.data`=undefined, `Array.isArray(data)`=false → rows=**null**
6. `if (!rows)` → **TRUE** → `<EmptyState tabId="weekly" />`
7. String shown: "No hay semanas cerradas disponibles. Data operativa disponible, data financiera parcial."

### Drivers tab (EMPTY)
1. `loadTab('drivers')` → `getYegoProProfitabilityDrivers()` → returns `{drivers: [{driver_id:'a53c...', driver_name:'Sender Quiros...',...}], summary:{...}}`
2. `setTabData(result)` → tabData = `{drivers: [...], ...}`
3. Render: `!tabLoading && !tabError && tabData && renderTabPanel('drivers', tabData)`
4. `renderTabPanel('drivers', data)` → `TabularPanel({data})`
5. `TabularPanel`: `data.rows`=undefined, `data.data`=undefined, `Array.isArray(data)`=false → rows=**null**
6. `if (!rows)` → **TRUE** → `<EmptyState tabId="drivers" />`
7. String shown: "No hay datos de conductores disponibles. Data operativa disponible, data financiera parcial."
