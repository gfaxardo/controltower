# OV2-C.0 — HOURLY GRAIN READINESS

> **Date:** 2026-06-06
> **Motor:** Control Foundation / Omniview V2 Core
> **Status:** AUDIT

---

## 1. DOES CT/TRIPS_2026 SUPPORT HOUR GRAIN?

**Yes.** CT has hourly infrastructure since migration 099 (`real_hourly_first_architecture`).

### Tables/Views Available

| Object | Type | Grain Key | Status |
|--------|------|-----------|--------|
| `ops.real_business_slice_hour_fact` | TABLE | `hour_start` (timestamp) | EXISTS, populated |
| `ops.v_real_trip_fact_v2` | VIEW | `trip_hour` | Canonical trip fact |
| `ops.mv_real_lob_hour_v2` | MV | `hour_start` | Hourly aggregation |
| `ops.v_real_business_slice_month_from_hour` | VIEW | `month` (from hour) | Monthly rollup |

### Columns in hour_fact

| Column | Type | Description |
|--------|------|-------------|
| hour_start | timestamp | Grain key |
| country, city, business_slice_name | text | Dimensions |
| trips_completed | bigint | Completed trips per hour |
| trips_cancelled | bigint | Cancelled trips |
| revenue_yego_net | numeric | Net YEGO revenue |
| active_drivers_connected_only | bigint | Connected drivers |
| avg_ticket | numeric | Average ticket |
| commission_pct | numeric | Commission % |
| total_fare_completed_positive_sum | numeric | Total fare sum |

**Verdict:** CT hour grain is **IMPLEMENTED and POPULATED**. Ready for serving.

---

## 2. DOES RAW_YANGO SUPPORT HOUR GRAIN?

**Not yet.** The raw_yango MVs currently only exist at day grain:
- `raw_yango.mv_orders_day`
- `raw_yango.mv_revenue_day`

### What would be needed for hour grain:

| Artifact | Description |
|----------|-------------|
| `raw_yango.mv_orders_hour` | Hourly aggregation of orders_raw by park_id, hour_bucket |
| `raw_yango.mv_revenue_hour` | Hourly aggregation of transactions_raw by park_id, hour_bucket |
| `raw_yango.mv_source_coverage_hour` | Hour-level coverage tracking |

### Proposed mv_orders_hour definition:

```sql
CREATE MATERIALIZED VIEW raw_yango.mv_orders_hour AS
SELECT
    park_id,
    date_trunc('hour', order_created_at) AS hour_bucket,
    operational_date,
    COUNT(*) AS orders_total,
    COUNT(*) FILTER (WHERE order_status = 'complete') AS orders_completed,
    COUNT(*) FILTER (WHERE order_status = 'cancelled') AS orders_cancelled,
    COUNT(DISTINCT driver_profile_id) AS unique_drivers,
    COUNT(DISTINCT car_id) AS unique_cars,
    now() AS refreshed_at
FROM raw_yango.orders_raw
GROUP BY park_id, date_trunc('hour', order_created_at), operational_date
WITH DATA;

CREATE UNIQUE INDEX uq_mv_orders_hour
ON raw_yango.mv_orders_hour (park_id, hour_bucket);
```

### Proposed mv_revenue_hour definition:

```sql
CREATE MATERIALIZED VIEW raw_yango.mv_revenue_hour AS
SELECT
    park_id,
    date_trunc('hour', event_at) AS hour_bucket,
    operational_date,
    COALESCE(currency_code, 'PEN') AS currency,
    COALESCE(SUM(ABS(amount)) FILTER (WHERE category_name = 'Partner fee for trip'), 0) AS revenue_partner_fee_amount,
    COUNT(*) FILTER (WHERE category_name = 'Partner fee for trip') AS revenue_partner_fee_count,
    COALESCE(SUM(amount) FILTER (WHERE category_name = 'Service fee for trip'), 0) AS platform_fee_amount,
    COALESCE(SUM(amount) FILTER (WHERE category_name = 'Service fee, VAT'), 0) AS platform_fee_vat_amount,
    COALESCE(SUM(amount) FILTER (WHERE category_name = 'Cash'), 0) AS gmv_cash_amount,
    COALESCE(SUM(amount) FILTER (WHERE category_name = 'Card payment'), 0) AS gmv_card_amount,
    COUNT(DISTINCT order_id) FILTER (WHERE order_id IS NOT NULL AND order_id != '') AS linked_orders,
    COUNT(*) AS total_transactions_count,
    CASE WHEN COUNT(DISTINCT order_id) FILTER (WHERE order_id IS NOT NULL AND order_id != '') > 0
         THEN COALESCE(SUM(ABS(amount)) FILTER (WHERE category_name = 'Partner fee for trip'), 0)
              / NULLIF(COUNT(DISTINCT order_id) FILTER (WHERE order_id IS NOT NULL AND order_id != ''), 0)
         ELSE NULL
    END AS revenue_per_order,
    'YANGO_TRANSACTIONS_API' AS revenue_source,
    'AUDIT_CERTIFIED' AS revenue_confidence,
    now() AS refreshed_at
FROM raw_yango.transactions_raw
GROUP BY park_id, date_trunc('hour', event_at), operational_date, COALESCE(currency_code, 'PEN')
WITH DATA;

CREATE UNIQUE INDEX uq_mv_revenue_hour
ON raw_yango.mv_revenue_hour (park_id, hour_bucket, currency);
```

---

## 3. GAPS SUMMARY

| Gap | Source | Status |
|-----|--------|--------|
| CT hour_fact exists and populated | CT_TRIPS_2026 | READY |
| Yango hour MVs | YANGO_API_RAW | NOT IMPLEMENTED |
| Omniview V2 hour serving endpoint | OV2 Core | READY (source registry supports it) |
| Hourly coverage tracking | OV2 Core | NOT IMPLEMENTED |

---

## 4. RECOMMENDATION

| Action | Priority | Effort |
|--------|----------|--------|
| Register CT hour grain in OV2 source registry | HIGH (already done) | None |
| Create `raw_yango.mv_orders_hour` migration | MEDIUM | 1 migration file |
| Create `raw_yango.mv_revenue_hour` migration | MEDIUM | 1 migration file |
| Add hour to YANGO_API_RAW supported grains | LOW | 1 line in registry |
| Not implement yet per OV2-C.0 scope rules | — | Deferred to OV2-C.1+ |

---

## 5. GOVERNANCE

| Rule | Status |
|------|--------|
| No UI touched | PASS |
| No MVs implemented (advisory only) | PASS |
| Additive scope | PASS |
| CT hour readiness confirmed | PASS |
