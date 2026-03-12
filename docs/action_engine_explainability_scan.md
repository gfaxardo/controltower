# Action Engine + Behavioral Alerts — Explainability & UX Upgrade Scan (Phase 0)

**Project:** YEGO Control Tower  
**Date:** 2026-03-11  
**Mode:** Read-only. No implementation before finishing this scan.

---

## A) Existing visible UI

### Behavioral Alerts tab

| Element | Location | Current state |
|--------|----------|----------------|
| Title / intro | BehavioralAlertsView.jsx | "Behavioral Alerts" + short paragraph (desviación vs línea base). |
| Filters | Same | Desde/Hasta, Ventana baseline (4/6/8), País, Ciudad, Park, Segmento actual, Tipo movimiento, Tipo alerta, Severidad, Banda de riesgo. |
| KPI cards | Same | 8 cards: Conductores monitoreados, Alto riesgo, Riesgo medio, Caídas críticas, Caídas moderadas, Recuperaciones fuertes, Erosión silenciosa, Alta volatilidad. No explain "why" or comparison period. |
| Insight panel | Same | Single text block (insight_text). No time context. |
| Help / glossary | Same | Collapsible "Ver explicación: Segmento, Movimiento, Línea base, Driver Risk Score". Good content but no Delta, Tendencia, or "última semana vs baseline". |
| Export | Same | CSV / Excel links. |
| Alerts table | Same | Conductor, País, Ciudad, Park, Segmento, Viajes sem., Base avg, Δ abs, Δ %, Alerta, Severidad, Risk Score, Risk Band, Tendencia (↑/↓/→), Acción (Ver detalle). No "Estado conductual", no "Persistencia", no "Semana analizada", no baseline window label. |
| Driver drilldown modal | Same | "Detalle conductor" + "Por qué se destaca" (risk_reasons) + table Semana, Viajes, Segmento, Base, Δ %, Alerta. No "Estado conductual", no "Desde hace X semanas", no explicit "última semana vs baseline". |

### Action Engine tab

| Element | Location | Current state |
|--------|----------|----------------|
| Sub-tabs | ActionEngineView.jsx | "Cohortes y acciones" | "Top Driver Behavior". |
| Filters | Same | Desde, Hasta, País, Ciudad, Parque, (Cohorts) Segmento, Prioridad. No "semana analizada" or "baseline" label. |
| KPI cards | Same | 6 cards (conductores accionables, cohortes detectados, alta prioridad, recuperables, alto valor en riesgo, cerca de subir). Numbers only. |
| Recommended actions panel | Same | Cards: action_name, cohort label + size, action_objective, priority badge, suggested_channel, "Ver cohorte". No "why now", no "decision basis", no "worsening/recovering", no week analyzed. |
| Cohort table | Same | Cohorte, Semana, Tamaño, Segmento dom., Riesgo avg, Delta %, Prioridad, Canal, Objetivo, Ver. No "Base de decisión", no "Persistencia", no "Estado conductual". |
| Cohort drilldown modal | Same | Title (cohort + week), count, table: Conductor, Segmento, Viajes sem., Baseline, Delta %, Riesgo, Alerta. No Estado conductual, Persistencia, Acción sugerida per row. |
| Help panel | Same | Short text: Action Engine vs cohort vs Top Driver Behavior. No Segmento/Baseline/Delta/Tendencia/Riesgo definitions. |
| Export | Same | CSV link (cohorts); "Exportar esta cohorte" in drilldown. |

---

## B) Existing data fields (backend / MV)

Available in **ops.mv_driver_behavior_alerts_weekly** / **ops.v_driver_behavior_alerts_weekly**:

| Field | In MV/View | In behavior_alerts drivers API | In behavior_alerts driver_detail API | In action_engine cohort_detail API |
|-------|------------|---------------------------------|--------------------------------------|------------------------------------|
| week_start, week_label | Yes | Yes | Yes | Yes |
| trips_current_week | Yes | Yes | Yes | Yes |
| avg_trips_baseline | Yes | Yes | Yes | Yes |
| delta_abs, delta_pct | Yes | Yes | Yes | Yes |
| risk_score, risk_band | Yes | Yes | Yes | Yes |
| alert_type, severity | Yes | Yes | Yes | Yes |
| movement_type | Yes | Yes | Yes | Yes |
| segment_current, segment_previous | Yes | Yes | Yes | Yes |
| weeks_declining_consecutively | Yes | **No** (not selected) | Yes | Yes (v_action_engine_driver_base has it) |
| weeks_rising_consecutively | Yes | **No** | **No** (not selected) | **No** (not in v_action_engine_driver_base SELECT) |
| active_weeks_in_window | Yes | No | No | Yes (driver_base) |

Baseline window: fixed in view (6 weeks); UI has selector 4/6/8 but backend/view may not be parameterized per request (documented as "view currently implements 6").

---

## C) Confusion points in visible UI

1. **Behavior direction unclear:** User sees Δ % and a trend icon (↑/↓) but not a clear "Empeorando / Mejorando / Estable / Volátil". Multiple metrics (delta, alert_type, severity) without a single semantic state.
2. **Comparison period not explicit:** No visible "Última semana cerrada vs baseline 6 semanas". Baseline window is in filters but not shown next to KPIs or table.
3. **"Since when" missing:** weeks_declining_consecutively / weeks_rising_consecutively exist in backend but are not shown in Behavioral Alerts table or in Action Engine drilldown. User cannot tell if change is one-week shock or sustained.
4. **Action rationale:** Recommendation cards show action_objective but not "why this population matters now" or "worsening vs recovering". Cohort table has "Objetivo" but no short rationale or decision basis.
5. **Alert labels vs numbers:** "Stable Performer" with a negative delta can feel contradictory without explanation. No companion label that ties alert_type to delta and trend.
6. **Dense tables:** Many columns with same weight; no semantic badges for direction/risk; Delta % and Risk not color-coded by sign/band.
7. **Cohort cards:** Current "recommended action" cards are compact but lack: week analyzed, decision basis, persistence, urgency clarity.
8. **Drilldown:** Raw numeric table; no "Estado conductual", "Persistencia", or "Acción sugerida" per row.
9. **Help panel:** Good start but missing: Delta, Tendencia/Estado conductual, comparación temporal, qué es "última semana vs baseline".
10. **Color semantics:** Alert and risk_band have colors; delta and trend do not. Inconsistent use of red/green for negative/positive delta.

---

## D) Existing UI wiring (active path)

### Behavioral Alerts

- **DB:** ops.mv_driver_behavior_alerts_weekly (list/export), ops.v_driver_behavior_alerts_weekly (summary).
- **Backend:** behavior_alerts_service.get_behavior_alerts_summary, get_behavior_alerts_drivers, get_behavior_alerts_driver_detail, get_behavior_alerts_export.
- **API:** GET /ops/behavior-alerts/summary, /drivers, /driver-detail, /export.
- **Frontend:** api.js getBehaviorAlertsSummary, getBehaviorAlertsDrivers, getBehaviorAlertsDriverDetail, getBehaviorAlertsExportUrl.
- **Component:** BehavioralAlertsView.jsx (mounted when activeTab === 'behavioral_alerts' in App.jsx).

### Action Engine

- **DB:** ops.v_action_engine_driver_base, ops.v_action_engine_cohorts_weekly, ops.v_action_engine_recommendations_weekly.
- **Backend:** action_engine_service (summary, cohorts, cohort_detail, recommendations, export).
- **API:** GET /ops/action-engine/summary, /cohorts, /cohort-detail, /recommendations, /export.
- **Frontend:** api.js getActionEngine*.
- **Component:** ActionEngineView.jsx (mounted when activeTab === 'action_engine' in App.jsx).

---

## Recommended UX changes (summary)

1. **Explainability model:** Separate visibly: (A) Current snapshot (trips_current_week, segment_current), (B) Baseline comparison (baseline_avg, delta_pct, label "vs baseline N semanas"), (C) Trend/persistence (consecutive declining/rising weeks, "Desde hace X semanas").
2. **Human-readable behavior direction:** Add "Estado conductual" (Empeorando, Mejorando, En recuperación, Estable, Volátil) derived from delta_pct + weeks_declining/rising + alert_type. Show in Behavioral Alerts table, driver detail, Action Engine recommendation cards, cohort table, drilldown.
3. **Time decision context:** Show "Última semana vs baseline 6 semanas", "N semanas consecutivas en caída", "Recuperación fuerte vs baseline", etc., on cards and in help.
4. **Persistence / "since when":** Add visible field: "3 semanas en deterioro", "2 semanas recuperándose". Use weeks_declining_consecutively / weeks_rising_consecutively.
5. **Alert label review:** Avoid contradiction; add short companion text where needed (e.g. "Estable en nivel bajo" when appropriate).
6. **Cohort card redesign:** Include: cohort name, driver count, week analyzed, decision basis, average change vs baseline, persistence summary, suggested action, channel, urgency.
7. **Recommended actions panel:** Add "why now", worsening/recovering, and keep title + brief explanation + key stats + CTA.
8. **Drilldown table:** Add columns: Estado conductual, Persistencia/Desde hace, Suggested action (or rationale). Semantic badges and delta color by sign.
9. **Semantic help panel:** Add definitions for Segmento, Baseline, Delta, Tendencia/Estado conductual, Riesgo, Action Engine, Behavioral Alerts (concise).
10. **Color system:** Red = worsening/negative/critical/high risk; green = improving/recovery/positive; gray = stable/neutral; amber = moderate; purple = volatile. Apply to delta %, badges, risk band, alert severity.
11. **Digestibility:** Primary: estado conductual, delta %, persistence, risk. Secondary: raw numbers. Group and space; short labels.
12. **Action rationale:** Surface short rationale on cohort cards, recommendation cards, and drilldown (e.g. "Evitar caída a segmento inferior").
13. **Filter/export:** Keep filters and export working; add optional columns (behavior_direction, persistence_label) to export if present in API.

---

## Files to touch (additive / non-destructive)

| File | Change |
|------|--------|
| backend/app/services/behavior_alerts_service.py | Add weeks_declining_consecutively, weeks_rising_consecutively to get_behavior_alerts_drivers SELECT; optionally add to export. |
| backend/app/services/action_engine_service.py | Add weeks_declining_consecutively, weeks_rising_consecutively to cohort_detail SELECT (add to view in migration if missing). |
| backend/alembic/versions/088_*.py (optional) | Add weeks_rising_consecutively to ops.v_action_engine_driver_base SELECT if not present. |
| frontend/src/components/BehavioralAlertsView.jsx | Add behavior direction, persistence, time context, color semantics, help text, drilldown columns, delta/risk colors. |
| frontend/src/components/ActionEngineView.jsx | Add behavior direction, time context, persistence on cards and table; redesign cohort/recommendation cards; drilldown columns; help panel; colors. |
| frontend/src/constants/explainabilitySemantics.js (new) | Centralize behavior_direction labels, color classes, persistence wording. |
| docs/action_engine_explainability_logic.md | Document derivation of behavior_direction and persistence labels. |

---

## Legacy paths / components that must NOT power the visible screen

- Do not use /controltower/* for Behavioral Alerts or Action Engine data.
- Do not replace BehavioralAlertsView or ActionEngineView with a different component without mounting the new one in App.jsx.
- Do not point Action Engine UI to /ops/behavior-alerts/* for cohort/recommendation data.
- After changes, the visible tabs must still call getBehaviorAlerts* and getActionEngine* (same API paths); only response shape may gain fields and UI must render them.

---

## Plan to verify active visible path after implementation

1. **Backend:** Confirm GET /ops/behavior-alerts/drivers includes weeks_declining_consecutively, weeks_rising_consecutively; GET /ops/action-engine/cohort-detail includes persistence fields where added.
2. **Frontend:** Grep for getBehaviorAlertsDrivers, getActionEngineCohortDetail; confirm BehavioralAlertsView and ActionEngineView import and use them (no duplicate or legacy service).
3. **App.jsx:** Confirm activeTab === 'behavioral_alerts' → BehavioralAlertsView, activeTab === 'action_engine' → ActionEngineView.
4. **Rendered UI:** Manually check Behavioral Alerts table shows "Estado conductual" and "Persistencia"; Action Engine cards show "Base de decisión" and persistence; drilldown shows new columns; colors apply to delta and risk.
5. **Document:** docs/action_engine_explainability_ui_wiring_report.md with chain DB → service → route → api.js → component → visible screen and proof that new fields are rendered.
