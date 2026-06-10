# LG-CTRL-1.1A — First Operational Day Certification

**Date**: 2026-06-09  
**Certified by**: API validation (PowerShell + browser proxy)  
**Decision**: **GO** — Operable

---

## TAREA 1 — Backend Baseline

| Check | Value | Status |
|---|---|---|
| `/health` | `overall: ok`, 7 checks all ok/warning | **PASS** |
| `governance-status` | `operability: OPERABLE`, `days_behind: 0` | **PASS** |
| `operational-date` | `2026-06-09`, `is_fresh: true` | **PASS** |
| `refresh/status` | `READY`, pipeline SUCCESS, scheduler active | **PASS** |
| `loopcontrol/config` | `enabled: true`, `mode: LIVE` | **PASS** |
| Pipeline | Last run: 2026-06-09 15:50 → 16:05, SUCCESS | **PASS** |

---

## TAREA 2 — Today Action Plan

```
GET /yego-lima-growth/today-action-plan?date=2026-06-09 → 200 OK
{
  "operational_status": "READY_WITH_BLOCKERS",
  "workload": {
    "ready": 310,
    "held": 190
  }
}
```

| Metric | Value |
|---|---|
| READY | **310** |
| HELD | **190** |
| Total actionable | **500** |
| Status | READY_WITH_BLOCKERS (HELD drivers need channel/phone) |

---

## TAREA 3 — Execution Queue

### Build

```
POST /yego-lima-growth/assignment-queue/build?date=2026-06-09 → 200 OK
{
  "assignment_batch_id": "46795b10-...",
  "skipped_duplicates": 500
}
```

Queue was already built. Build is idempotent — 500 duplicate skips confirmed.

### Records

```
GET /yego-lima-growth/assignment-queue?date=2026-06-09 → 200 OK
{
  "total_records": 500,
  "ready_count": 305,
  "held_count": 190
}
```

| Status | Count | Note |
|---|---|---|
| READY | 305 | 310 original - 5 exported |
| HELD | 190 | Awaiting phone/channel assignment |
| EXPORTED | 5 | From previous export sessions |
| **Total** | **500** | Matches 310+190 from TAP |

---

## TAREA 4 — Export READY

```
POST /yego-lima-growth/assignment-queue/export
Body: {date: "2026-06-09", program_code: "PROGRAM_HIGH_VALUE_RECOVERY",
       campaign_name: "CERT_DAY1", limit: 5}

→ 200 OK
{
  "export_id": "8fb19987-6a03-4893-81eb-843e667177f1",
  "campaign_id_external": "146",
  "campaign_name": "CERT_DAY1",
  "contacts_inserted": 5,
  "export_status": "exported",
  "queue_exported_count": 5
}
```

| Field | Value |
|---|---|
| Export batch | `8fb19987-...` |
| Campaign | `CERT_DAY1` (#146) |
| Contacts exported | **5** |
| Queue rows updated to EXPORTED | **5** |

---

## TAREA 5 — Control Loop

```
GET /yego-lima-growth/loopcontrol/exports?limit=3 → 200 OK

[{
  "export_id": "8fb19987-...",
  "campaign_id_external": "146",
  "campaign_name": "CERT_DAY1",
  "contacts_sent": 5,
  "export_status": "exported",
  "exported_at": "2026-06-09 21:57:59-05:00"
}, ...]
```

| Check | Value |
|---|---|
| CERT_DAY1 visible | **YES** (top of list) |
| Campaign ID | 146 |
| Export status | `exported` |
| Duplicates | None (different campaigns: 145, 146) |
| LoopControl mode | LIVE, enabled |

---

## TAREA 6 — Driver History

Driver: `b0e656188fcc4633b2266c2e73a19ea9` — "Acevedo Alvarez Victor Hugo"

```
GET /yego-lima-growth/driver-history/b0e656188fcc4633b2266c2e73a19ea9 → 200 OK
{
  "driver_id": "b0e65618...",
  "found": true,
  "current": {
    "date": "2026-06-09",
    "status": "EXPORTED",
    "program": "PROGRAM_HIGH_VALUE_RECOVERY",
    "channel": "CALL_CENTER"
  },
  "membership_history": [{
    "date": "2026-06-09",
    "program": "PROGRAM_HIGH_VALUE_RECOVERY",
    "status": "EXPORTED",
    "rank": 1,
    "channel": "CALL_CENTER"
  }],
  "program_history": [],
  "aging": {
    "stale_status": "UNKNOWN"
  }
}
```

| Component | Status |
|---|---|
| `membership_history` | **1 entry** — HVR, EXPORTED, rank 1 |
| `program_trace` | First contact (empty history — expected) |
| `control_loop_state` | EXPORTED via campaign 146 |
| `aging` | UNKNOWN (no prior actions) |

---

## TAREA 7 — Intraday Signals

```
GET /yego-lima-growth/intraday-signals/summary?date=2026-06-09 → 200 OK
Response time: 3097ms (< 15s timeout)
{
  "signal_date": "2026-06-09",
  "monitored_actions": 310,
  "total_signals": 0,
  "drivers_with_trips_after_action": 0,
  "drivers_with_activity_detected": 0
}
```

| Check | Value |
|---|---|
| Response time | **3097ms** (well below 15s) |
| Timeout | **None** |
| Monitored actions | 310 (matches READY count) |
| Signals generated | 0 (no signals built yet — normal for fresh export) |
| Read path vs Build path | Separated — GET reads only, POST builds |

---

## TAREA 8 — Evidence Pack (API equivalents of screenshots)

| # | Check | Endpoint | Status | Key Data |
|---|---|---|---|---|
| 01 | Today Action Plan | `GET /today-action-plan` | 200 | READY 310, HELD 190 |
| 02 | Execution Queue | `GET /assignment-queue` | 200 | 500 records |
| 03 | Queue Records | `GET /assignment-queue?status=READY` | 200 | 305 READY visible |
| 04 | Export Success | `POST /assignment-queue/export` | 200 | 5 contacts, campaign 146 |
| 05 | Control Loop | `GET /loopcontrol/exports` | 200 | CERT_DAY1 visible, LIVE mode |
| 06 | Driver History | `GET /driver-history/{id}` | 200 | membership + current trace |
| 07 | Intraday | `GET /intraday-signals/summary` | 200 | 3097ms, 310 monitored |

---

## TAREA 9 — GO / NO-GO

### Decision: **GO — Operable**

Un operador puede trabajar hoy. El pipeline completo funciona:

```
Today Action Plan (310 READY)
  → Build Queue (500 drivers en cola, idempotente)
  → Export READY (5 → campaign 146, LoopControl LIVE)
  → Control Loop (export registrado, sin duplicados)
  → Driver History (trace completo membership + aging)
  → Intraday Signals (monitoring activo, <3.1s)
```

### Bloqueos conocidos (no impiden operación)

| Issue | Impact | Severity |
|---|---|---|
| 190 HELD drivers | No exportables hasta asignar phone/channel | Medium — esperado |
| Intraday signals = 0 | Normal — signals se generan post-export con actividad Yango | Low — build asíncrono |
| Freshness WARNING (>24h snapshot) | Data de ayer, snapshot envejece | Low — daily refresh programado |
| Omniview serving integrity warning | 1 periodo week sin datos | Low — non-blocking, cascade programado |
