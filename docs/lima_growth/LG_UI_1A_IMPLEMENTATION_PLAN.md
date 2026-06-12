# LG-UI-1A — IMPLEMENTATION PLAN

**Date:** 2026-06-12
**Phase:** LG-UI-1A / Dashboard MVP Implementation
**Status:** PLAN

---

## 0. GOVERNANCE STATUS

- OMNI-P0: DATA LAYER CLOSED (OV2 series), VISUAL LAYER PENDING
- LG is separate motor (POST_OV2_TRANSITION_AUDIT.md:157, OV2_CLOSE_5:142)
- LG-SCH-2A: CERTIFIED
- LG-SERV-2A: CERTIFIED
- LG-TRUTH-1A: SOURCE_OF_TRUTH_RECONCILED
- LG-UI-1A Architecture: CERTIFIED

No governance conflict for LG-UI-1A implementation.

---

## 1. ARCHITECTURE SUMMARY

The existing `LimaGrowthDashboardV2.jsx` is an OPERATIONAL EXECUTION dashboard (Today's Action Plan, Queue, Signals, Config). LG-UI-1A creates a parallel **INTELLIGENCE VIEW dashboard** with 6 tabs for visualization and exploration.

Both dashboards coexist:
- **V2 (existing)**: Operational execution — build queues, export, configure capacity
- **UI-1A (new)**: Intelligence view — overview, segments, movement, RNA, driver explorer

---

## 2. FILE STRUCTURE (to create/modify)

```
frontend/src/
├── pages/
│   └── LimaGrowthDashboardUI1A.jsx          [NEW] Main dashboard page
│   └── lima-growth-ui1a/                     [NEW] Modular architecture
│       ├── hooks/
│       │   └── useGrowthIntelligence.js      [NEW] Data fetching hook
│       ├── components/
│       │   ├── FreshnessBanner.jsx           [NEW] Freshness/health/operability strip
│       │   ├── ExplainabilityTooltip.jsx     [MODIFY] Reuse with growth context
│       │   └── SharedComponents.jsx          [NEW] KPI cards, status badges, tables
│       └── sections/
│           ├── OverviewTab.jsx               [NEW] Tab 1
│           ├── ProgramsTab.jsx               [NEW] Tab 2
│           ├── SegmentsTab.jsx               [NEW] Tab 3
│           ├── MovementTab.jsx               [NEW] Tab 4
│           ├── RNATab.jsx                    [NEW] Tab 5
│           └── DriverExplorerTab.jsx         [NEW] Tab 6
├── services/
│   └── api.js                               [MODIFY] Add growth intelligence API functions
└── App.jsx                                  [MODIFY] Register new route
```

---

## 3. ENDPOINT CONTRACTS

### 3.1 ENDPOINTS TO CONSUME (existing)

| Tab | Endpoint | Source | Status |
|-----|----------|--------|--------|
| Global | `GET /growth/health` | serving_operability_service | EXISTS |
| Global | `GET /growth/freshness` | serving_freshness_audit_service | EXISTS |
| Global | `GET /growth/operability` | serving_operability_service | EXISTS |
| Overview | `GET /yego-lima-growth/operational-summary?date=` | serving_fact | EXISTS |
| Overview | `GET /yego-lima-growth/driver-state/summary?date=` | serving_fact | EXISTS |
| Overview | `GET /yego-lima-growth/operational-truth?date=` | DB query | EXISTS |
| Programs | `GET /yego-lima-growth/programs/summary?date=` | DB query | EXISTS |
| Programs | `GET /yego-lima-growth/programs/status?date=` | DB query | EXISTS |
| Segments | `GET /yego-lima-growth/taxonomy/summary?date=` | DB query | EXISTS |
| Movement | `GET /yego-lima-growth/movement/summary?date=` | DB query | EXISTS |
| Movement | `GET /yego-lima-growth/movement/list?date=` | DB query | EXISTS |
| RNA | `GET /yango-loyalty/summary` | MV read | EXISTS |
| RNA | `GET /yango-loyalty/kpis?city=` | MV read | EXISTS |
| RNA | `GET /yango-loyalty/city-comparison?month=&country=` | MV read | EXISTS |
| Driver Explorer | `GET /drivers/identity?*` | DB query | EXISTS |
| Driver Explorer | `GET /drivers/activity-summary?*` | DB query | EXISTS |
| Driver Explorer | `GET /drivers/lifecycle-summary?*` | DB query | EXISTS |

### 3.2 ENDPOINTS TO CREATE (serving-only, minimum)

None needed initially. All tab data can be derived from existing endpoints. 
If driver explorer needs a consolidated view exceeding existing endpoints, a lightweight `/yego-lima-growth/driver-explorer?date=&*` endpoint will be created as a serving-only aggregator.

---

## 4. COMPONENT DESIGNS

### 4.1 Dashboard Shell (LimaGrowthDashboardUI1A.jsx)

- Left sidebar with tab navigation (6 tabs + subtle branding)
- Top: FreshnessBanner (always visible)
- Main area: tab content with error boundary
- States: loading (per-tab), error (with retry), degraded (stale banner)

### 4.2 FreshnessBanner (always-on-top strip)

Data from `/growth/health` + `/growth/freshness` + `/growth/operability`
Shows:
- Overall system status (HEALTHY / WARNING / DEGRADED / CRITICAL)
- Stale assets count
- Freshness age per critical asset
- Remediation suggestions if degraded
- Scheduler status

### 4.3 Overview Tab

Data from: operational-summary + driver-state/summary + operational-truth

Sections:
1. **KPI Cards Row**: Total drivers, drivers with program, drivers without program, active programs, movement today, RNA drivers
2. **Program Distribution**: Bar chart (program -> driver count)
3. **Queue Status**: READY / HELD / EXPORTED counts
4. **Freshness & Operability Summary**: Quick status from /growth/health

### 4.4 Programs Tab

Data from: programs/summary + programs/status

Sections:
1. **Program Cards (4)**: ACTIVE_GROWTH, CHURN_PREVENTION, 14_90, HIGH_VALUE_RECOVERY
   - Each shows: eligible drivers, prioritized, queue count, priority, trend
2. **Program Comparison**: Side-by-side metrics
3. **Drilldown button**: Navigate to Driver Explorer filtered by program

### 4.5 Segments Tab

Data from: taxonomy/summary

Sections:
1. **Lifecycle Distribution**: Bar chart (ACTIVE, NEW_ACTIVE, AT_RISK, DECLINING, CHURNED)
2. **Activity Bands**: heavy, regular, light counts
3. **Value Tiers**: Top 20%, Mid 60%, Bottom 20%
4. **Momentum**: rising, stable, falling
5. **Drilldown button**: Filter Driver Explorer by segment

### 4.6 Movement Tab

Data from: movement/summary + movement/list

Sections:
1. **Movement KPIs**: Entries, exits, program changes today
2. **Transition Types**: Bar chart
3. **Top Movers Table**: driver_id, from->to, type, trigger
4. **Drilldown**: Driver movement history

### 4.7 RNA Tab

Data from: yango-loyalty/summary + kpis + city-comparison

Sections:
1. **RNA KPIs**: Total RNA, New (N), Reactivable (R)
2. **Contactability**: With phone / Without phone
3. **Cancelled Signals**: Post-contact cancellations
4. **City Comparison Table**
5. **Root Causes** (static/manual)

### 4.8 Driver Explorer Tab

Data from: /drivers/identity + /drivers/activity-summary + /drivers/lifecycle-summary

Master table with filters:
- program, lifecycle, segment, movement, RNA, search

Columns:
- driver_id, lifecycle, segment, program, movement, RNA status, last activity
- Explainability summary per row

---

## 5. DATA FLOW

```
/growth/health ────┐
/growth/freshness ─┤
/growth/operability ┤──> FreshnessBanner (global, always on)
                    │
operational-summary ┤
driver-state/summary┤──> Overview Tab
operational-truth ──┘
                    │
programs/summary ───┤
programs/status ────┘──> Programs Tab
                    │
taxonomy/summary ──────> Segments Tab
                    │
movement/summary ──┐
movement/list ─────┘──> Movement Tab
                    │
yango-loyalty/* ──────> RNA Tab
                    │
/drivers/* ───────────> Driver Explorer Tab
```

All data pre-computed (serving facts) or lightweight COUNT/MAX queries. No heavy runtime computation in UI.

---

## 6. PERFORMANCE CONSTRAINTS

- No runtime recalculation in frontend
- No N+1 queries from UI
- All endpoint data consumed as-is (no joins in frontend)
- Endpoints expected < 2s
- No historical calculations in UI
- Loading states per tab (not global freeze)

---

## 7. STATES

### Loading
- Per-tab skeleton/spinner
- FreshnessBanner shows "Checking..." initially

### Error
- Per-tab error message with retry button
- Graceful degradation (other tabs remain functional)

### Stale/Degraded
- FreshnessBanner shows amber/red when assets stale
- Shows age, remediation suggestion
- UI DOES NOT freeze
- Data shown with stale badge

---

## 8. ROUTE REGISTRATION

Add to App.jsx:
- New tab or sub-tab under "Lima Growth" for the intelligence dashboard
- Path: `/lima-growth/intelligence` or new top-level tab
- Component: lazy loaded `LimaGrowthDashboardUI1A`

---

## 9. IMPLEMENTATION ORDER

1. Write implementation plan (THIS DOCUMENT)
2. Add API functions to api.js
3. Create SharedComponents (KPICards, status badges)
4. Create FreshnessBanner component
5. Create useGrowthIntelligence hook
6. Create Dashboard Shell (LimaGrowthDashboardUI1A.jsx)
7. Create OverviewTab
8. Create ProgramsTab
9. Create SegmentsTab
10. Create MovementTab
11. Create RNATab
12. Create DriverExplorerTab
13. Register route in App.jsx
14. QA: build backend, build frontend, API validation, UI render
15. Certification document

---

## 10. RISKS

| Risk | Mitigation |
|------|-----------|
| Movement data stale (last Jun 5) | MovementTab shows stale banner |
| RNA root causes manual | RNATab uses static/manual table |
| Some V2 shadow tables have 0 rows | Fallback to V1 tables where needed |
| No dedicated driver explorer endpoint | Use existing /drivers/* filters, create minimal endpoint if needed |
| Freshness may show CRITICAL (pre-existing) | FreshnessBanner shows real status, not fake-green |
