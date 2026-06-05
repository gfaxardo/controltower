# MONTH_TRIPS_MISMATCH — Root Cause Analysis

**Motor:** Omniview Hardening  
**Fecha:** 2026-06-02  
**Issue:** MONTH_TRIPS_MISMATCH — May 2026  
**Estado:** ROOT CAUSE IDENTIFIED — No correction yet  

---

## 1. EVIDENCE SUMMARY

### 1.1 Data by Source — May 2026

| Source | Trips_completed | Status |
|--------|----------------|--------|
| RAW `trips_2026` (Completado) | **822,042** | Has data |
| `month_fact` (aggregated) | **817,513** | Has data, refreshed Jun 1 |
| `day_fact` (aggregated) | **0 rows** | **NO DATA for May** |
| `week_fact` (aggregated) | **0 rows** | **NO DATA for May** |
| `v_real_business_slice_month_serving` | **817,513** | Matches month_fact |
| `mv_real_lob_day_v2` (LOB) | **NULL** | **NO DATA for May** |

### 1.2 Day Fact Date Range

| Month | Rows in day_fact | Positive trip rows |
|-------|-----------------|-------------------|
| Jan 2026 | 591 | 545 |
| Feb 2026 | 544 | 510 |
| Mar 2026 | 581 | 549 |
| Apr 2026 | 621 | 595 |
| **May 2026** | **0** | **0** |
| Jun 2026 | 21 | 21 |

### 1.3 Week Fact Date Range

| Metric | Value |
|--------|-------|
| Min week_start | 2024-12-30 |
| Max week_start | **2026-04-20** |
| Rows for May weeks | **0** |

### 1.4 Refresh Timestamps

| Month | month_fact refreshed_at |
|-------|------------------------|
| Jan | 2026-03-30 |
| Feb | 2026-03-30 |
| Mar | 2026-04-21 |
| Apr | 2026-06-01 |
| **May** | **2026-06-01 12:11** |

---

## 2. ROOT CAUSE

**day_fact and week_fact incremental refresh was NOT executed for May 2026.**

The month_fact load was run (June 1, 2026 at 12:11) — covering May 2026. This is confirmed by:
- `month_fact` has 23 rows with total 817,513 trips
- `refreshed_at = 2026-06-01 12:11:36`
- `loaded_at = 2026-06-01 12:11:36`

The day_fact and week_fact loads were NOT executed for the same date range:
- `day_fact` has **zero rows** for the entire month of May 2026
- `week_fact` max date is **2026-04-20** (S17) — weeks S18-S22 for May are missing

### 2.1 Why this causes the mismatch

1. **Omniview Matrix at monthly grain** → reads `FACT_MONTHLY` (serving view → month_fact) → **817,513 trips** (correct)
2. **Omniview Matrix at daily grain** → reads `FACT_DAILY` (day_fact) → **0 rows for May** → shows 0/MISSING
3. **Omniview Matrix at weekly grain** → reads `FACT_WEEKLY` (week_fact) → **0 rows for May weeks** → shows 0/MISSING

### 2.2 Comparison

| Grain | Source | Data? | Trips |
|-------|--------|-------|-------|
| Monthly | month_fact | YES | 817,513 |
| Weekly | week_fact | **NO** | 0 |
| Daily | day_fact | **NO** | 0 |

**This is the MONTH_TRIPS_MISMATCH: monthly view shows 817K trips, weekly/daily views show 0.**

### 2.3 Why month_fact was loaded but day_fact was not

The `business_slice_incremental_load.py` has separate code paths for each grain:
- `refresh_omniview_real_slice_incremental --grain month --start-date 2026-05-01` → loads month_fact (executed Jun 1)
- `refresh_omniview_real_slice_incremental --grain day --start-date 2026-05-01` → loads day_fact (NOT executed)
- `refresh_omniview_real_slice_incremental --grain week --start-date 2026-05-01` → loads week_fact (NOT executed)

### 2.4 Timeline

| Date | Event |
|------|-------|
| 2026-03-30 | month_fact loaded for Jan, Feb (old pipeline) |
| 2026-04-21 | month_fact loaded for Mar |
| 2026-05 (all month) | **No day_fact or week_fact refresh executed** |
| 2026-06-01 12:11 | month_fact loaded for May (817K trips) |
| 2026-06-01 13:36 | month_fact loaded for April |
| 2026-06-01+ | day_fact getting new data for June |

---

## 3. IMPACTED COMPONENTS

### 3.1 Source of Truth

SOT registry (`source_of_truth_registry.py:97-112`):
- `omniview_matrix` → primary: `ops.real_business_slice_month_fact` → **OK**
- `business_slice` → primary: `ops.real_business_slice_month_fact` → **OK**

Both domains point to month_fact, which has data. But the SOT does not cover the day/weekly fact tables directly — they are secondary sources populated by rollup.

### 3.2 Affected API Endpoints

| Endpoint | Grain | Source | Impact |
|----------|-------|--------|--------|
| `GET /ops/business-slice/monthly` | Monthly | Serving view → month_fact | **OK** (817K trips) |
| `GET /ops/business-slice/weekly` | Weekly | `FACT_WEEKLY` | **BROKEN** (0 trips for May) |
| `GET /ops/business-slice/daily` | Daily | `FACT_DAILY` | **BROKEN** (0 trips for May) |
| `GET /ops/business-slice/omniview` (daily) | Daily | `FACT_DAILY` | **BROKEN** (0 trips for May) |
| `GET /ops/business-slice/omniview` (weekly) | Weekly | `FACT_WEEKLY` | **BROKEN** (0 trips for May) |
| `GET /ops/business-slice/omniview-projection` (daily) | Daily | `FACT_DAILY` | **BROKEN** (0 trips for May) |

### 3.3 Affected UI

| View | Grain | Impact |
|------|-------|--------|
| Omniview Matrix — Mensual | Monthly | Shows revenue correctly |
| Omniview Matrix — Semanal | Weekly | Shows 0 trips/revenue for May weeks |
| Omniview Matrix — Diario | Daily | Shows 0 trips/revenue for May days |
| Omniview Reports | Any | Weekly/daily gaps for May |

### 3.4 Materialized Views

- `ops.mv_real_lob_day_v2` — also missing May data (built from day_fact rollup)
- `serving.omniview_projection_daily_fact` — also missing May data

---

## 4. FILTERS AND CONDITIONS

### 4.1 Completed Flag

The business_slice_incremental_load pipeline applies:
```sql
FILTER (WHERE completed_flag)
```
for all aggregation queries. This is correct and consistent.

### 4.2 Resolution Filters

The resolution CTE uses:
- Rule matching by park_id + tipo_servicio + works_terms
- DISTINCT ON (trip_id) to prevent duplicates
- UNMATCHED trips bucket for trips without rule match

These filters are correct and consistent between grains.

### 4.3 Scheduler

The APScheduler config in `backend/app/settings.py` controls refresh intervals. The refresh was triggered for month_fact (May data exists) but NOT for day_fact or week_fact.

---

## 5. REGRESSION ANALYSIS

### 5.1 Is this a regression?

**YES.** Previous months (Jan-Apr 2026) have day_fact data. May is the first month with a complete day_fact gap.

### 5.2 Commit that introduced the issue?

This is NOT a code regression — it's an **operations/refresh gap**. The code is correct; the incremental refresh script was simply not executed for the `day` and `week` grains for May 2026.

The month_fact load on June 1 proves the code works — it successfully loaded 817K trips for May. The day_fact and week_fact loads were either:
1. Not triggered by the scheduler
2. Executed but failed silently (unlikely — no error rows, just 0 rows)
3. Never called by any refresh process

### 5.3 Prior similar incident

The CF-H1 week_fact 43-day staleness incident (documented in `ai_current_phase.md:154-167`) was an identical root cause: week_fact refresh not executed for S18-S22. This is a recurrence of the same operational pattern.

---

## 6. VERIFICATION MATRIX

| Check | Status | Detail |
|-------|--------|--------|
| Source of Truth defined? | **PASS** | `omniview_matrix` → `month_fact` (canonical). daily/weekly via `day_fact`/`week_fact` |
| month_fact used? | **PASS** | Yes — data correct for May (817K) |
| v_resolved used? | N/A | Not the primary source for serving; fallback only |
| RAW trips source? | **PASS** | `trips_2026` has 822K completados for May |
| Filters applied? | **PASS** | completed_flag, resolution rules correct |
| Completed condition? | **PASS** | `condicion='Completado'` filter applied |
| Scheduler refresh? | **FAIL** | day_fact and week_fact NOT refreshed for May |
| MVs involved? | **FAIL** | `mv_real_lob_day_v2` also stale (depends on day_fact) |

---

## 7. DETERMINATION

| Question | Answer |
|----------|--------|
| Which value is correct? | **817,513 (month_fact)** — represents resolved, deduplicated business slice data. RAW = 822,042 (0.55% gap from DISTINCT ON dedup) |
| Why is raw = 0? | Raw is NOT 0. RAW = 822,042 completados. day_fact = 0 rows (refresh gap). month_fact = 817,513 (refreshed). |
| Is there a regression? | Yes — day_fact and week_fact are missing May 2026 data while month_fact has it |
| Which commit caused it? | No code commit. Operational gap: `refresh_omniview_real_slice_incremental --grain day --grain week` not executed for May |

---

## 8. CLASSIFICATION

| Layer | Status |
|-------|--------|
| Source (RAW) | **PASS** |
| Enriched Base | TIMEOUT (can't verify — expensive view) |
| month_fact | **PASS** |
| day_fact | **FAIL** — No data for May 2026 |
| week_fact | **FAIL** — No data for May 2026 |
| Serving View | **PASS** (matches month_fact) |
| LOB chain (mv) | **FAIL** — Stale, depends on day_fact |

**Overall: FAIL — day_fact and week_fact missing May 2026 data. month_fact is correct.**

---

## 9. RECOMMENDED CORRECTION

Execute the missing incremental refreshes:
```bash
python -m scripts.refresh_omniview_real_slice_incremental --start-date 2026-05-01 --end-date 2026-06-01 --grain day
python -m scripts.refresh_omniview_real_slice_incremental --start-date 2026-05-01 --end-date 2026-06-01 --grain week
```

Then refresh dependent materialized views and projection serving facts.
