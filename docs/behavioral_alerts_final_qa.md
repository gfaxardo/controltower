# Behavioral Alerts — Final QA Checklist

**Date:** 2026-03-11  
**Phase:** 10 — Final QA checklist

---

- [ ] **Precheck completed** — docs/behavioral_alerts_precheck.md; inventory of migrations, routes, frontend, SQL objects.
- [ ] **Migrations verified/applied** — 081–085 present; two fixes applied to 085 (alias c, DROP VIEW + CREATE VIEW). User must run `alembic upgrade head` and confirm current = 085.
- [ ] **Refresh verified/run if needed** — docs/behavioral_alerts_refresh_report.md; refresh not run (migrations not at 085); optional for view-based reads, recommended for MV after upstream refresh.
- [ ] **Backend routes validated** — Routes and params documented; live hit not run (DB at 080). User to validate after 085.
- [ ] **Response fields validated** — Summary/drivers/driver-detail/export shapes and new fields (risk_score, risk_band, segment_previous, movement_type, risk_reasons, alert_severity) documented; live check pending.
- [ ] **Frontend service path validated** — docs/behavioral_alerts_ui_wiring_report.md; single path: api.js → /ops/behavior-alerts/* → BehavioralAlertsView.
- [ ] **Mounted tab validated** — App.jsx mounts BehavioralAlertsView when activeTab === 'behavioral_alerts'; nav button "Behavioral Alerts" present.
- [ ] **Visible UI validated** — To be verified by user: tab, table, KPIs, drilldown, export, help panel (docs/behavioral_alerts_ui_render_validation.md).
- [ ] **Filters validated** — To be verified by user: filters affect table, KPIs, export (docs/behavioral_alerts_filter_validation.md).
- [ ] **Drilldown validated** — To be verified by user: "Por qué se destaca" block and risk_reasons (docs/behavioral_alerts_ui_render_validation.md).
- [ ] **Export validated** — To be verified by user: file downloads, columns include movement_type, alert_severity, risk_score, risk_band (docs/behavioral_alerts_export_validation.md).
- [ ] **No legacy endpoint/service/component powering the tab** — Confirmed in wiring report; only BehavioralAlertsView and /ops/behavior-alerts/*.
- [ ] **Fixes applied documented** — docs/behavioral_alerts_fix_log.md (085 alias b→c; DROP VIEW + CREATE VIEW).
- [ ] **Final status defined** — docs/behavioral_alerts_go_no_go.md.
