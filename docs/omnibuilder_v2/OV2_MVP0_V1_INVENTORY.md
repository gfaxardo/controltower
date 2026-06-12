# OV2-MVP.0 — OMNIVIEW V1 INVENTORY

> **Fase:** OV2-MVP.0 — Feature Parity Audit
> **Sub-document:** V1 Inventory
> **Fecha:** 2026-06-12
> **Source:** Production code at `/operacion/omniview-matrix`

---

## 1. ROUTES (Frontend)

| Route | Tab | Status | View |
|-------|-----|--------|------|
| `/operacion/omniview-matrix` | Operacion | **ACTIVE (default)** | `BusinessSliceOmniviewMatrix` — canonical production matrix |
| `/operacion/omniview` | Operacion | HIDDEN_FROM_NAV | `BusinessSliceOmniview` — legacy flat view |
| `/operacion/reportes` | Operacion | ACTIVE | `BusinessSliceOmniviewReports` — ECharts reports |
| `/operacion/control-loop-plan-vs-real` | Operacion | ACTIVE | `ControlLoopPlanVsRealView` — standalone PvR |
| `/operacion/business-slice` | Operacion | HIDDEN_FROM_NAV | `BusinessSliceView` — business slice detail |
| `/operacion/lob-drill` | Operacion | ACTIVE | `RealLOBDrillView` — LOB dimensional drill |
| `/performance/plan-vs-real` | Performance | ACTIVE | Monthly PvR + Weekly PvR |
| `/performance/real` | Performance | ACTIVE | `RealOperationalView` |
| `/operacion/oportunidades` | Operacion | ACTIVE | `OperationalOpportunitiesView` |
| `/en-revision/real-vs-proyeccion` | En revision | BACKLOG, HIDDEN | `RealVsProjectionView` — Forecast Engine |

---

## 2. COMPONENTS (Frontend)

### 2.1 Core Matrix (12 components)

| Component | Lines | Purpose |
|-----------|-------|---------|
| `BusinessSliceOmniviewMatrix.jsx` | 4,072 | Main production matrix grid |
| `BusinessSliceOmniviewMatrixTable.jsx` | — | Virtual-scrolled table renderer |
| `BusinessSliceOmniviewMatrixHeader.jsx` | — | Column headers |
| `BusinessSliceOmniviewMatrixCell.jsx` | — | Individual cell (value + signal color) |
| `BusinessSliceOmniviewProjectionCell.jsx` | — | Projection-mode cell |
| `BusinessSliceOmniviewProjectionTable.jsx` | — | Projection-mode table |
| `BusinessSliceOmniviewKpis.jsx` | — | KPI strip (Trips, Revenue, Comm%, Drivers, Cancel%) |
| `BusinessSliceOmniviewInspector.jsx` | 904 | Side panel: Evolution + Momentum drill |
| `OmniviewProjectionDrill.jsx` | 870 | Projection drill panel |
| `OmniviewTopDeviations.jsx` | — | Top-5 deviations (deprecated) |
| `MatrixExecutiveBanner.jsx` | — | Executive summary banner |
| `OmniviewErrorBoundary.jsx` | — | Error boundary wrapper |

### 2.2 Shared Omniview (8 components)

| Component | Purpose |
|-----------|---------|
| `omniviewMatrixUtils.js` (1208 lines) | Matrix utilities, KPI definitions, formatting, signal colors |
| `OmniviewFilterPrimitives.jsx` | Year/Month selects, FilterSelect |
| `OmniviewCommandHeader.jsx` | Health indicators (freshness dot, trust status, coverage %) |
| `OmniviewFreshnessGovernanceCard.jsx` | Freshness governance card |
| `OmniviewMomentumDrillChart.jsx` | ECharts momentum drill chart |
| `OmniviewMomentumPriorityStrip.jsx` | Momentum priority strip |
| `OperationalPriorityLayer.jsx` | Operational priority layer |
| `insightEngine.js` | Insights/thresholds engine |
| `alertingEngine.js` | Alert generation |
| `rootCauseEngine.js` | Root cause analysis |
| `trustInspectorDiagnostics.js` | Trust diagnostics for inspector |

### 2.3 Supporting (7 components)

| Component | Purpose |
|-----------|---------|
| `OperationalStatusBar.jsx` | Collapsible bar: freshness, coverage, period state, trust, KPI summary |
| `GlobalFreshnessBanner.jsx` | Global data freshness banner |
| `DataTrustBadge.jsx` | Trust status badge (ok/warning/blocked) |
| `DataStateBadge.jsx` | Data state indicator |
| `FactStatusPanel.jsx` | Fact layer materialization status + backfill controls |
| `BusinessSliceOmniviewReports.jsx` | ECharts-based reports (852 lines) |
| `BusinessSliceInsightsPanel.jsx` | Insights panel |

---

## 3. BACKEND ENDPOINTS (V1 — `/ops`)

### 3.1 Core Matrix (16 endpoints)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/ops/business-slice/omniview` | REAL comparison: current vs previous period |
| GET | `/ops/business-slice/monthly` | Monthly business slice table |
| GET | `/ops/business-slice/weekly` | Weekly business slice table |
| GET | `/ops/business-slice/daily` | Daily business slice table |
| GET | `/ops/business-slice/omniview-projection` | Projection mode (plan vs real) |
| GET | `/ops/business-slice/omniview-projection/serving-plan-versions` | Plan versions for projection |
| GET | `/ops/business-slice/omniview-momentum-drill` | Momentum drill series |
| GET | `/ops/business-slice/matrix-operational-trust` | Matrix integrity validation |
| GET | `/ops/business-slice/filters` | Available filters |
| GET | `/ops/business-slice/coverage` | Coverage data |
| GET | `/ops/business-slice/unmatched` | Unmatched items |
| GET | `/ops/business-slice/conflicts` | Conflicts |
| GET | `/ops/business-slice/subfleets` | Subfleet listing |
| GET | `/ops/business-slice/fact-status` | Fact table status |
| POST | `/ops/business-slice/backfill` | Trigger backfill |
| POST | `/ops/business-slice/matrix-issue-action` | Log matrix issue action |

### 3.2 Plan vs Real (3 endpoints)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/ops/plan-vs-real/monthly` | Monthly PvR comparison |
| GET | `/ops/plan-vs-real/alerts` | PvR alerts |
| GET | `/ops/control-loop/plan-vs-real` | Control loop PvR |

### 3.3 Real Drill (5 endpoints)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/ops/real-drill/summary` | Country/period timeline |
| GET | `/ops/real-drill/by-lob` | By LOB drill |
| GET | `/ops/real-drill/by-park` | By park drill |
| GET | `/ops/real-drill/coverage` | Coverage drill |
| GET | `/ops/real-drill/totals` | Totals over range |

### 3.4 Real LOB (10 endpoints)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/ops/real-lob/monthly` | Monthly LOB |
| GET | `/ops/real-lob/weekly` | Weekly LOB |
| GET | `/ops/real-lob/drill` | LOB drill PRO |
| GET | `/ops/real-lob/drill/children` | Drill children |
| GET | `/ops/real-lob/drill/parks` | Park drill filter |
| GET | `/ops/real-lob/filters` | LOB filters |
| GET | `/ops/real-lob/comparatives/*` | WoW/MoM comparatives |

### 3.5 Freshness/Health (6 endpoints)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/ops/business-slice/real-freshness` | Fact freshness |
| GET | `/ops/omniview/freshness` | Full governance: RAW → day → week → month |
| GET | `/ops/omniview/weekly-serving-guardrails` | week_fact vs serving |
| GET | `/ops/serving/health` | Serving layer health |
| GET | `/ops/serving/coverage` | Serving fact coverage |
| GET | `/ops/serving/integrity` | Serving integrity |

### 3.6 Other (7 endpoints)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/ops/real-operational/snapshot` | Today/yesterday/this_week |
| GET | `/ops/real-operational/day-view` | Last N days |
| GET | `/ops/real-operational/hourly-view` | Hourly |
| GET | `/ops/data-freshness` | Data freshness audit |
| GET | `/ops/data-pipeline-health` | Pipeline health |
| GET | `/ops/kpi-consistency-audit` | KPI grain consistency |
| GET | `/ops/rollup-mismatch-audit` | Rollup mismatch diagnostic |

---

## 4. KPIs VISIBLES

| KPI | Format | Support |
|------|--------|---------|
| `trips_completed` | Integer | day/week/month |
| `active_drivers` | Integer | day/week/month |
| `revenue_yego_net` | Currency PEN | day/week/month |
| `avg_ticket` | Currency PEN | day/week/month |
| `trips_per_driver` | Decimal | day/week/month |
| `commission_pct` | Percentage | day/week/month |
| `cancel_rate_pct` | Percentage | day/week/month |

---

## 5. VIEWS / MODES

| View | Description |
|------|-------------|
| **Matrix (Real)** | Core matrix: KPI × business_slice grid, current vs previous period |
| **Matrix (Projection)** | Plan vs real projection matrix with root cause analysis |
| **Evolution** | Current vs previous comparison (HIDDEN: EVOLUTION_LEGACY flag) |
| **Reports** | ECharts bar/line/heatmap charts |
| **Control Loop PvR** | Standalone plan vs real table with signal colors |
| **LOB Drill** | Dimensional drill (country → city → park → LOB → service) |
| **Real Operational** | Snapshot/day-view/hourly operational view |

---

## 6. FILTERS

| Filter | Type | Granularity |
|--------|------|-------------|
| Year | Select | — |
| Month | Select (ENE-DIC) | — |
| City | Select | — |
| Country | Select | — |
| Business Slice | Select | — |
| KPI focus | Select | — |
| Grain | Toggle | day / week / month |
| Subfleet | Toggle | on/off |
| Plan version | Select | — |

---

## 7. UX FEATURES

| Feature | Status | Notes |
|---------|--------|-------|
| Sticky headers | ✓ | Matrix column headers |
| Virtual scroll | ✓ | Large matrix performance |
| Signal colors | ✓ | Green/amber/red per thresholds |
| Cell inspector side panel | ✓ | Evolution + Momentum modes |
| KPI cards strip | ✓ | Live values + delta arrows |
| Operational status bar | ✓ | Collapsible freshness/coverage/trust |
| Freshness governance | ✓ | RAW → day → week → month chain |
| Trust badges | ✓ | ok/warning/blocked |
| Backfill controls | ✓ | Trigger + progress |
| Error boundary | ✓ | Graceful failure |
| Loading skeleton | ✓ | Skeleton during fetch |
| Empty state | ✓ | Smart empty state |
| Fullscreen toggle | ✓ | F11 or button |
| ECharts reports | ✓ | Bar, line, heatmap |

---

## 8. DATABASE OBJECTS (Production Serving Chain)

```
public.trips_2026
    ↓
ops.real_business_slice_hour_fact
    ↓
ops.real_business_slice_day_fact    ← PRIMARY daily serving
ops.real_business_slice_week_fact   ← PRIMARY weekly serving
ops.real_business_slice_month_fact  ← PRIMARY monthly serving
    ↓
ops.driver_day_slice_fact           ← bridge (driver-park-day)
    ↓
ops.real_drill_dim_fact             ← dimensional drill
    ↓
ops.omniview_v2_serving_snapshot    ← pre-built payload cache (V2)
```

**MVs:** `mv_real_trips_monthly` (LEGACY), `mv_real_lob_month_v2` (CANONICAL), `mv_plan_vs_real_monthly_fact_canonical`

---

## 9. SERVICE FILES

| Service | Role |
|---------|------|
| `business_slice_omniview_service.py` | Matrix current-vs-previous, MoM/WoW/DoD, signals |
| `plan_vs_real_service.py` | Plan vs Real monthly (realkey, parity) |
| `real_drill_service.py` | Real LOB drill |
| `real_lob_drill_pro_service.py` | Enhanced drill PRO |
| `omniview_freshness_governance_service.py` | Freshness governance chain |
| `omniview_matrix_integrity_service.py` | Matrix integrity validation |
| `control_loop_plan_vs_real_service.py` | Control loop PvR |
| `projection_expected_progress_service.py` | Expected progress from serving |

---

## 10. V1 TOTAL SCOPE SUMMARY

| Category | Count |
|----------|-------|
| Routes | 10 (5 ACTIVE, 2 HIDDEN, 1 BACKLOG) |
| Components | 30+ |
| Endpoints | 47+ |
| KPIs | 7 core |
| Views/Modes | 7 |
| Filter dimensions | 9 |
| Service files | 8+ |
| DB fact tables | 5 core + 6 MVs + 10 views |
| Lines of code (matrix) | ~4,072 + 904 + 870 + 1,208 = ~7,054 (core only) |
