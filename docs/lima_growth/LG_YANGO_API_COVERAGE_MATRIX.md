# LG — Yango API Coverage Matrix

**Date:** 2026-06-06
**Registry:** LG-R2.9I.2A.0 Source Migration

---

## YANGO FLEET API — ENDPOINT COVERAGE

### Orders — `POST /v1/parks/orders/list`

| Field | Available | Used In | Notes |
|-------|:---:|------|------|
| order_id | YES | orders_raw | Unique per order |
| driver_profile_id | YES | orders_raw | Links to driver |
| status (completed) | YES | orders_raw | Filtered for completed |
| created_at | YES | orders_raw | Order timestamp |
| price | YES | orders_raw | Revenue tracking |
| park_id | YES | orders_raw | Fleet identifier |

**Coverage:** 100% of required fields for operational use.

### Driver Profiles — `POST /v1/parks/driver-profiles/list`

| Field | Available | Used In | Notes |
|-------|:---:|------|------|
| driver_profile_id | YES | driver_profiles_raw | Unique per driver |
| full_name | YES | driver_profiles_raw | Driver identity |
| phone | YES | driver_profiles_raw | Contact information |
| work_status | YES | driver_360 | Active/blocked |
| car_id | YES | driver_profiles_raw | Vehicle link |

**Coverage:** 100% of required identity fields.

### Supply Hours — `GET /v2/parks/contractors/supply-hours`

| Field | Available | Used In | Notes |
|-------|:---:|------|------|
| contractor_id | YES | driver_360 | Links to driver_profile_id |
| supply_seconds | YES | driver_360 | Converted to supply_hours |
| date | YES | driver_360 | Per-day granularity |

**Coverage:** 100%. Used directly in `driver_360_service.py` for HOT-tier drivers.

### Transactions — `POST /v2/parks/transactions/list`

| Field | Available | Used In | Notes |
|-------|:---:|------|------|
| transaction_id | YES | transactions_raw | Revenue tracking |
| category | YES | mv_revenue_day | partner_rides, fees, etc. |
| amount | YES | mv_revenue_day | Revenue amounts |

**Coverage:** 100% for revenue fields.

---

## EXISTING RAW TABLES (raw_yango schema)

| Table | Source Endpoint | Rows | Date Range |
|-------|----------------|------|------------|
| orders_raw | POST orders/list | Variable | Cursor-paginated |
| driver_profiles_raw | POST driver-profiles/list | Variable | Offset-paginated |
| transactions_raw | POST transactions/list | Variable | Cursor-paginated |

---

## EXISTING MATERIALIZED VIEWS

| View | Source | Content |
|------|--------|---------|
| mv_orders_day | orders_raw | Daily orders (completed/cancelled) |
| mv_transactions_day | transactions_raw | Daily transactions by category |
| mv_revenue_day | transactions_raw | Revenue breakdown |
| mv_driver_profiles_snapshot | driver_profiles_raw | Latest profile per driver |
| mv_source_coverage_day | All raw tables | Coverage stats per day |

---

## DRIVER 360 INTEGRATION

`growth.yango_lima_driver_360_daily` currently populated by:
- Yango API supply-hours (HOT-tier drivers)
- `growth.yango_lima_orders_raw` (pre-aggregated orders)
- `growth.yango_lima_eligible_universe_daily` (driver selection)

**Status:** Yango API is already the live source for driver_360. trips_2026 is only used for historical enrichment (best_week, lifecycle transitions).

---

## FIELDS STATUS

| Field | Source | Status |
|-------|--------|:---:|
| completed_orders (today) | Yango API → orders_raw → driver_360 | LIVE |
| supply_hours (today) | Yango API → driver_360 | LIVE |
| driver identity (name, phone) | Yango API → driver_profiles_raw | LIVE |
| work_status | Yango API → driver_profiles_raw | LIVE |
| revenue (today) | Yango API → transactions_raw → mv_revenue_day | LIVE |
| best_week_12w | trips_2026 → history layer | HISTORICAL |
| lifetime_trips | trips_2026 → history layer | HISTORICAL |
| first_seen | trips_2026 → history layer | HISTORICAL |
| lifecycle transitions | trips_2026 → history layer | HISTORICAL |

---

## VERDICT

**YANGO_API_COVERAGE: SUFFICIENT FOR OPERATIONAL LIVE SOURCE.**

All operational fields (completed_orders, supply_hours, driver identity, work_status, revenue) are available from Yango API. tri_ps_2026 provides only historical enrichment (best_week, lifetime, first_seen) which is the correct architectural separation.
