# OV2-F.6B — MIGRATION READINESS

> **Date:** 2026-06-08
> **Status: BLOCKED**

## COULD YANGO REPLACE trips_2025/trips_2026?

**NO — BLOCKED for multiple reasons.**

## WHAT'S MISSING

| Requirement | CT (trips_2026) | Yango | Gap |
|-------------|-----------------|-------|-----|
| Full day coverage | 85K trips/day (all slices) | 1,000 orders (partial ingestion) | 85× |
| Trip-level detail | Individual trips | Individual orders | ✅ Available |
| Slice resolution | business_slice_mapping_rules | Only category (econom, comfort...) | No business slice mapping |
| Revenue at trip level | revenue_yego_final, revenue_yego_net | price field | Different calculation |
| Driver attribution | conductor_id | driver_profile_id | Different ID systems |
| Historical data | 2025 + 2026 full | 3 days only | No history |
| Automatic ingestion | ELT pipeline | Manual CLI only | No automation |
| Multiple parks | 22 parks | 1 park | 21 parks missing |
| Cancel reasons | motivo_cancelacion | Not fetched | Missing |
| Distance/time | distancia_km, duration | mileage | Partially available |

## MINIMUM REQUIREMENTS FOR MIGRATION

1. Automatic Yango ingestion scheduled daily
2. Full ingestion (unlimited pages) for all parks
3. Driver ID mapping table (conductor_id ↔ driver_profile_id)
4. Business slice resolution for Yango categories
5. Revenue reconciliation and normalization
6. Historical backfill (at least 3 months)
7. Performance validation (Yango API rate limits)

## VERDICT

**BLOCKED** — Yango cannot replace CT as the primary data source. It can serve as a reconciliation/validation source for the Lima main park with full ingestion enabled.

---

*End of Migration Readiness*
