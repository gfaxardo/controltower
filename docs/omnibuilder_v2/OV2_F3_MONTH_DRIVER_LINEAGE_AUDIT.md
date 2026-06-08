# OV2-F.3 — MONTH DRIVER LINEAGE AUDIT

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Freshness Chain
> **Status:** AUDIT COMPLETE — **FAIL (uses raw trips)**

---

## 1. CURRENT LINEAGE

month_fact active_drivers is built from **raw trips**, same as the old week_fact:

```
public.trips_2025 + public.trips_2026 (6.8M rows)
  → _bs_enriched_month (TEMP TABLE)
  → _RESOLVE_AND_AGG_MONTH_FROM_TEMP
  → COUNT(DISTINCT driver_id) FILTER (WHERE completed_flag)
  → INSERT INTO ops.real_business_slice_month_fact
```

## 2. EVIDENCE

| Fact | month_fact | week_fact (rebuilt) | Bridge |
|------|-----------|---------------------|--------|
| active_drivers | 65,283 | 16,814 | — |
| trips | 5,628,108 | 482,936 | 1,001,200 |

month_fact drivers (65K) ≠ week_fact drivers (16K). The discrepancy confirms month_fact was NOT rebuilt from week or bridge — it uses the old raw path.

## 3. CLASSIFICATION

**Type: FAIL — Uses raw trips**

month_fact should be rebuilt from:
1. `driver_day_slice_fact` for exact monthly distinct drivers, OR
2. Derived from week_fact if weeks within the month are complete

## 4. REMEDIATION

```sql
-- Rebuild month_fact from bridge
INSERT INTO month_fact_staging
SELECT date_trunc('month', activity_date)::date AS month,
       country, city, business_slice_name,
       COUNT(DISTINCT driver_id) FILTER (WHERE completed_trips > 0) AS active_drivers
FROM ops.driver_day_slice_fact
GROUP BY 1,2,3,4
```

## 5. VERDICT

**FAIL** — month_fact.active_drivers still comes from raw trips. Must be rebuilt from bridge. Backlog for F.3.

---

*End of Month Driver Lineage Audit*
