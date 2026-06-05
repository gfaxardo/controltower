# OV2-A.2 — YANGO FLEET API: ENDPOINT MAP FOR OMIVIEW V2 SOURCE DISCOVERY

> **Fase:** OV2-A.2 — Endpoint Inventory & Classification  
> **Fecha:** 2026-06-04  
> **Fuente documental:** Yango Fleet API Docs (`https://fleet.yango.com/docs/api/en`)  
> **Propósito:** Mapear, clasificar y priorizar todos los endpoints relevantes para descubrimiento de fuentes en Omniview V2

---

## 1. CLASSIFICATION LEGEND

| Classification | Meaning | Signal |
|----------------|---------|--------|
| `REPORTING` | Read-only endpoint providing operational data usable in dashboards/reports | Green |
| `RECONCILIATION` | Endpoint with traceable IDs and metrics suitable for cross-validation against CT sources | Blue |
| `FINANCIAL_CANDIDATE` | Endpoint exposing revenue, cost, or balance data that could feed financial facts | Gold |
| `NOT_USEFUL` | Read-only endpoint with no actionable data for Omniview metrics | Grey |
| `UNSAFE_FOR_AUTOMATION` | Write/mutate endpoint — **never call from Omniview pipeline** | Red |

An endpoint may carry multiple classifications (e.g., `REPORTING \| RECONCILIATION`).

---

## 2. ENDPOINT INVENTORY BY RESOURCE

### 2.1 Cars

#### 2.1.1 `POST /v2/parks/vehicles/car` — Car Creation

| Aspect | Detail |
|--------|--------|
| **Path** | `/v2/parks/vehicles/car` |
| **Method** | `POST` |
| **Parameters** | Vehicle attributes (brand, model, number, callsign, category, color, boosters, etc.) |
| **Pagination** | N/A |
| **Revenue/Cost/Price Fields** | None |
| **Grain** | 1 call = 1 car created |
| **Utility for Omniview** | None — write-only mutation |
| **Risk Assessment** | EXTREME. Would create phantom vehicles in the park if called erroneously |
| **Classification** | `UNSAFE_FOR_AUTOMATION` |

#### 2.1.2 `PUT /v2/parks/vehicles/car` — Car Update

| Aspect | Detail |
|--------|--------|
| **Path** | `/v2/parks/vehicles/car` |
| **Method** | `PUT` |
| **Parameters** | Car ID + fields to update |
| **Pagination** | N/A |
| **Revenue/Cost/Price Fields** | None |
| **Grain** | 1 call = 1 car updated |
| **Utility for Omniview** | None — write-only mutation |
| **Risk Assessment** | EXTREME. Would corrupt vehicle data in the park |
| **Classification** | `UNSAFE_FOR_AUTOMATION` |

#### 2.1.3 `GET /v2/parks/vehicles/car` — Get Car

| Aspect | Detail |
|--------|--------|
| **Path** | `/v2/parks/vehicles/car` |
| **Method** | `GET` |
| **Parameters** | `park_id`, `car_id` (query params) |
| **Pagination** | N/A — single entity |
| **Revenue/Cost/Price Fields** | None |
| **Grain** | 1 car |
| **Utility for Omniview** | Low — fleet inventory lookup. Useful only to enrich driver/car mappings for reconciliation |
| **Risk Assessment** | LOW. Read-only, per-car |
| **Classification** | `NOT_USEFUL` |

#### 2.1.4 `POST /v1/parks/cars/list` — List Cars

| Aspect | Detail |
|--------|--------|
| **Path** | `/v1/parks/cars/list` |
| **Method** | `POST` |
| **Parameters** | `limit`, `offset`, `park_id` in request body; filterable by `car_id`, `brand`, `model`, `number`, `callsign`, `category` |
| **Pagination** | Offset-based. `limit` (max undocumented), `offset`, response includes `total` |
| **Revenue/Cost/Price Fields** | None |
| **Grain** | car |
| **Utility for Omniview** | Medium — provides fleet-wide car inventory. Can be joined with orders/drivers for dimensional enrichment. Not a financial source |
| **Risk Assessment** | LOW. Read-only, bulk |
| **Classification** | `REPORTING` |

---

### 2.2 ContractorProfiles (Drivers)

#### 2.2.1 `DELETE /v1/parks/driver-profiles/car-bindings` — Detach Car from Driver

| Aspect | Detail |
|--------|--------|
| **Path** | `/v1/parks/driver-profiles/car-bindings` |
| **Method** | `DELETE` |
| **Parameters** | `driver_profile_id`, `car_id` |
| **Pagination** | N/A |
| **Revenue/Cost/Price Fields** | None |
| **Grain** | 1 driver-car binding |
| **Utility for Omniview** | None — destructive operation |
| **Risk Assessment** | EXTREME. Would break driver-car assignments in production |
| **Classification** | `UNSAFE_FOR_AUTOMATION` |

#### 2.2.2 `PUT /v1/parks/driver-profiles/car-bindings` — Bind Car to Driver

| Aspect | Detail |
|--------|--------|
| **Path** | `/v1/parks/driver-profiles/car-bindings` |
| **Method** | `PUT` |
| **Parameters** | `driver_profile_id`, `car_id` |
| **Pagination** | N/A |
| **Revenue/Cost/Price Fields** | None |
| **Grain** | 1 driver-car binding |
| **Utility for Omniview** | None — write-only mutation |
| **Risk Assessment** | EXTREME. Would alter driver-car assignments |
| **Classification** | `UNSAFE_FOR_AUTOMATION` |

#### 2.2.3 `POST /v1/parks/driver-profiles/list` — List Driver Profiles

| Aspect | Detail |
|--------|--------|
| **Path** | `/v1/parks/driver-profiles/list` |
| **Method** | `POST` |
| **Parameters** | `limit` (max 1000), `offset`, `park_id`; filterable by `driver_profile.id`, `work_status`, `work_rule_id`, `car_id` |
| **Pagination** | Offset-based. `limit` max 1000, `offset`, response includes `total` |
| **Revenue/Cost/Price Fields** | `account.balance` (string), `account.currency` (string) |
| **Grain** | driver_profile |
| **Utility for Omniview** | High — provides driver universe with state (`work_status`, `current_status`), car bindings, and balance. Already used by Lima Growth Engine for eligible driver discovery |
| **Risk Assessment** | LOW. Read-only, bulk |
| **Classification** | `REPORTING` |

#### 2.2.4 `GET /v2/parks/contractors/driver-profile` — Get Driver Profile

| Aspect | Detail |
|--------|--------|
| **Path** | `/v2/parks/contractors/driver-profile` |
| **Method** | `GET` |
| **Parameters** | `driver_profile_id` (query param) |
| **Pagination** | N/A — single entity |
| **Revenue/Cost/Price Fields** | `account.balance` (string), `account.currency` (string) |
| **Grain** | 1 driver_profile |
| **Utility for Omniview** | Low — per-driver lookup, redundant with the bulk list endpoint |
| **Risk Assessment** | LOW. Read-only |
| **Classification** | `NOT_USEFUL` |

#### 2.2.5 `POST /v2/parks/contractors/driver-profile` — Driver Profile Creation

| Aspect | Detail |
|--------|--------|
| **Path** | `/v2/parks/contractors/driver-profile` |
| **Method** | `POST` |
| **Parameters** | Driver attributes (name, phone, work_rule_id, etc.) |
| **Pagination** | N/A |
| **Revenue/Cost/Price Fields** | None |
| **Grain** | 1 driver_profile created |
| **Utility for Omniview** | None — write-only mutation |
| **Risk Assessment** | EXTREME. Would create phantom drivers in the park |
| **Classification** | `UNSAFE_FOR_AUTOMATION` |

#### 2.2.6 `PUT /v2/parks/contractors/driver-profile` — Driver Profile Update

| Aspect | Detail |
|--------|--------|
| **Path** | `/v2/parks/contractors/driver-profile` |
| **Method** | `PUT` |
| **Parameters** | Driver ID + fields to update |
| **Pagination** | N/A |
| **Revenue/Cost/Price Fields** | None |
| **Grain** | 1 driver_profile updated |
| **Utility for Omniview** | None — write-only mutation |
| **Risk Assessment** | EXTREME. Would corrupt driver data |
| **Classification** | `UNSAFE_FOR_AUTOMATION` |

#### 2.2.7 `POST /v2/parks/contractors/auto-courier-profile` — Auto Courier Creation

| Aspect | Detail |
|--------|--------|
| **Path** | `/v2/parks/contractors/auto-courier-profile` |
| **Method** | `POST` |
| **Parameters** | Courier attributes |
| **Pagination** | N/A |
| **Revenue/Cost/Price Fields** | None |
| **Grain** | 1 courier_profile created |
| **Utility for Omniview** | None — courier-specific, write-only |
| **Risk Assessment** | EXTREME. Would create spurious courier profiles |
| **Classification** | `UNSAFE_FOR_AUTOMATION` |

#### 2.2.8 `POST /v2/parks/contractors/walking-courier-profile` — Walking Courier Creation

| Aspect | Detail |
|--------|--------|
| **Path** | `/v2/parks/contractors/walking-courier-profile` |
| **Method** | `POST` |
| **Parameters** | Courier attributes |
| **Pagination** | N/A |
| **Revenue/Cost/Price Fields** | None |
| **Grain** | 1 courier_profile created |
| **Utility for Omniview** | None — courier-specific, write-only |
| **Risk Assessment** | EXTREME. Would create spurious courier profiles |
| **Classification** | `UNSAFE_FOR_AUTOMATION` |

#### 2.2.9 `GET /v2/parks/contractors/supply-hours` — Get Driver Online Time

| Aspect | Detail |
|--------|--------|
| **Path** | `/v2/parks/contractors/supply-hours` |
| **Method** | `GET` |
| **Parameters** | `driver_profile_id`, `date_from`, `date_to` (query params) |
| **Pagination** | N/A — per-driver, returns daily array. **No bulk endpoint exists** |
| **Revenue/Cost/Price Fields** | None |
| **Grain** | driver × day |
| **Utility for Omniview** | Medium — `supply_duration_seconds` is a useful utilization metric. Crippled by per-driver architecture: requires 1 HTTP call per driver per day. Already used by Lima Growth Engine for driver 360 reports |
| **Risk Assessment** | MEDIUM. Rate-limiting at fleet scale (N drivers × D days = explosion). Not viable for daily bulk serving facts |
| **Classification** | `REPORTING` |

#### 2.2.10 `GET /v1/parks/contractors/blocked-balance` — Get Driver Balance

| Aspect | Detail |
|--------|--------|
| **Path** | `/v1/parks/contractors/blocked-balance` |
| **Method** | `GET` |
| **Parameters** | `driver_profile_id` (query param) |
| **Pagination** | N/A — single entity |
| **Revenue/Cost/Price Fields** | Balance (float), blocked_balance (float), currency |
| **Grain** | 1 driver |
| **Utility for Omniview** | Low — per-driver balance lookup. Could serve as reconciliation checkpoint for driver-level financial state, but per-driver architecture limits scalability |
| **Risk Assessment** | LOW. Read-only, but rate-limiting risk at scale |
| **Classification** | `RECONCILIATION` |

---

### 2.3 DriverWorkRules

#### 2.3.1 `GET /v1/parks/driver-work-rules` — List Work Rules

| Aspect | Detail |
|--------|--------|
| **Path** | `/v1/parks/driver-work-rules` |
| **Method** | `GET` |
| **Parameters** | `park_id` (query param) |
| **Pagination** | No pagination — returns all work rules for the park |
| **Revenue/Cost/Price Fields** | None (commission/rate info may be embedded in rule configuration fields) |
| **Grain** | work_rule |
| **Utility for Omniview** | Low — reference/lookup data for dimensional enrichment. Work rules appear on orders and driver profiles but provide no financial metrics themselves |
| **Risk Assessment** | LOW. Read-only, reference data |
| **Classification** | `NOT_USEFUL` |

---

### 2.4 Orders (HIGH-VALUE CLUSTER)

#### 2.4.1 `POST /v1/parks/orders/list` — List Orders

| Aspect | Detail |
|--------|--------|
| **Path** | `/v1/parks/orders/list` |
| **Method** | `POST` |
| **Parameters** | `limit` (max 500), `cursor`, `park_id`; filterable by `order_ids[]`, `short_ids[]`, `booked_at.from/to`, `ended_at.from/to`, `type`, `statuses[]`, `payment_methods[]`, `providers[]`, `categories[]`, `price.from/to`, `driver_profile.id`, `car.id` |
| **Pagination** | Cursor-based. `limit` max 500, response includes `next_cursor` to page forward |
| **Revenue/Cost/Price Fields** | `price` (STRING — fixed-point sum, e.g. `"15.9900"`; NOT an object with `final_cost`) |
| **Grain** | order |
| **Utility for Omniview** | HIGH. The primary orders endpoint. Provides: order grain with timestamps, status, payment method, mileage, price, driver_link, car_link, work_rule_link, cancellation_description. Already integrated in Lima Growth Engine. |
| **Risk Assessment** | MEDIUM. Cursor pagination requires sequential traversal; rate limits apply. **IMPORTANT**: `price` is a string, not an object — current CT code that reads `price.final_cost` may be invalid against actual API response |
| **Classification** | `REPORTING \| RECONCILIATION` |

**Response Fields Detail:**

| Field | Type | Notes |
|-------|------|-------|
| `id` | string | Order ID |
| `short_id` | integer | Short order ID |
| `status` | string | `complete`, `cancelled`, etc. |
| `created_at` | ISO datetime | Creation timestamp |
| `booked_at` | ISO datetime | Booking timestamp |
| `ended_at` | ISO datetime | Completion timestamp |
| `provider` | string | Provider name |
| `category` | string | Service category |
| `amenities` | array | Amenity flags |
| `address_from` | object | Pickup address |
| `route_points` | array | Route waypoints |
| `events` | array | Order lifecycle events |
| `payment_method` | string | Payment method |
| `driver_profile` | object | `{ id, name }` |
| `car` | object | `{ id, brand_model, license, callsign }` |
| `type` | object | `{ id, name }` |
| `price` | **string** | Fixed-point string (e.g. `"12.5000"`). **NOT** `{ final_cost: number }` |
| `driver_work_rule` | object | `{ id, name }` |
| `mileage` | number | Trip distance |
| `cancellation_description` | string | Reason if cancelled |
| `park_details` | object | `{ tariff, passenger, company }` |

#### 2.4.2 `POST /v1/parks/orders/track` — Get Order Track

| Aspect | Detail |
|--------|--------|
| **Path** | `/v1/parks/orders/track` |
| **Method** | `POST` |
| **Parameters** | `order_id` |
| **Pagination** | N/A |
| **Revenue/Cost/Price Fields** | None |
| **Grain** | GPS track points |
| **Utility for Omniview** | None — GPS/geolocation data. Irrelevant for financial/operational metrics |
| **Risk Assessment** | LOW. Read-only, but irrelevant |
| **Classification** | `NOT_USEFUL` |

---

### 2.5 Transactions (REVENUE DISCOVERY CLUSTER)

#### 2.5.1 `POST /v2/parks/driver-profiles/transactions` — [DEPRECATED] Create Transaction

| Aspect | Detail |
|--------|--------|
| **Path** | `/v2/parks/driver-profiles/transactions` |
| **Method** | `POST` |
| **Parameters** | Transaction attributes |
| **Pagination** | N/A |
| **Revenue/Cost/Price Fields** | `amount` (input), `category_id` |
| **Grain** | 1 transaction created |
| **Utility for Omniview** | None — deprecated write endpoint. Superseded by v3 |
| **Risk Assessment** | CRITICAL. Deprecated + write = double red flag |
| **Classification** | `UNSAFE_FOR_AUTOMATION` |

#### 2.5.2 `POST /v2/parks/driver-profiles/transactions/list` — List Transactions by Driver

| Aspect | Detail |
|--------|--------|
| **Path** | `/v2/parks/driver-profiles/transactions/list` |
| **Method** | `POST` |
| **Parameters** | `driver_profile_id`, `limit` (max 1000, default 40), `cursor`, `park_id`; filterable by `event_at.from/to`, `category_ids[]` |
| **Pagination** | Cursor-based. `limit` max 1000, default 40. Response includes `next_cursor` |
| **Revenue/Cost/Price Fields** | `amount` (string fixed-point), `currency_code`, `category_id`, `category_name` |
| **Grain** | driver × transaction |
| **Utility for Omniview** | HIGH. Enables per-driver financial reconciliation. Filterable by `category_ids` to isolate revenue categories (`partner_rides`, `platform_card`). Downside: per-driver architecture means exploding API calls at fleet scale |
| **Risk Assessment** | MEDIUM. Cursor pagination; per-driver calls multiply with fleet size |
| **Classification** | `FINANCIAL_CANDIDATE \| RECONCILIATION` |

#### 2.5.3 `POST /v2/parks/orders/transactions/list` — List Transactions by Orders

| Aspect | Detail |
|--------|--------|
| **Path** | `/v2/parks/orders/transactions/list` |
| **Method** | `POST` |
| **Parameters** | `order_ids[]` (required), `park_id` |
| **Pagination** | None explicitly documented — returns transactions for the given order IDs |
| **Revenue/Cost/Price Fields** | `amount` (string fixed-point), `currency_code`, `category_id`, `category_name` |
| **Grain** | order × transaction |
| **Utility for Omniview** | HIGH. Provides order-level financial breakdown: see exactly which transaction categories hit each order. Ideal for validating revenue composition per order. Requires order IDs as input → must be paired with orders/list |
| **Risk Assessment** | LOW. Read-only, scoped to known order IDs |
| **Classification** | `FINANCIAL_CANDIDATE \| RECONCILIATION` |

#### 2.5.4 `POST /v2/parks/transactions/categories/list` — List Transaction Categories

| Aspect | Detail |
|--------|--------|
| **Path** | `/v2/parks/transactions/categories/list` |
| **Method** | `POST` |
| **Parameters** | `park_id` |
| **Pagination** | No pagination — returns all categories |
| **Revenue/Cost/Price Fields** | None directly (metadata), but `is_affecting_driver_balance` flags which categories impact financial state |
| **Grain** | category |
| **Utility for Omniview** | HIGH. Taxonomy of all financial transaction types. Critical for mapping revenue streams. Identifies which categories contribute to GMV, commissions, fees, and driver payments |
| **Risk Assessment** | LOW. Read-only, reference data |
| **Classification** | `REPORTING \| FINANCIAL_CANDIDATE` |

**Transaction Category Groups (Key for Revenue Discovery):**

| Group ID | Group Name | Omniview Relevance |
|----------|-----------|-------------------|
| `platform_card` | Card payment | **GMV** — gross payment via card |
| `platform_corporate` | Corporate payment | **GMV** — gross payment via corporate account |
| `platform_bonus` | Bonus | Promotional bonus (not core revenue) |
| `platform_tip` | Tip | Driver tip (not YEGO revenue) |
| `platform_fees` | Platform's fees | **Commission taken by Yango** (YEGO cost) |
| `partner_fees` | Partner's fee | **YEGO fees charged to driver** (YEGO revenue from driver) |
| `partner_rides` | Payments for partner's rides | **YEGO REVENUE** — payments received by YEGO from rides |
| `partner_other` | Other partner payments | Other YEGO income |
| `platform_other` | Other platform payments | Miscellaneous platform income |
| `platform_promotion` | Promo campaigns | Marketing spend |
| `cash_collected` | Cash | Cash transactions |

#### 2.5.5 `POST /v2/parks/transactions/list` — List Transactions by Park ⭐

| Aspect | Detail |
|--------|--------|
| **Path** | `/v2/parks/transactions/list` |
| **Method** | `POST` |
| **Parameters** | `limit` (max 1000), `cursor`, `park_id`; filterable by `event_at.from/to` (date range) and `category_ids[]` (category filter) |
| **Pagination** | Cursor-based. `limit` max 1000. Response includes `next_cursor` |
| **Revenue/Cost/Price Fields** | `amount` (string fixed-point), `currency_code`, `category_id`, `category_name` |
| **Grain** | park × transaction |
| **Utility for Omniview** | **HIGHEST**. Park-level transaction listing with date range and category filters. This is the single most valuable endpoint for revenue discovery because: (1) park-scoped = no per-driver explosion, (2) filterable by date range and category, (3) includes `order_id` and `driver_profile_id` for traceability, (4) `amount` + `category_id` enables revenue/cost breakdown |
| **Risk Assessment** | LOW. Read-only, bulk, park-scoped |
| **Classification** | `FINANCIAL_CANDIDATE \| RECONCILIATION \| REPORTING` |

**Response Fields Detail:**

| Field | Type | Notes |
|-------|------|-------|
| `id` | string | Transaction ID |
| `event_at` | ISO datetime | When the transaction occurred |
| `category_id` | string | Links to `/transactions/categories/list` |
| `category_name` | string | Human-readable category name |
| `amount` | string | Fixed-point string (e.g. `"15.9900"`) |
| `currency_code` | string | ISO currency code |
| `description` | string | Transaction description |
| `created_by` | object | `{ identity, passport_uid, dispatcher_id, dispatcher_name }` |
| `driver_profile_id` | string | **Driver link** — enables driver-level reconciliation |
| `order_id` | string | **Order link** — enables order-level reconciliation |
| `event_id` | string | Event identifier |

#### 2.5.6 `POST /v3/parks/driver-profiles/transactions` — Create Transaction v3

| Aspect | Detail |
|--------|--------|
| **Path** | `/v3/parks/driver-profiles/transactions` |
| **Method** | `POST` |
| **Parameters** | Transaction attributes (v3 schema) |
| **Pagination** | N/A |
| **Revenue/Cost/Price Fields** | `amount` (input), `category_id` |
| **Grain** | 1 transaction created |
| **Utility for Omniview** | None — write endpoint. Would create spurious financial transactions |
| **Risk Assessment** | CRITICAL. Would inject fake financial transactions into the park |
| **Classification** | `UNSAFE_FOR_AUTOMATION` |

#### 2.5.7 `GET /v3/parks/driver-profiles/transactions/status` — Get Transaction Status

| Aspect | Detail |
|--------|--------|
| **Path** | `/v3/parks/driver-profiles/transactions/status` |
| **Method** | `GET` |
| **Parameters** | `transaction_id` (query param) |
| **Pagination** | N/A |
| **Revenue/Cost/Price Fields** | None |
| **Grain** | 1 transaction status |
| **Utility for Omniview** | None — status-only check for a single transaction |
| **Risk Assessment** | LOW. Read-only, but irrelevant |
| **Classification** | `NOT_USEFUL` |

---

## 3. CLASSIFICATION SUMMARY MATRIX

| # | Path | Method | Classification | Safe for Pipeline? |
|---|------|--------|---------------|---------------------|
| 1 | `/v2/parks/vehicles/car` | POST | `UNSAFE_FOR_AUTOMATION` | NO |
| 2 | `/v2/parks/vehicles/car` | PUT | `UNSAFE_FOR_AUTOMATION` | NO |
| 3 | `/v2/parks/vehicles/car` | GET | `NOT_USEFUL` | YES |
| 4 | `/v1/parks/cars/list` | POST | `REPORTING` | YES |
| 5 | `/v1/parks/driver-profiles/car-bindings` | DELETE | `UNSAFE_FOR_AUTOMATION` | NO |
| 6 | `/v1/parks/driver-profiles/car-bindings` | PUT | `UNSAFE_FOR_AUTOMATION` | NO |
| 7 | `/v1/parks/driver-profiles/list` | POST | `REPORTING` | YES |
| 8 | `/v2/parks/contractors/driver-profile` | GET | `NOT_USEFUL` | YES |
| 9 | `/v2/parks/contractors/driver-profile` | POST | `UNSAFE_FOR_AUTOMATION` | NO |
| 10 | `/v2/parks/contractors/driver-profile` | PUT | `UNSAFE_FOR_AUTOMATION` | NO |
| 11 | `/v2/parks/contractors/auto-courier-profile` | POST | `UNSAFE_FOR_AUTOMATION` | NO |
| 12 | `/v2/parks/contractors/walking-courier-profile` | POST | `UNSAFE_FOR_AUTOMATION` | NO |
| 13 | `/v2/parks/contractors/supply-hours` | GET | `REPORTING` | YES |
| 14 | `/v1/parks/contractors/blocked-balance` | GET | `RECONCILIATION` | YES |
| 15 | `/v1/parks/driver-work-rules` | GET | `NOT_USEFUL` | YES |
| 16 | `/v1/parks/orders/list` | POST | `REPORTING \| RECONCILIATION` | YES |
| 17 | `/v1/parks/orders/track` | POST | `NOT_USEFUL` | YES |
| 18 | `/v2/parks/driver-profiles/transactions` | POST | `UNSAFE_FOR_AUTOMATION` | NO |
| 19 | `/v2/parks/driver-profiles/transactions/list` | POST | `FINANCIAL_CANDIDATE \| RECONCILIATION` | YES |
| 20 | `/v2/parks/orders/transactions/list` | POST | `FINANCIAL_CANDIDATE \| RECONCILIATION` | YES |
| 21 | `/v2/parks/transactions/categories/list` | POST | `REPORTING \| FINANCIAL_CANDIDATE` | YES |
| 22 | `/v2/parks/transactions/list` | POST | `FINANCIAL_CANDIDATE \| RECONCILIATION \| REPORTING` | YES |
| 23 | `/v3/parks/driver-profiles/transactions` | POST | `UNSAFE_FOR_AUTOMATION` | NO |
| 24 | `/v3/parks/driver-profiles/transactions/status` | GET | `NOT_USEFUL` | YES |

### Summary Counts

| Classification | Count |
|----------------|-------|
| `UNSAFE_FOR_AUTOMATION` | 9 |
| `NOT_USEFUL` | 5 |
| `REPORTING` (only or includes) | 4 |
| `RECONCILIATION` (only or includes) | 1 |
| `FINANCIAL_CANDIDATE` (includes) | 5 |
| **TOTAL** | **24** |

---

## 4. TOP 5 MOST USEFUL ENDPOINTS FOR OMNIVIEW V2

| Rank | Endpoint | Classification | Why |
|------|----------|---------------|-----|
| **#1** | `POST /v2/parks/transactions/list` | `FINANCIAL_CANDIDATE \| RECONCILIATION \| REPORTING` | Park-level transaction feed with date-range and category filters. Single endpoint delivers: revenue by category (`partner_rides`, `platform_card`), commissions (`platform_fees`), fees (`partner_fees`), all linked to `driver_profile_id` and `order_id`. No per-driver explosion. This is the **revenue discovery king** for Omniview V2 |
| **#2** | `POST /v1/parks/orders/list` | `REPORTING \| RECONCILIATION` | Primary orders feed. Provides trip grain with price, driver, car, mileage, timestamps. Already integrated in CT. Pair with #1 for order-level revenue reconciliation. **Caution**: `price` is a string, not `{ final_cost }` — code must be verified |
| **#3** | `POST /v2/parks/orders/transactions/list` | `FINANCIAL_CANDIDATE \| RECONCILIATION` | Order-scoped financial breakdown. Given order IDs from #2, reveals the exact transaction composition per order — separating GMV, commission, partner revenue, tip, etc. Essential for validating CT's `revenue_yego` calculation |
| **#4** | `POST /v2/parks/transactions/categories/list` | `REPORTING \| FINANCIAL_CANDIDATE` | Category taxonomy. Without this, transaction streams are unlabeled. Provides the mapping from `category_id` to revenue group (`partner_rides` = YEGO income, `platform_fees` = Yango commission, etc.). One-time fetch, persistent reference |
| **#5** | `POST /v1/parks/driver-profiles/list` | `REPORTING` | Driver universe with state and car bindings. Provides the driver dimension for all financial data. Balance fields offer snapshot reconciliation points. Already integrated |

### Pipeline Dependency Flow

```
#5 (driver-profiles/list) ──── dim: driver universe
         │
#2 (orders/list) ───────────── fact: trips + price
         │
         ├──── order_ids ────► #3 (orders/transactions/list) ──── fact: order financial breakdown
         │
#4 (categories/list) ───────── dim: category taxonomy
         │
#1 (transactions/list) ─────── fact: park-level revenue stream (category_ids filterable via #4)
```

---

## 5. CRITICAL OBSERVATIONS

### 5.1 `price` Field Type in Orders

The official docs state `price` is a **string** (fixed-point representation, e.g. `"15.9900"`), NOT an object with `final_cost`. The A1 certification matrix and current CT code reference `price.final_cost` as a number. This must be verified against live API responses — if the docs are correct, CT's Lima Growth Engine may be reading a non-existent field.

### 5.2 Transaction Endpoints Are the Revenue Unlock

The transaction cluster (endpoints #19-#22) was not evaluated in OV2-A.1. These endpoints expose the financial ledger of the park and are the most promising source for revenue discovery. The `partner_rides` and `platform_card` category groups represent YEGO's income streams.

### 5.3 Per-Driver Endpoints Do Not Scale

Endpoints #13 (supply-hours) and #14 (blocked-balance) require one HTTP call per driver. At Lima's fleet size (~hundreds of drivers), daily reconciliation would require hundreds of calls. These are viable for spot-checks but not for daily bulk serving facts.

### 5.4 Cursor Pagination Is Sequential

Endpoints #16, #19, #22 use cursor-based pagination (`next_cursor`). This means:
- No random access to pages (cannot jump to page N)
- Must traverse sequentially from the beginning
- Date-range filters mitigate the need for full traversal
- Parallelization is not possible on the same cursor stream

---

## 6. RISK REGISTER

| ID | Risk | Severity | Endpoints Affected | Mitigation |
|----|------|----------|--------------------|------------|
| R-A2-1 | `price` field type mismatch (string vs object) | HIGH | #16 | Verify with live API probe; update CT code if needed |
| R-A2-2 | Accidental call to write/mutate endpoint | CRITICAL | #1, #2, #5, #6, #9, #10, #11, #12, #18, #23 | Pipeline must use an allowlist of safe endpoint paths. Reject any non-GET/non-list POST |
| R-A2-3 | Rate-limiting at fleet scale for per-driver endpoints | MEDIUM | #13, #14, #19 | Use park-level alternatives (#22) for bulk; per-driver only for spot audits |
| R-A2-4 | Transaction category taxonomy changes | MEDIUM | #4, #21 | Re-fetch categories periodically; detect new/removed category_ids |
| R-A2-5 | Cursor expiration during long traversals | LOW | #16, #19, #22 | Use date-range filters to keep traversal windows short |
| R-A2-6 | Order-transaction join gaps (orphan transactions) | MEDIUM | #3, #20 | Validate that every transaction in #22 has a resolvable `order_id` |

---

## 7. RECOMMENDATIONS

### 7.1 Immediate (OV2-A)

1. **Probe transaction endpoints live**: Execute `probe_revenue_api_source.py` against `/v2/parks/transactions/list`, `/v2/parks/transactions/categories/list`, and `/v2/parks/orders/transactions/list`
2. **Verify `price` field type**: Confirm whether `/v1/parks/orders/list` returns `price` as string or object with `final_cost`
3. **Publish transaction category map**: Export the full category taxonomy to `backend/exports/audits/transaction_categories/` as reference data

### 7.2 Short-Term (OV2-B)

4. **Build park-level revenue pipeline**: Consume `/v2/parks/transactions/list` filtered by `partner_rides` and `platform_card` category groups → aggregate to daily revenue facts
5. **Cross-validate orders vs transactions**: For a sample date range, fetch orders via #16 and their transactions via #20; verify that `SUM(transactions.amount)` per order reconciles with `orders.price`
6. **Create pipeline endpoint allowlist**: Hardcode the 15 safe endpoints in pipeline configuration; reject all others at the HTTP client layer

### 7.3 Long-Term (OV2-C)

7. **Promote park transactions to canonical revenue source**: If reconciliation proves consistent, use `POST /v2/parks/transactions/list` as the primary revenue feed for Omniview V2, with CT's `comision_empresa_asociada` as the reconciliation counterpart
8. **Monitor category taxonomy changes**: Build a scheduled job that diffs `/v2/parks/transactions/categories/list` output and alerts on new/removed categories

---

## 8. VERIFICATION OF GOVERNANCE

| Rule | Status |
|-------|--------|
| No modifica Omniview V1 | PASS |
| No modifica UI productiva | PASS |
| No reemplaza fuentes actuales sin validación | PASS |
| Read-only / discovery scope | PASS |
| Control Foundation scope | PASS |
| Credenciales enmascaradas | PASS |
| Sin inserción en tablas | PASS |
| Sin modificar serving facts | PASS |
| Pipeline endpoint allowlist enforced | PENDING (requires implementation) |

---

## 9. SIGNATURE

| Campo | Valor |
|-------|-------|
| **Mapeado por** | OV2-A.2 Endpoint Discovery |
| **Fecha** | 2026-06-04 |
| **Fuente** | Yango Fleet API official docs (`https://fleet.yango.com/docs/api/en`) |
| **Próxima revisión** | Post-ejecución de probe contra endpoint #22 (`/v2/parks/transactions/list`) con datos live |
| **Estado** | `DOCUMENTED` (pendiente validación con API live) |
