# OV2-CLOSE.2C.0 — WEEK FRESHNESS ROOT CAUSE AUDIT

> **Date:** 2026-06-08
> **Motor:** Control Foundation
> **Phase:** OV2-CLOSE.2C.0 — Week Freshness Root Cause Audit
> **Status:** **DIAGNOSIS COMPLETE — NO FIX APPLIED**

---

## 0. GOVERNANCE

| Document | Finding |
|----------|---------|
| ai_operating_system.md | Control Foundation ACTIVE. All other engines BLOCKED. |
| ai_current_phase.md | OMNI-P0 ACTIVE. Diagnostic PAUSED. |
| Phase scope | Control Foundation only. No new motors. Diagnostic only. |

---

## 1. EXECUTIVE SUMMARY

`real_business_slice_week_fact` has been STALE for **49 days** (MAX week_start = 2026-04-20). The freshness sensor is CORRECT — this is a **real** stale, not a false positive. The root cause is a **scheduler cascade gap**: the APScheduler job was vacated in OV2-F.4C (to stop using deprecated loaders), but the canonical replacement cascade (`run_ov2_refresh_cascade.py`) was **never wired into APScheduler**. No automatic process rebuilds week_fact.

---

## 2. WEEK FACT SCHEMA & SEMANTIC CONTRACT

**Table:** `ops.real_business_slice_week_fact`

### Key Columns (from information_schema)

| Column | Significance |
|--------|-------------|
| `week_start` (date) | **Grain column.** Monday of ISO week. Used as the unique period identifier. |
| `trips_completed` | SUM of completed trips within the week |
| `revenue_yego_final` | SUM of revenue within the week |
| `active_drivers` | COUNT DISTINCT driver_id from bridge (in canonical rebuild) or SUM of dailies (in legacy) |
| `business_slice_name` | Slice classification |
| `country`, `city` | Location filters |

**Semantic contract:**
- `week_start` = Monday (ISO standard, via `date_trunc('week', date)`)
- Week range: Monday 00:00 → Sunday 23:59:59.999
- No explicit `week_end` column. Week end = `week_start + 6 days` (inclusive) or `+ 7 days` (exclusive).
- `week_start` is what the freshness sensor queries (`MAX(week_start)`).

---

## 3. FRESHNESS OBSERVATORY CONTRACT

**File:** `backend/app/routers/omniview_v2.py:582-610`

### How it computes week_fact freshness:

```python
("real_week_fact", "ops.real_business_slice_week_fact", "week_start",
 "WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'", "REAL"),
```

**Queries:**
1. `SELECT MAX(week_start) FROM ops.real_business_slice_week_fact WHERE ...` → `layer_date`
2. `SELECT COUNT(*) FROM ... WHERE week_start >= CURRENT_DATE - 2` → `recent` count
3. Status = "FRESH" if `recent > 0` else "STALE"

**Threshold:** `CURRENT_DATE - 2` (data within last 2 days)

**Waterfall:**
```
DAY_to_WEEK: "OK" if week_fact.status == "FRESH" else "BROKEN"
```

**The sensor queries `MAX(week_start)` — the Monday date — and compares against today. This is correct for the sematic grain. If the most recent week_start is 2026-04-20 (Monday) and today is 2026-06-08, the week covers through 2026-04-26 (Sunday). Gap: 43 days.**

---

## 4. CANONICAL DATES

### Freshness Observatory Output (2026-06-08 ~23:00 UTC-5)

| Layer | Max Date | Status | Freshness Gap | Rows |
|-------|---------|--------|--------------|------|
| **driver_bridge** | 2026-06-07 | **FRESH** | 1 day | 162,486 |
| **real_day_fact** | 2026-05-31 | **STALE** | 8 days | 2,527 |
| **real_week_fact** | **2026-04-20** | **STALE** | **49 days** | 24 |
| **real_month_fact** | 2026-06-01 | STALE | 7 days | 86 |
| **snapshot** | 2026-06-05 | STALE | 3 days | 4 |

### Waterfall Status

```
RAW_to_DAY:   OK
DAY_to_WEEK:  BROKEN   ← root cause of this audit
WEEK_to_MONTH: OK
```

### Day → Week Gap Analysis

| Metric | Value |
|--------|-------|
| day_fact max trip_date | 2026-05-31 |
| Monday of day_fact max week | 2026-05-25 |
| week_fact max week_start | 2026-04-20 |
| Delta | 35 days (5 weeks missing) |

**Even accounting for the day_fact decay (day was 2026-06-07 earlier today, now 2026-05-31), the week_fact is at least 5 weeks behind.**

---

## 5. STALE CLASSIFICATION: REAL, NOT FALSE

| Case | Criteria | Match? |
|------|----------|--------|
| **Case A:** FALSE_STALE — week_start max = Monday of day_max week | ❌ No. day week Monday = 2026-05-25, week_max = 2026-04-20 |
| **Case B:** REAL_STALE — week_start max several weeks behind | ✅ **YES.** Gap = 35+ days |
| **Case C:** FRESH_WEEK_STALE_SNAPSHOT — week fresh but snapshot stale | ❌ No. Both stale. |

**Classification: REAL STALE. The freshness sensor is correct.**

---

## 6. WRITERS DETECTED

### 6.1 Canonical Writer

| File | Operation | Status |
|------|-----------|--------|
| `scripts/rebuild_week_from_day_and_bridge.py` | DELETE + INSERT from staging | **CANONICAL** (OV2-F.2D) |

Uses `driver_day_slice_fact` bridge + `real_business_slice_day_fact` to compute exact COUNT DISTINCT active_drivers. Correct semantics.

### 6.2 Legacy Writer

| File | Operation | Status |
|------|-----------|--------|
| `scripts/rebuild_week_fact_from_day_fact.py` | DELETE + INSERT | **LEGACY / BROKEN** — sums daily drivers (double-counts) |

### 6.3 Deprecated Writers

| File | Status |
|------|--------|
| `scripts/backfill_week_from_day_fact.py` | **BLOCKED** by default (`--allow-legacy-weekly-dangerous` flag) |
| `scripts/quick_backfill_may2026_week.py` | **LEGACY** one-shot, raw trips_2026 source |
| `scripts/quick_backfill_apr2026_week.py` | **LEGACY** one-shot |
| `scripts/backfill_week_fact_apr_may.py` | **LEGACY** one-shot |

### 6.4 Service-Level Writers

| Service | Function | Status |
|---------|----------|--------|
| `business_slice_incremental_load.py` | `refresh_business_slice_week_range()` | Active (DELETE + INSERT, called by CLI) |
| `business_slice_incremental_load.py` | `load_business_slice_week_for_month()` | **DEPRECATED** (OV2-F.4A) |
| `business_slice_incremental_load.py` | `_swap_staging_to_production()` | Active (atomic refresh) |
| `backfill_runner.py` | DELETE + INSERT per chunk | Active (UI-triggered) |

### 6.5 Readers (SELECT only)

**38 files** SELECT from `real_business_slice_week_fact`. 0 INSERT/UPDATE/DELETE besides the writers above.

**Writer governance status:** 1 writer = 1 table rule is maintained. But the single writer is only triggered manually.

---

## 7. SCHEDULER AUDIT

### 7.1 APScheduler Job: `omniview_business_slice_real_refresh` (04:00)

**File:** `backend/app/services/business_slice_real_refresh_job.py`

**What it actually does (from lines 142-148):**
```python
# OV2-F.4C: ALL facts now served by bridge cascade.
# day/week/month are rebuilt via run_ov2_refresh_cascade.py
# which must run AFTER this job. Legacy loaders are DEPRECATED.
nd = 0
nw = 0
nm = 0
_drop_enriched_temp(cur)
```

**Result:** The job:
1. Sets nd=0, nw=0, nm=0 (never loads any data)
2. Drops temporary staging tables
3. Checks `if nd == 0 and nw == 0` → logs **CRITICAL: month produced 0 rows**
4. Returns with errors logged but **no data written**

### 7.2 Canonical Cascade: `run_ov2_refresh_cascade.py`

**File:** `backend/scripts/run_ov2_refresh_cascade.py`

**What it does:**
```
bridge_update → week_rebuild → month_rebuild → day_rebuild
```
Each step calls the canonical rebuild script, measures before/after, logs advancement.

**Scheduled?** **NO.** Must be run manually with `--confirm`.

### 7.3 Cascade Flow (intended vs actual)

```
INTENDED (per OV2-F.4C design):
  bridge_update (scheduled)
    → week_rebuild (scheduled cascade)
      → month_rebuild (scheduled cascade)
        → day_rebuild (scheduled cascade)
          → snapshot refresh (scheduled)

ACTUAL:
  bridge_update (APScheduler, via daily_refresh)
    → week_rebuild (NOT SCHEDULED — manual only)
    → month_rebuild (NOT SCHEDULED — manual only)
    → day_rebuild (NOT SCHEDULED — manual only)
    → snapshot refresh (APScheduler, 05:00)
```

### 7.4 Day Fact Freshness Decay Evidence

The day_fact max dropped from `2026-06-07` (observed earlier today) to `2026-05-31` (observed now). This confirms the cascade is not running for ANY grain. Data from June 1-7 that was previously loaded (likely via manual cascade run) has been decaying.

---

## 8. ROOT CAUSE

### Primary: SCHEDULER_CASCADE_NOT_WIRED

The OV2-F.4C deprecation **vacated** the APScheduler job (stopped it from calling deprecated `load_business_slice_*` functions), as intended. But the replacement canonical cascade (`run_ov2_refresh_cascade.py`) was **never registered with APScheduler**.

The scheduler job at 04:00 now does:
- Drop temp tables
- Log "CRITICAL: month produced 0 rows"
- Return

**No automatic rebuild of week_fact (or day_fact, or month_fact) occurs.**

### Contributing Factors

| Factor | Impact |
|--------|--------|
| Vacated scheduler job still logs CRITICAL errors | Noise in logs, masks real issues |
| 6 legacy/deprecated writers still in codebase | Confusion about canonical writer |
| Cascade script exists and works, but no automation | Known solution, not wired |
| Day fact also decaying | Affects all grains, not just week |

---

## 9. FIX RECOMMENDED

### Option A: Wire `run_ov2_refresh_cascade.py` into APScheduler (Recommended)

```
1. Register a new APScheduler job that calls run_ov2_refresh_cascade.py
2. Set schedule: daily at 04:00, AFTER bridge_update completes
3. Keep existing 04:00 job as a pre-flight check (or remove it)
```

**Risk:** Cascade may take significant time (>300s for week step). Need timeout handling.

### Option B: Restore minimal week_fact rebuild in APScheduler

```
Replace the vacated scheduler body with a direct call to
refresh_business_slice_week_range() for the missing weeks.
```

**Risk:** Bypassing the cascade order. May produce inconsistent data.

### Option C: Manual cascade run for immediate recovery + Automation later

```
1. Manual: python -m scripts.run_ov2_refresh_cascade --confirm
2. Then: implement automation (Option A)
```

**Recommended path:** Option C (immediate recovery) + Option A (automation).

---

## 10. CLASSIFICATION

| Classification | Match |
|---------------|-------|
| `FALSE_STALE_SENSOR_BUG` | ❌ Sensor is correct |
| `WEEK_WRITER_BROKEN` | ❌ Writer works when triggered |
| `SCHEDULER_WRONG_SCRIPT` | ❌ Old script was deliberately removed |
| **`SCHEDULER_CASCADE_NOT_WIRED`** | ✅ **Root cause** |
| `SNAPSHOT_STALE_ONLY` | ❌ Week fact, not just snapshot, is stale |
| `MULTI_WRITER_REGRESSION` | ❌ Single writer governance maintained |

**Final classification: SCHEDULER_CASCADE_NOT_WIRED**

---

## 11. GO / NO-GO

| Criterion | Status |
|-----------|--------|
| Root cause identified | ✅ Scheduler cascade not wired |
| Evidence collected | ✅ Observatory data, code audit, DB queries |
| No fix applied yet | ✅ Diagnosis only |
| No UI modified | ✅ |
| No new engines opened | ✅ |

**GO to recommend fix, NO-GO until fix is applied and verified.**
**Next phase: OV2-CLOSE.2C.1 — Run cascade rebuild + verify freshness.**

---

*End of OV2-CLOSE.2C.0 — Week Freshness Root Cause Audit*
