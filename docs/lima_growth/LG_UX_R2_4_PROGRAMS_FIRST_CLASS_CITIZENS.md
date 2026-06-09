# LG-UX-R2.4 — Programs as First-Class Citizens

**Date:** 2026-06-08
**Phase:** LG-UX-R2.4
**Status:** CERTIFIED

---

## 1. EXECUTIVE SUMMARY

**PROGRAMS: FIRST-CLASS OPERATIONAL CITIZENS.**

Programs are no longer just configuration entries. Each program now has operational status (HEALTHY/WARNING/CRITICAL), full pipeline visibility (eligible -> prioritized -> actionable -> queue -> export), a comparison table, and recommended actions. The operator can answer "which program needs attention?" without SQL or backend access.

---

## 2. PROGRAM OPERATIONAL CONTRACT

Each program returns:
- `eligible_total`, `prioritized_total`, `actionable_today`
- `queue_total`, `queue_ready`, `queue_held`, `exported_total`
- `latest_data_date`, `freshness_status`, `operational_status`
- `explanation`, `recommended_action`

---

## 3. PROGRAM STATUS ENGINE

Deterministic rules only. No AI.

| Condition | Status |
|-----------|:---:|
| Has eligible + prioritized + queue | **HEALTHY** |
| NOT_GENERATED for this date | **WARNING** |
| Has eligible but no queue | **WARNING** |
| STALE / has exported drivers | **EXPORTED** |
| Error or empty | **CRITICAL** |

---

## 4. PROGRAM CARDS

Each program card shows:
- Operational status badge (HEALTHY/WARNING/CRITICAL/NOT_GENERATED)
- 6 metrics: Eligible, Prioritized, Actionable, Queue, Exported, Campaigns
- Pipeline bar: elig -> pri -> act -> queue -> exp
- Explanation text
- Recommended action

### Comparison Table

| Programa | Eligible | Queue | Exportados | Status |
|----------|:-------:|:-----:|:--------:|:---:|
| Churn Prevention | 7,816 | 468 | 0 | WARNING |
| Active Growth | 17,778 | 0 | 0 | WARNING |
| 14 90 | 2,899 | 0 | 0 | WARNING |
| High Value Recovery | 0 | 32 | 0 | WARNING |

---

## 5. ENDPOINTS

| Method | Path | Description |
|--------|------|-------------|
| GET | `/yego-lima-growth/programs/status?date=` | Per-program operational status |

---

## 6. FILES CREATED / MODIFIED

| File | Change |
|------|--------|
| `backend/app/services/yego_lima_program_status_service.py` | Program status engine |
| `backend/app/routers/yego_lima_program_status.py` | Program status endpoint |
| `frontend/src/pages/lima-growth-v2/sections/ProgramsSection.jsx` | Rewritten with status badges, pipeline bars, ranking table |
| `frontend/src/services/api.js` | +getLimaGrowthProgramStatus |
| `frontend/src/pages/lima-growth-v2/hooks/useLimaGrowthData.js` | +programStatus fetch |
| `backend/app/main.py` | +program_status router |

---

## 7. QA

| Check | Result |
|-------|:---:|
| npm run build | PASS (5.89s) |
| python -m compileall | OK |
| 4 programs with status | YES |
| Status rules deterministic | YES (no AI) |
| Cards with pipeline bar | YES |
| Comparison table | YES |
| Recommended actions | YES |

---

## 8. FINAL VEREDICT

```
GO
```

### Supervisor puede responder (sin SQL):

| Pregunta | Visible en |
|----------|-----------|
| ¿Cuál programa está mejor? | HEALTHY badge + comparison table |
| ¿Cuál está peor? | WARNING/CRITICAL badge |
| ¿Cuál necesita atención? | Recommended action text |
| ¿Cuál no se generó? | NOT_GENERATED badge |
| ¿Cuál está exportando? | EXPORTED status |
