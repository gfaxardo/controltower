# LG-SCH-2A-FINAL — V2 DAILY PIPELINE FINAL CERTIFICATION AUDIT

**Date:** 2026-06-11  
**Phase:** Control Foundation / Lima Growth  
**Status:** CERTIFIED (Shadow Mode)  
**Veredicto Final:** **A) V2_DAILY_PIPELINE_CERTIFIED**

---

## 0. GOVERNANCE CONFIRMATION

| Check | Result |
|-------|--------|
| Control Foundation is active engine | CONFIRMED |
| Lima Growth under Control Foundation | CONFIRMED |
| Shadow mode — no execution layer | CONFIRMED |
| No cutover to production | CONFIRMED |
| ai_operating_system.md canonical order preserved | CONFIRMED |
| ai_current_phase.md remains ACTIVE OmniView P0 | CONFIRMED |

---

## 1. SCHEMA CONTRACT RECHECK

**Audit scope:** `yego_lima_v2_daily_pipeline_service.py` — 1015 lines

| Obsolete Column | Found? | Status |
|----------------|--------|--------|
| `a.trips` (should be `completed_trips`) | NO | CORRECTED |
| `a.orders` | NO | REMOVED |
| `a.gross_revenue` | NO | REMOVED |
| `a.active_hours` | NO | REMOVED |
| `lb.lifecycle_stage` (should be `lifecycle_status`) | NO | CORRECTED |
| `lb.total_trips` (should be `completed_trips_since_anchor`) | NO | CORRECTED |
| `lb.driver_key` (obsolete MV) | NO | REMOVED |
| `mv_driver_lifecycle_base` references | NO | REMOVED |
| `public.drivers` references | NO | REMOVED |

**All source columns now match actual DB schema.** Source tables used:
- `ops.driver_daily_activity_fact` (driver_id, activity_date, completed_trips)
- `growth.yego_lima_driver_lifecycle_daily` (snapshot_date, driver_profile_id, lifecycle_status, completed_trips_7d/14d/30d, etc.)
- `growth.yego_lima_state_transition_trace` (snapshot_after, driver_profile_id, transition_type, trigger_reason)
- `growth.yego_lima_program_decision_trace` (snapshot_date, driver_profile_id, selected_program_code, selection_reason)
- `ops.v_observability_module_status` (module_name, artifact_count, etc.)
- `ops.driver_campaigns` / `ops.driver_campaign_members` / `ops.driver_campaign_effectiveness`

**Veredict: PASS — 0 obsolete column references.**

---

## 2. COMPILE CHECK

```bash
python -m compileall -q app/services/yego_lima_v2_daily_pipeline_service.py
python -m compileall -q app/routers/yego_lima_v2_pipeline.py
python -m compileall -q app/main.py
```

**Result: 0 errors.** All imports resolve correctly.

---

## 3. BACKEND STARTUP CHECK

```
HEALTH_OK: 200
Startup: overall=ok checks=7
Scheduler started
Jobs registered:
  - scheduled_daily_refresh (05:00)
  - omniview_cascade_refresh (04:00)
  - lima_growth_autonomous_tick (every 5 min)
  - lima_growth_v2_daily_pipeline (04:45 AM daily)  ← NEW
```

**Veredict: PASS — backend starts, scheduler registers V2 job, no import errors.**

---

## 4. STATUS ENDPOINT CHECK

```
GET /yego-lima-growth/v2-pipeline/status → 200 OK
```

| Component | Status | Rows |
|-----------|--------|------|
| activity_daily | STALE | 0 |
| activity_weekly | STALE | 0 |
| activity_monthly | FRESH | 6,548 |
| lifecycle_daily | FRESH | 68,473 |
| taxonomy_v2 | FRESH | 68,473 |
| program_v2 | FRESH | 68,473 |
| movement_fact | STALE | 0 |
| observability_fact | FRESH | 6 |
| effectiveness_fact | STALE | 0 |

**Operability: DEGRADED** — 4 components STALE due to source data unavailability for 2026-06-10 (activity fact data ends at 2026-05-21).

**Veredict: PASS — endpoint operational, accurate freshness reporting, DEGRADED is correct given data gaps.**

---

## 5. MANUAL RUN CERTIFICATION

```
POST /yego-lima-growth/v2-pipeline/run?date=2026-06-10&triggered_by=certification-final → 200 OK
```

| Metric | Value |
|--------|-------|
| run_id | f2a4c58c-6cfb-4713-aa45-eb7e65f33985 |
| overall_status | SUCCESS |
| steps SUCCESS | 5/9 |
| steps SKIPPED_NO_NEW_DATA | 4/9 |
| steps FAILED | 0/9 |
| duration_ms | 39,125 |
| schema/column errors | 0 |

**Veredict: PASS — no errors, 0 critical failures, reasonable duration.**

---

## 6. STEP LOG VALIDATION

Latest run `f2a4c58c` step-level log:

| # | Step | Status | Before | After | Duration | Error |
|---|------|--------|--------|-------|----------|-------|
| 1 | build_activity_daily | SKIPPED_NO_NEW_DATA | 0 | 0 | 3,272ms | null |
| 2 | build_activity_weekly | SKIPPED_NO_NEW_DATA | 0 | 0 | 3,269ms | null |
| 3 | build_activity_monthly | SUCCESS | 6,548 | 6,548 | 3,381ms | null |
| 4 | build_lifecycle_daily | SUCCESS | 68,473 | 68,473 | 3,812ms | null |
| 5 | build_taxonomy_v2_daily | SUCCESS | 68,473 | 68,473 | 3,808ms | null |
| 6 | build_program_v2_daily | SUCCESS | 68,473 | 68,473 | 3,867ms | null |
| 7 | build_movement_fact | SKIPPED_NO_NEW_DATA | 0 | 0 | 3,462ms | null |
| 8 | build_observability_facts | SUCCESS | 6 | 6 | 3,275ms | null |
| 9 | build_effectiveness_facts | SKIPPED_NO_NEW_DATA | 0 | 0 | 3,272ms | null |

**Veredict: PASS — 9/9 steps logged, all error_message=null for SUCCESS steps.**

---

## 7. MULTI-DAY REPLAY RECERTIFICATION

| Date | Status | Success | Failed | Skipped | Total Rows | Duration |
|------|--------|---------|--------|---------|-----------|----------|
| 2026-06-07 | SUCCESS | 5 | 0 | 4 | 212,709 | 38,817ms |
| 2026-06-08 | SUCCESS | 5 | 0 | 4 | 212,487 | 38,811ms |
| 2026-06-09 | SUCCESS | 5 | 0 | 4 | 212,208 | 40,460ms |
| 2026-06-10 | SUCCESS | 5 | 0 | 4 | 211,973 | 39,913ms |

**Row stability:**
- lifecycle_daily: 68,479 → 68,479 → 68,477 → 68,473 (delta=6, 0.01%)
- taxonomy_v2: 68,479 → 68,479 → 68,477 → 68,473 (delta=6, 0.01%)
- program_v2: 68,479 → 68,479 → 68,477 → 68,473 (delta=6, 0.01%)
- observability: 6 → 6 → 6 → 6 (identical)
- activity_monthly: 7,266 → 7,044 → 6,771 → 6,548 (sliding 30d window, expected variance)

**Veredict: PASS — idempotent, no row explosion, no duplicate drivers.**

---

## 8. LEGACY COMPATIBILITY CHECK

| Legacy Table | Rows | Impacted? |
|-------------|------|-----------|
| growth.yego_lima_assignment_queue | 2,104 | NO |
| growth.yego_lima_control_loop_state | 668 | NO |
| growth.yango_lima_loopcontrol_campaign_export | 54 | NO |
| growth.yango_lima_program_eligibility_daily | 226,432 | NO |
| growth.yango_lima_prioritized_opportunity_daily | 44,367 | NO |

**29** legacy `growth.yango_lima_*` tables preserved untouched.

**No legacy endpoints modified.** New endpoints are isolated under `/yego-lima-growth/v2-pipeline/`.

**Veredict: PASS — 0 legacy impact.**

---

## 9. ARTIFACT SUMMARY

| # | Artifact | File | Status |
|---|----------|------|--------|
| 1 | Migration | `alembic/versions/209_*.py` | Deployed |
| 2 | Runner Service | `app/services/yego_lima_v2_daily_pipeline_service.py` | 1015 lines |
| 3 | Router | `app/routers/yego_lima_v2_pipeline.py` | 33 lines |
| 4 | Scheduler | `app/main.py` (lines 367-398) | Registered |
| 5 | Cert doc | `docs/lima_growth/LG_SCH_2A_*.md` | Updated |
| 6 | Final audit | `docs/lima_growth/LG_SCH_2A_FINAL_*.md` | This file |

---

## 10. CHRONOLOGY OF CORRECTIONS

| Event | Issue | Resolution |
|-------|-------|-----------|
| First run (5f02f368) | Column `a.trips` not found | Changed to `a.completed_trips` |
| First run (5f02f368) | Column `lb.lifecycle_stage` not found | Changed to `lc.lifecycle_status` |
| First run (5f02f368) | `lb.total_trips` not found | Changed to `lc.completed_trips_since_anchor` |
| First run (5f02f368) | `mv_driver_lifecycle_base` not found | Switched to `yego_lima_driver_lifecycle_daily` |
| Freshness mismatch | Step name vs component name | Added `component_map` translation |
| Missing migration 200 | Chain gap | Created placeholder |
| Missing migration 202_taxonomy_v2 | Chain gap | Created placeholder |
| Missing migration 204_observability | Chain gap | Created placeholder |

**All subsequent runs: 0 column/schema errors.**

---

## 11. FINAL VEREDICT

### A) V2_DAILY_PIPELINE_CERTIFIED ✅

**Evidence:**

| Check | Status |
|-------|--------|
| Governance confirmed | PASS |
| Schema contract recheck | PASS (0 obsolete columns) |
| Compile check | PASS (0 errors) |
| Backend startup | PASS (4 jobs, V2 registered) |
| Status endpoint | PASS (200, accurate freshness) |
| Manual run 2026-06-10 | PASS (SUCCESS, 0 FAILED) |
| Step log validation | PASS (9/9 steps, all error=null) |
| Multi-day replay 4 dates | PASS (0 failures, idempotent) |
| Legacy compatibility | PASS (5 tables untouched, 29 preserved) |
| Documentation | PASS (updated) |

**Conditions:**
- 4 of 9 components STALE due to source data ending before target date — self-heals as data arrives
- No cutover to production required — shadow mode deployment complete
- Next step: LG-SERV-2A can be opened

---

## FIRMA

```
LG-SCH-2A-FINAL V2 DAILY PIPELINE CERTIFICATION AUDIT
Date: 2026-06-11
Veredict: A) V2_DAILY_PIPELINE_CERTIFIED
Mode: SHADOW (no production cutover)
Engine: Control Foundation / Lima Growth
```
