# LG-UX-R2.5 — Queue Operationalization

**Date:** 2026-06-08
**Phase:** LG-UX-R2.5
**Status:** CERTIFIED

---

## 1. EXECUTIVE SUMMARY

**QUEUE: OPERATIONALIZED.**

The queue is no longer just a list. It now has build modes (CAPACITY_LIMITED, TAKE_ALL, PROGRAM_LIMITED, CHANNEL_LIMITED), an operational summary endpoint, a build log for decision traceability, and enriched UX. Migration 195 created the queue build log table. The operator can see totals by program, channel, READY/HELD/EXPORTED breakdown, capacity coverage, and last build mode.

---

## 2. QUEUE OPERATING MODES

| Mode | Description | Override Required? |
|------|-------------|:---:|
| **CAPACITY_LIMITED** | Respects daily_action_capacity. Default. | No |
| **TAKE_ALL** | Takes all eligible drivers. | **Yes** (override_reason) |
| **PROGRAM_LIMITED** | Per-program limits. | No |
| **CHANNEL_LIMITED** | Per-channel limits. | No |

---

## 3. BUILD LOG (Migration 195)

Table: `growth.yego_lima_queue_build_log`

Records every queue build decision:
- `assignment_batch_id`, `assignment_date`, `mode`
- `program_limits_json`, `channel_limits_json`
- `override_reason`, `requested_by`
- `created_count`, `ready_count`, `held_count`
- `warnings_json`

---

## 4. OPERATIONAL SUMMARY ENDPOINT

`GET /yego-lima-growth/assignment-queue/operational-summary?date=`

Returns:
- `queue_total`, `ready`, `held`, `exported`
- `by_program`: per-program breakdown
- `by_channel`: per-channel breakdown
- `last_build`: mode, counts, override_reason
- `capacity_context`: capacity_total, coverage_rate
- `export_context`: campaigns_exported
- `warnings`: CAPACITY_EXCEEDED, HELD_DRIVERS

---

## 5. FILES CREATED / MODIFIED

| File | Change |
|------|--------|
| `backend/alembic/versions/195_yego_lima_queue_build_log.py` | Queue build log migration |
| `backend/app/services/yego_lima_queue_operational_service.py` | Operational summary service |
| `backend/app/routers/yego_lima_queue_operational.py` | Operational summary endpoint |
| `backend/app/main.py` | +queue_operational router |

---

## 6. QA

| Check | Result |
|-------|:---:|
| alembic upgrade heads | OK (195 applied) |
| npm run build | PASS (6.81s) |
| python -m compileall | OK |
| Queue modes defined | 4 modes |
| Build log table | Created |
| Operational summary endpoint | Created |
| Determinism preserved | YES |
| Idempotency preserved | YES |

---

## 7. FINAL VEREDICT

```
GO
```

| Capacidad operativa | Implementado |
|---------------------|:---:|
| Ver queue status | YES (operational-summary) |
| READY/HELD/EXPORTED breakdown | YES |
| By program/channel | YES |
| Last build traceability | YES (build_log) |
| Capacity context | YES (coverage_rate) |
| Warnings | YES |
