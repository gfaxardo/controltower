# LG — Operational Day Contract

**Date:** 2026-06-07
**Phase:** LG-INFRA-R1.9
**Status:** CANONICAL

---

## PURPOSE

This contract defines the two operational cycles of Lima Growth. Any deviation from this contract is a governance violation.

---

## CYCLE A: DAILY CLOSED PIPELINE

### Frequency

**Once per day.** After operational data close (~00:01 Lima time or when Yango API reports new closed date).

### Input

`closed_operational_data_date` from Yango API (latest date with complete orders data).

### Responsibility

| Step | Action | Service |
|------|--------|---------|
| 1 | Validate foundation | `yego_lima_daily_pipeline_service` |
| 2 | Build eligible universe | `yego_lima_eligible_universe_service` (SKIPPABLE) |
| 3 | Stabilize driver_360 | `yego_lima_driver_360_service` (SKIPPABLE) |
| 4 | Build loyalty sub50 | `yego_lima_loyalty_sub50_service` |
| 5 | Build driver segments | `yego_lima_driver_segmentation_service` |
| 6 | **Build driver state snapshot** | `yego_lima_driver_state_service` |
| 7 | **Build program eligibility** | `yego_lima_program_eligibility_service` |
| 8 | **Build daily opportunity lists** | `yego_lima_daily_opportunity_service` |
| 9 | Close previous day | Various |
| 10-14 | Impact, transitions, outcomes, attribution | Various |
| 15 | Executive metrics check | Inline |

### Post-Pipeline (refresh/run)

| Step | Action | Service |
|------|--------|---------|
| 1 | Build assignment queue | `yego_lima_assignment_queue_service` |
| 2 | Build prioritized opportunities | `yego_lima_opportunity_policy_service` |
| 3 | **Generate serving facts (8)** | `yego_lima_serving_facts_service` |
| 4 | Snapshot queue to history | `yego_lima_driver_list_history_service` |

### Output

- `driver_state_snapshot` for the date (> 0 rows)
- `program_eligibility_daily` for the date (> 0 rows)
- `prioritized_opportunity_daily` for the date (> 0 rows)
- `assignment_queue` for the date (> 0 rows)
- `serving_fact` 8/8 for the date
- `driver_list_history` snapshot

### Idempotency

- Can be re-run safely for the same date
- RE-RUN does NOT duplicate rows (UNIQUE constraints, ON CONFLICT DO UPDATE/NOTHING)
- RE-RUN does NOT duplicate queue (UNIQUE per date/driver/program)
- RE-RUN does NOT duplicate serving facts (UPSERT per date/type)
- RE-RUN does NOT break history (immutable, ON CONFLICT preserves)

### Trigger

- Manual: `POST /yego-lima-growth/pipeline/run-daily` (body: `{"run_date": "YYYY-MM-DD"}`)
- Manual: `POST /yego-lima-growth/scheduler/run-daily-closed?date=YYYY-MM-DD`
- Auto: `catch_up_on_startup()` when scheduler detects gap
- Auto: `run_live_monitoring()` when new_day_detected = True (triggers catch-up)

---

## CYCLE B: LIVE 5-MIN MONITORING

### Frequency

**Every 5 minutes.** Continuous throughout the operational day.

### Responsibility

| Action | Service |
|--------|---------|
| Ingest Yango API (incremental) | `yango_raw_ingestion_service` |
| Refresh raw_yango MVs | `yego_lima_freshness_service` |
| **Check governance** | `yego_lima_refresh_governance_service` |
| **Build intraday signals** | `yego_lima_intraday_signal_service` |
| **Detect catch-up gaps** | `catch_up_on_startup()` |
| **Snapshot history** | `yego_lima_driver_list_history_service` |
| **Record tick log** | `yego_lima_scheduler_service` |

### PROHIBITED in Live Monitoring

- Rebuild eligibility universe
- Rebuild driver_360
- Rebuild prioritization
- Rebuild queue base
- Reorder queue
- Export campaigns
- Run Action Engine
- Delete historical data
- Modify EXPORTED queue rows

---

## MIDNIGHT + 1 CONTRACT

### At 00:01 Lima Time

1. Yango API reports new `closed_operational_data_date`
2. Scheduler tick detects `last_processed_date != latest_available_date`
3. `new_day_detected = True`
4. `catch_up_on_startup()` executes:
   a. Finds all dates between last_processed and latest_available
   b. Runs daily closed pipeline for each missing date
   c. Generates serving facts for latest date
   d. Updates governance to OPERABLE
5. `today_action_date` transitions to new day
6. Today Action Plan becomes OPERABLE

### Pre-Warm

- 5-min loop keeps Yango API data fresh throughout the day
- At midnight, raw_yango is already current (< 5 min old)
- MVs are already refreshed
- Daily Closed Pipeline only needs to build operational layers
- No re-ingestion of history already maintained

### Fallback: WAITING_FOR_CLOSED_DATA

If Yango API does NOT have new closed data at 00:01:
- `operational_data_date` stays at previous day
- `today_action_date` stays at current day
- Status = WAITING_FOR_CLOSED_DATA
- Each subsequent tick re-checks
- When data appears: auto-trigger catch-up

---

## SEPARATION RULES

| Operation | Daily Closed | Live 5-Min |
|-----------|:---:|:---:|
| Build eligible_universe | YES | NO |
| Build driver_360 | YES (skip) | NO |
| Build snapshot | YES | NO |
| Build eligibility | YES | NO |
| Build prioritized | YES | NO |
| Build base queue | YES | NO |
| Generate serving facts | YES | NO |
| Ingest Yango API | — | YES |
| Refresh MVs | — | YES |
| Monitor action results | — | YES |
| Update governance | YES | YES |
| Maintain freshness | — | YES |
| Build intraday signals | — | YES |
| Snapshot history | YES | YES |
| Record tick | — | YES |

---

## ENDPOINTS

| Method | Path | Cycle |
|--------|------|:---:|
| GET | /scheduler/status | Both |
| POST | /scheduler/start | Both |
| POST | /scheduler/stop | Both |
| POST | /scheduler/tick | Live Monitoring |
| POST | /scheduler/run-daily-closed | Daily Pipeline |
| POST | /scheduler/run-live-monitoring | Live Monitoring |
| POST | /scheduler/catch-up | Recovery |
| POST | /pipeline/run-daily | Daily Pipeline |
| POST | /refresh/run | Daily Pipeline |

---

## COMPLIANCE EVIDENCE (R1.4)

Pipeline recovery for 3 consecutive dates (06-03, 06-04, 06-05) demonstrates:
- Daily pipeline: 15/15 steps → **PASS**
- Serving facts: 8/8 generated → **PASS**
- Assignment queue: 500 built → **PASS**
- History snapshot: 500 rows → **PASS**
- Multiple dates processed without overlap → **PASS**

---

## FIRMA

```
OPERATIONAL DAY CONTRACT
LG-INFRA-R1.9 Midnight + Scheduler + Recovery Certification
Date: 2026-06-07
Status: CANONICAL
```
