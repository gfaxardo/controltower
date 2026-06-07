# LG-UX-R2.9G.3 — Daily Refresh Pipeline & Runtime Reliability

**Date:** 2026-06-06
**Phase:** LG-UX-R2.9G.3 Daily Refresh Pipeline & Runtime Reliability
**Prior:** R2.9G.2 Visual Certification Mismatch Incident (invalidated)

---

## 1. EXECUTIVE SUMMARY

**DAILY REFRESH FOUNDATION CERTIFIED.**

Se descubrio que el pipeline diario de Lima Growth EXISTE (15 pasos, `yego_lima_daily_pipeline_service.py`) pero nunca fue ejecutado automaticamente. Se creo:

- Orquestador que envuelve los servicios existentes
- Run log + step log tables
- Endpoints de status/run/history
- Deteccion de operational date vs today action date
- UI visibility (freshness en header, operational date visible)
- Scheduler backlog

---

## 2. REFRESH AUDIT: WHAT EXISTS

| Element | Status |
|---------|:---:|
| Daily pipeline (15 steps) | EXISTS (`yego_lima_daily_pipeline_service.py`) |
| Individual build endpoints | EXIST (pipeline, state, lab routers) |
| Bootstrap script | EXISTS (`run_lima_growth_bootstrap.py`) |
| APScheduler in main.py | EXISTS (Omniview only, no Lima Growth jobs) |
| LoopControl auto-export | SETTINGS only (not wired) |
| Run log tracking | **CREATED** (R2.9G.3) |
| Refresh orchestrator | **CREATED** (R2.9G.3) |
| Automatic scheduler | **NOT IMPLEMENTED** (backlog) |

---

## 3. WHAT WAS MISSING

1. No run log (now: `yego_lima_refresh_run_log` + `yego_lima_refresh_step_log`)
2. No orchestrator (now: `yego_lima_daily_refresh_service.py`)
3. No endpoint to check/trigger refresh (now: `/refresh/status`, `/refresh/run`, `/refresh/history`)
4. No operational date detection (now: `/refresh/operational-date`)
5. No UI visibility for freshness/data age
6. No scheduler (backlog created)

---

## 4. OPERATIONAL DATE CONTRACT

```
operational_data_date = latest date with complete data (2026-06-02)
today_action_date = today's date for action planning (2026-06-06)
```

UI shows both: "Fecha data: 2026-06-02" + freshness status.

---

## 5. PIPELINE STEPS

| Step | Status |
|------|:---:|
| detect_operational_date | IMPLEMENTED |
| validate_source_readiness | IMPLEMENTED |
| build_assignment_queue | IMPLEMENTED (wraps existing) |
| build_prioritized_opportunities | IMPLEMENTED (wraps existing) |
| Full 15-step daily pipeline | EXISTS (manual trigger) |

---

## 6. RUN LOG

Tables created:
- `growth.yego_lima_refresh_run_log` (run status, dates, warnings, summary)
- `growth.yego_lima_refresh_step_log` (per-step status, rows, errors, remediation)

---

## 7. ENDPOINTS

| Method | Path | Purpose |
|--------|------|---------|
| GET | /yego-lima-growth/refresh/status | Current refresh status + freshness |
| POST | /yego-lima-growth/refresh/run | Trigger manual refresh |
| GET | /yego-lima-growth/refresh/history | Past runs |
| GET | /yego-lima-growth/refresh/operational-date | Latest data date |

---

## 8. UI VISIBILITY

Header shows:
- "Fecha data: 2026-06-02"
- Freshness status (STALE/WARNING visible in yellow)
- Universe + READY + HELD counts

---

## 9. SCHEDULER BACKLOG

Created: `docs/backlog/BACKLOG_LIMA_GROWTH_DAILY_REFRESH_SCHEDULER.md`

- Daily cron at 03:00 America/Lima
- Gated by `LIMA_GROWTH_DAILY_REFRESH_ENABLED`
- Retry policy (2 retries, 30min delay)
- Alerting on failure

---

## 10. ROUTING / TIMEOUTS

- Frontend uses port 5174 (5173 occupied)
- Backend port 8000
- Lima Growth URL: `/lima-growth` (SPA routing)
- API timeouts: 30s default, backend responds within 10s

---

## 11. ARCHIVOS CREADOS / MODIFICADOS

### Creados:
| Archivo | Proposito |
|---------|-----------|
| `backend/app/services/yego_lima_daily_refresh_service.py` | Refresh orchestrator |
| `backend/app/routers/yego_lima_daily_refresh.py` | Refresh router |
| `docs/backlog/BACKLOG_LIMA_GROWTH_DAILY_REFRESH_SCHEDULER.md` | Scheduler backlog |
| `docs/lima_growth/LG_UX_R2_9G_3_DAILY_REFRESH_PIPELINE_RUNTIME_RELIABILITY.md` | Este documento |
| DB: `growth.yego_lima_refresh_run_log` | Run log table |
| DB: `growth.yego_lima_refresh_step_log` | Step log table |

### Modificados:
| Archivo | Cambio |
|---------|--------|
| `backend/app/main.py` | +daily_refresh router |
| `frontend/.../LimaGrowthDashboardV2.jsx` | +operational date label + freshness in header |

---

## 12. QA

| Check | Resultado |
|-------|:---------:|
| Run log table created | YES |
| Step log table created | YES |
| Refresh orchestrator compiles | OK |
| 4 endpoints functional | YES |
| Backend compile | OK |
| Frontend build | PASS |
| Operational date detected | 2026-06-02 |
| Steps NOT_IMPLEMENTED | None (all wrap existing services) |
| Scheduler backlog created | YES |

---

## 13. VEREDICTO

```
DAILY REFRESH FOUNDATION CERTIFIED
```

**Evidencia:**
- Pipeline existe (15 steps, manual) — documentado
- Orquestador creado (wraps existing services)
- Run log + step log tables funcionales
- 4 endpoints para status/run/history
- UI muestra operational date + freshness
- Scheduler backlog registrado para automatizacion futura
- GO para continuar roadmap (R3.1 Program Registry Foundation cuando se resuelva routing)
