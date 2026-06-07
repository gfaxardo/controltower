# OV2-C.3A — MATRIX SOURCE ABSTRACTION

> **Date:** 2026-06-06
> **Motor:** Control Foundation / Matrix Data Contract

---

## 1. CORE PRINCIPLE

**MatrixZone never knows the physical source.** It receives MatrixResponse, which is the same shape regardless of whether data originated from CT, Yango, or a future hybrid source.

```
Backend                          Frontend
┌──────────────┐                ┌──────────────┐
│ CT_TRIPS_2026 │──┐             │              │
└──────────────┘  │             │  MatrixZone  │
                  ├─ MatrixResponse ─→  │  (renders)   │
┌──────────────┐  │             │              │
│ YANGO_API_RAW │──┘             └──────────────┘
└──────────────┘
```

---

## 2. CURRENT SOURCES

### 2.1 CT_TRIPS_2026

| Attribute | Value |
|-----------|-------|
| Status | CURRENT_BASELINE |
| canonical_ready | true |
| Supported grains | hour, day, week, month |
| Supported metrics | orders, revenue, active_drivers, avg_ticket, trips_per_driver, commission_pct, cancel_rate_pct, revenue_per_order |
| Source tables | ops.real_business_slice_{hour,day,week,month}_fact |
| Limitations | Hour grain may have gaps for some slices |
| Required transformations | SUM by (country, city, trip_date), pivot to matrix |
| Warnings | Revenue uses revenue_yego_final (includes proxy fallback) |
| Lineage | country/city → business_slice → day_fact → trips_completed |

### 2.2 YANGO_API_RAW

| Attribute | Value |
|-----------|-------|
| Status | FUTURE_CANDIDATE |
| canonical_ready | false |
| Supported grains | day (hour planned, week/month not yet) |
| Supported metrics | orders, revenue, active_drivers, revenue_per_order, trips_per_driver |
| Source tables | raw_yango.mv_orders_day, raw_yango.mv_revenue_day |
| Limitations | Single park (Lima). No slice mapping. Short series (2 days). |
| Required transformations | Park-level aggregation, no slice grouping |
| Warnings | PARTIAL_PARK_COVERAGE, API_COVERAGE_WARNING, CANONICAL_NOT_READY |
| Lineage | park_id → mv_orders_day → orders_completed |

---

## 3. FUTURE SOURCES

### 3.1 YANGO_CANONICAL (hypothetical)

| Attribute | Value |
|-----------|-------|
| Status | CANONICAL (promoted from FUTURE_CANDIDATE) |
| canonical_ready | true |
| Prerequisites | ≥30 days data, ≥99.5% coverage, CT delta <3%, hourly grain available |
| Supported grains | hour, day (week/month via rollup) |
| Supported metrics | Full OV2 metric set |
| Limitations | Requires park→slice mapping, plan data not native |

### 3.2 HYBRID_HISTORICAL_CT_REALTIME_YANGO (hypothetical)

| Attribute | Value |
|-----------|-------|
| Status | HYBRID (experimental) |
| canonical_ready | false (experimental) |
| Historical source | CT_TRIPS_2026 (back to 2025) |
| Realtime source | YANGO_API_RAW (current day) |
| Merge logic | If period < today: use CT. If period = today: use Yango. |
| Required transformations | Union of CT + Yango with source flag per cell |

---

## 4. SOURCE TRANSFORMATION RULES

Each source backend repository must transform its native data into MatrixResponse.

### 4.1 CT → MatrixResponse

```
1. Query real_business_slice_{grain}_fact for (country, city, date_range)
2. GROUP BY trip_date, business_slice_name
3. PIVOT: rows = business slices, columns = dates
4. For each (slice, date) cell:
   - Extract trips_completed, revenue_yego_final, active_drivers, etc.
   - Attach period_status from period_closure_registry
   - Attach coverage_pct from coverage tracking
   - Normalize to CellContract
5. Build MatrixResponse with metadata, columns, rows, cells
```

### 4.2 Yango → MatrixResponse

```
1. Query mv_orders_day + mv_revenue_day for (park_id, date_range)
2. GROUP BY order_date (no slice grouping — single "Lima fleet" row)
3. PIVOT: single row, columns = dates
4. For each (fleet, date) cell:
   - Extract orders_completed, revenue_partner_fee_amount, unique_drivers
   - Attach period_status = CURRENT (no closure registry for Yango)
   - Attach coverage_pct from mv_source_coverage_day
   - Set canonical_ready = false
   - Attach source warnings
5. Build MatrixResponse
```

### 4.3 Hybrid → MatrixResponse

```
1. Determine split date (today)
2. For dates < split_date: use CT pipeline
3. For dates = split_date: use Yango pipeline
4. UNION rows with source_period flag
5. Mark hybrid cells with comparison_basis = "HYBRID_CT_YANGO"
6. Build unified MatrixResponse
```

---

## 5. MATRIX RESPONSE UNIFORMITY

Regardless of source, MatrixResponse always has:

| Guarantee | Enforcement |
|-----------|------------|
| columns[] always sorted by sort_key | Backend sorts before response |
| rows[] always sorted by sort_key | Backend sorts before response |
| cells[] always has (row_id, column_id) | Backend populates coordinates |
| All CellContract fields present | Backend normalization layer |
| cell_status pre-computed | Backend applies status rules |
| canonical_ready explicit | From source registry |
| warnings always an array (even if empty) | Backend always includes |

---

## 6. MATRIX RESPONSE SIZE ESTIMATES

| Grain | Typical Rows | Typical Columns | Cells | ~Size |
|-------|-------------|-----------------|-------|-------|
| hour | 1-6 slices × 24h? No, 24 columns | 24 | 144 | ~50KB |
| day (7d) | 6 slices | 7 | 42 | ~20KB |
| day (30d) | 6 slices | 30 | 180 | ~80KB |
| week (12w) | 6 slices | 12 | 72 | ~35KB |
| month (12m) | 6 slices | 12 | 72 | ~35KB |

All well within acceptable API response size (<500KB).
