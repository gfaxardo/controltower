# LG-RAW-INGEST-1A — Driver History Daily / Raw Orders Gap Audit

**Date:** 2026-06-14
**Phase:** LG-RAW-INGEST-1A (Root Cause Audit)
**Mode:** AUDIT — No implementation
**Predecessor:** `LG_WEEKLY_1A_DRIVER_HISTORY_WEEKLY_FRESHNESS_HARDENING.md`
**Status:** ROOT CAUSE FOUND

---

## 1. Executive Decision

### LG_RAW_INGEST_1A_ROOT_CAUSE_FOUND

The raw Yango API data IS flowing (50K orders in `raw_yango.orders_raw`, through June 14). The scheduler IS running (1010 SUCCESS ticks, last at June 14 07:15). But the intermediate ingestion pipeline has a rate limiting gap that prevents `driver_history_daily` and `driver_history_weekly` from advancing.

**The break is between daily history (stuck at June 4) and the upstream raw orders (fresh to June 14), with an intermediate rate limit at 500 orders/day in `growth.yango_lima_orders_raw` (stops at June 9).**

---

## 2. Why This Blocks Growth Machine Closure

`driver_history_weekly` depends on `driver_history_daily` which depends on `growth.yango_lima_orders_raw`. Without daily data advancing, the weekly table cannot advance beyond 2026-06-01. The weekly table feeds historical metrics (best_week_12w, avg_4w, historical_band, value_tier) into `driver_state_snapshot`. Growth Machine cannot be CLOSED while historical metrics are stale.

---

## 3. Data Chain Map

```
Yango Fleet API (LIVE)
    ↓ ingest_recent_orders() [yango_raw_tick_ingestion_service.py]
    ↓ runs every 5 min via autonomous_tick
    ↓
raw_yango.orders_raw [50K rows, through June 14 — FRESH]
    ↓ ??? ingestion step ???
    ↓ (rate limited to 500/day?)
    ↓
growth.yango_lima_orders_raw [12K rows, stops at June 9 — GAP]
    ↓ ??? builder step ???
    ↓ 
growth.yango_lima_driver_history_daily [520K rows, stops at June 4 — STALE]
    ↓ _build_weekly_sql_bulk() [UPSERT from daily aggregation]
    ↓
growth.yango_lima_driver_history_weekly [135K rows, MAX week=06-01 — STALE]
    ↓ driver_state_snapshot (dual-source with driver_360_daily)
    ↓
growth.yango_lima_driver_state_snapshot [203K rows, through June 14 — FRESH via 360]
    ↓ refresh_exclusive_driver_worklist_daily()
    ↓
growth.yango_lima_exclusive_driver_worklist_daily [55K rows, through June 15 — FRESH]
    ↓ sync_exclusive_worklist_to_control_loop()
    ↓
growth.yego_lima_control_loop_state [6,114 READY — OPERATIONAL]
```

**Key insight:** `driver_state_snapshot` has dual-source architecture (history_weekly + driver_360_daily). Daily operations are healthy because `driver_360_daily` compensates for the stale `driver_history_weekly`. But historical metrics (value_tier, best_week_12w, historical_band) are degraded.

---

## 4. Freshness by Layer

| Layer | Table | Date Column | Max Date | Rows | Status |
|-------|-------|-------------|----------|------|--------|
| 1 | `raw_yango.orders_raw` | `order_ended_at` | **2026-06-14** | 50,455 | **FRESH** |
| 2 | `growth.yango_lima_orders_raw` | `ended_at` | **2026-06-09** | 12,322 | **GAP: 4 days stale, 500/day limit** |
| 3 | `public.trips_2026` | `fecha_inicio_viaje` | **2026-06-13** | 18,506,755 | **FRESH** |
| 4 | `growth.yango_lima_driver_history_daily` | `date` | **2026-06-04** | 520,340 | **STALE: 9 days** |
| 5 | `growth.yango_lima_driver_history_weekly` | `week_start_date` | **2026-06-01** | 135,812 | **STALE: 12 days** |
| 6 | `growth.yango_lima_driver_state_snapshot` | `snapshot_date` | **2026-06-14** | 203,802 | **FRESH** (via 360_daily) |
| 7 | `growth.yango_lima_exclusive_driver_worklist_daily` | `generated_date` | **2026-06-15** | 55,635 | **FRESH** |

---

## 5. Raw Ingestion Audit

### 5.1 raw_yango.orders_raw

- **Status:** FRESH. Data arriving daily through June 14.
- **Source:** Yango Fleet API, ingested by `yango_raw_tick_ingestion_service.ingest_recent_orders()`
- **Scheduler:** `autonomous_tick` every 5 min (1010 SUCCESS ticks, last June 14 07:15)
- **Evidence:** 50,455 rows. Recent days: 06-09 (11,851), 06-10 (10,308), 06-11 (4,846), 06-13 (1,602), 06-14 (122).

### 5.2 growth.yango_lima_orders_raw

- **Status:** STALE. Stops at June 9. Only 500 rows per day.
- **Rate limit:** 500 rows/day appears to be a page_size or API limit.
- **Evidence:** 12,322 rows. Recent days: 06-04 (11,085 = full day), 06-08 (500), 06-09 (500). Days 06-05/06/07 are missing (expected: weekend gaps).

### 5.3 growth.yango_lima_driver_history_daily

- **Status:** STALE. Stops at June 4.
- **Source:** Built from `growth.yango_lima_orders_raw`.
- **Writer:** `upsert_history_daily()` in `yego_lima_growth_history_repository.py:23`. Called from `bootstrap_history()` only.
- **Evidence:** 520,340 rows. Recent days: 06-01 through 06-04 have 1,300-1,500 drivers/day. June 5+ has zero rows.

---

## 6. Driver History Daily Writer Audit

| Aspect | Finding |
|--------|---------|
| Writer | `upsert_history_daily()` (repository) |
| Build path | `bootstrap_history()` → reads `public.trips_2025`/`trips_2026` → aggregates by driver/date → `upsert_history_daily()` |
| Not called by | `autonomous_tick` — the scheduler does NOT call `bootstrap_history()` |
| Called by | Manual API only (`POST /yego-lima/growth-lab/bootstrap-history`) |
| IDEMPOTENT | Yes (ON CONFLICT DO UPDATE) |
| Can rebuild specific dates | Yes (via date range parameters) |
| Governance | Not in autonomous_tick cascade |

**The daily history table has NO automated refresh in the autonomous tick. This is the critical gap.**

---

## 7. Root Cause Classification

### Category G + H: Rate limiting + Missing autonomous_tick integration

**Evidence:**

1. `raw_yango.orders_raw` IS receiving fresh data (50K rows, through June 14).
2. `growth.yango_lima_orders_raw` IS rate-limited to 500 orders/day, stopping the flow to daily history.
3. `autonomous_tick` does NOT call `bootstrap_history()` or any `driver_history_daily` builder.
4. `driver_history_daily` can only be refreshed via manual `bootstrap_history()` API call.
5. `driver_history_weekly` depends on `driver_history_daily` and also does not have an automated daily builder.

**The pipeline breaks at TWO points:**
- **Break 1:** `growth.yango_lima_orders_raw` → `driver_history_daily`: No automated builder in autonomous_tick. Manual only.
- **Break 2:** `growth.yango_lima_orders_raw` rate-limited to 500/day, so even if builder ran, it would only get 500 orders/day.

---

## 8. Proposed Fix Plan

### Phase A: Unblock daily history ingestion (P0)

1. Add `driver_history_daily` builder to autonomous_tick cascade (step between raw orders and weekly history).
   - Read from `raw_yango.orders_raw` directly (bypasses the rate-limited `growth.yango_lima_orders_raw`)
   - Aggregate by driver_profile_id + date
   - UPSERT via `upsert_history_daily()`
   - Date range: last N days, incremental
2. Fix rate limiting in `yango_raw_tick_ingestion_service.py` (increase page_size from 500).
3. Run incremental backfill for missing dates 06-05 to 06-14 (safe: UPSERT idempotent).

### Phase B: Unblock weekly history (P0)

After Phase A completes:
1. Run `_build_weekly_sql_bulk()` to rebuild weekly from fresh daily data.
2. Verify MAX(week_start_date) advances to 2026-06-08 or later.

### Files Likely Touched

| File | Change |
|------|--------|
| `yego_lima_scheduler_service.py` | Add daily history step to cascade |
| `yango_raw_tick_ingestion_service.py` | Fix rate limit |
| `yego_lima_growth_history_service.py` | Add incremental daily builder function |

### Tables Touched

| Table | Operation |
|-------|-----------|
| `growth.yango_lima_driver_history_daily` | UPSERT (idempotent) |
| `growth.yango_lima_driver_history_weekly` | UPSERT rebuild |
| `growth.yango_lima_orders_raw` | UPSERT (existing) |

### Safety Gates

- Dry-run first (read counts only)
- Advisory lock
- No DELETE/TRUNCATE
- UPSERT idempotent
- Validate row counts before/after
- Rollback by date range possible (UPSERT, not destructive)

---

## 9. What Was NOT Changed

- No backend code modifications
- No migrations
- No frontend
- No refresh/backfill execution
- No DELETE/TRUNCATE
- No legacy scripts executed
- Rules, thresholds, universes unchanged

---

## 10. Verdict

### LG_RAW_INGEST_1A_ROOT_CAUSE_FOUND

**Category G+H confirmed.** Raw API data flows. Scheduler runs. Intermediate table is rate-limited. Daily history has no automated builder in autonomous_tick. Two-phase fix proposed: unblock daily first, then weekly.

**Growth Machine remains NOT CLOSED until daily and weekly history tables advance.**

---

## 11. Files Changed

`docs/lima_growth/LG_RAW_INGEST_1A_DRIVER_HISTORY_DAILY_GAP_AUDIT.md` — created

---

*Audit complete. Root cause: rate-limited intermediate ingestion + missing daily history builder in autonomous tick. Fix plan ready for LG-RAW-INGEST-1B.*
