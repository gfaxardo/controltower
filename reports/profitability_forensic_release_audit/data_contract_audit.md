# Profitability Data Contract Audit — Endpoint-by-Endpoint Evidence

## Park ID: `64085dd85e124e2c808806f70d527ea8`

## Results

| Tab | Endpoint | Status | Rows | Key Data | UI Shows Empty? | Root Cause |
|-----|----------|--------|------|----------|-----------------|------------|
| **Overview** | `/overview` | OK | 17 KPIs, 30 trip days | billing_weeks=1, shift_days=26, profit=-5509.9 | NO (was before) | Server was DOWN. Now renders DiagnosticHeader + KPIs + cards |
| **Weekly Closed** | `/weekly?weeks=12` | OK | 1 week | 2026-05-18, profit=S/-5,509.90, revenue=142,474 | NO (was before) | Server was DOWN. Now renders 1 row |
| **Last Closed Day** | `/daily?days=30` | OK | 30 days | First day: 2026-05-27, 507 trips | NO (was before) | Server was DOWN. Now renders 30 rows |
| **Drivers** | `/drivers` | OK | 26 drivers | 2 profitable, 24 in loss | NO (was before) | Server was DOWN. Now renders 26 rows |
| **Vehicles** | `/vehicles` | LIMITED | 102 vehicles | Kia Soluto 2025 + 101 more | NO (was before) | Server was DOWN. Now renders 102 rows |

## Detailed Evidence

### Overview
```
HTTP 200
Status: OK
park_id: 64085dd85e124e2c808806f70d527ea8
billing_weeks_available: 1
shift_days_available: 26
days_with_trips: 30
data_confidence: MEDIUM
financial_history_status: PARTIAL
operational_history_status: HEALTHY
KPIs: 17 (trips_completed_30d, trips_cancelled_30d, cancellation_rate,
  revenue_gross_30d, ticket_avg, active_drivers,
  work_hours_weekly, revenue_per_hour, trips_per_hour,
  fuel_cost_weekly, maintenance_cost_weekly,
  driver_payment_weekly, profit_weekly, profit_per_trip,
  margin_pct, km_per_trip_total, fuel_per_km)
source_coverage.billing_weeks: 1
source_coverage.shift_days: 26
```

### Weekly Closed
```
HTTP 200
Status: OK
total_weeks: 1
source: module_weekly_billing
Week 2026-05-18: profit=-5509.9
```

### Last Closed Day
```
HTTP 200
Status: OK
total_days: 30
source: trips_2026
First day: 2026-05-27, trips_completed=507
All 30 days have data
```

### Drivers
```
HTTP 200
Status: OK
total_drivers: 26
profitable_count: 2
loss_count: 24
pct_profitable: 0.0769
source: module_weekly_billing
First driver: profit=195.4
```

### Vehicles
```
HTTP 200
Status: LIMITED
vehicles: 102
First vehicle: Kia Soluto 2025
source: module_miauto_cronograma
limitacion: No vehicle-to-driver assignment
```

## UI Rendering Path

For **Overview** tab (`activeTab === 'overview'`):
```
YegoProProfitabilityPage
  → <OverviewDiagnostic diagData={...} diagLoading={...} />
      → <DiagnosticHeader overview=... drivers=... vehicles=... />
      → <TopRankedCard rows={vehicles} /> (if vehicles loaded)
      → <DriverLeaderboard drivers={...} /> (if drivers loaded)
      → <DataConfidence /> (always renders)
```

`DiagnosticHeader.hasData` condition:
```
netWeekly !== null           → -5509.9 ✓
revWeekly !== null           → revenue present ✓
driverRows.length > 0        → 26 ✓
vehicleRows.length > 0       → 102 ✓
→ hasData = true → renders KPIs
```

For **tabs** (weekly/daily/drivers/vehicles):
```
loadTab(tabId) → fetcher() → setTabData(result)
!tabLoading && !tabError && tabData → renderTabPanel(tabId, tabData)
!tabLoading && !tabError && !tabData → <EmptyState />
```

## Verdict

**NONE of the 5 tabs are actually empty.** All endpoints return data.

The "No data" appearance reported by the user was caused by:
1. **Application servers were DOWN** (Vite :5173, uvicorn :8000) — confirmed by port audit
2. **Browser was showing CACHED content** from a previous session — only explanation for seeing UI on a dead port

With servers now running, all tabs render actual data. The only data quality warning is:
- `financial_history_status: PARTIAL` (only 1 billing week — need 4+ for reliable trends)
- `data_confidence: MEDIUM` (due to limited billing history)
