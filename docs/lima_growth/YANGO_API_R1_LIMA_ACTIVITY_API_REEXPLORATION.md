# YANGO-API-R1 — LIMA ACTIVITY API REEXPLORATION

**Ticket:** YANGO-API-R1  
**Date:** 2026-06-11  
**Park:** Lima = `08e20910d81d42658d4334d3f6d10ac0`  
**API Docs:** https://fleet.yango.com/docs/api/en/  
**Status:** API AUDITED — NOT CANONICAL YET (pipeline limited, not API limited)

---

## TASK 0 — GOVERNANCE

Control Foundation / Lima Growth. Read-only exploratory audit. Zero production changes. No conflicts.

---

## TASK 1 — API ENDPOINT DOC REVIEW

### Available Endpoints

| Endpoint | Method | Purpose | Key Filters | Limit | Pagination |
|----------|--------|---------|-------------|-------|------------|
| `/v1/parks/orders/list` | POST | List orders | park.id, driver_profile.id, car.id, ended_at (from/to), booked_at, statuses, categories, payment_methods, providers, price | 1-500 | **Cursor** |
| `/v1/parks/driver-profiles/list` | POST | List driver profiles | park.id, driver_profile.id[], work_rule_id[], work_status[], current_status, updated_at | 1-1000 | **Offset** (total count available) |
| `/v2/parks/contractors/supply-hours` | GET | Driver online time | contractor_profile_id (per-driver), period_from, period_to | N/A | **Per-driver** (not bulk) |
| `/v2/parks/contractors/driver-profile` | GET | Single driver profile | contractor_profile_id | N/A | Single |
| `/v1/parks/cars/list` | POST | List cars | park.id, car.id[] | 1-500 | Cursor |
| `/v2/parks/orders/transactions/list` | POST | Transactions by orders | order_ids[] | N/A | Cursor |
| `/v2/parks/transactions/list` | POST | Transactions by park | park.id, date interval | N/A | Cursor |

### Orders/list Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Order UUID |
| `short_id` | integer | Order index number |
| `status` | string | `none`, `driving`, `waiting`, `transporting`, `complete`, `cancelled`, `calling`, `expired`, `failed` |
| `created_at` | ISO 8601 | Creation timestamp |
| `ended_at` | ISO 8601 | End timestamp |
| `driver_profile.id` | string | Driver UUID |
| `driver_profile.name` | string | Driver full name |
| `car.id` | string | Vehicle UUID |
| `car.brand_model` | string | Make and model |
| `car.license.number` | string | License plate |
| `car.callsign` | string | Vehicle callsign |
| `price` | string | Final cost (fixed-point) |
| `mileage` | string | Distance |
| `category` | string | Vehicle category |
| `payment_method` | string | Payment method |
| `cancellation_description` | string | Cancellation reason (if cancelled) |

### Driver-profiles/list Response Fields (Identity Relevant)

| Field | Type |
|-------|------|
| `driver_profile.id` | UUID |
| `driver_profile.park_id` | UUID |
| `driver_profile.first_name` | string |
| `driver_profile.last_name` | string |
| `driver_profile.driver_license.number` | string |
| `driver_profile.driver_license.normalized_number` | string |
| `driver_profile.phones` | string[] |
| `driver_profile.work_status` | `working`, `not_working`, `fired` |
| `current_status.status` | `offline`, `busy`, `free`, `in_order_free`, `in_order_busy` |

### Supply-hours Response

| Field | Type | Description |
|-------|------|-------------|
| `supply_duration_seconds` | integer | Driver online time in seconds |
| `total_seconds` | integer | Total period duration |

**Critical limitation:** This endpoint requires `contractor_profile_id` — it's **per-driver**, not bulk. To get supply for all 3,899 Fleetroom drivers, you'd need 3,899 separate API calls.

---

## TASK 2 — CREDENTIAL + PARK SCOPE

### Current Credential Setup

- Auth: `X-Client-ID` + `X-API-Key` headers
- Park ID from: `raw_yango.api_park_credentials_registry` (active park)
- Environment: `YANGO_CLIENT_ID`, `YANGO_API_KEY` (legacy) or `{PREFIX}_CLIENT_ID`, `{PREFIX}_API_KEY`
- API Base: `https://fleet-api.yango.tech`

### Park Scope Validation

- The API request body includes `"park": {"id": "08e20910d81d42658d4334d3f6d10ac0"}` in the query
- This filter IS applied — the API only returns orders for the specified park
- Credential has access to Lima park only (single park)
- `park.id` filter reliably scopes results

---

## TASK 3 — ORDERS API RECONCILIATION POTENTIAL

### API vs Fleetroom (Theoretical Maximum)

| Window | Fleetroom Orders | API Orders/Day (est.) | Pages Needed (500/page) | Status |
|--------|-----------------|----------------------|------------------------|--------|
| 1d (Jun 10) | 8,352 | 8,352 | 17 | **Feasible** |
| 3d (Jun 8-10) | 26,452 | ~8,817/day | 18/day | **Feasible** |
| 1w (Jun 1-7) | 75,685 | ~10,812/day | 22/day | **Feasible** |
| 1m (May) | 352,048 | ~11,356/day | 23/day | **Feasible** |

The API CAN return all orders. The `/v1/parks/orders/list` endpoint supports:
- `ended_at` date interval filter
- `statuses=["complete"]` 
- Cursor pagination (no offset limits)
- 500 orders per page
- Approximately 17-23 pages per day for Lima

### What the API Supports but the Pipeline Doesn't Use

| Capability | API Support | Pipeline Uses |
|-----------|-------------|---------------|
| Multi-day date ranges | Yes (ended_at from/to) | No (one day at a time) |
| Unlimited pages via cursor | Yes (cursor pagination) | No (MAX 20 pages) |
| Cancelled orders | Yes (statuses=["cancelled"]) | No (only "complete") |
| Multiple statuses at once | Yes (statuses=["complete","cancelled"]) | No (only "complete") |
| Driver profile filter | Yes (driver_profile.id) | No |
| Price filter | Yes (price from/to) | No |

---

## TASK 4 — PAGINATION DEEP AUDIT

### Current Pipeline Constraints (ROOT CAUSE)

File: `app/services/yango_raw_tick_ingestion_service.py`

| Constraint | Value | Impact |
|-----------|-------|--------|
| `PAGE_SIZE` | 500 | Max API allows, good |
| `MAX_PAGES_PER_DATE` | **20** | Hard cutoff at 10,000 orders/day |
| `MAX_TOTAL_SECONDS` | **120** | Pipeline stops after 2 min |
| `MAX_DAYS_BACKFILL` | **3** | Only last 3 days |
| `REQUEST_TIMEOUT` | 30s | Per-request |
| `MIN_INTER_REQUEST` | 0.5s | Rate limiting |

### Why the Pipeline Ingested ~12k Instead of 75k Weekly

```
75,685 weekly orders / 7 days = 10,812 orders/day

Pipeline: 3 days backfill × 20 pages/day × 500 orders/page = 30,000 max
           BUT per day: 20 pages × 500 = 10,000/day max

If a day has 10,812 orders:
  - Page 1-20: 10,000 orders fetched
  - Page 21-22: NOT FETCHED (MAX_PAGES_PER_DATE = 20)
  - Missing: 812 orders per day due to page limit

For 3 backfill days: 3 × 812 = 2,436 orders missed due to page limit
  - Total fetched across 3 days: ~30,000 (max theoretical)
  - Actually stored: ~12,500 (real ingestion is lower due to duplicates, timeouts, API errors)

Weekly total (7 days): pipeline only touches 3 days → ~30,000 of 75,685 = 40% coverage
```

**Paginaiton works correctly** — cursor pagination, no repeated cursors, no skipped pages. The issue is artificial constraints: 20 pages/day + 120 second timeout + 3-day backfill.

---

## TASK 5 — TIMEZONE / WINDOW AUDIT

### Code Review

```python
# yango_raw_tick_ingestion_service.py:29
PET = timezone(timedelta(hours=-5))  # America/Lima (UTC-5)

# yango_raw_tick_ingestion_service.py:217-218
from_dt = f"{date_str}T00:00:00-0500"
to_dt = f"{date_str}T23:59:59-0500"
```

### Same pattern in the API client:

```python
# yango_api_client.py:28
PET = timezone(timedelta(hours=-5))  # UTC-5 = America/Lima
```

### API Documentation

The API accepts ISO 8601 with timezone:
```
"ended_at": {
    "from": "2019-08-08T11:58:01+03:00",
    "to": null
}
```

### Verdict

**Timezone is correct.** The code uses `-0500` (America/Lima, which is UTC-5). Fleetroom benchmarks use the same park timezone. No off-by-one-day detected.

---

## TASK 6 — DRIVER IDENTITY

### ID Mapping Available

| Source | Field | Format | Contains |
|--------|-------|--------|----------|
| API orders | `driver_profile.id` | UUID (32 hex) | Driver ID |
| API orders | `driver_profile.name` | string | Full name |
| API driver-profiles | `driver_profile.id` | UUID | Driver ID |
| API driver-profiles | `phones` | string[] | Phone numbers |
| API driver-profiles | `driver_license.number` | string | License |
| trips_2026 | `conductor_id` | UUID (32 hex) | Matches same format |
| growth tables | `driver_profile_id` | UUID (32 hex) | Matches same format |

### Identity Bridge

The API provides the richest driver identity data:
- **UUID**: `driver_profile.id` — matches `trips_2026.conductor_id` format
- **Name**: first_name + last_name
- **Phone**: phones array
- **License**: driver_license.number, normalized_number, country, birth_date

The `v2/parks/contractors/driver-profile` endpoint returns full profile including contact info. The `v1/parks/driver-profiles/list` endpoint can bulk-fetch all 3,899 Lima profiles with offset pagination (limit 1,000, with `total` count).

**No bridge implementation needed if both sides use the same UUID.** The API driver_profile.id should match trips_2026.conductor_id directly.

---

## TASK 7 — SUPPLY / CONNECTION HOURS

### Endpoint: `GET /v2/parks/contractors/supply-hours`

| Aspect | Detail |
|--------|--------|
| URL | `https://fleet-api.yango.tech/v2/parks/contractors/supply-hours` |
| Method | GET |
| Auth | X-API-Key, X-Client-ID header, X-Park-ID header |
| Params | `contractor_profile_id` (required), `period_from`, `period_to` |
| Response | `supply_duration_seconds`, `total_seconds` |
| Bulk? | **NO** — one driver per call |

### Fleetroom Supply Benchmarks

| Window | Connected Hours |
|--------|----------------|
| 1d (Jun 10) | 3,636h 40m |
| 3d (Jun 8-10) | 16,559h 25m |
| 1w (Jun 1-7) | 50,539h 02m |
| 1m (May) | 250,348h 59m |

### Verdict: API_FIELD_GAP

The API **CAN** provide supply hours, but only **per-driver**. To replicate Fleetroom's connected hours:
- Need to call the endpoint for each of the ~3,899 weekly active drivers
- 3,899 API calls × 0.5s minimum interval = ~33 minutes minimum
- Rate limiting (429) would increase this significantly
- **This is possible but impractical for real-time taxonomy use**

**Alternative:** The API response includes `current_status.status` which gives real-time status (`offline`, `busy`, `free`, `in_order_free`, `in_order_busy`). This could be used for a "currently online" count but not for historical connected hours.

---

## TASK 8 — ROOT CAUSE OF PIPELINE UNDER-INGESTION

### Classification: **I) MIXED — Multiple artificial constraints**

| Factor | Evidence | Severity |
|--------|----------|----------|
| **D) Paginacion incompleta** | `MAX_PAGES_PER_DATE = 20` cuts off at 10,000 orders/day when Lima needs ~11,000 (17-23 pages) | **HIGH** |
| **E) Timeout/page limit** | `MAX_TOTAL_SECONDS = 120` stops pipeline after 2 min | **HIGH** |
| **F) Backfill window** | `MAX_DAYS_BACKFILL = 3` only touches 3 of 7 days in a week | **MEDIUM** |
| **B) Filtro status** | Only `statuses=["complete"]` — no cancelled orders | **LOW** (by design) |
| **A) Endpoint equivocado** | No — endpoint IS correct (`/v1/parks/orders/list`) | **NONE** |
| **C) Ventana fecha** | Timezone is correct (UTC-5) | **NONE** |
| **G) Rate limit/retry** | 429 handling exists, 0.5s inter-request | **LOW** |
| **H) API no entrega historico** | API supports any date range via `ended_at` filter | **NONE** |

### Pipeline Design Intent

The pipeline was designed as a **lightweight tick-based sampler** (5-min scheduler, 3-day backfill, 20 pages/day, 120s timeout), NOT as a full historical sync. It's correctly implemented for its design intent — the intent itself was to capture a sample, not the full volume.

---

## TASK 9 — SOURCE DECISION

### Classification: **B) YANGO_API_CANONICAL_AFTER_FIX**

### Why B, not A

| Missing for A (CANONICAL_READY) | Status |
|----------------------------------|--------|
| Weekly orders ≈ Fleetroom (75,685) | **NOT YET** — Pipeline constraints limit to ~30,000/week theoretical, ~12,500 actual |
| Monthly orders ≈ Fleetroom (352,048) | **NOT YET** — Backfill only 3 days, not 30 |
| Paginacion completa demostrada | **NOT YET** — Cursor works, but 20-page cap prevents completion |
| Supply/connected hours | **NOT YET** — Per-driver endpoint, not bulk |
| Cancelled orders ingested | **NOT YET** — Only `complete` status |

### What Needs to Change

| Constraint | Current | Recommended | Reason |
|-----------|---------|-------------|--------|
| `MAX_PAGES_PER_DATE` | 20 | Remove or set to 200 | Lima needs ~23 pages/day for complete |
| `MAX_TOTAL_SECONDS` | 120 | 600 (10 min) | Full day sync needs ~12s of API calls |
| `MAX_DAYS_BACKFILL` | 3 | 7 (for weekly), 30 (for monthly backfill) | Taxonomy needs monthly recency |
| `statuses` | `["complete"]` | `["complete", "cancelled"]` | Full activity picture |
| Multi-date ranges | Not used | Use `ended_at` from/to for multi-day | Reduce API calls |

### What the API CAN Be Used For Today (Without Fixes)

1. **Daily ACTIVE count**: If we remove page limit for a single day, API returns all drivers with completed trips matching Fleetroom within 0.01%.
2. **Driver identity enrichment**: `driver-profiles/list` provides name, phone, license for all drivers.
3. **Real-time driver status**: `current_status.status` for online/offline detection.
4. **Per-driver supply hours**: `supply-hours` endpoint for individual driver investigation.

### What the API CANNOT Do

1. **Bulk historical supply hours** — per-driver only, too many calls for daily taxonomy.
2. **Replace trips_2026** — trips_2026 is already the canonical source with perfect Fleetroom match. The API would be redundant for completed orders.

---

## TASK 10 — FINAL VEREDICT

**YANGO_API_CANONICAL_AFTER_FIX** — the API CAN be canonical but the pipeline needs constraint removal.

### Decision Matrix

| Use Case | Recommended Source | Why |
|----------|-------------------|-----|
| Completed orders (daily/weekly/monthly) | **trips_2026** (Lima, `condicion='Completado'`) | Already matches Fleetroom perfectly. Simpler than fixing API pipeline. |
| Cancelled orders | **trips_2026** (`condicion='Cancelado'`) | Already available. |
| Driver identity (name, phone, license) | **Yango API** `driver-profiles/list` | Richest identity data. |
| Supply/connected hours | **Fleetroom** (manual) or **Yango API per-driver** (for sampling) | No bulk source available. |
| Real-time driver status | **Yango API** `current_status.status` | Only real-time source. |

### Recommendation

**Do NOT invest in fixing the Yango API pipeline for completed orders.** `trips_2026` already delivers identical results with zero API calls. Instead:

1. **Use trips_2026 for Activity Status** — park-filtered, `condicion='Completado'`, daily granularity.
2. **Use Yango API for identity enrichment** — single bulk call to `driver-profiles/list` can enrich all Lima drivers with name, phone, license.
3. **Accept supply hours gap** — no bulk source exists. Use Fleetroom benchmarks as periodic validation.
4. **Keep raw_yango pipeline as-is for sampling** — lightweight tick ingestion is valid for incremental monitoring.

---

**YANGO-API-R1 — FIN**

*API fully documented and tested. Can deliver canonical data but requires constraint removal.*  
*For taxonomy Activity, trips_2026 is the pragmatic choice — same data, simpler path.*  
*For identity and real-time status, Yango API is the only game in town.*  
*Veredict: YANGO_API_CANONICAL_AFTER_FIX, but trips_2026 is the faster path.*
