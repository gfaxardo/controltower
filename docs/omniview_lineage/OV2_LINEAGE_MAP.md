# OV2 LINEAGE MAP — Omniview V2 Source Inventory

**Generated:** 2026-06-06  
**Phase:** Control Foundation — Omniview P0 Recovery (ACTIVE)  
**Scope:** Endpoints /matrix, /shell, snapshot, MVs, raw tables, fallbacks

---

## 1. ENDPOINT CATALOG

### 1.1 Router: `omniview_v2.py` (Prefix: `/ops/omniview-v2`)

| # | Endpoint | Method | Service | Snapshot? | Runtime? |
|---|----------|--------|---------|-----------|----------|
| 1 | `GET /ops/omniview-v2/sources` | GET | `source_registry` (no DB) | No | N/A |
| 2 | `GET /ops/omniview-v2/summary` | GET | `v2_core_service` | No | Always live |
| 3 | `GET /ops/omniview-v2/health` | GET | `v2_core_service` | No | Always live |
| 4 | `GET /ops/omniview-v2/compare` | GET | `v2_core_service` | No | Always live |
| 5 | `GET /ops/omniview-v2/matrix` | GET | `v2_matrix_view_model_service` | **Yes** (single-day) | `allow_runtime=true` |
| 6 | `GET /ops/omniview-v2/operating-date` | GET | Inline SQL (direct) | No | Always live |

### 1.2 Router: `omniview_v2_shell.py` (Prefix: `/ops/omniview-v2`)

| # | Endpoint | Method | Service | Snapshot? | Runtime? |
|---|----------|--------|---------|-----------|----------|
| 7 | `GET /ops/omniview-v2/shell` | GET | `v2_shell_service` | **Yes** (single-day) | `allow_runtime=true` |
| 8 | `GET /ops/omniview-v2/shell/sections` | GET | `v2_shell_service` | No | Static |
| 9 | `GET /ops/omniview-v2/shell/section/{id}` | GET | `v2_shell_service` | No | Delegates to shell |

### 1.3 Router: `omniview_v2_shadow.py` (Prefix: `/ops/omniview-v2-shadow`)

| # | Endpoint | Method | Service |
|---|----------|--------|---------|
| 10 | `GET /ops/omniview-v2-shadow/daily` | GET | `shadow_service` |
| 11 | `GET /ops/omniview-v2-shadow/coverage` | GET | `shadow_service` |
| 12 | `GET /ops/omniview-v2-shadow/reconciliation` | GET | `shadow_service` |
| 13 | `GET /ops/omniview-v2-shadow/health` | GET | `shadow_service` |

---

## 2. SOURCE SYSTEMS (V2 Registry)

### 2.1 CT_TRIPS_2026 (CANONICAL — `canonical_ready=true`)

**Status:** CURRENT_BASELINE  
**Metrics (9):**

| metric_id | label | source_field | Aggregation | Confidence |
|-----------|-------|-------------|-------------|------------|
| orders | Orders Completed | trips_completed | SUM | HIGH |
| revenue | Revenue YEGO Final | revenue_yego_final | SUM | HIGH |
| active_drivers | Active Drivers | active_drivers | SUM | HIGH |
| avg_ticket | Average Ticket | avg_ticket | AVG | HIGH |
| trips_per_driver | Trips per Driver | trips_per_driver | AVG | HIGH |
| commission_pct | Commission % | commission_pct | AVG | HIGH |
| cancel_rate_pct | Cancellation Rate % | cancel_rate_pct | AVG | HIGH |
| revenue_per_order | Revenue per Order | revenue_yego_net | COMPUTED | HIGH |
| supply_hours | Supply Hours | supply_hours | SUM | LOW |

**Supported grains:** hour, day, week, month

### 2.2 YANGO_API_RAW (SHADOW — `canonical_ready=false`)

**Status:** FUTURE_CANDIDATE  
**Metrics (5):**

| metric_id | label | source_field | Aggregation | Confidence |
|-----------|-------|-------------|-------------|------------|
| orders | Orders Completed | orders_completed | SUM | MEDIUM |
| revenue | Revenue Partner Fee | revenue_partner_fee_amount | SUM | MEDIUM |
| active_drivers | Active Drivers | unique_drivers | SUM | MEDIUM |
| revenue_per_order | Revenue per Order | revenue_per_order | COMPUTED | MEDIUM |
| trips_per_driver | Trips per Driver | orders_completed | COMPUTED | MEDIUM |

**Supported grains:** day only  
**Warnings:** PARTIAL_PARK_COVERAGE, API_COVERAGE_WARNING, CANONICAL_NOT_READY

---

## 3. DATABASE ARTIFACTS (V2)

### 3.1 CT_TRIPS_2026 Source Tables

| Table | Grain | Date Field | Query Pattern |
|-------|-------|------------|---------------|
| `ops.real_business_slice_hour_fact` | hour | hour_start | SUM(trips_completed), SUM(revenue_yego_final), SUM(active_drivers) GROUP BY hour_start |
| `ops.real_business_slice_day_fact` | day | trip_date | SUM(...) GROUP BY trip_date |
| `ops.real_business_slice_week_fact` | week | week_start | SUM(...) GROUP BY week_start |
| `ops.real_business_slice_month_fact` | month | month | SUM(...) GROUP BY month |

**Note:** These are the **SAME** tables used by Omniview V1.

### 3.2 YANGO_API_RAW Materialized Views

| MV | Source Table | Key Columns | Refresh |
|----|-------------|-------------|---------|
| `raw_yango.mv_orders_day` | `raw_yango.orders_raw` | park_id, order_date, orders_completed, unique_drivers | `refresh_raw_yango_mvs.py` |
| `raw_yango.mv_revenue_day` | `raw_yango.transactions_raw` | park_id, revenue_date, revenue_partner_fee_amount, revenue_per_order | `refresh_raw_yango_mvs.py` |
| `raw_yango.mv_transactions_day` | `raw_yango.transactions_raw` | park_id, transaction_date, currency, amount_sum | `refresh_raw_yango_mvs.py` |
| `raw_yango.mv_driver_profiles_snapshot` | `raw_yango.driver_profiles_raw` | park_id, driver_profile_id, last_seen_at | `refresh_raw_yango_mvs.py` |
| `raw_yango.mv_source_coverage_day` | orders_raw + transactions_raw | park_id, coverage_date, coverage_status | `refresh_raw_yango_mvs.py` |

### 3.3 V2 Snapshot Table

| Table | Schema | Purpose |
|-------|--------|---------|
| `ops.omniview_v2_serving_snapshot` | ops | Pre-computed shell + matrix JSONB payloads |

**Columns:** id, source_system, grain, operating_date, payload_type (shell|matrix), payload (JSONB), status (READY|STALE|FAILED|BUILDING), coverage_pct, freshness_status, generated_at, expires_at, build_ms, source_tables, warnings, payload_hash

**Unique key:** (source_system, grain, operating_date, payload_type)

---

## 4. SNAPSHOT SERVING ARCHITECTURE

```
SINGLE-DAY REQUEST (date_from == date_to)
  │
  ├─ TRY: get_served_payload(source, grain, date, type)
  │   └─ SELECT payload FROM ops.omniview_v2_serving_snapshot
  │       WHERE source=? AND grain=? AND operating_date=? AND payload_type=? AND status='READY'
  │       ORDER BY generated_at DESC LIMIT 1
  │
  ├─ FOUND: Return JSONB payload + served_from_snapshot=true
  │
  └─ NOT FOUND + allow_runtime=false (default):
      └─ Return empty response + SERVING_SNAPSHOT_MISSING warning
          - Matrix: 0 columns, 0 rows, 0 cells
          - Shell: source_status=SNAPSHOT_MISSING, empty sections

MULTI-DAY REQUEST (date_from != date_to):
  └─ ALWAYS runtime: build_matrix_response() or build_shell()

RUNTIME (allow_runtime=true):
  └─ Always live query against source tables, no snapshot
```

**Snapshot Build:** `omniview_v2_snapshot_service.build_and_store_shell_snapshot()` / `build_and_store_matrix_snapshot()` calls the same build functions used for runtime, then upserts the result to `ops.omniview_v2_serving_snapshot`.

---

## 5. RUNTIME FALLBACK (V2)

| Fallback | Trigger | Behavior |
|----------|---------|----------|
| Snapshot → Runtime | Single-day + snapshot missing + `allow_runtime=true` | Live query against source tables |
| Snapshot → Empty | Single-day + snapshot missing + `allow_runtime=false` | Empty matrix/shell + warning |
| Matrix → Shell adapter | `/matrix` endpoint fails + `VITE_OV2_ALLOW_MATRIX_FALLBACK=true` | `shellToMatrixResponse.js` converts shell to matrix |
| CT data unavailable | Shadow reconciliation, exact date not found | 4-level fallback: EXACT → NEAREST(30d) → NO_DATE_IN_RANGE → UNAVAILABLE |

---

## 6. ENDPOINT-TO-DATABASE TRACEABILITY (V2 Runtime)

```
GET /ops/omniview-v2/summary
  → source_repository.get_kpis()
    → ops.real_business_slice_{grain}_fact (CT)
    → raw_yango.mv_orders_day + mv_revenue_day (Yango)

GET /ops/omniview-v2/matrix (runtime)
  → matrix_repository.get_matrix_data()
    → ops.real_business_slice_{grain}_fact GROUP BY business_slice_name (CT)
    → raw_yango.mv_orders_day + mv_revenue_day (Yango, single "Lima Fleet" row)

GET /ops/omniview-v2/operating-date
  → SELECT MAX(trip_date) FROM ops.real_business_slice_day_fact (CT)
  → SELECT MAX(order_date) FROM raw_yango.mv_orders_day (Yango)

GET /ops/omniview-v2-shell (runtime)
  → source_repository.get_kpis() + get_coverage() + get_freshness()
  → Same tables as above
  → build_shell() pre-computes shared data, then builds 10 sections

GET /ops/omniview-v2-shadow/*
  → shadow_repository reads from raw_yango.mv_* (5 MVs)
  → Reconciliation: raw_yango.mv_* vs ops.real_business_slice_day_fact
```

---

## 7. KPI → SOURCE MATRIX (V2)

| KPI | CT Source | Yango Source |
|-----|-----------|-------------|
| **trips** | `ops.real_business_slice_{grain}_fact.trips_completed` | `raw_yango.mv_orders_day.orders_completed` |
| **revenue** | `ops.real_business_slice_{grain}_fact.revenue_yego_final` (direct, no COALESCE) | `raw_yango.mv_revenue_day.revenue_partner_fee_amount` |
| **drivers** | `ops.real_business_slice_{grain}_fact.active_drivers` | `raw_yango.mv_orders_day.unique_drivers` |
| **ticket** | `ops.real_business_slice_{grain}_fact.avg_ticket` | Computed: revenue / orders |
| **TPD** | Computed: orders / drivers or `trips_per_driver` column | Computed: orders / drivers |
| **Plan vs Real** | Available via `shell.plan_vs_real` section | **BLOCKED** — no plan infrastructure |

---

## 8. SHELL SECTIONS (10 Sections)

| # | Section ID | Purpose | Data Source |
|---|-----------|---------|-------------|
| 1 | `executive_state` | Active source, warnings count, last refresh | Cross-source |
| 2 | `source_health` | Per-source health (coverage, freshness) | source_repository |
| 3 | `kpi_strip` | Key KPI values | get_omniview_v2_summary |
| 4 | `revenue_integrity` | Revenue value, revenue_per_order, delta vs CT | Reconciliation |
| 5 | `operational_coverage` | Coverage %, days with data, gap dates | get_coverage |
| 6 | `growth_movement` | Direction, magnitude %, prior period | KPI comparison |
| 7 | `plan_vs_real` | Plan availability, periods, source note | Plan readiness check |
| 8 | `slice_readiness` | Slice count, slice list (6 slices) | CT business_slice |
| 9 | `lineage_audit` | Metric-to-table traceability | source_registry |
| 10 | `alerts_warnings` | All warnings categorized | Cross-section |

---

## 9. ARCHITECTURAL DIFFERENCES V1 vs V2

| Dimension | V1 | V2 |
|-----------|----|----|
| **Source table for CT** | Same 3 fact tables | Same 3 fact tables (IDENTICAL) |
| **Revenue column** | `COALESCE(revenue_yego_final, revenue_yego_net)` | `revenue_yego_final` (direct, no COALESCE) |
| **API pattern** | Raw rows → frontend pivots | Pre-built MatrixResponse (columns, rows, cells) |
| **Serving layer** | Direct table reads (no cache) | `ops.omniview_v2_serving_snapshot` (pre-computed JSONB) |
| **Multi-source** | CT only (single source) | CT + Yango (dual source, comparison) |
| **Lineage** | Implicit (SQL inspection needed) | Explicit (per-metric lineage in response) |
| **canonical_ready** | Not exposed | Explicit boolean per response |
| **Source gating** | No source system concept | `source_system` param required |
| **Plan vs Real** | Built-in (MV-based) | Readiness check, blocked for Yango |
| **Freshness** | Separate endpoint | Embedded in every response |

---

## 10. KNOWN V2 ARCHITECTURAL RISKS

| Risk | Severity | Detail |
|------|----------|--------|
| **Shares V1 fact tables** | **CRITICAL** | CT_TRIPS_2026 reads from `ops.real_business_slice_{day/week/month}_fact` — same as V1 |
| **Snapshot staleness** | **MEDIUM** | Snapshot only for single-day; multi-day always runtime |
| **Yango shadow gated** | **LOW** | `canonical_ready=false` prevents operational use |
| **Shell complexity** | **MEDIUM** | 10-section build makes N DB calls; snapshot mitigates this |
| **Matrix fallback to shell** | **LOW** | `shellToMatrixResponse` adapter is TEMPORARY bridge |
| **No revenue COALESCE** | **LOW (improvement)** | V2 reads `revenue_yego_final` directly — cleaner than V1, but exposes NULLs explicitly |
