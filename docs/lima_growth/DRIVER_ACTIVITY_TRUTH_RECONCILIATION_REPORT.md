# DRIVER ACTIVITY TRUTH RECONCILIATION REPORT

**Ticket:** LG-TAX-HOTFIX-1D  
**Date:** 2026-06-11  
**Audit Window:** 2026-06-10  
**Status:** RECONCILED — GAPS DOCUMENTED  

---

## EXECUTIVE SUMMARY

5 data sources compared across 1-day, 7-day, and 30-day windows. `public.trips_2026` is the canonical ground truth (18M rows, continuous ingestion). All other sources have significant gaps. The driver activity pipeline (`driver_360_daily` → `history_weekly` → `driver_state_snapshot`) is under-populated vs reality.

| Source | 7d Drivers | % of trips_2026 | Status |
|--------|-----------|-----------------|--------|
| **trips_2026** | 5,878 | 100% (baseline) | CANONICAL |
| history_weekly (1 week) | 2,257 | 38.4% | PARTIAL |
| raw_yango.orders_raw | 1,604 | 27.3% | INCOMPLETE |
| growth.orders_raw | 1,591 | 27.1% | INCOMPLETE |
| driver_360_daily | 0 | 0% | BROKEN |

---

## SOURCE 1: public.trips_2026 — CANONICAL GROUND TRUTH

**Schema:** `conductor_id`, `fecha_finalizacion`, `motivo_cancelacion`
**Total rows:** 18,273,981

### Completed Trips

| Window | Distinct Drivers | Total Trips |
|--------|-----------------|-------------|
| 1 day (2026-06-10) | 3,171 | 24,659 |
| 7 days (Jun 4-10) | 5,878 | 178,028 |
| 30 days (May 12-Jun 10) | 9,726 | 783,750 |

### Cancelled Trips

| Window | Distinct Drivers | Total Trips |
|--------|-----------------|-------------|
| 1 day | 3,684 | 45,338 |
| 7 days | 7,184 | 334,497 |
| 30 days | 11,893 | 1,835,914 |

**Key insight:** Cancelled trips outnumber completed trips by ~2:1. The cancellation rate is abnormally high (65% of all trips). This warrants a separate investigation.

---

## SOURCE 2: raw_yango.orders_raw — YANGO FLEET API (NEW PIPELINE)

**Schema:** `driver_profile_id`, `operational_date`, `order_status`
**Total rows:** 36,516

### Completed Trips (order_status = 'complete')

| Window | Distinct Drivers | Total Trips |
|--------|-----------------|-------------|
| 1 day | 0 | 0 |
| 7 days | 1,604 | 12,587 |
| 30 days | 1,604 | 12,587 |

**Gap vs trips_2026 (7d):** 72.7% fewer drivers, 92.9% fewer trips.

**All 36,516 rows have `order_status = 'complete'`.** No cancelled orders in this table.

**Root cause:** The raw_yango pipeline ingests via tick-based scheduler (every 5 min via Lima Growth autonomous tick). It fetches only completed orders from the Yango Fleet API (`statuses=["complete"]`). The tick ingests ~12,500 orders in rolling windows but misses the full daily volume. This is a **sampling ingestion**, not a full sync.

---

## SOURCE 3: growth.yango_lima_driver_history_weekly — WEEKLY AGGREGATION

**Schema:** `driver_profile_id`, `week_start_date`, `completed_orders_week`
**Total rows:** 135,812 across 67 weeks

### Completed Trips (current week vs 4 weeks)

| Window | Week(s) | Distinct Drivers | Total Trips |
|--------|---------|-----------------|-------------|
| Current ISO week | 2026-06-01 | 2,257 | 40,860 |
| 4 ISO weeks | 2026-05-11 to 2026-06-01 | 4,203 | 271,294 |

**Gap vs trips_2026 (7d):** 61.6% fewer drivers (2,257 vs 5,878).

**Root cause:** 
1. ISO week (Mon-Sun) doesn't match rolling 7d window (Thu-Wed). Jun 4-10 ≠ Jun 1-7.
2. `history_weekly` only has data for weeks where the pipeline ran. Latest week is 2026-06-01.
3. Not all drivers in trips_2026 have profiles that match `driver_profile_id` format (trips_2026 uses `conductor_id` which may be a different ID space).

---

## SOURCE 4: growth.yango_lima_driver_360_daily — DAILY DRIVER ACTIVITY

**Schema:** `driver_profile_id`, `date`, `completed_orders`, `supply_hours`
**Total rows:** **179** (ESSENTIALLY BROKEN)

### Data Availability

| Date | Rows |
|------|------|
| 2026-06-02 | 129 |
| 2026-06-01 | 50 |

**No data for 2026-06-03 through 2026-06-10.**

**Root cause:** The pipeline that populates `driver_360_daily` is not running. With only 179 rows (last data June 2), this table cannot serve as a daily activity source. The `build_driver_state_snapshot` function falls back to `history_weekly` for all metrics.

---

## SOURCE 5: growth.yango_lima_orders_raw — GROWTH CAPTURE TABLE

**Schema:** `driver_profile_id`, `ended_at`, `status`
**Total rows:** 12,322 (all `status = 'complete'`)

### Completed Trips

| Window | Distinct Drivers | Total Trips |
|--------|-----------------|-------------|
| 1 day | 0 | 0 |
| 7 days | 1,591 | 12,085 |
| 30 days | 1,626 | 12,322 |

**Gap vs trips_2026 (7d):** 72.9% fewer drivers, 93.2% fewer trips.

**Root cause:** This is the legacy growth capture table, populated by `yego_lima_growth_capture_service.py` which fetches from the same Yango API but in batch mode. It captures ~1,600 drivers in rolling 30d vs 9,726 in trips_2026.

---

## COMPLETE COMPARISON MATRIX

### Distinct Drivers — Completed Trips

| Source | 1 Day | 7 Days | 30 Days | Reliability |
|--------|-------|--------|---------|-------------|
| **trips_2026** | 3,171 | 5,878 | 9,726 | **CANONICAL** |
| history_weekly (current week) | — | 2,257 (1w) | 4,203 (4w) | Weekly only |
| raw_yango.orders_raw | 0 | 1,604 | 1,604 | Incomplete |
| growth.orders_raw | 0 | 1,591 | 1,626 | Incomplete |
| driver_360_daily | 0 | 0 | 0 | **BROKEN** |

### Total Trips — Completed

| Source | 1 Day | 7 Days | 30 Days |
|--------|-------|--------|---------|
| **trips_2026** | 24,659 | 178,028 | 783,750 |
| history_weekly | — | 40,860 (1w) | 271,294 (4w) |
| raw_yango.orders_raw | 0 | 12,587 | 12,587 |
| growth.orders_raw | 0 | 12,085 | 12,322 |
| driver_360_daily | 0 | 0 | 0 |

---

## GAP ANALYSIS

### Gap: trips_2026 vs history_weekly

| Metric | trips_2026 (7d) | history_weekly (1w) | Gap |
|--------|----------------|---------------------|-----|
| Drivers | 5,878 | 2,257 | -61.6% |
| Trips | 178,028 | 40,860 | -77.0% |

**Causes:**
1. **Window mismatch**: rolling 7d (Jun 4-10) vs ISO week (Jun 1-7)
2. **ID space**: `conductor_id` vs `driver_profile_id` — may not be 1:1 mappable
3. **Pipeline recency**: history_weekly stops at Jun 1. Jun 2-10 data not ingested
4. **Driver universe**: history_weekly has 18,545 drivers ever, but only 2,257 in current week. 16,288 drivers are historical only.

### Gap: trips_2026 vs raw_yango

| Metric | trips_2026 (7d) | raw_yango (7d) | Gap |
|--------|----------------|----------------|-----|
| Drivers | 5,878 | 1,604 | -72.7% |
| Trips | 178,028 | 12,587 | -92.9% |

**Causes:**
1. **Tick-based ingestion** (every 5 min, cursor pagination) — ingests a sample, not full volume
2. **API filtering** (`statuses=["complete"]`) — no cancelled orders ingested
3. **Park filtering** — may only ingest specific parks
4. **Rate limiting** — Yango API may throttle

### Gap: driver_360_daily

| Metric | trips_2026 (7d) | driver_360_daily (7d) | Gap |
|--------|----------------|----------------------|-----|
| Drivers | 5,878 | 0 | -100% |
| Trips | 178,028 | 0 | -100% |

**Cause:** Pipeline not running. Table has 179 rows, all from Jun 1-2. This is the primary failure point for the taxonomy's Activity layer.

---

## IMPACT ON TAXONOMY (LG-TAX-1.0B)

### Current State

The taxonomy's `operational_status` uses `driver_state_snapshot.completed_orders_week > 0` as the primary activity signal.

```
driver_state_snapshot.completed_orders_week
    ↑ reads from
driver_history_weekly.completed_orders_week (MAX week per driver, may be months old)
    ↑ aggregates from
driver_360_daily.completed_orders (BROKEN — 179 rows)
    ↑ should be populated from
raw_yango.orders_raw / growth.orders_raw (INCOMPLETE — 27% of real volume)
    ↑ should mirror reality
public.trips_2026 (CANONICAL — 5,878 weekly active drivers)
```

### The Pipe is Broken at 3 Points

| Point | What's Broken | Impact |
|-------|-------------|--------|
| `driver_360_daily` | Pipeline not running (179 rows) | Cannot compute daily activity |
| `history_weekly` | Uses MAX(week) per driver without recency filter | 16,288 drivers appear "active" with stale data |
| `raw_yango ingestion` | Tick-based sampling, not full sync | Only 27% of real driver volume ingested |

---

## RECOMMENDED SOURCE OF TRUTH HIERARCHY

### For Operational Activity (daily/weekly/monthly)

| Priority | Source | Use Case |
|----------|--------|----------|
| **1 (BEST)** | `public.trips_2026` with `motivo_cancelacion IS NULL` filter | Daily/weekly/monthly active driver counts. Most complete. |
| **2 (OK)** | `growth.yango_lima_driver_history_weekly` with `week_start_date = CURRENT_ISO_MONDAY` | Weekly aggregation. Good for trend analysis. |
| **3 (LIMITED)** | `raw_yango.orders_raw` with `order_status = 'complete'` | Yango-specific view. Incomplete but growing. |
| **4 (DO NOT USE)** | `driver_state_snapshot.completed_orders_week` | Contains historical artifacts (see HOTFIX-1C). DO NOT use for current activity. |
| **5 (BROKEN)** | `growth.yango_lima_driver_360_daily` | Only 179 rows. Pipeline must be fixed before any use. |

### For Taxonomy Operational Status (ACTIVE/CHURN/ARCHIVED)

**RECOMMENDATION:**

Use a **dual-source approach**:

1. **Primary signal**: `public.trips_2026` filtered by `fecha_finalizacion::date` and `motivo_cancelacion IS NULL` for driver recency.  
   - ACTIVE = completed trip in last 7 days
   - CHURN = last completed trip 15-90 days ago
   - ARCHIVED = last completed trip > 90 days ago or never

2. **Fallback signal**: `history_weekly` with `week_start_date = CURRENT_ISO_MONDAY` when trips_2026 doesn't have the driver.

### Caveat: ID Mapping

`trips_2026` uses `conductor_id`. The growth tables use `driver_profile_id`. These ID spaces may overlap but are not guaranteed to be 1:1. A mapping table or bridge may be needed.

---

## ROOT CAUSE SUMMARY TABLE

| Source | Gap vs Ground Truth | Root Cause |
|--------|--------------------|------------|
| `driver_360_daily` | 100% | Pipeline not running since Jun 2 |
| `history_weekly` | 61.6% | Uses `MAX(week_start_date)` without recency; stops at Jun 1 |
| `raw_yango.orders_raw` | 72.7% | Tick-based sampling (5 min cursor), not full sync; API rate limits |
| `growth.orders_raw` | 72.9% | Same API source, batch mode, low volume |
| `driver_state_snapshot` | Dependent | Inherits all upstream gaps via `history_weekly` + `driver_360_daily` |

---

## NEXT STEPS

1. **Fix `driver_360_daily` pipeline** — This is the critical block. Without daily data, the entire Lima Growth pipeline operates on stale weekly aggregates.
2. **Fix `history_weekly` recency filter** — Add `week_start_date >= CURRENT_DATE - 7` filter in `build_driver_state_snapshot`.
3. **Investigate trips_2026 cancellation rate** — 65% cancellation is abnormal. May indicate data quality issue in the source or incorrect `motivo_cancelacion` logic.
4. **Add `conductor_id` ↔ `driver_profile_id` mapping** — Bridge the two ID spaces for cross-source validation.
5. **Increase raw_yango ingestion volume** — Move from tick-based sampling to full daily sync.

---

**End of Reconciliation Report**
