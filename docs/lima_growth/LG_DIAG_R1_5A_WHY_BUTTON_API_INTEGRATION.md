# LG-DIAG-R1.5A — Why Button API Integration

**Date:** 2026-06-08
**Motor:** Control Foundation / Diagnostic Hardening
**Phase:** LG-DIAG-R1.5A
**Status:** WHY BUTTON API INTEGRATION CERTIFIED

---

## 1. EXECUTIVE SUMMARY

**API INTEGRATION: CERTIFIED.**

Frontend API client functions created for all 3 diagnostic endpoints. Backend serving API serves from persisted trace tables. Code compiles. Build passes. Consumer integration layer ready.

---

## 2. CONSUMERS IDENTIFIED

| Screen | Has driver_id? | Integration Point |
|--------|:---:|-------------------|
| Execution Queue (table rows) | YES | Each queue row has driver_id |
| Programs (cards) | YES | Per-driver via program detail |
| Command Center (KPIs) | PARTIAL | Aggregate view, drill-down to driver |

---

## 3. FRONTEND API CLIENT

```javascript
// api.js — Diagnostic Trace (LG-DIAG-R1.5A)

getDriverDiagnosticTrace(driverId)
  → GET /yego-lima-growth/diagnostic-trace/{driverId}

getProgramTraceList(filters)
  → GET /yego-lima-growth/diagnostic-trace/program/list

getTransitionTraceList(filters)
  → GET /yego-lima-growth/diagnostic-trace/transition/list
```

All functions use existing API client with timeout=15s.

---

## 4. BACKEND SERVING API

| Endpoint | Source Table | Recalculation? |
|----------|-------------|:---:|
| GET /diagnostic-trace/{id} | program_decision_trace + state_transition_trace | **NO** |
| GET /diagnostic-trace/program/list | program_decision_trace | **NO** |
| GET /diagnostic-trace/transition/list | state_transition_trace | **NO** |

Zero runtime logic. Pure read from persisted data.

---

## 5. RESPONSE CONTRACT

```json
{
  "driver_id": "87035c62...",
  "found": true,
  "program_trace": {
    "selected_program": "CHURN_PREVENTION",
    "selection_reason": "HIGHER_PRIORITY",
    "eligible_programs": ["ACTIVE_GROWTH", "CHURN_PREVENTION"],
    "opportunity_score": 100.58,
    "final_rank": 1749,
    "policy_version": "v1"
  },
  "transition_trace": {
    "transition_type": "RETENTION:HEALTHY->CHURN_RISK",
    "trigger_reason": "churn_risk_flag",
    "rule_deltas": [{"rule": "RET_CHURN_RISK", "before": "FAIL", "after": "MATCH"}]
  }
}
```

---

## 6. ERROR HANDLING

| State | Behavior |
|-------|----------|
| Driver not found | `found: false` |
| No trace for driver | Empty program_trace / transition_trace |
| API error | Standard axios error handling |
| Empty results | Empty records array, total=0 |

---

## 7. FILES MODIFIED

| File | Change |
|------|--------|
| `frontend/src/services/api.js` | +3 diagnostic API functions |

---

## 8. QA

| Check | Result |
|-------|:---:|
| npm run build | PASS (29.77s) |
| python -m compileall | OK |
| API functions added | YES (3) |
| Backend serving endpoints | YES (3) |
| Reads from persisted tables | YES |
| No recalculation | YES |

---

## 9. FINAL VERDICT

```
WHY BUTTON API INTEGRATION CERTIFIED
```

**Frontend can now call diagnostic APIs. Backend serves from persisted traces. Integration layer complete. UI "Why?" button implementation is the next step (backlogged).**
