# BACKLOG — Control Loop Live Result Monitoring

**Date:** 2026-06-07
**Phase:** BACKLOG — INTRAIDAY SIGNAL LAYER FOUNDED (R1.3)
**Registry:** LG-INFRA-R1.2 / LG-INFRA-R1.3

---

## STATUS UPDATE (2026-06-07)

**LG-INFRA-R1.3 Intraday Signal Layer Foundation is COMPLETE.**

The foundation for live result monitoring is now in place:

- `growth.yego_lima_intraday_driver_signal` table created (migration 192)
- `yego_lima_intraday_signal_service.py` service operational
- Scheduler `run_live_monitoring()` now builds intraday signals every 5-min tick
- Endpoints live at `/yego-lima-growth/intraday-signals/*`
- UI panel visible in Lima Growth Dashboard > Intraday Signals
- Non-causality disclaimer enforced throughout

The signal layer *observes* drivers post-action — it does not assert attribution.

---

## WHAT IS NOW READY

| Capability | Status |
|-----------|:---:|
| Per-driver signal observation | READY |
| Trips after action detection | READY |
| Reactivation flag | READY |
| Activity detection today | READY |
| Signal summary API | READY |
| UI visibility (observation only) | READY |
| 5-min scheduler integration | READY |

---

## WHAT REMAINS BLOCKED

| Capability | Reason |
|-----------|--------|
| Attribution formal | Blocked — R3.1 Attribution Engine not yet built |
| Impact formal | Blocked — requires Attribution foundation |
| ROI calculation | Blocked — requires Impact foundation |
| Causal inference | Blocked — requires holdout/control groups |
| Holdout/control group | Blocked — experimental design not yet done |
| Auto-export based on signals | Blocked — Action Engine not yet active |

---

## NEED

Today the 5-min live monitoring loop maintains Yango API freshness but does NOT track what happened to drivers that were contacted. Result signals (did the driver return to operate? did they complete more trips?) are now *observed* via the Intraday Signal Layer (R1.3) but attribution is NOT yet implemented.

---

## RESULT SIGNAL TABLE (EXISTS)

Table: `growth.yego_lima_intraday_driver_signal` (created by migration 192)

Key fields: signal_id, signal_date, driver_profile_id, action_date, queue_id, campaign_id_external, action_channel, action_sent_at, observed_at, trips_after_action, supply_hours_after_action, first_trip_after_action_at, reactivation_detected, activity_detected_today, signal_status

---

## LIVE MONITORING TICK (NOW ACTIVE)

Every 5 minutes via `run_live_monitoring()`:

1. Query Yango API for recent orders by contacted drivers
2. Compare against action_sent_at timestamps
3. Update intraday signals (upsert):
   - `first_trip_after_action_at` if first trip detected
   - `trips_after_action` counter
   - `reactivation_detected` flag
   - `activity_detected_today` flag
4. Update governance heartbeat
5. Record scheduler tick

---

## NOT IMPLEMENTED (R3.1+)

- Formal Impact/Attribution territory
- Blocked until R3.1 (Impact + Attribution foundational)
- Signal observation ready; causal analysis blocked

---

## DEPENDENCIES

| Dependency | Status |
|-----------|:---:|
| Yango API (orders lookup by driver) | EXISTS |
| Intraday Signal Layer (R1.3) | **DONE** |
| LoopControl result sync (campaign → driver mapping) | PARTIAL (table exists, not populated) |
| Impact measurement (causal analysis) | BACKLOG |
| Attribution (channel/program attribution) | BACKLOG |

---

## FIRMA

```
BACKLOG REGISTRY ENTRY — UPDATED
Control Loop Live Result Monitoring
Updated: 2026-06-07
Phase: LG-INFRA-R1.3 (Foundation Complete)
Status: OBSERVATION LAYER READY → Attribution/Impact blocked until R3.1
Next review: Post R3.1 Attribution Engine
```
