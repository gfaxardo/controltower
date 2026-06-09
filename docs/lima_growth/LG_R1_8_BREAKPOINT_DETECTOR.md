# LG-R1.8 — Breakpoint Detector

**Date:** 2026-06-07
**Phase:** LG-INFRA-R1.8

---

## TOP 10 BREAKPOINTS IN THE LIMA GROWTH LINEAGE CHAIN

Each entry identifies where the chain can break, the impact, and remediation.

---

### BP-01: Yango API Unavailable

| Field | Value |
|-------|-------|
| **Layer** | RAW ingestion |
| **Symptom** | No new orders in `orders_raw` |
| **Impact** | `driver_history_daily` stops updating → `driver_history_weekly` → `driver_state_snapshot` → everything downstream |
| **Detection** | `data_freshness.orders_api` shows RED |
| **Remediation** | Wait for API. Retry ingestion. No stale fallback. |
| **Severity** | **CRITICAL** |

---

### BP-02: driver_history_weekly Empty

| Field | Value |
|-------|-------|
| **Layer** | Snapshot universe |
| **Symptom** | `build_driver_state_snapshot()` returns "No drivers found in history_weekly" |
| **Impact** | ZERO rows in snapshot → eligibility → opportunities → queue → serving → UI |
| **Detection** | Snapshot row count = 0 |
| **Remediation** | Bootstrap history from trips tables. Run `bootstrap-history` endpoint. |
| **Severity** | **CRITICAL** |

---

### BP-03: driver_state_snapshot Missing for Date

| Field | Value |
|-------|-------|
| **Layer** | Keystone snapshot |
| **Symptom** | `validate_source_readiness()` fails |
| **Impact** | Serving facts not generated. UI shows MISSING_SERVING_FACT. |
| **Detection** | `prioritized_opportunity_daily` = 0 for that date |
| **Remediation** | Run daily pipeline for the missing date. |
| **Severity** | **HIGH** |

---

### BP-04: program_eligibility Empty

| Field | Value |
|-------|-------|
| **Layer** | Eligibility |
| **Symptom** | 0 eligible drivers for a date |
| **Impact** | `daily_opportunity_list` = 0 → `prioritized` = 0 → queue empty |
| **Detection** | Eligibility count = 0 |
| **Remediation** | Re-run `build_program_eligibility` for the date. |
| **Severity** | **HIGH** |

---

### BP-05: Prioritized Opportunities Empty

| Field | Value |
|-------|-------|
| **Layer** | Prioritization |
| **Symptom** | `prioritized_opportunity_daily` has 0 rows |
| **Impact** | Queue build fails. No actionable drivers. |
| **Detection** | `prioritized_opportunity_daily` = 0 |
| **Remediation** | Run `POST /policy/build-prioritized-opportunities` with active policy. |
| **Severity** | **HIGH** |

---

### BP-06: Assignment Queue Build Fails

| Field | Value |
|-------|-------|
| **Layer** | Queue |
| **Symptom** | `create_assignment_batch()` returns 0 created |
| **Impact** | No drivers in queue. No campaign export possible. |
| **Detection** | `assignment_queue` = 0 rows for date |
| **Remediation** | Verify prioritized has data, policy active, channel allocation configured. |
| **Severity** | **MEDIUM** |

---

### BP-07: Serving Fact Missing

| Field | Value |
|-------|-------|
| **Layer** | Serving cache |
| **Symptom** | UI endpoint returns MISSING_SERVING_FACT |
| **Impact** | UI shows remediation message instead of data |
| **Detection** | `serving_fact` table has 0 rows for date |
| **Remediation** | Run `POST /refresh/run`. Force runtime generation as fallback. |
| **Severity** | **MEDIUM** |

---

### BP-08: DB Pool Saturation

| Field | Value |
|-------|-------|
| **Layer** | Infrastructure |
| **Symptom** | "too many clients already" |
| **Impact** | Backend cannot start. Scheduler cannot run. UI returns 500. |
| **Detection** | Connection failures in logs |
| **Remediation** | Terminate idle connections. Server-side: pg_terminate_backend(). Long-term: pgBouncer. |
| **Severity** | **CRITICAL** |

---

### BP-09: Scheduler Not Running

| Field | Value |
|-------|-------|
| **Layer** | Scheduler |
| **Symptom** | `tick_count` not incrementing. `tick_log` has no recent entries. |
| **Impact** | No intraday signals. No history snapshots. Governance stale. |
| **Detection** | `scheduler_status.tick_count` unchanged for > 10 minutes |
| **Remediation** | Check DB pool (BP-08). Check APScheduler process. Re-enable scheduler. |
| **Severity** | **MEDIUM** |

---

### BP-10: Policy Not Active

| Field | Value |
|-------|-------|
| **Layer** | Prioritization |
| **Symptom** | `build_prioritized_opportunities()` returns "No active policy" |
| **Impact** | Prioritized table empty → queue empty |
| **Detection** | `POST /policy/active` returns `active: false` |
| **Remediation** | `POST /policy/default` → `POST /policy/activate/{id}` |
| **Severity** | **HIGH** |

---

## BREAKPOINT CHAIN DEPENDENCY

```
BP-01 (API)  ──→  BP-02 (history)  ──→  BP-03 (snapshot)
                                              │
                    ┌─────────────────────────┘
                    ▼
              BP-04 (eligibility)
                    │
                    ▼
          BP-10 (policy)  ──→  BP-05 (prioritized)
                                     │
                                     ▼
                               BP-06 (queue)
                                     │
                                     ▼
                               BP-07 (serving)
                                     │
                                     ▼
                                  UI
```

**Infrastructure breakpoints (parallel):**
- BP-08 (DB pool) blocks BP-01 through BP-07
- BP-09 (scheduler) blocks intraday signals and history snapshots

---

## R1.9 EXPANSION — 6 NEW BREAKPOINTS

### BP-11: Midnight Rollover Failure

| Field | Value |
|-------|-------|
| **Layer** | Scheduler / Pipeline |
| **Symptom** | `new_day_detected` stays False for > 24 hours |
| **Impact** | Previous day's data becomes stale. No new lists generated. |
| **Detection** | `today_action_date` not advancing. Serving facts age > 24h. |
| **Remediation** | Check Yango API availability. Manually run pipeline for new date. |
| **Severity** | **CRITICAL** |

### BP-12: Scheduler Stopped Unexpectedly

| Field | Value |
|-------|-------|
| **Layer** | Scheduler (APScheduler) |
| **Symptom** | `tick_count` unchanged for > 10 minutes |
| **Impact** | No intraday signals. No history snapshots. Governance stale. |
| **Detection** | `scheduler_status.tick_count` static. `tick_log` has no recent entries. |
| **Remediation** | Check APScheduler process. Restart backend. Check DB pool (BP-08). |
| **Severity** | **HIGH** |

### BP-13: Catch-Up Failure on Restart

| Field | Value |
|-------|-------|
| **Layer** | Catch-up engine |
| **Symptom** | `catch_up_on_startup()` returns CATCHUP_FAILED |
| **Impact** | Unprocessed dates remain unprocessed. Serving facts stale. |
| **Detection** | `dates_failed[]` non-empty in catch-up result |
| **Remediation** | Check individual date errors. Re-run pipeline manually for failed dates. |
| **Severity** | **HIGH** |

### BP-14: Startup Recovery Blocked

| Field | Value |
|-------|-------|
| **Layer** | Infrastructure / Backend |
| **Symptom** | Backend cannot start — "too many clients already" |
| **Impact** | Complete outage. Scheduler, UI, API all down. |
| **Detection** | Connection failures in backend logs |
| **Remediation** | Terminate external DB connections. Restart PostgreSQL. Implement pgBouncer. |
| **Severity** | **CRITICAL** |

### BP-15: Queue Duplication on Re-Run

| Field | Value |
|-------|-------|
| **Layer** | Assignment Queue |
| **Symptom** | Row count doubles for same date after pipeline re-run |
| **Impact** | Duplicate campaign exports. Double-contacting drivers. |
| **Detection** | `COUNT(*)` for assignment_date increases after re-run |
| **Remediation** | Verify UNIQUE constraint on `(assignment_date, driver_id, program_code)`. Verify ON CONFLICT DO NOTHING. |
| **Severity** | **MEDIUM** |

### BP-16: Serving Facts Not Regenerated After Catch-Up

| Field | Value |
|-------|-------|
| **Layer** | Serving Facts |
| **Symptom** | Serving facts remain stale (> 24h) after successful catch-up |
| **Impact** | UI shows old data despite pipeline having run |
| **Detection** | `generated_at` older than last refresh_run_log SUCCESS |
| **Remediation** | Force `generate_all_serving_facts()` in catch-up completion. Run `POST /refresh/run`. |
| **Severity** | **HIGH** |

---

## UPDATED BREAKPOINT CHAIN (16 Total)

```
BP-01 (API)  ──→  BP-02 (history)  ──→  BP-03 (snapshot)
                                              │
                    ┌─────────────────────────┘
                    ▼
              BP-04 (eligibility)
                    │
                    ▼
          BP-10 (policy)  ──→  BP-05 (prioritized)
                                     │
                                     ▼
                               BP-06 (queue)  ←── BP-15 (duplication)
                                     │
                                     ▼
                               BP-07 (serving) ←── BP-16 (regen)
                                     │
                                     ▼
                                  UI

Infrastructure (parallel):
  BP-08 (DB pool) ──→ BP-14 (startup blocked)
  BP-09 (scheduler) ──→ BP-12 (scheduler stopped)
  BP-11 (midnight) ──→ BP-13 (catch-up failure)
```

---

## FIRMA

```
BREAKPOINT DETECTOR (EXPANDED)
LG-INFRA-R1.8 / R1.9 Midnight + Scheduler + Recovery Certification
Date: 2026-06-07
Breakpoints: 16 total (10 original + 6 R1.9 expansion)
```
