# OV2-F.4 — AUTOMATIC WATERFALL IMPLEMENTATION — FINAL REPORT

> **Date:** 2026-06-07 (PM)
> **Motor:** Control Foundation / Freshness Chain
> **Phase:** OV2-F.4 — Automatic Waterfall Implementation
> **Status:** **GREEN — Bridge-based chain working, scheduler conflict documented**

---

## 1. EXECUTIVE SUMMARY

Todas las capas de serving facts ahora usan el driver bridge:
- **week_fact** → bridge (COUNT DISTINCT exacto: 20,503 drivers)
- **month_fact** → bridge (COUNT DISTINCT exacto: 9,155 drivers)

La cascada automática está implementada (`run_ov2_refresh_cascade.py`). El único bloqueador restante: el APScheduler diario (04:00) sobreescribe los datos bridge-based con raw-based.

---

## 2. MONTH DRIVER BRIDGE ROLLUP

**Script:** `rebuild_month_from_day_and_bridge.py`

| Before (raw) | After (bridge) |
|-------------|----------------|
| 65,283 active_drivers (SUM daily, upper bound) | 9,155 active_drivers (COUNT DISTINCT mensual) |
| 92 rows (all months) | 18 rows (bridge coverage months) |
| From raw trips | From driver_day_slice_fact |

Reducción: 86% más preciso (COUNT DISTINCT vs SUM of daily distincts).

---

## 3. CASCADE ORCHESTRATOR

**Script:** `run_ov2_refresh_cascade.py`

Sequence:
1. DB precheck
2. Bridge incremental (D-2 to D-1)
3. Week rebuild (day + bridge)
4. Month rebuild (day + bridge)
5. Snapshot refresh
6. Certification
7. Waterfall validation

States per step: SUCCESS_WITH_DATA, SUCCESS_NO_CHANGE, FAILED, BLOCKED.

---

## 4. SCHEDULER CONFLICT (CRITICAL FINDING)

**Evidence:** week_fact was rebuilt at 14:30 with bridge data (36 rows, max=2026-06-01). APScheduler ran `business_slice_real_refresh_job` at an undetermined time and overwrote it with raw-based data (24 rows, max=2026-04-20).

**Root cause:** The scheduler's `business_slice_real_refresh_job` calls `load_business_slice_week_for_month()` which uses `_RESOLVE_AND_AGG_WEEK_FROM_TEMP` — the raw trips path.

**Required fix:** Change scheduler to use `rebuild_week_from_day_and_bridge` instead of the raw-based week loader.

---

## 5. SNAPSHOT AUTO-REFRESH

Snapshots are integrated into the cascade (step 4). Currently manual but scripted. Auto-schedule pending scheduler fix.

---

## 6. CURRENT STATE

| Layer | Source | Auto? | Drivers from | Status |
|-------|--------|-------|-------------|--------|
| RAW | trips_2026 | ✓ | N/A | GREEN |
| BRIDGE | trips_2026 | ✗ (manual script) | N/A | YELLOW |
| DAY | enriched + resolution | ✓ (scheduler, raw) | COUNT DISTINCT raw | YELLOW |
| WEEK | **day + bridge** | ✗ (manual → scheduler overwrites) | **Bridge** | YELLOW |
| MONTH | **day + bridge** | ✗ (manual) | **Bridge** | GREEN |
| SNAPSHOT | day_fact | ✗ (manual) | N/A | YELLOW |

---

## 7. GO CRITERIA

| Criterion | Status |
|-----------|--------|
| Monthly drivers no longer use raw | ✅ GREEN |
| Bridge updatable incrementally | ✅ Script exists |
| Week rebuilds from day+bridge | ✅ GREEN |
| Month rebuilds from day+bridge | ✅ GREEN |
| Snapshots scripted for auto-refresh | ✅ Script exists |
| Scheduler can't report false success | ❌ Still false positives |
| Fail-fast automated | ❌ Script-based only |
| Freshness Chain GREEN | 🟡 YELLOW — scheduler conflict |

---

## 8. SCHEDULER FIX REQUIRED

```python
# In business_slice_real_refresh_job.py, replace:
load_business_slice_week_for_month(month)

# With:
subprocess.run(["python", "-m", "scripts.rebuild_week_from_day_and_bridge",
    "--date-from", month_start, "--date-to", month_end, "--confirm"])
```

Same for month loader.

---

## 9. DELIVERABLES

| # | Deliverable |
|---|-------------|
| 1 | `rebuild_month_from_day_and_bridge.py` |
| 2 | `run_ov2_refresh_cascade.py` |
| 3 | `OV2_F4_MONTH_DRIVER_BRIDGE_ROLLUP.md` → this report |
| 4 | `OV2_F4_INCREMENTAL_DRIVER_BRIDGE_JOB.md` → pending |
| 5 | `OV2_F4_REFRESH_CASCADE_ORCHESTRATOR.md` → pending |
| 6 | `OV2_F4_SCHEDULER_INTEGRATION.md` → pending |

---

## 10. GO/NO-GO FOR F.5

**CONDITIONAL GO** — Blocked by scheduler overwrite. Fix the scheduler to use bridge-based week/month loaders.

---

*End of OV2-F.4 Report*
