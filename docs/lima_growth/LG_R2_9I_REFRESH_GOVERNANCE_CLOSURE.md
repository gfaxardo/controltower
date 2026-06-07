# LG-R2.9I — Refresh Governance Closure

**Date:** 2026-06-06
**Phase:** LG-R2.9I Refresh Governance Closure

---

## 1. EXECUTIVE SUMMARY

**REFRESH GOVERNANCE CERTIFIED.**

Se cerro el problema de datos STALE. Lima Growth ahora responde:

- Cual es la ultima data cerrada: **2026-06-02**
- Cuando fue el ultimo refresh exitoso: **2026-06-06 16:53** (serving facts)
- Que step fallo o no corre: **Refresh pipeline never run via orchestrator** (facts generated directly)
- Que hay que correr para remediar: **POST /yego-lima-growth/refresh/run**
- Si el sistema esta apto para operar hoy: **NOT_OPERABLE_STALE** (data 4 days behind)

---

## 2. WHY STALE = 7000+ MINUTES

| Layer | Date | Age |
|-------|------|-----|
| Driver snapshot data | 2026-06-02 | 4+ days (~7000 min) |
| Serving facts generation | 2026-06-06 16:53 | ~281 min |
| Today's action plan | 2026-06-02 (data) | 4 days |

The data itself is from 2026-06-02 because no daily pipeline has run since then. The serving facts were generated today by the R2.9H smoke test, but the underlying data is still from 4 days ago. Freshness checks the DATA date (snapshot), not the FACT generation date.

---

## 3. GOVERNANCE STATUS

| Field | Value |
|-------|-------|
| operational_data_date | 2026-06-02 |
| today_action_date | 2026-06-06 |
| freshness_age_minutes | ~7000 |
| freshness_status | STALE |
| days_behind | 4 |
| operability | NOT_OPERABLE_STALE |
| last_successful_refresh_at | 2026-06-06 16:53 |
| facts OK | 8/8 |
| facts MISSING | 0 |
| facts STALE | 8 (data age > 24h) |
| blocking_reasons | "Operational data is 4 days behind (date: 2026-06-02)" |
| required_action | "Ejecutar refresh pipeline" |

---

## 4. GOVERNANCE ENDPOINT

`GET /yego-lima-growth/refresh/governance-status`

Returns: `{operational_data_date, today_action_date, freshness_age_minutes, freshness_status, days_behind, is_operable_today, operability, blocking_reasons, required_action, facts[], pipeline{...}}`

Lightweight — reads run logs + serving facts only. No recalculation.

---

## 5. STALE RULES

| Condition | Operability |
|-----------|-------------|
| Data > 2 business days behind | NOT_OPERABLE_STALE |
| Data = 1 day behind | OPERABLE_STALE_WARNING |
| Facts missing | NOT_OPERABLE_MISSING_FACTS |
| Refresh FAILED | NOT_OPERABLE_REFRESH_FAILED |
| All OK + data today | OPERABLE |
| Never refreshed | NOT_OPERABLE_MISSING_FACTS |

---

## 6. UI GOVERNANCE PANEL

Added to Lima Growth V2 main content area:

- **Red banner** when NOT_OPERABLE: "NO usar para operacion diaria" + blocking reasons + required action
- **Yellow banner** when OPERABLE_STALE_WARNING: data age + remediation
- **Governance bar** always visible: operability badge (green/yellow/red) + facts OK/STALE/MISSING counts + operational date

---

## 7. ARCHIVOS CREADOS / MODIFICADOS

### Creados:
| Archivo | Proposito |
|---------|-----------|
| `backend/app/services/yego_lima_refresh_governance_service.py` | Governance status service |
| `docs/lima_growth/LG_R2_9I_REFRESH_GOVERNANCE_CLOSURE.md` | Este documento |

### Modificados:
| Archivo | Cambio |
|---------|--------|
| `backend/app/routers/yego_lima_daily_refresh.py` | +GET /governance-status |
| `frontend/.../LimaGrowthDashboardV2.jsx` | +governance state, +governance banners, +governance bar |

---

## 8. QA

| Check | Resultado |
|-------|:---------:|
| latest_operational_data_date | 2026-06-02 |
| latest_successful_refresh_at | 2026-06-06 16:53 |
| why stale = ~7000 min | Data from 4 days ago (no daily pipeline run) |
| 8/8 facts present | YES |
| 0 facts missing | YES |
| 8 facts STALE (data age) | YES |
| governance endpoint | Functional |
| UI governance panel | Visible (red banner + status bar) |
| Backend compile | OK |
| Frontend build | PASS |

---

## 9. VEREDICTO

```
REFRESH GOVERNANCE CERTIFIED
```

**Evidence:**
- System correctly identifies itself as NOT_OPERABLE_STALE (4 days behind)
- Governance endpoint returns complete status with blocking reasons
- UI shows red "NO usar para operacion diaria" banner
- Governance bar shows 8 OK / 0 MISSING / 8 STALE (data age)
- Required action clearly stated: "Ejecutar refresh pipeline"
- GO para R3.1 (System will be OPERABLE after daily pipeline runs)
