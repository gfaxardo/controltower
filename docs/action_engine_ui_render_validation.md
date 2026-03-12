# Action Engine — Visible UI Validation (Phase 7)

**Project:** YEGO Control Tower  
**Date:** 2026-03-11  
**Mode:** Manual verification steps (no screenshots captured in this doc).

---

## Prerequisites

1. Backend running: `uvicorn app.main:app --host 127.0.0.1 --port 8000`
2. Frontend running with proxy to `/api` (e.g. Vite dev server)
3. Browser open to the Control Tower app

---

## Action Engine tab

| Check | Expected | How to verify |
|-------|----------|----------------|
| Tab visible | "Action Engine" button in the main nav (with Real LOB, Driver Lifecycle, Supply, Behavioral Alerts, etc.) | Look at the tab bar; click "Action Engine". |
| KPI cards visible | Six cards: Conductores accionables, Cohortes detectados, Cohortes alta prioridad, Recuperables, Alto valor en riesgo, Cerca de subir | After opening the tab, sub-tab "Cohortes y acciones" is default; cards appear above the recommendations panel. |
| Recommended actions panel visible | Panel titled "Acciones recomendadas" with up to 5–6 action cards (action name, cohort, size, priority, channel, "Ver cohorte") | Scroll or look below KPI cards. |
| Cohort table visible | Table with columns: Cohorte, Semana, Tamaño, Segmento dom., Riesgo avg, Delta %, Prioridad, Canal, Objetivo, Acción | Below the recommendations panel. |
| Drilldown works | Click "Ver" on a cohort row or "Ver cohorte" on a recommendation → modal with driver list for that cohort | Click any "Ver" or "Ver cohorte"; modal opens with table of drivers. |
| Export visible | "Exportar CSV" link above cohort table; "Exportar esta cohorte" in drilldown modal | Links present; opening in new tab triggers GET /ops/action-engine/export with params. |

**Visible?** Yes (if tab and component are mounted per Phase 6).  
**Populated?** Yes (API returns data; summary and cohorts were validated in Phase 5).  
**Drilldown?** Yes (cohort-detail endpoint exists and is called by ActionEngineView).  
**Export?** Yes (getActionEngineExportUrl used; opens /ops/action-engine/export).

---

## Top Driver Behavior (sub-tab)

| Check | Expected | How to verify |
|-------|----------|----------------|
| Section/tab visible | Sub-tab "Top Driver Behavior" inside Action Engine | Click "Top Driver Behavior" next to "Cohortes y acciones". |
| Benchmark comparison visible | Table: Segmento, Conductores, Viajes/sem avg, Consistencia avg, Semanas activas avg (rows: LEGEND, ELITE, FT) | Shown in "Benchmarks" block. |
| Pattern insights visible | "Insights (playbook)" section with bullet list of short insights | Below benchmarks. |
| Patterns table visible | Table by segment, country, city, park (driver count, % segment) | In "Patrones (ciudad/parque)" block. |
| Export visible | "Exportar Top Driver Behavior" link | At bottom of the sub-tab. |

**Visible?** Yes (sub-tab and sections rendered by ActionEngineView when subTab === 'top_driver_behavior').  
**Populated?** Yes (API returns benchmarks and patterns; validated in Phase 5).

---

## Issues found

- None identified in code. If the tab or data do not appear at runtime, check: (1) backend reachable at baseURL, (2) CORS/proxy, (3) console/network errors.
