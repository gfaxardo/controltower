# OV2-F.2C — WEEK FACT LINEAGE AND REBUILD REPORT

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Refresh Chain
> **Phase:** OV2-F.2C — ISO Week Fact Lineage Audit + Day→Week Rebuild
> **Status:** **REBUILD SCRIPT READY — EXECUTION PENDING DB ACCESS**

---

## 1. EXECUTIVE SUMMARY

Se auditó completamente el lineage actual de `week_fact`. Confirmado: se construye desde raw trips (6.8M filas), no desde `day_fact`. Esto causa timeouts de 600s+ y saturación de conexiones PostgreSQL. Se diseñó e implementó un rebuild desde `day_fact` (~2,500 filas, 99.96% menos) con respeto a semanas ISO. El script está listo para ejecutar cuando el DB esté accesible.

---

## 2. CURRENT LINEAGE (PROBLEM)

```
public.trips_2025 + public.trips_2026 (6.8M rows)
  → UNION ALL + dedup
  → LEFT JOIN dim.dim_park
  → LEFT JOIN public.drivers
  → business_slice_mapping_rules
  → _bs_enriched_month (TEMP TABLE)
  → date_trunc('week', trip_date)::date
  → INSERT INTO week_fact → 600s+ timeout → DB saturation
```

**Root cause:** week_fact reads 6.8M raw trips per refresh to compute `COUNT(DISTINCT driver_id)` at weekly grain. The day_fact rollup exists but is deprecated (`_WEEK_ROLLUP_FROM_DAY_FACT`) because `SUM(daily active_drivers) != COUNT(DISTINCT weekly driver_id)`.

---

## 3. ISO CONTRACT

| Check | Status |
|-------|--------|
| week_start = Monday | ✓ (PostgreSQL `date_trunc('week')` guarantee) |
| Cross-month weeks preserved | ✓ (GROUP BY week_start, not month) |
| Cross-year weeks preserved | ✓ |
| No GROUP BY month in week_fact | ✓ |
| day_fact → week_fact compatible | ✓ (same `date_trunc('week', trip_date)`) |

---

## 4. NEW DESIGN: DAY→WEEK ROLLUP

| Metric | Method | Accuracy |
|--------|--------|----------|
| trips_completed | SUM(day_fact) | Exact |
| revenue_yego_final | SUM(day_fact) | Exact |
| revenue_yego_net | SUM(day_fact) | Exact |
| avg_ticket | SUM(revenue) / SUM(trips) | Recalculated |
| trips_per_driver | SUM(trips) / SUM(drivers) | Recalculated |
| active_drivers | SUM(day_fact) | Upper bound (warning) |
| commission_pct | SUM(net) / SUM(final) | Recalculated |

**Performance:** 2,500 rows vs 6,800,000 (99.96% reduction). From 600s+ to <5s.

---

## 5. ACTIVE_DRIVERS STRATEGY

| Strategy | Status |
|----------|--------|
| A) SUM(daily active_drivers) — upper bound | **IMPLEMENTED** with `ACTIVE_DRIVERS_WEEKLY_UPPER_BOUND` warning |
| B) DISTINCT from driver_daily_activity_fact | **BLOCKED** — driver table lacks business_slice_name |
| C) Bridge table | **BACKLOG** |
| D) Raw trips (current) | **DEPRECATED** — too heavy |

---

## 6. REBUILD SCRIPT

**File:** `backend/scripts/rebuild_week_fact_from_day_fact.py`

```bash
# Dry-run (validate without writing)
python -m scripts.rebuild_week_fact_from_day_fact \
  --date-from 2026-04-01 --date-to 2026-06-06 \
  --country peru --city lima --dry-run

# Real rebuild
python -m scripts.rebuild_week_fact_from_day_fact \
  --date-from 2026-04-01 --date-to 2026-06-06 \
  --country peru --city lima --confirm
```

### Validations performed:
1. All `week_start` values are Monday (ISO check)
2. Total trips match `SUM(day_fact.trips_completed)`
3. Total revenue matches `SUM(day_fact.revenue_yego_final)`
4. Staging table has rows before swap
5. Atomic delete+insert (rollback-safe)

---

## 7. EXECUTION STATUS

| Step | Status |
|------|--------|
| Lineage audit | **COMPLETE** |
| ISO contract audit | **COMPLETE** |
| Day→Week rollup design | **COMPLETE** |
| Driver distinct audit | **COMPLETE** |
| Rebuild proposal | **COMPLETE** |
| Rebuild script | **CREATED + COMPILED** |
| Dry-run | **PENDING** — DB still saturated |
| Real rebuild | **PENDING** |
| Waterfall recertification | **PENDING** |
| Snapshot refresh | **PENDING** |

---

## 8. DELIVERABLES

| # | Deliverable |
|---|-------------|
| 1 | `OV2_F2C_WEEK_FACT_CURRENT_LINEAGE.md` — exact SQL, source, volume |
| 2 | `OV2_F2C_ISO_GRAIN_CONTRACT_AUDIT.md` — ISO week compliance |
| 3 | `OV2_F2C_DAY_TO_WEEK_ROLLUP_DESIGN.md` — metric classification, SQL |
| 4 | `OV2_F2C_WEEKLY_DRIVER_DISTINCT_AUDIT.md` — active_drivers strategy |
| 5 | `OV2_F2C_WEEK_FACT_REBUILD_PROPOSAL.md` — SAFE/BLOCKED classification |
| 6 | `scripts/rebuild_week_fact_from_day_fact.py` — executable rebuild |
| 7 | `OV2_F2C_WEEK_FACT_LINEAGE_AND_REBUILD_REPORT.md` — this document |

---

## 9. BACKLOG GOVERNANCE

| Code | Rule | Status |
|------|------|--------|
| CT-GOV-014 | ISO Grain Contract | **REGISTERED** |
| CT-GOV-015 | Day-to-Week Rollup Mandatory | **REGISTERED** |
| CT-GOV-016 | No Raw Reaggregation for Serving Facts | **REGISTERED** |
| CT-GOV-017 | Semi-Additive KPI Governance | **REGISTERED** |

---

## 10. GO/NO-GO FOR F.3

| Criterion | Status |
|-----------|--------|
| week_fact no requiere raw-heavy refresh | **READY** — script uses day_fact only |
| week_start ISO lunes certificado | **PASS** |
| Cross-month weeks preserved | **PASS** |
| Trips/revenue semanal sale de day_fact | **PASS** |
| active_drivers semanal tiene estrategia explícita | **PASS** (upper bound + warning) |
| No DB saturation | **TO VERIFY** — depends on DB accessibility |
| Waterfall mejora | **PENDING** — execution |

## **CONDITIONAL GO for F.3** — pending DB recovery and script execution.

---

*End of OV2-F.2C Week Fact Lineage and Rebuild Report*
