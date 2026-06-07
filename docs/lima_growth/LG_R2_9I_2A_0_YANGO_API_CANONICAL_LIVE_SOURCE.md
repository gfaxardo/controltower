# LG-R2.9I.2A.0 — Yango API Canonical Live Source Migration

**Date:** 2026-06-06
**Phase:** LG-R2.9I.2A.0 Yango API Canonical Live Source Migration

---

## 1. EXECUTIVE SUMMARY

**YANGO_API_LIVE IS CANONICAL OPERATIONAL SOURCE.**

The migration is complete from an architectural standpoint. Yango Fleet API (`raw_yango.*`) already serves as the live operational source for Lima Growth:

- `yango_api_client.py` (1155 lines) — calls 4 API endpoints
- `ingest_yango_raw_landing.py` (1279 lines) — ingests into 3 raw tables
- 5 materialized views aggregate daily data (orders, revenue, drivers, coverage)
- `driver_360_service.py` uses Yango API supply-hours for HOT drivers
- `trips_2025/trips_2026` correctly limited to historical enrichment

**What was done:** Formalized the deprecation of trips tables as operational sources, documented the source registry, and established the governance contract.

---

## 2. COVERAGE AUDIT

See: `docs/lima_growth/LG_YANGO_API_COVERAGE_MATRIX.md`

All operational fields are available from Yango API:
- completed_orders → `raw_yango.orders_raw`
- supply_hours → API `get_supply_hours()` direct
- driver identity → `raw_yango.driver_profiles_raw`
- revenue → `raw_yango.transactions_raw` → `mv_revenue_day`

---

## 3. DEPRECATION REGISTRY

See: `docs/lima_growth/LG_DEPRECATED_OPERATIONAL_SOURCES.md`

- `trips_2025` and `trips_2026`: **HISTORICAL_ENRICHMENT only**
- Yango API: **LIVE_OPERATIONAL**
- Conflict rule: Yango API always wins

---

## 4. SOURCE REGISTRY

| Source | Role | Canonical |
|--------|------|:---:|
| `raw_yango.*` (Yango Fleet API) | LIVE_OPERATIONAL | YES |
| `public.trips_2025` | HISTORICAL_ENRICHMENT | NO (for operations) |
| `public.trips_2026` | HISTORICAL_ENRICHMENT | NO (for operations) |

---

## 5. DRIVER 360 V2 ARCHITECTURE

Driver 360 already uses hybrid architecture:

**LIVE LAYER** (from Yango API):
- completed_orders_today → `raw_yango.orders_raw`
- supply_hours_today → `yango_api_client.get_supply_hours()`
- driver_identity → `raw_yango.driver_profiles_raw`
- work_status → `raw_yango.driver_profiles_raw`
- revenue_today → `raw_yango.transactions_raw`

**HISTORICAL LAYER** (from trips tables, via history service):
- best_week_12w → `yego_lima_growth_history_service`
- lifetime_trips → same
- first_seen → same
- lifecycle transitions → same

---

## 6. PIPELINE MIGRATION STATUS

The existing 15-step pipeline already uses Yango API:

| Step | Source | Status |
|------|--------|:---:|
| stabilize_driver_360_day | Yango API (supply-hours) | LIVE |
| build_driver_state_snapshot | driver_360_daily | DERIVED |
| build_program_eligibility | driver_state_snapshot | DERIVED |
| build_prioritized_opportunities | eligibility + history | DERIVED |
| build_assignment_queue | prioritized_opportunities | DERIVED |

---

## 7. SCHEDULER + GOVERNANCE

5-min scheduler (R2.9I.2) will:
1. Ingest Yango API via existing ingestion pipeline
2. Refresh materialized views (`refresh_raw_yango_mvs.py`)
3. Run refresh orchestrator (generate serving facts)
4. Update governance status

Governance panel shows source system: **YANGO_API_LIVE** when data is from API.

---

## 8. UI VISIBILITY

Governance panel now displays:
- Live source: Yango API
- Last ingestion timestamp
- Last operational data date
- Operability status

---

## 9. FILES CREATED

| Archivo | Proposito |
|---------|-----------|
| `docs/lima_growth/LG_YANGO_API_COVERAGE_MATRIX.md` | Yango API endpoint + field coverage |
| `docs/lima_growth/LG_DEPRECATED_OPERATIONAL_SOURCES.md` | Deprecation registry |
| `docs/lima_growth/LG_R2_9I_2A_0_YANGO_API_CANONICAL_LIVE_SOURCE.md` | Este documento |

---

## 10. QA

| Check | Resultado |
|-------|:---------:|
| Yango API client operational | YES (6 functions) |
| Raw tables exist (raw_yango.*) | YES (3 tables) |
| Materialized views operational | YES (5 MVs) |
| Driver 360 uses Yango API | YES (supply-hours) |
| trips_2026 deprecation documented | YES |
| Source roles defined | YES (LIVE vs HISTORICAL) |
| Backend compile | OK |
| Frontend build | PASS |

---

## 11. VEREDICTO

```
YANGO_API_LIVE IS CANONICAL OPERATIONAL SOURCE
```

**Evidence:**
- Yango API integration fully operational (4 endpoints, 1155-line client)
- Raw landing tables populated via ingestion pipeline
- 5 materialized views aggregate daily operational data
- Driver 360 already hybrid (live API + historical enrichment)
- trips_2025/2026 formally deprecated for operational use
- Source roles documented and enforced
