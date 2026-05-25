# BEHAVIORAL MVP — QA

**Date**: 2025-05-25
**Build**: PASS (9.32s, 812 modules)

---

## No IA Check

| Rule | Violated? |
|---|---|
| No LLM / embeddings | ✅ None present |
| No ML models | ✅ None present |
| No forecast predictions | ✅ None present |
| No generated recommendations | ✅ Zero "haz", "recomienda", "llama" text |
| Deterministic thresholds only | ✅ All hardcoded constants |
| Deterministic classification | ✅ Pure if/else rules |
| No scoring invented | ✅ All metrics from DB |

---

## No Invented Signals Check

| Signal | Source | Valid? |
|---|---|---|
| Trips | `SUM(completed_trips)` from fact table | ✅ Real column |
| Active days | `COUNT DISTINCT activity_date` from fact table | ✅ Real column |
| Days since last | `MAX(activity_date)` vs CURRENT_DATE | ✅ Real column |
| Weekend share | `EXTRACT(ISODOW)` + aggregation | ✅ Derived from real column |
| Delta pct | Current vs previous window comparison | ✅ Derived from real column |

---

## No Runtime Pesado Check

| Concern | Mitigation |
|---|---|
| Raw scan per request | ❌ Fixed — uses `ops.driver_daily_activity_fact` (pre-aggregated) |
| Large response | ❌ Fixed — limit=100 (max 500) |
| Unbounded queries | ❌ Fixed — window_days capped at 90 |
| No caching | Can be added later (300s TTL like behavioral_pattern_diagnosis) |

---

## API Response Check

| Field | Present? |
|---|---|
| `drivers[]` with driver_id, status, severity | ✅ |
| `summary` with by_status counts | ✅ |
| `signals_used[]` | ✅ |
| `signals_unavailable[]` | ✅ |
| `diagnostic_mode: "deterministic"` | ✅ |
| `note` about MVP limitations | ✅ |
| Empty response for no drivers | ✅ |
| Error response with detail | ✅ |

---

## UI Check

| State | Renders? |
|---|---|
| No country selected | ✅ "Selecciona un pais" message |
| Loading | ✅ Spinner + text |
| Error | ✅ Red banner with detail |
| Empty data | ✅ "Sin datos" message |
| Normal data | ✅ Driver list with status chips |
| Expanded (>8 drivers) | ✅ "Ver todos" toggle |
| Signal gaps note | ✅ Amber footer with unavailable signals |

---

## Integration Check

| Item | Status |
|---|---|
| Backend service created | ✅ `behavioral_diagnostic_mvp_service.py` |
| Router created | ✅ `behavioral_mvp.py` |
| Registered in main.py | ✅ |
| Frontend API function | ✅ `getBehavioralDiagnosisMvp` in api.js |
| UI component | ✅ `BehavioralDiagnosisMvpPanel.jsx` |
| Feature flag | Not yet gated — standalone panel |
| Omniview integration | Not yet — panel available for manual placement |

---

## VERDICT: PASS
