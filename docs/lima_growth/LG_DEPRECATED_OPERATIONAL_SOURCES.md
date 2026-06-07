# LG — Deprecated Operational Sources

**Date:** 2026-06-06
**Registry:** LG-R2.9I.2A.0

---

## DEPRECATED FOR OPERATIONAL FRESHNESS

### `public.trips_2025`
- **Deprecation date:** 2026-06-06
- **Reason:** Replaced by Yango Fleet API as canonical live source
- **Allowed use:** Historical enrichment ONLY (lifetime_trips, first_seen, best_week, best_month)
- **Prohibited use:** freshness checks, queue eligibility, daily action plans, governance operability
- **Replacement:** `raw_yango.orders_raw` + `raw_yango.mv_orders_day`

### `public.trips_2026`
- **Deprecation date:** 2026-06-06
- **Reason:** Same as trips_2025
- **Allowed use:** Historical enrichment ONLY (latest 12 months for historical context)
- **Prohibited use:** Same as trips_2025
- **Replacement:** Same as trips_2025

---

## SOURCE ROLE ASSIGNMENT

| Source | Role |
|--------|------|
| `raw_yango.*` (Yango Fleet API) | **LIVE_OPERATIONAL** |
| `public.trips_2025` | **HISTORICAL_ENRICHMENT** |
| `public.trips_2026` | **HISTORICAL_ENRICHMENT** |
| `growth.yango_lima_driver_360_daily` | DERIVED (LIVE + HISTORICAL) |

---

## CONFLICT RESOLUTION

> If Yango API data conflicts with trips_2025/trips_2026: **Yango API wins. Always.**

---

## RISKS AVOIDED

| Risk | Mitigation |
|------|------------|
| Using stale trips data for freshness | trips_2026 stops at 2026-06-05 in raw form, but operational freshness requires Yango API |
| Confusing historical enrichment with live status | Source role explicitly documented per table |
| Hardcoding trips as operational dependency | All operational services now reference Yango API paths |

---

## COMPLIANCE CHECKLIST

- [x] Yango API is live source for completed_orders
- [x] Yango API is live source for supply_hours
- [x] Yango API is live source for driver identity
- [x] trips_2026 is NOT used for freshness checks
- [x] trips_2026 is NOT used for queue eligibility
- [x] trips_2026 is NOT used for governance operability
- [x] trips_2026 is ONLY used for historical enrichment
- [x] Source roles documented and enforced
