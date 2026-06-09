# LG-DIAG-R1.4A — Diagnostic Trace Serving API

**Date:** 2026-06-08
**Motor:** Control Foundation / Diagnostic Hardening
**Phase:** LG-DIAG-R1.4A
**Status:** DIAGNOSTIC TRACE SERVING API CERTIFIED

---

## 1. EXECUTIVE SUMMARY

**SERVING API: CERTIFIED.**

3 endpoints serve diagnostic traces directly from persisted tables. No recalculation. No runtime logic. Pagination included. Reads from migrated + backfilled data (5,558 decision traces + 1,205 transition traces).

---

## 2. ENDPOINTS

| Method | Path | Description |
|--------|------|-------------|
| GET | `/yego-lima-growth/diagnostic-trace/{driver_id}` | Full diagnostic view for one driver |
| GET | `/yego-lima-growth/diagnostic-trace/program/list?filters` | Decision traces (paginated) |
| GET | `/yego-lima-growth/diagnostic-trace/transition/list?filters` | Transition traces (paginated) |

### Driver Diagnostic Response

```json
{
  "driver_id": "...",
  "program_trace": {
    "selected_program": "CHURN_PREVENTION",
    "selection_reason": "HIGHER_PRIORITY",
    "eligible_programs": ["ACTIVE_GROWTH", "CHURN_PREVENTION"],
    "opportunity_score": 100.58,
    "final_rank": 1749,
    "policy_version": "v1",
    "run_id": "diag_e3d1b134"
  },
  "transition_trace": {
    "transition_type": "RETENTION:HEALTHY->CHURN_RISK",
    "trigger_reason": "churn_risk_flag",
    "rule_deltas": [{"rule": "RET_CHURN_RISK", "before": "FAIL", "after": "MATCH"}],
    "policy_version": "v1"
  }
}
```

---

## 3. FILTERS

| Endpoint | Available Filters |
|----------|------------------|
| program/list | driver_id, snapshot_date, selected_program, run_id |
| transition/list | driver_id, snapshot_before, snapshot_after, run_id |

All support: `limit` (1-1000), `offset` (0+).

---

## 4. NO RECALCULATION

All endpoints read directly from:
- `growth.yego_lima_program_decision_trace` (backfilled 5,558 rows)
- `growth.yego_lima_state_transition_trace` (backfilled 1,205 rows)

Zero runtime computation. Zero JOINs to operational tables. Pure serving.

---

## 5. FILES CREATED

| File | Purpose |
|------|---------|
| `backend/app/services/yego_lima_diagnostic_trace_service.py` | Serving service |
| `backend/app/routers/yego_lima_diagnostic_trace.py` | Serving endpoints |
| `docs/...LG_DIAG_R1_4A_DIAGNOSTIC_TRACE_SERVING_API.md` | This document |

---

## 6. QA

| Check | Result |
|-------|:---:|
| npm run build | PASS (11.06s) |
| python -m compileall | OK |
| Reads from persisted tables only | YES |
| No recalculation | YES |
| Pagination | YES |
| Indexes present | YES (4 per table) |

---

## 7. FINAL VERDICT

```
DIAGNOSTIC TRACE SERVING API CERTIFIED
```

**WHY AM I HERE? WHY THIS PROGRAM? WHY DID I MOVE? WHAT RULE CHANGED? — All answerable from persisted traces via serving API.**
