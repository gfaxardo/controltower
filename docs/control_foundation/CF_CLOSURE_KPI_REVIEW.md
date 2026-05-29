# CF Closure — KPI Review

## Fecha: 2026-05-29

---

## trips_completed

| Aspecto | Estado | Evidencia |
|---------|--------|-----------|
| Definición | `COUNT(*) FILTER (WHERE completed_flag)` | `business_slice_incremental_load.py:339` |
| Daily | CORRECT — COUNT per trip_date | Fact table day |
| Weekly | CORRECT — SUM of daily trips | Week rollup |
| Monthly | CORRECT — COUNT per month | Month fact |
| Freshness | `MAX(trip_date) WHERE trips_completed > 0` | Per-KPI freshness engine |
| Cross-grain | Additive: SUM(daily) = monthly, SUM(weekly) = monthly | Verified |
| Verdict | **PASS** | |

---

## active_drivers

| Aspecto | Estado | Evidencia |
|---------|--------|-----------|
| Definición | `COUNT(DISTINCT driver_id) FILTER (WHERE completed_flag)` | `business_slice_incremental_load.py:503` |
| Daily | CORRECT — COUNT DISTINCT per day | Day fact from enriched |
| Weekly | **FIXED (CF-H1)** — was SUM proxy, now COUNT DISTINCT from enriched | `_RESOLVE_AND_AGG_WEEK_FROM_TEMP:503` |
| Monthly | CORRECT — COUNT DISTINCT per month | Month fact from enriched |
| Freshness | `MAX(date) WHERE active_drivers > 0` | Per-KPI freshness engine |
| Cross-grain | Semi-additive. SUM(daily) ≠ monthly (expected for distinct) | Documented |
| Verdict | **PASS** | |

---

## revenue_yego_net

| Aspecto | Estado | Evidencia |
|---------|--------|-----------|
| Definición | `NULLIF(comision_empresa_asociada, 0)` → `ABS(...)` → `SUM(...)` | `enriched_base:133` → `incremental_load:968` → `fact:83` |
| Fuente RAW | `comision_empresa_asociada` en `public.trips_unified` | Migration 126 |
| Daily | CORRECT — SUM of revenue per day | `_RESOLVE_AND_AGG_DAY_FROM_TEMP:355` |
| Weekly | CORRECT — SUM of daily revenue via enriched | `_RESOLVE_AND_AGG_WEEK_FROM_TEMP:516` |
| Monthly | CORRECT — SUM of revenue per month | `_RESOLVE_AND_AGG_FROM_TEMP:83` |
| Fallback | Proxy: `ticket * commission_pct` when comision is NULL | `revenue_yego_final` |
| Freshness | `MAX(date) WHERE revenue_yego_net > 0` | Per-KPI freshness engine |
| GMV vs Revenue | Explicitamente separados. Revenue ≠ GMV. | Migration 010, audit scripts |
| Verdict | **PASS** | |

---

## avg_ticket

| Aspecto | Estado | Evidencia |
|---------|--------|-----------|
| Definición | `AVG(ticket) FILTER (WHERE completed AND ticket IS NOT NULL)` | `_RESOLVE_AND_AGG_DAY_FROM_TEMP:342` |
| Daily | CORRECT — AVG per day | Day fact |
| Weekly | CORRECT — Weighted AVG of daily AVGs | `SUM(ticket_sum)/SUM(ticket_count)` |
| Monthly | CORRECT — AVG per month | Month fact |
| Freshness | Inherits from trips | OK |
| Non-additive ratio | Recomputed per grain, not summed | Verified |
| Verdict | **PASS** | |

---

## trips_per_driver

| Aspecto | Estado | Evidencia |
|---------|--------|-----------|
| Definición | `trips_completed / active_drivers` (where drivers > 0) | `_RESOLVE_AND_AGG_DAY_FROM_TEMP:349-354` |
| Daily | CORRECT — daily trips / daily drivers | Day fact |
| Weekly | **CORRECT (via CF-H1 fix)** — weekly trips / weekly distinct drivers | Week fact from enriched |
| Monthly | CORRECT — monthly trips / monthly drivers | Month fact |
| Freshness | Derived from parent KPIs | OK |
| Verdict | **PASS** | |

---

## Resumen Final

| KPI | Daily | Weekly | Monthly | Freshness | Cross-Grain | Estado |
|-----|-------|--------|---------|-----------|-------------|--------|
| trips_completed | ✓ | ✓ | ✓ | ✓ | ✓ | PASS |
| active_drivers | ✓ | ✓ (fixed) | ✓ | ✓ | N/A (semi-additive) | PASS |
| revenue_yego_net | ✓ | ✓ | ✓ | ✓ | ✓ | PASS |
| avg_ticket | ✓ | ✓ | ✓ | ✓ | N/A (ratio) | PASS |
| trips_per_driver | ✓ | ✓ (fixed) | ✓ | ✓ | N/A (derived) | PASS |

**Ningún KPI crítico tiene incertidumbre material.**
