# Action Engine + Visual Layer — Validation (Phase 13, Step 10)

**Project:** YEGO Control Tower  
**Date:** 2026-03-11

---

## Verification checklist

### Action Engine

| Check | Expected |
|-------|----------|
| Action Engine loads correctly | Tab "Cohortes y acciones" loads; KPIs and cohort table appear. |
| Endpoints used | Only `/ops/action-engine/summary`, `/cohorts`, `/cohort-detail`, `/recommendations`, `/export`. |
| KPIs show color signals | Tasa reactivación, Tasa conversión, Riesgo bajada % with green/amber/red by threshold. Cohortes alta prioridad with red when > 0. |
| Time range filter | Dropdown "Rango temporal" with 7, 14, 30, 60 days and "Rango personalizado". Selecting preset updates from/to; "Custom" shows date pickers. |
| Cohort table | Column groups: "Cohort info", "Comportamiento", "Acciones". Row spacing (py-3). Column "Score" with 0–100 and color (80–100 red, 50–79 amber, 0–49 green). |
| Filters affect queries | Changing from/to, country, city, park, segment, priority refetches summary, recommendations, cohorts. |
| Export works | "Exportar CSV" link opens/ downloads action-engine export with current filters. |

### Top Driver Behavior

| Check | Expected |
|-------|----------|
| Top Driver Behavior loads correctly | Sub-tab loads; summary, benchmarks, patterns, playbook insights appear. |
| Endpoints used | Only `/ops/top-driver-behavior/summary`, `/benchmarks`, `/patterns`, `/playbook-insights`, `/export`. |
| Time range | Same from/to as Action Engine; preset applies to both. |
| Export works | "Exportar Top Driver Behavior" link works. |

### Behavioral Alerts

| Check | Expected |
|-------|----------|
| Alerts load correctly | Table of drivers with alert type, segment, trips, delta, etc. |
| Severity tags | Column "Severidad" with badges: CRITICAL (red), WARNING (amber), INFO (blue). |
| Time range filter | Same preset dropdown (7, 14, 30, 60 days, Custom). |
| Export Drivers | Button "Exportar conductores (CSV filtrado)" downloads CSV with driver_id, driver_name, park, segment, alert_type, severity, trips_last_week, trips_baseline, delta_percent, recommended_action for current page/filter. |
| Driver detail modal | "Ver detalle" opens modal with "Driver Behavior Timeline — Viajes últimas 8 semanas" line chart (trips + segment history). |

### General

| Check | Expected |
|-------|----------|
| No backend/schema changes | No SQL, migrations, or view changes in this phase. |
| No legacy endpoints | No use of `/controltower/*` for Action Engine or Top Driver Behavior. |

---

## Manual steps

1. Open Control Tower → **Action Engine**. Confirm KPIs (including colored conversion/reactivation/downgrade rates), time range dropdown, and cohort table with Score column and grouped headers.
2. Switch to **Top Driver Behavior**. Confirm data loads and export link works.
3. Open **Behavioral Alerts**. Confirm time range preset, Severidad column, "Exportar conductores (CSV filtrado)" download, and driver detail modal with timeline chart.
4. Change time range to 7 days; confirm dates update and data refetches.
5. Select "Rango personalizado" and set from/to; confirm requests use new range.
