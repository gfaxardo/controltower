# OV2-C.0 — SOURCE-AGNOSTIC OMNIVIEW V2 FOUNDATION

> **Date:** 2026-06-06
> **Motor:** Control Foundation / Omniview V2 Core Architecture
> **Status:** FOUNDATION DEFINED

---

## 1. PURPOSE

Omniview V2 is designed as a **source-agnostic operational intelligence layer**. It must serve KPIs from any registered source system without coupling to specific tables, schemas, or ingestion pipelines. Today it serves from CT/trips_2026. Tomorrow it can serve from Yango API/raw_yango without architectural changes.

---

## 2. SOURCE SYSTEMS

### 2.1 Current Source: `CT_TRIPS_2026`

| Attribute | Value |
|-----------|-------|
| Status | `CURRENT_BASELINE` |
| Canonical ready | `true` (day/week/month), `false` (hour — partial) |
| Data origin | `trips_2025`, `trips_2026`, `comision_empresa_asociada` |
| Serving layer | `ops.real_business_slice_*_fact` |

**Tables by grain:**

| Grain | Table | Status |
|-------|-------|--------|
| hour | `ops.real_business_slice_hour_fact` | EXISTS — coverage TBD |
| day | `ops.real_business_slice_day_fact` | ACTIVE |
| week | `ops.real_business_slice_week_fact` | ACTIVE |
| month | `ops.real_business_slice_month_fact` | ACTIVE |

**Available metrics:**

| Metric ID | Field | Unit |
|-----------|-------|------|
| trips_completed | trips_completed | count |
| revenue_yego_net | revenue_yego_net | PEN |
| active_drivers | active_drivers | count |
| avg_ticket | avg_ticket | PEN |
| trips_per_driver | trips_per_driver | ratio |
| commission_pct | commission_pct | percentage |
| cancel_rate_pct | cancel_rate_pct | percentage |

### 2.2 Future Source: `YANGO_API_RAW`

| Attribute | Value |
|-----------|-------|
| Status | `FUTURE_CANDIDATE` |
| Canonical ready | `false` |
| Data origin | Yango Fleet API (transactions, orders, driver profiles) |
| Ingestion layer | `raw_yango.orders_raw`, `raw_yango.transactions_raw`, `raw_yango.driver_profiles_raw` |
| Serving layer | `raw_yango.mv_*_day` |

**Tables by grain:**

| Grain | Table | Status |
|-------|-------|--------|
| hour | Not yet implemented | PLANNED |
| day | `raw_yango.mv_orders_day`, `raw_yango.mv_revenue_day` | ACTIVE (shadow) |
| week | Not yet implemented | PLANNED |
| month | Not yet implemented | PLANNED |

**Available metrics:**

| Metric ID | Field | Unit |
|-----------|-------|------|
| orders_completed | orders_completed | count |
| revenue_partner_fee | revenue_partner_fee_amount | PEN |
| unique_drivers | unique_drivers | count |
| revenue_per_order | revenue_per_order | PEN |
| revenue_per_txn | revenue_per_partner_fee_txn | PEN |

---

## 3. SUPPORTED GRAINS

| Grain | CT_TRIPS_2026 | YANGO_API_RAW | Notes |
|-------|--------------|---------------|-------|
| hour | EXISTS (hour_fact) | PLANNED | CT hour_fact populated via hourly-first pipeline since migration 099 |
| day | ACTIVE | ACTIVE (shadow) | Primary grain for both sources |
| week | ACTIVE | PLANNED | CT week_fact derived from day_fact |
| month | ACTIVE | PLANNED | CT month_fact derived from day_fact or hour_fact |

---

## 4. BASE METRICS

All sources must map to these canonical metric IDs:

| Metric ID | Description | CT source | Yango source |
|-----------|-------------|-----------|-------------|
| orders | Total completed orders/trips | trips_completed | orders_completed |
| revenue | Total revenue (YEGO) | revenue_yego_net | revenue_partner_fee_amount |
| active_drivers | Unique active drivers | active_drivers | unique_drivers |
| supply_hours | Driver online hours (if available) | N/A | N/A |
| revenue_per_order | Revenue per completed order | revenue_yego_net / trips_completed | revenue_per_order (computed) |
| trips_per_driver | Trips per active driver | trips_per_driver | orders_completed / unique_drivers |
| avg_ticket | Average ticket value | avg_ticket | N/A |
| commission_pct | Commission percentage | commission_pct | N/A |
| cancel_rate_pct | Cancellation rate | cancel_rate_pct | orders_cancelled / orders_total |

---

## 5. UNIFIED RESPONSE CONTRACT

Every Omniview V2 response MUST include:

```json
{
  "source_system": "CT_TRIPS_2026",
  "source_status": "CURRENT_BASELINE",
  "canonical_ready": true,
  "grain": "day",
  "period": {
    "from": "2026-06-04",
    "to": "2026-06-04"
  },
  "filters": {
    "country": "peru",
    "city": "lima"
  },
  "kpis": [
    {
      "metric_id": "orders",
      "label": "Orders Completed",
      "value": 14213,
      "unit": "count",
      "source_system": "CT_TRIPS_2026",
      "source_table": "ops.real_business_slice_day_fact",
      "grain": "day",
      "period": "2026-06-04",
      "confidence": "HIGH",
      "is_estimated": false,
      "warning_codes": [],
      "lineage": {
        "origin_table": "ops.real_business_slice_day_fact",
        "origin_field": "trips_completed",
        "aggregation": "SUM",
        "filters_applied": {"country": "peru", "city": "lima"}
      }
    }
  ],
  "coverage": {
    "days_with_data": 1,
    "expected_days": 1,
    "coverage_pct": 100.0
  },
  "freshness": {
    "last_refreshed_at": "2026-06-06T12:00:00Z",
    "stale_since": null
  },
  "warnings": [],
  "generated_at": "2026-06-06T12:00:00Z"
}
```

### Required top-level fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| source_system | string | YES | Source system identifier |
| source_status | string | YES | CURRENT_BASELINE, FUTURE_CANDIDATE, DEPRECATED |
| canonical_ready | boolean | YES | Whether this source is certified for operational decisions |
| grain | string | YES | hour, day, week, month |
| period | object | YES | {from, to} ISO date strings |
| filters | object | YES | Active filters applied |
| kpis | array | YES | List of KpiValue objects |
| coverage | object | YES | Coverage statistics |
| freshness | object | YES | Freshness metadata |
| warnings | array | YES | Warning objects |
| generated_at | string | YES | ISO timestamp |

---

## 6. SOURCE SWITCHING

### Rules:
1. **Never mix sources silently.** If source A and source B are requested, they appear in separate sections or responses.
2. **Canonical ready must be explicit.** No implicit promotion.
3. **Default source**: `CT_TRIPS_2026` (current baseline).
4. **YANGO_API_RAW** always has `canonical_ready: false` and `status: FUTURE_CANDIDATE`.
5. **Compare mode**: `/compare` endpoint shows side-by-side KPIs from two sources without mixing.

### Future source switching flow:
```
1. YANGO_API_RAW achieves >=99.5% coverage for >=30 days
2. Shadow reconciliation shows delta <3% vs CT
3. Revenue coverage >=95%
4. Hourly grain available
5. Governance approval → canonical_ready promoted
```

---

## 7. GOVERNANCE

| Rule | Status |
|------|--------|
| No UI touched | PASS (design only) |
| No Omniview V1 touched | PASS |
| No serving productivo replaced | PASS |
| CT_TRIPS_2026 remains default | PASS |
| YANGO_API_RAW canonical_ready=false | PASS |
| Additive and parallel architecture | PASS |
