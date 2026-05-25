# BEHAVIORAL DIAGNOSIS MVP — FINAL REPORT

**Date**: 2025-05-25
**Motor**: Diagnostic Engine 2A.3
**Status**: **GO**

---

## 1. WHAT WAS BUILT

| Layer | File | Purpose |
|---|---|---|
| **Backend Service** | `backend/app/services/behavioral_diagnostic_mvp_service.py` | Driver-level classification using 5 available signals |
| **API Router** | `backend/app/routers/behavioral_mvp.py` | `GET /ops/diagnostics/behavioral/mvp` |
| **Registration** | `backend/app/main.py` | Router included |
| **Frontend API** | `frontend/src/services/api.js` | `getBehavioralDiagnosisMvp(params)` |
| **UI Component** | `frontend/src/components/diagnostics/BehavioralDiagnosisMvpPanel.jsx` | Panel with summary, driver list, signal gaps |

---

## 2. SIGNALS USED (5)

| Signal | Source |
|---|---|
| Trips (`completed_trips`) | `ops.driver_daily_activity_fact` |
| Active days | `COUNT DISTINCT activity_date` |
| Days since last trip | `MAX(activity_date)` vs today |
| Weekend share | `ISODOW IN (6,7)` fraction |
| Delta pct | Current vs previous 28d window |

---

## 3. SIGNALS BLOCKED (10)

revenue, avg_ticket, trip_hour, distance, duration, online_hours, cancellation, acceptance, zone, tipo_servicio — all not available in current fact table columns.

---

## 4. CLASSIFICATION RULES (7 statuses)

| Status | Rule |
|---|---|
| `churned` | days_since_last ≥ 30 |
| `inactive_risk` | days_since_last ≥ 14 |
| `at_risk` | delta_pct ≤ -40% |
| `declining` | delta_pct ≤ -25% |
| `top` | trips_per_day ≥ 5 AND active_days ≥ 30% of period |
| `growing` | delta_pct ≥ +25% |
| `stable` | default |

---

## 5. FILES CREATED (8)

| File | Purpose |
|---|---|
| `docs/diagnostics/BEHAVIORAL_MVP_PRECHECK.md` | GO/NO-GO |
| `docs/diagnostics/BEHAVIORAL_MVP_SIGNAL_GAPS.md` | What's missing |
| `docs/diagnostics/BEHAVIORAL_MVP_QA.md` | QA checklist |
| `docs/diagnostics/BEHAVIORAL_MVP_REPORT.md` | This report |
| `backend/app/services/behavioral_diagnostic_mvp_service.py` | Service |
| `backend/app/routers/behavioral_mvp.py` | Router |
| `frontend/src/services/api.js` (+1 function) | API call |
| `frontend/src/components/diagnostics/BehavioralDiagnosisMvpPanel.jsx` | UI |

---

## 6. BUILD

```
npm run build → PASS (9.32s, 812 modules)
```

---

## 7. RISKS

| Risk | Status |
|---|---|
| Raw scan on large datasets | Mitigated — uses pre-aggregated fact table, limit=100 |
| 5 signals insufficient for full diagnosis | DOCUMENTED — gaps visible in UI and docs |
| No Omniview integration yet | ACCEPTED — panel is standalone, integration is next phase |

---

## 8. NEXT PHASE

Integrate `BehavioralDiagnosisMvpPanel` into Omniview as a secondary diagnostic panel. Feature-gate with `VITE_BEHAVIORAL_MVP_ENABLED` flag. Connect classification to existing severity badges in Omniview cells.
