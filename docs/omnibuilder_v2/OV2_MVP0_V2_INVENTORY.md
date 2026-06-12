# OV2-MVP.0 — OMNIVIEW V2 INVENTORY

> **Fase:** OV2-MVP.0 — Feature Parity Audit
> **Sub-document:** V2 Inventory
> **Fecha:** 2026-06-12
> **Source:** Shadow code at `/operacion/omniview-v2-shadow` + `/ops/omniview-v2`

---

## 1. ROUTES (Frontend)

| Route | Tab | Status | View |
|-------|-----|--------|------|
| `/operacion/omniview-v2-shadow` | Operacion | **DEV / SHADOW** | `OmniviewV2ShadowPage` — live API V2 |
| `/operacion/omniview-v2-matrix-sandbox` | Operacion | **DEV / MOCK** | `OmniviewV2MatrixSandbox` — mock data |

**NOT registered in production navigation registry.** DEV-only routes. Not in `controlTowerNavigationRegistry.js`.

---

## 2. COMPONENTS (Frontend)

### 2.1 Pages (2)

| Component | Lines | Purpose |
|-----------|-------|---------|
| `OmniviewV2ShadowPage.jsx` | 371 | Live API V2 page |
| `OmniviewV2MatrixSandbox.jsx` | 98 | Mock data playground |

### 2.2 Matrix Components (7)

| Component | Purpose |
|-----------|---------|
| `MatrixShell.jsx` | Main grid container |
| `MatrixHeader.jsx` | Column headers |
| `MatrixRow.jsx` | Row renderer |
| `MatrixCell.jsx` | Cell renderer |
| `CellInspector.jsx` | Drawer: Value, Source, Trust, Lineage, Drill |
| `CellBadge.jsx` | Cell annotation badges |
| `CellDelta.jsx` | Delta change indicator |

### 2.3 Base Components (7)

| Component | Purpose |
|-----------|---------|
| `SourceBadge.jsx` | CANONICAL / SHADOW badge (green/amber) |
| `CoverageBadge.jsx` | Coverage % (ok/warning/blocked) |
| `FreshnessBadge.jsx` | "Updated {date}" / stale |
| `StatusBadge.jsx` | Generic status indicator |
| `MetricValue.jsx` | Formatted metric display |
| `DeltaValue.jsx` | Delta display |
| `PeriodBadge.jsx` | Period status badge |
| `WarningBadge.jsx` | Warning display |

### 2.4 Layout Components (6)

| Component | Purpose |
|-----------|---------|
| `OmniviewV2CommandHeader.jsx` | Source selector, grain, date pickers, badges |
| `OmniviewV2ContextBar.jsx` | Context breadcrumb |
| `OmniviewV2ExecutiveState.jsx` | KPI cards strip |
| `OmniviewV2AlertStrip.jsx` | Alerts/warnings strip |
| `OmniviewV2SectionShell.jsx` | Section container |
| `OmniviewV2GlobalEmptyState.jsx` | Global empty state (NO_DATA, today-empty) |

### 2.5 States (2)

| Component | Purpose |
|-----------|---------|
| `MatrixSkeleton.jsx` | Loading skeleton |
| `MatrixEmptyState.jsx` | Per-section empty state |

### 2.6 Hooks (4)

| Hook | Purpose |
|------|---------|
| `useOmniviewV2Shell.js` | Fetch shell data |
| `useOmniviewV2Matrix.js` | Fetch matrix data (with fallback adapter) |
| `useOmniviewV2PlanReal.js` | Fetch plan vs real monthly |
| `useOmniviewV2DrillCell.js` | Fetch cell drill data |

### 2.7 Design System (2)

| File | Purpose |
|------|---------|
| `omniviewV2Tokens.js` | CSS variable definitions (`--ov2-*`) |
| `MatrixVisualSystem.css` | V2 matrix visual styles |

### 2.8 Adapters (1)

| File | Purpose |
|------|---------|
| `shellToMatrixResponse.js` | Fallback adapter when real `/matrix` unavailable |

### 2.9 Mocks (1)

| File | Purpose |
|------|---------|
| `mockMatrixResponse.js` | Mock scenarios (CT Day/Week/Month, Yango Day, Warnings, Compare) |

---

## 3. BACKEND ENDPOINTS (V2)

### 3.1 Core V2 (`/ops/omniview-v2`) — 11 endpoints

| Method | Path | Purpose | DB Source |
|--------|------|---------|-----------|
| GET | `/ops/omniview-v2/sources` | List registered data sources | In-memory `SourceRegistry` |
| GET | `/ops/omniview-v2/summary` | KPIs from single source/grain | `ops.real_business_slice_*` or `raw_yango.mv_orders_day` |
| GET | `/ops/omniview-v2/health` | Health for all sources | Multi-source |
| GET | `/ops/omniview-v2/compare` | Side-by-side CT vs Yango | Both sources |
| GET | `/ops/omniview-v2/matrix` | MatrixResponse (snapshot-first) | `ops.real_business_slice_*` + `ops.driver_day_slice_fact` |
| GET | `/ops/omniview-v2/operating-date` | Latest closed date + freshness | `ops.real_business_slice_day_fact` |
| GET | `/ops/omniview-v2/plan-real/monthly` | Monthly PvR matrix | `ops.plan_trips_monthly` + `ops.real_business_slice_month_fact` |
| GET | `/ops/omniview-v2/plan-real/versions` | Plan versions | `ops.plan_trips_monthly` |
| GET | `/ops/omniview-v2/infra-health` | DB pool status | `connection_pool` |
| GET | `/ops/omniview-v2/backend-identity` | Git hash, branch, env | OS-level |
| GET | `/ops/omniview-v2/drill/cell` | Lineage-aware cell drill | `ops.driver_day_slice_fact` |
| GET | `/ops/omniview-v2/cell-audit` | Complete cell auditability | `ops.driver_day_slice_fact` + `ops.real_business_slice_day_fact` |
| GET | `/ops/omniview-v2/reconciliation/park` | CT vs Yango by park+date | `ops.driver_day_slice_fact` vs `raw_yango.mv_orders_day` |
| GET | `/ops/omniview-v2/freshness-observatory` | Cross-layer freshness | REAL, BRIDGE, SNAPSHOT |

### 3.2 Shell (`/ops/omniview-v2/shell`) — 3 endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/ops/omniview-v2/shell` | Full product shell (snapshot-first) |
| GET | `/ops/omniview-v2/shell/sections` | Available sections |
| GET | `/ops/omniview-v2/shell/section/:id` | Single section |

### 3.3 Shadow (`/ops/omniview-v2-shadow`) — 4 endpoints

| Method | Path | Purpose | DB Source |
|--------|------|---------|-----------|
| GET | `/ops/omniview-v2-shadow/daily` | Daily from raw_yango MVs | `raw_yango.mv_orders_day`, `mv_revenue_day` |
| GET | `/ops/omniview-v2-shadow/coverage` | Source coverage by day | `raw_yango.mv_source_coverage_day` |
| GET | `/ops/omniview-v2-shadow/reconciliation` | Yango vs CT reconciliation | `raw_yango.mv_orders_day` vs `ops.real_business_slice_day_fact` |
| GET | `/ops/omniview-v2-shadow/health` | Shadow API health | All shadow MVs |

---

## 4. KPIs VISIBLES

| KPI | V2 Name | Support |
|-----|---------|---------|
| `completed_trips` | orders | day/week/month |
| `active_drivers` | active_drivers | day/week/month |
| `revenue_yego` | revenue | day/week/month |
| `gmv` | — | unavailable |
| `avg_ticket` | avg_ticket | day/week/month |
| `trips_per_driver` | trips_per_driver | day/week/month |
| `commission_pct` | — | unavailable |
| `cancel_rate_pct` | — | unavailable |
| `business_slice` | — | unavailable |

**5 of 7 V1 KPIs available. Commission and cancel rate not yet mapped to V2.**

---

## 5. VIEWS / MODES

| View | Description | Status |
|------|-------------|--------|
| **Real Matrix** | Core matrix: KPI × grain grid | WORKING |
| **Plan vs Real (Monthly)** | Monthly PvR matrix | WORKING (monthly only) |
| **Shadow (Yango raw)** | Daily shadow from raw_yango MVs | WORKING |
| **Sandbox (Mock)** | Mock data playground | WORKING (dev only) |

---

## 6. FILTERS

| Filter | Type | Status |
|--------|------|--------|
| Source System | Select (CT_TRIPS_2026 / YANGO_API_RAW) | WORKING |
| Grain | Toggle (day / week / month) | WORKING |
| Date From | date input | WORKING |
| Date To | date input | WORKING |
| KPI | Select (orders, revenue, drivers, avg_ticket, tpd) | WORKING |
| Mode | Toggle (Real Matrix / Plan vs Real Monthly) | WORKING |

**Missing vs V1:** City, Country, Business Slice, Subfleet, Year, Month selects. No operational period selector.

---

## 7. UX FEATURES

| Feature | Status | Notes |
|---------|--------|-------|
| Source badge (CANONICAL/SHADOW) | ✓ | `SourceBadge.jsx` |
| Coverage badge | ✓ | `CoverageBadge.jsx` with ok/warning/blocked |
| Freshness badge | ✓ | `FreshnessBadge.jsx` |
| Cell inspector drawer | ✓ | Structured: Value, Source, Period, Trust, Warnings, Lineage, Comparison, Drill |
| Park drill with top drivers | ✓ | `useOmniviewV2DrillCell` |
| Executive state KPI strip | ✓ | 5 KPIs, clickable |
| Alert strip | ✓ | Warning codes from shell sections |
| Global empty states | ✓ | NO_DATA, today-empty with guidance |
| Operating date | ✓ | Smart date init from backend |
| Fallback adapter | ✓ | When `/matrix` unavailable |
| Loading skeleton | ✓ | `MatrixSkeleton.jsx` |
| Error boundary | ✗ | Not separate; fallback adapter handles |
| Fullscreen toggle | ✗ | Missing |
| Zoom control | ✗ | Missing |
| Sticky headers | ? | MatrixShell — likely present |
| Signal colors | ✗ | No threshold-based green/amber/red colors |
| Insights / alerts engine | ✗ | No insight/alerting engine |
| ECharts reports | ✗ | No chart views |
| Subfleet toggle | ✗ | Missing filter |
| Backfill controls | ✗ | Missing |
| Operational status bar | ✗ | Missing (no collapsible freshness/coverage/trust bar) |
| KPI delta arrows | ✗ | DeltaValue exists but signal direction missing |
| Projection / momentum drill | ✗ | No Evolution/Momentum modes |
| Period status in cells | ✓ | PeriodBadge in cell inspector |

---

## 8. DATABASE OBJECTS

### V2 Specific

| Object | Schema | Purpose |
|--------|--------|---------|
| `omniview_v2_serving_snapshot` | `ops` | Pre-built payload cache |
| `omniview_metric_source_registry` | `ops` | Metric ownership + badges |
| `omniview_canonical_day_fact_shadow` | `ops` | Canonical mapper shadow (CF-H2G) |
| `mv_orders_day` | `raw_yango` | Orders from Yango API |
| `mv_revenue_day` | `raw_yango` | Revenue from Yango API |
| `mv_transactions_day` | `raw_yango` | Transactions from Yango API |
| `mv_source_coverage_day` | `raw_yango` | Coverage tracking |

### Reused from V1

| Object | Purpose |
|--------|---------|
| `ops.real_business_slice_day_fact` | Real daily facts |
| `ops.real_business_slice_week_fact` | Real weekly facts |
| `ops.real_business_slice_month_fact` | Real monthly facts |
| `ops.driver_day_slice_fact` | Driver bridge table |
| `ops.plan_trips_monthly` | Plan data |

---

## 9. SERVICE FILES

| Service | Role |
|---------|------|
| `omniview_v2_core_service.py` | Source-agnostic summary, health, compare |
| `omniview_v2_matrix_view_model_service.py` | Raw → MatrixResponse transformation |
| `omniview_v2_plan_real_service.py` | PvR matrix builder |
| `omniview_v2_shell_service.py` | Pre-built product sections |
| `omniview_v2_shadow_service.py` | API contract from raw_yango MVs |
| `omniview_v2_source_registry.py` | Source definitions (CT_TRIPS_2026, YANGO_API_RAW) |
| `omniview_v2_snapshot_service.py` | Serving snapshot management |

---

## 10. V2 TOTAL SCOPE SUMMARY

| Category | Count |
|----------|-------|
| Routes | 2 (DEV only, not production-nav) |
| Components | 30+ (modular, in subfolder) |
| Endpoints | 18+ (14 core + 3 shell + 4 shadow) |
| KPIs | 5 (of 7 V1 KPIs) |
| Views/Modes | 4 |
| Filter dimensions | 6 (vs 9 V1) |
| Service files | 7 |
| DB tables (V2-specific) | 7 (4 shadow MVs + 1 snapshot + 1 shadow fact + 1 registry) |
| Lines of code (page+hooks) | ~371 + 156 + ~800 (hooks) ≈ ~1,300 (lean) |

---

## 11. KNOWN BUGS / LIMITATIONS

| # | Issue | Severity | Status |
|---|-------|----------|--------|
| 1 | Fallback adapter produces partial data when `/matrix` unavailable | MEDIUM | Known (by design) |
| 2 | `ingested_at` column bug in mapper (FIXED in CF-H2E.2) | — | FIXED |
| 3 | Multipark `park_id` parameter bug in mapper (FIXED in CF-H2E.2) | — | FIXED |
| 4 | No double-scroll fix verified in V2 | LOW | Unknown |
| 5 | Commission and cancel rate KPIs not mapped | MEDIUM | Missing queries |
| 6 | Business slice dimension not supported | HIGH | Missing entire dimension |
| 7 | Mock sandbox UI doesn't match real page | LOW | Dev tool only |
| 8 | Plan vs Real: monthly only (no daily/weekly) | HIGH | Missing grains |
| 9 | No projection mode equivalent to V1 | HIGH | Missing feature |
| 10 | Source registry hardcodes park_id `08e20910...` | MEDIUM | Multipark-ready but not tested |
| 11 | Snapshot table no auto-expiry (unbounded growth) | MEDIUM | Missing pruning |
| 12 | V2 not in navigation registry (DEV route only) | HIGH | Blocking production use |
