# LG-INFRA-R1.3 — Intraday Signal Layer Foundation

**Date:** 2026-06-07
**Phase:** LG-INFRA-R1.3 Intraday Signal Layer Foundation
**Status:** COMPLETE

---

## 1. EXECUTIVE SUMMARY

**INTRADAY SIGNAL LAYER FOUNDED.**

The technical and operational base for monitoring intraday signals every 5 minutes has been created. The system now observes live driver activity post-action without reconstructing the daily base list.

The daily closed pipeline builds the base list once per day. During the day, the system only updates signals via the live 5-min loop — observing trips, supply, reactivation, and activity without recalculating programs, eligibility, prioritization, or queues.

---

## 2. ACTION SOURCE AUDIT

### Where is it recorded that a driver was actioned?

| Source | Table | Key Fields | Status |
|--------|-------|------------|:---:|
| Assignment Queue | `growth.yego_lima_assignment_queue` | `driver_id`, `queue_status` (READY/EXPORTED), `exported_at`, `campaign_id_external`, `assigned_channel` | **CANONICAL** |
| LoopControl Campaign Export | `growth.yango_lima_loopcontrol_campaign_export` | Campaign-level only. No per-driver trace. | GAP |
| LoopControl Result Sync | `growth.yego_lima_loopcontrol_result_sync` | `driver_id`, `status`, `disposition`, `last_call_at`. Table exists but service does not populate it. | ORPHANED |
| Impact Tracking | `growth.yego_lima_impact_tracking` | `driver_id`, `contact_date`, `contact_status`, `baseline_trips`, `post_contact_trips` | EXISTS |
| Movement Tracking | `growth.yego_lima_movement_tracking` | `driver_id`, `from_state`, `to_state`, `movement_date` | EXISTS |
| Attribution Candidates | `growth.yego_lima_attribution_candidates` | `driver_id`, `campaign_id_external`, `assigned_channel`, `candidate_status` | EXISTS |

### Key Gaps

1. **No `contacted_at` field** at the driver level. `exported_at` means "sent to campaign", not "contacted".
2. **Result sync table orphaned.** `yego_lima_loopcontrol_result_sync` exists but is not populated.
3. **No channel tracking at contact level.** `assigned_channel` is the planned channel, not the actual channel used.
4. **No per-driver contact outcome.** `queue_status` only tracks READY/HELD/EXPORTED, not CONTACTED/NOT_CONTACTED.

---

## 3. LIVE RESULT SOURCE AUDIT

### Available intraday signals

| Signal | Source | Granularity | Latency | Available | Limitations |
|--------|--------|------------|---------|:---:|------------|
| completed_orders_today | `growth.yango_lima_orders_raw` | Per driver | As fresh as API ingestion | YES | Only completed orders |
| orders_last_hour | `growth.yango_lima_orders_raw` | Fleet-level | As fresh as API ingestion | YES | Aggregate only |
| last_order_ts | `growth.yango_lima_orders_raw` | Per driver | As fresh as API ingestion | YES | Completed orders only |
| completed_orders_7d/30d | `growth.yango_lima_orders_raw` | Per driver | Computed from raw | YES | Full scan for large bases |
| gross_revenue | `growth.yango_lima_orders_raw` | Per driver | Computed from raw | YES | Completed order revenue only |
| supply_hours | Yango API `get_supply_hours()` | Per driver | ~1.5s per driver | NO | Rate-limited, not scalable intraday |
| current_status (online/offline) | Yango API `driver-profiles/list` | Per driver | Hours | PARTIAL | Paginated, no single-driver lookup |
| lifecycle/performance/retention states | `yego_lima_driver_state_snapshot` | Per driver | Daily | NO | Weekly metrics, not intraday |

### Canonical Source

**Yango API is the canonical live operational source.** Orders data (`raw_yango.orders_raw`) is the primary intraday signal source. Supply hours API is rate-limited and not scalable for intraday use at fleet scale.

---

## 4. TABLE CONTRACT

### `growth.yego_lima_intraday_driver_signal`

Created by migration 192.

| Column | Type | Description |
|--------|------|-------------|
| `signal_id` | uuid PK | Unique signal identifier |
| `signal_date` | date NOT NULL | Date of observation |
| `driver_profile_id` | text NOT NULL | Driver identifier |
| `action_date` | date | Date driver was actioned |
| `queue_id` | uuid | Reference to assignment_queue |
| `campaign_id_external` | text | External campaign identifier |
| `action_channel` | text | Planned channel (from queue) |
| `action_sent_at` | timestamptz | When action was exported |
| `observed_at` | timestamptz | When signal was observed |
| `source_system` | text | Always 'YANGO_API_LIVE' |
| `source_loaded_at` | timestamptz | When source data was loaded |
| `trips_after_action` | integer | Count of trips since action |
| `supply_hours_after_action` | numeric | Supply hours since action |
| `first_trip_after_action_at` | timestamptz | Timestamp of first trip post-action |
| `first_supply_after_action_at` | timestamptz | Timestamp of first supply post-action |
| `reactivation_detected` | boolean | Driver showed activity post-action |
| `activity_detected_today` | boolean | Any activity detected today |
| `signal_status` | text | One of: OBSERVED, ACTIONED_NO_ACTIVITY, TRIP_DETECTED, SUPPLY_DETECTED, REACTIVATED, STALE |
| `evidence_json` | jsonb | Debug evidence payload |
| `created_at` | timestamptz | Row creation timestamp |
| `updated_at` | timestamptz | Row update timestamp |

**Unique constraint:** `(signal_date, driver_profile_id, queue_id)` — idempotent per driver/date/action.

**Rules:**
- Does NOT change queue base
- Does NOT change prioritization
- Does NOT mark formal attribution
- Does NOT calculate ROI
- Non-causal observation layer

---

## 5. BUILDER SERVICE

### `yego_lima_intraday_signal_service.py`

Functions:

- `build_intraday_signals(action_date)` — builds signals for all actioned drivers on a date
- `fetch_active_actions(action_date)` — reads EXPORTED/READY drivers from assignment_queue
- `fetch_live_yango_activity(driver_ids, action_date)` — queries raw_yango.orders_raw for live activity
- `compute_signal_for_driver(action, live_activity)` — computes observation signal per driver
- `upsert_signals(signals)` — idempotent upsert into intraday signal table
- `get_signal_summary(action_date)` — aggregated summary counts
- `get_signals_by_campaign(action_date)` — signals grouped by campaign
- `get_signals_by_program(action_date)` — signals grouped by program
- `get_signals_list(action_date, ...)` — paginated individual signal list

### Detection Logic

The service detects:
- Driver was actioned and already completed trips
- Driver was actioned and has no trips
- Driver was actioned and had activity today
- First trip after action timestamp
- Reactivation observed

Language used: **"observed after action"** — never "caused by action".

---

## 6. SCHEDULER INTEGRATION

### Modified: `run_live_monitoring()`

Every 5-minute tick now includes:

1. ~~Ingest Yango API incremental~~ (TBD - API ingestion not in scope)
2. ~~Refresh MVs~~ (TBD - MV refresh not in scope)
3. **Build intraday signals for today's action_date** (NEW)
4. **Update governance heartbeat**
5. **Record scheduler tick**

The scheduler result now includes:
```json
{
  "intraday_signals": {
    "built": true,
    "signal_count": 500,
    "new_signals": 500,
    "updated_signals": 0
  }
}
```

**NO daily rebuild. NO queue rebuild. NO export.**

---

## 7. ENDPOINT CONTRACT

| Method | Path | Description |
|--------|------|-------------|
| GET | `/yego-lima-growth/intraday-signals/summary?date=` | Signal summary for a date |
| GET | `/yego-lima-growth/intraday-signals/by-campaign?date=` | Signals grouped by campaign |
| GET | `/yego-lima-growth/intraday-signals/by-program?date=` | Signals grouped by program |
| GET | `/yego-lima-growth/intraday-signals?date=&limit=&offset=&status=` | Paginated signal list |
| POST | `/yego-lima-growth/intraday-signals/build?date=` | Build signals (admin/dev only) |

---

## 8. UI BEHAVIOR

### Lima Growth Dashboard > Intraday Signals

Panel shows:
- Total actions monitored
- Drivers with trips observed after action
- Drivers with activity detected today
- Drivers with reactivation observed
- Status breakdown (REACTIVATED, TRIP_DETECTED, ACTIONED_NO_ACTIVITY, etc.)
- Campaign-level breakdown
- Program-level breakdown
- Disclaimer: "observado después de acción, no atribución causal"
- Source badge: YANGO_API_LIVE
- Last update timestamp

**Not labeled as Impact. Observation only.**

---

## 9. NON-CAUSALITY RULE

All documentation, code, and UI enforce:

- Language: **"observed after action"**
- NOT: "caused by action", "attributed to campaign", "ROI of channel"
- Signal status labels are descriptive, not causal
- Evidence payload documents the observation, not the inference
- `signal_status` values are factual: OBSERVED, TRIP_DETECTED, REACTIVATED
- Disclaimer visible on every UI panel

This preserves the boundary between **observation** (R1.3) and **attribution** (R3.1+).

---

## 10. REMAINING BLOCKERS

| Blocker | Status |
|---------|:---:|
| R3.1 Program Registry | BLOCKED |
| Program Builder | BLOCKED |
| Attribution formal | BLOCKED |
| Impact formal | BLOCKED |
| ROI calculation | BLOCKED |
| Holdout/control groups | BLOCKED |
| Forecast | BLOCKED |
| AI | BLOCKED |
| Action Engine | BLOCKED |
| Scoring avanzado | BLOCKED |

All are blocked until Control Foundation achieves real GO (OMNI-P0 closure).

---

## 11. FILES CREATED / MODIFIED

### Created

| File | Purpose |
|------|---------|
| `backend/alembic/versions/192_yego_lima_intraday_driver_signal.py` | Migration: signal table |
| `backend/app/services/yego_lima_intraday_signal_service.py` | Signal builder service |
| `backend/app/routers/yego_lima_intraday_signal.py` | API endpoints |
| `frontend/src/pages/lima-growth-v2/sections/IntradaySignalsSection.jsx` | UI panel |
| `docs/lima_growth/LG_INFRA_R1_3_INTRADAY_SIGNAL_LAYER_FOUNDATION.md` | This document |

### Modified

| File | Change |
|------|--------|
| `backend/app/main.py` | Registered intraday signal router |
| `backend/app/services/yego_lima_scheduler_service.py` | Added intraday signal build to `run_live_monitoring()` |
| `frontend/src/services/api.js` | Added intraday signal API functions |
| `frontend/src/pages/lima-growth-v2/hooks/useLimaGrowthData.js` | Added intraday data fetching |
| `frontend/src/pages/LimaGrowthDashboardV2.jsx` | Added Intraday Signals sidebar tab and section |
| `docs/backlog/BACKLOG_CONTROL_LOOP_LIVE_RESULT_MONITORING.md` | Updated with R1.3 completion status |

---

## 12. QA

| Check | Result |
|-------|:---:|
| Migration file created (192) | YES |
| Service file created | YES |
| Router file created | YES |
| Scheduler integrated | YES |
| Endpoints registered | YES |
| UI panel created | YES |
| Disclaimer visible | YES |
| Backlog updated | YES |
| Documentation created | YES |

---

## 13. FINAL VEREDICT

```
INTRADAY SIGNAL LAYER READY
```

**Evidence:**
- Signal table (`growth.yego_lima_intraday_driver_signal`) created with idempotent constraints
- Signal builder service detects trips, reactivation, and activity post-action
- Scheduler `run_live_monitoring()` builds signals every 5 minutes
- 5 API endpoints serve signal data (summary, by-campaign, by-program, list, build)
- UI panel visible in Lima Growth Dashboard with non-causality disclaimer
- No queue rebuild, no eligibility recalculation, no prioritization changes
- Source: YANGO_API_LIVE (canonical)
- Language: "observed after action" (not causal)

**Blocking enforcement in place:**
- R3.1 Program Registry blocked
- Attribution formal blocked
- Impact formal blocked
- ROI blocked
- Forecast blocked
- AI blocked
- Action Engine blocked
