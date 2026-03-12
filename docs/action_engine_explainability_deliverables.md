# Action Engine + Behavioral Alerts — Explainability Deliverables (Phase 18)

**Project:** YEGO Control Tower  
**Date:** 2026-03-11

---

## 1) Implementation

- Backend: behavior_alerts_service and action_engine_service expose weeks_declining_consecutively and weeks_rising_consecutively (and active_weeks_in_window where applicable).
- Migration 088: v_action_engine_driver_base adds weeks_rising_consecutively; dependent views recreated.
- Frontend: explainabilitySemantics.js (getBehaviorDirection, getPersistenceLabel, getDeltaPctColor, getDecisionContextLabel, colors, COHORT_RATIONALE). BehavioralAlertsView and ActionEngineView use these for Estado conductual, Persistencia, time context, rationale, and semantic colors.

---

## 2–6) Documents

| Doc | Path |
|-----|------|
| Scan | docs/action_engine_explainability_scan.md |
| Logic | docs/action_engine_explainability_logic.md |
| UI wiring report | docs/action_engine_explainability_ui_wiring_report.md |
| Render validation | docs/action_engine_explainability_render_validation.md |
| Fix log | docs/action_engine_explainability_fix_log.md |
| Final QA | docs/action_engine_explainability_final_qa.md |

---

## 7) Files touched

**Backend**

- backend/app/services/behavior_alerts_service.py — SELECT weeks_declining_consecutively, weeks_rising_consecutively in drivers and driver_detail.
- backend/app/services/action_engine_service.py — SELECT active_weeks_in_window, weeks_declining_consecutively, weeks_rising_consecutively in cohort_detail and export.
- backend/alembic/versions/088_action_engine_driver_base_weeks_rising.py — Add weeks_rising_consecutively to v_action_engine_driver_base; DROP/CREATE + recreate dependent views.

**Frontend**

- frontend/src/constants/explainabilitySemantics.js — New file.
- frontend/src/components/BehavioralAlertsView.jsx — Estado conductual, Persistencia, time context, help panel, driver detail, semantic colors.
- frontend/src/components/ActionEngineView.jsx — Decision context, rationale on cards and drilldown, Estado conductual, Persistencia in drilldown, semantic colors, help panel.

**Docs**

- docs/action_engine_explainability_scan.md
- docs/action_engine_explainability_logic.md
- docs/action_engine_explainability_ui_wiring_report.md
- docs/action_engine_explainability_render_validation.md
- docs/action_engine_explainability_fix_log.md
- docs/action_engine_explainability_final_qa.md
- docs/action_engine_explainability_deliverables.md (this file)

---

## 8) Manual testing steps

1. **Backend:** Run `alembic upgrade 088` in backend; ensure no errors.
2. **Behavioral Alerts:** Open Control Tower → Behavioral Alerts. Check: time context line above table; columns Estado conductual and Persistencia; Delta % colored; help panel with Segmento, Baseline, Delta, Tendencia, Persistencia, Riesgo. Open driver detail: "Por qué se destaca", Estado conductual, Persistencia, colored delta.
3. **Action Engine:** Open Action Engine → Cohortes y acciones. Check: time context; recommendation cards with week, "Base: …", "Cambio promedio: …", rationale; cohort table "Objetivo / Rationale"; drilldown header with rationale; table with Estado conductual, Persistencia, colored delta and alert badges; help panel.
4. **Filters:** Change date/park/city filters; confirm KPIs and tables update.
5. **Export:** Export cohort/drivers; confirm file downloads and contains expected columns.

---

## 9) Screenshots or validation notes

- Validation steps and expected outcomes are in docs/action_engine_explainability_render_validation.md.
- Screenshots can be added to that doc or to this deliverables doc if the environment allows.

---

## 10) Risks / minor pending items

- **Migration 088 mandatory:** If 088 is not applied, action_engine cohort_detail and export will fail when selecting weeks_rising_consecutively. Ensure 088 is run in all environments (dev/staging/prod).
- **MV behavior_alerts:** weeks_rising_consecutively must exist in ops.mv_driver_behavior_alerts_weekly; if not, add it in a separate migration and ensure the service SELECT matches.
- **Export columns:** Export may be extended later to include behavior_direction and persistence_label as derived columns; current implementation relies on raw weeks_* in backend and derivation in frontend for UI only.
- **Baseline weeks:** Action Engine uses BASELINE_WEEKS = 6 in the frontend label; if the backend uses a different window, consider making it configurable or syncing the value from API.
