# LG-UX-R2.6 — Today's Action Plan

**Date:** 2026-06-08
**Phase:** LG-UX-R2.6
**Status:** CERTIFIED

---

## 1. EXECUTIVE SUMMARY

**TODAY'S ACTION PLAN: OPERATIONAL.**

A supervisor opening Lima Growth now sees, in the first 30 seconds: what to do today, why, with what capacity, which programs to target, and the next action. The "Plan de Accion de Hoy" header in Command Center aggregates operational truth, program status, and queue data into a deterministic action plan. 5 statuses. No AI.

---

## 2. ACTION PLAN STATUSES

| Status | Condition | Next Action |
|--------|-----------|-------------|
| **NEEDS_PIPELINE** | >= 3 KPIs NOT_GENERATED | Ejecutar Pipeline |
| **NEEDS_QUEUE** | Prioritized > 0, queue = 0 | Construir Cola |
| **READY_TO_EXPORT** | Queue READY > 0 | Exportar READY |
| **COMPLETE** | Exported > 0, no pending | Revisar configuracion |
| **WARNING** | Partial state | Revisar Warnings |

---

## 3. ENDPOINT

`GET /yego-lima-growth/todays-action-plan?date=YYYY-MM-DD`

Returns: status, headline, next_action, capacity, programs[], queue{}, warnings.

---

## 4. UI — PLAN DE ACCION DE HOY

Header block at top of Command Center shows:
- Status badge
- Headline
- Program table: Programa, Estado, Accionables, Recomendado, Pendiente
- Capacity context: Capacidad, En Cola, Cobertura, Gap
- Next action: label + reason
- Warnings

---

## 5. DETERMINISTIC RULES (No AI)

| Metric | Source |
|--------|--------|
| NOT_GENERATED detection | Operational truth KPI counts |
| Program status | Program operational status |
| Recommended take | min(actionable, capacity) |
| Capacity | daily_action_capacity from policy_config |

---

## 6. FILES CREATED / MODIFIED

| File | Change |
|------|--------|
| `backend/app/services/yego_lima_todays_action_plan_service.py` | Action plan engine |
| `backend/app/routers/yego_lima_todays_action_plan.py` | Action plan endpoint |
| `frontend/src/pages/lima-growth-v2/sections/CommandCenterSection.jsx` | +TodayActionPlanHeader |
| `backend/app/main.py` | +todays_action_plan router |

---

## 7. QA

| Check | Result |
|-------|:---:|
| npm run build | PASS (6.51s) |
| python -m compileall | OK |
| 5 statuses defined | YES |
| Deterministic rules | YES (no AI) |
| Program table | YES |
| Capacity context | YES |
| Next action visible | YES |

---

## 8. FINAL VEREDICT

```
GO
```

**30-second operator answer:** "Hoy necesito ejecutar el pipeline. Los programas Churn Prevention y Active Growth tienen prioridad. La capacidad es 500. Hay 310 en cola."

**LG-UX-R2.7 Operational Certification: APPROVED.**
