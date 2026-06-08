# OV2-F.2C — WEEK FACT CURRENT LINEAGE

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Refresh Chain
> **Status:** AUDIT COMPLETE

---

## 1. CURRENT BUILD PATH

week_fact is built from **RAW TRIPS**, not day_fact.

```
public.trips_2025 + public.trips_2026 (6.8M rows)
  → UNION ALL + dedup (DISTINCT ON id)
  → LEFT JOIN dim.dim_park (park metadata)
  → LEFT JOIN public.drivers (works_terms)
  → ops.business_slice_mapping_rules (slice resolution)
  → _bs_enriched_month (TEMP TABLE)
  → date_trunc('week', trip_date)::date AS week_start
  → GROUP BY week_start, country, city, business_slice_name
  → INSERT INTO ops.real_business_slice_week_fact
```

## 2. WHY IT READS RAW TRIPS

The comment at `business_slice_incremental_load.py:816-817`:
> "DEPRECATED para active_drivers: SUM(daily distinct) != COUNT(DISTINCT driver_id) semanal."

The canonical path reads raw trips to compute `COUNT(DISTINCT driver_id)` at weekly grain. The day_fact rollup (`_WEEK_ROLLUP_FROM_DAY_FACT`) is deprecated because `SUM(day_fact.active_drivers)` ≠ true weekly distinct drivers.

## 3. VOLUME

| Metric | Value |
|--------|-------|
| Raw trips scanned per staging | **6,861,415** (2 months) |
| Enrichment time | ~100 seconds |
| Staging time (week) | >600s (exceeds timeout) |
| DB connections consumed | 8-12 direct connections |
| Result: week_fact rows (Lima) | 367 |

## 4. EXACT QUERY (week_start computation)

```sql
date_trunc('week', trip_date)::date AS week_start
```

PostgreSQL `date_trunc('week')` = Monday of the ISO week. This IS correct for ISO weeks.

## 5. PROBLEM SUMMARY

| Problem | Impact |
|---------|--------|
| Reads 6.8M raw trips per refresh | 600s+ timeout, DB saturation |
| Each refresh opens 8-12 new connections | `FATAL: too many clients` |
| day_fact already has the aggregated data | Unnecessary re-processing |
| Stale for 48 days | week-level matrix/shell broken |

---

*End of Current Lineage Audit*
