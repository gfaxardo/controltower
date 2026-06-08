# OV2-F.4A — SCHEDULER CANONICALIZATION — FINAL REPORT

> **Date:** 2026-06-07 (PM)
> **Motor:** Control Foundation / Freshness Chain
> **Phase:** OV2-F.4A — Scheduler Canonicalization + Legacy Deprecation
> **Status:** **GREEN — Single-writer ownership established, legacy paths deprecated**

---

## 1. EXECUTIVE SUMMARY

Se auditó y deprecó todas las rutas legacy que escribían week_fact y month_fact desde raw trips. El APScheduler ahora solo escribe day_fact. Week y month quedan bajo control exclusivo del bridge cascade. 0 WATERFALL_BROKEN. 10/10 certification. Un único dueño por tabla.

---

## 2. LEGACY REFRESH INVENTORY

| Function | File | Table | Frequency | Status |
|----------|------|-------|-----------|--------|
| `load_business_slice_day_for_month` | `business_slice_incremental_load.py` | day_fact | Daily (scheduler) | **ACTIVE** |
| `load_business_slice_week_for_month` | `business_slice_incremental_load.py` | week_fact | Daily (scheduler) | **DEPRECATED** |
| `load_business_slice_month` | `business_slice_incremental_load.py` | month_fact | Daily (scheduler) | **DEPRECATED** |
| `_RESOLVE_AND_AGG_WEEK_FROM_TEMP` | `business_slice_incremental_load.py` | week_fact | Via load_week | **DEPRECATED** (indirect) |
| `_RESOLVE_AND_AGG_FROM_TEMP` | `business_slice_incremental_load.py` | month_fact | Via load_month | **DEPRECATED** (indirect) |
| `rebuild_week_from_day_and_bridge` | `rebuild_week_from_day_and_bridge.py` | week_fact | Cascade orchestrator | **CANONICAL** |
| `rebuild_month_from_day_and_bridge` | `rebuild_month_from_day_and_bridge.py` | month_fact | Cascade orchestrator | **CANONICAL** |
| `refresh_omniview_v2_snapshots` | `refresh_omniview_v2_snapshots.py` | snapshot | Cascade orchestrator | **CANONICAL** |
| `build_driver_bridge_direct` | `build_driver_bridge_direct.py` | driver_day_slice_fact | Cascade orchestrator | **CANONICAL** |

---

## 3. WRITE OWNERSHIP REGISTRY

| Table | Writer | Path | Type |
|-------|--------|------|------|
| `driver_day_slice_fact` | `build_driver_bridge_direct` | trips_2026 → bridge | CANONICAL |
| `day_fact` | `load_business_slice_day_for_month` (scheduler) | raw → enriched → day_fact | CANONICAL |
| `week_fact` | `rebuild_week_from_day_and_bridge` | day_fact + bridge → week | CANONICAL |
| `month_fact` | `rebuild_month_from_day_and_bridge` | day_fact + bridge → month | CANONICAL |
| `snapshot` | `refresh_omniview_v2_snapshots` | day_fact → snapshot | CANONICAL |

**1 table = 1 owner.** No double-writers.

---

## 4. SCHEDULER AUDIT

| Job | Schedule | Status | Action |
|-----|----------|--------|--------|
| `business_slice_real_refresh` | Daily 04:00 | **MODIFIED** — week/month removed | Only writes day_fact |
| `serving_fact_daily_refresh` | Daily 05:00 | ACTIVE | Projection facts |
| `real_data_watchdog` | Every 15min | ACTIVE | Monitoring |

---

## 5. LEGACY DEPRECATION

| Function | Replaced by | Guard |
|----------|------------|-------|
| `load_business_slice_week_for_month` | `rebuild_week_from_day_and_bridge` | DEPRECATED comment + removed from scheduler import |
| `load_business_slice_month` | `rebuild_month_from_day_and_bridge` | DEPRECATED comment + removed from scheduler import |
| `_RESOLVE_AND_AGG_WEEK_FROM_TEMP` | Bridge cascade | Called only by deprecated function |
| `_RESOLVE_AND_AGG_FROM_TEMP` | Bridge cascade | Called only by deprecated function |

---

## 6. RUNTIME PROTECTION

Scheduler job (`business_slice_real_refresh_job.py`):
- Removed imports of `load_business_slice_week_for_month` and `load_business_slice_month`
- Week/month refresh skipped with comment referencing bridge cascade
- If legacy function is called, the import error serves as protection

Cascade orchestrator (`run_ov2_refresh_cascade.py`):
- Runs bridge → week → month → snapshot in order
- Validates each step before proceeding
- Reports status per step

---

## 7. CERTIFICATION

| Check | Result |
|-------|--------|
| RAW→DAY | OK (2026-06-06 ≥ 2026-06-06) |
| DAY→WEEK | OK (2026-06-06 ≥ 2026-06-01) |
| WEEK→MONTH | OK (2026-06-01 ≥ 2026-06-01) |
| DAY→SNAPSHOT | OK (2026-06-06 ≥ 2026-06-05) |
| WATERFALL_BROKEN | 0 |
| Certification | 10/10 GO |

---

## 8. GO CRITERIA

| Criterion | Status |
|-----------|--------|
| week_fact = 1 writer | ✅ `rebuild_week_from_day_and_bridge` |
| month_fact = 1 writer | ✅ `rebuild_month_from_day_and_bridge` |
| snapshots = 1 writer | ✅ `refresh_omniview_v2_snapshots` |
| Scheduler uses bridge path | ✅ week/month removed |
| Legacy routes deprecated | ✅ 4 functions marked DEPRECATED |
| Runtime protected | ✅ Import error guard |
| Freshness Chain = GREEN | ✅ |
| 0 WATERFALL_BROKEN | ✅ |
| V1 intact | ✅ |

## **GREEN — GO for F.5**

---

*End of OV2-F.4A Report*
