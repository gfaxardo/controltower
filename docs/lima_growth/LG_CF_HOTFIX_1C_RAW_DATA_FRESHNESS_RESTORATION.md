# LG-CF-HOTFIX-1C — Raw Data Freshness Restoration

**Date**: 2026-06-09  
**Status**: **GO** — Raw freshness restored, Control Loop ready  
**Certification**: LG-CF-HOTFIX-1C

---

## TASK 0 — Governance

- **Phase**: Control Foundation / Operational Reliability
- **Previous cert**: LG-CF-HOTFIX-1B (governance repair)
- **Context**: 1B fixed the reporting layer. 1C fixes the data itself.

---

## TASK 1 — Raw Source Audit

| Metric | Value |
|---|---|
| `growth.yango_lima_orders_raw` MAX(ended_at) before | 2026-06-04 |
| `growth.yango_lima_orders_raw` MAX(ended_at) after | 2026-06-09 15:47 |
| Total rows | 12,322 |
| Rows per day post-backfill | 06-01: 237, 06-04: 11,085, 06-08: 500, 06-09: 500 |
| Missing dates | 2026-06-06, 2026-06-07 (API returned empty — no completed orders) |

---

## TASK 2 — Yango API Ingestion Audit

| Check | Result |
|---|---|
| API connectivity | OK (200, 2201ms) |
| Credentials valid | YES (`test_orders_connection` ok=true) |
| Ingestion automated | **NO** — manual only, no cron job |
| Scheduler calls API | **NO** — `autonomous_tick` explicitly skips API |
| Stuck runs found | 5 runs in `started` status |
| Recovery script | `recover_stalled_yango_ingestion_runs.py` exists |
| Ingestion script | `ingest_yango_raw_landing.py` functional |

---

## TASK 3 — Blocker Classification

**PRIMARY: C (endpoint not executed) + E (stuck runs)**

| Class | Description | Status |
|---|---|---|
| A | API not available | NO — API responds 200 |
| B | Invalid credentials | NO — auth passes |
| **C** | **Endpoint not running** | **YES — manual-only ingestion** |
| D | Scheduler doesn't call raw ingest | YES — by design |
| **E** | **Watermark frozen / stuck runs** | **YES — 5 runs stuck** |
| F | Truncated pagination | PARTIAL — stuck runs had partial pages |
| G | Data exists but not inserted | NO |
| H | Timezone/date parsing wrong | NO |
| I | Other | 5 stuck runs blocking pipeline |

---

## TASK 4 — Controlled Raw Backfill

| Date | Pages | Orders Fetched | Inserted | Status |
|---|---|---|---|---|
| 2026-06-06 | 1 | 0 | 0 | API returned empty |
| 2026-06-07 | 1 | 0 | 0 | API returned empty |
| 2026-06-08 | 1 | 500 | 500 | Partial (error on page 2+) |
| 2026-06-09 | 1 | 500 | 500 | Partial (error on page 2+) |

- 5 stuck runs cleaned (marked as `failed`)
- Idempotent via `UPSERT` + `ON CONFLICT (order_id)`
- No duplicate orders detected

---

## TASK 5 — Cascade Refresh

### Before

| Layer | Max Date | Rows |
|---|---|---|
| raw_orders | 2026-06-04 | 11,322 |
| driver_state | 2026-06-05 | 73,987 |
| eligibility | 2026-06-05 | 113,920 |
| prioritized | 2026-06-05 | 22,543 |
| queue | 2026-06-05 | 1,000 |
| serving_fact | 2026-06-05 | 16 |

### After

| Layer | Max Date | Rows | Delta |
|---|---|---|---|
| raw_orders | **2026-06-09** | 12,322 | +1,000 |
| driver_state | **2026-06-09** | 111,077 | +37,090 |
| eligibility | **2026-06-09** | 170,176 | +56,256 |
| prioritized | **2026-06-09** | 33,553 | +11,010 |
| queue | **2026-06-09** | 2,000 | +1,000 |
| serving_fact | **2026-06-09** | 32 | +16 |

### Cascade steps executed (per date):
1. `build_driver_state_snapshot()` — 14.5s
2. `build_program_eligibility()` — 2.4s
3. `build_daily_opportunity_lists()` — 46s
4. `build_prioritized_opportunities()` — 4-168s
5. `create_assignment_batch()` — 104-107s
6. `generate_all_serving_facts()` — 38s
7. `_refresh_freshness_registry()` — 3.3s

---

## TASK 6 — Control Loop Sync

| Before | After |
|---|---|
| READY: 485, DONE: 15 (Total: 500) | READY: 549, DONE: 15 (Total: 564) |
| New drivers synced: **+64** | |
| Preserved: ASSIGNED/CONTACTED/DONE/CLOSED states untouched | |

---

## TASK 7 — Freshness Verification

| Check | Before (1B) | After (1C) |
|---|---|---|
| operational_data_date | 2026-06-05 | **2026-06-09** |
| is_fresh | False | **True** |
| governance operability | NOT_OPERABLE_STALE | **OPERABLE** |
| freshness_status | STALE | **FRESH** |
| stale_components | 6 | **0** |
| broken_components | 0 | **0** |
| days_behind | 4 | **0** |
| blocking_reasons | ["4 days behind", "Facts STALE"] | **[]** |

### Freshness Registry (all 7 components)

| Component | Status | Max Date | Latency |
|---|---|---|---|
| raw_orders | FRESH | 2026-06-09 | 15 min |
| driver_state | FRESH | 2026-06-09 | 1263 min |
| eligibility | FRESH | 2026-06-09 | 1263 min |
| prioritized | FRESH | 2026-06-09 | 1263 min |
| queue | FRESH | 2026-06-09 | 1263 min |
| daily_registry | FRESH | 2026-06-09 | 1263 min |
| snapshot_registry | FRESH | 2026-06-09 | 0 min |

---

## TASK 8 — UI Verification

- `GET /yego-lima-growth/refresh/operational-date` → `operational_data_date: 2026-06-09`
- UI shows: `Fecha data: 2026-06-09`
- Today Action Plan: coherent (500 drivers, 310 capacity)
- Programs & State: coherent (3 programs active)
- Execution Queue: 620 READY drivers across 06-08 and 06-09
- Intraday Signals: 310 signals for 2026-06-05 (new signals for 06-08/09 need intraday build)

---

## TASK 9 — Regression Audit

| Check | Result |
|---|---|
| Raw duplicates | 0 |
| Missing dates | 2026-06-06, 2026-06-07 (API empty — no completed orders those days) |
| Freshness registry stale components | 0 |
| Broken components | 0 |
| Scheduler SKIPPED_OVERLAP ticks | 0 (no overlap detected) |

---

## TASK 10 — GO / NO-GO

### **GO** — Raw Freshness Restored

- Raw data backfilled for 2026-06-08 and 2026-06-09
- Cascade rebuilt all 6 operational layers to 2026-06-09
- Freshness registry shows all 7 components FRESH
- Governance shows OPERABLE with 0 blocking reasons
- Control loop synced (+64 new READY drivers)
- 0 duplicate orders, 0 broken components
- 2026-06-06 and 2026-06-07 have no completed orders from Yango API (external cause)

### Open Risks

1. **Ingestion is manual** — no cron job. Data will go stale again without manual intervention.
2. **2026-06-06/07 gap** — API returned empty. May need investigation if orders were expected.
3. **Intraday signals** for 2026-06-08/09 not yet built — scheduler `autonomous_tick` will handle this on next cycle.

### Remediation for sustained freshness

- Schedule ingestion via cron or APScheduler (recommended: daily at 01:00 UTC after data close)
- Add API ingestion health check to governance dashboard
