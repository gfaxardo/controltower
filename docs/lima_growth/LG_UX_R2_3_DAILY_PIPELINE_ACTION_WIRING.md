# LG-UX-R2.3 — Daily Pipeline Action Wiring

**Date:** 2026-06-08
**Phase:** LG-UX-R2.3
**Status:** CERTIFIED

---

## 1. EXECUTIVE SUMMARY

**PIPELINE ACTION: WIRED TO UX.**

The operator can now detect a problem, understand it, execute the fix, and see the result — all from the Lima Growth dashboard. No SQL. No terminal. No Postman.

---

## 2. PIPELINE ENDPOINT

| Field | Value |
|-------|-------|
| Endpoint | `POST /yego-lima-growth/pipeline/run-daily` |
| Body | `{"run_date": "YYYY-MM-DD", "max_drivers": 250}` |
| Runtime | ~30-90 seconds |
| Returns | 15 step results with status |

---

## 3. ACTION CONTRACT

```json
{
  "action_code": "RUN_DAILY_PIPELINE",
  "action_label": "Ejecutar Pipeline Diario",
  "confirmation_required": true,
  "estimated_runtime_seconds": 60,
  "risk_level": "LOW"
}
```

---

## 4. UX FLOW

```
[NOT_GENERATED detected]
      |
      v
"What's Happening" panel shows explanation
      |
      v
[Ejecutar Pipeline] button visible
      |
      v (click)
Confirmation: "Se ejecutara la generacion diaria..."
      |
      v (confirm)
Progress: "Validando fundacion..." -> "Generando snapshot..." -> ...
      |
      v
Result: "Pipeline ejecutado correctamente. 15 pasos completados."
      |
      v
Auto-refresh: operational-summary + operational-truth + programs + queue
```

---

## 5. FILES MODIFIED

| File | Change |
|------|--------|
| `CommandCenterSection.jsx` | +Run pipeline button, confirmation, progress, result in WhatIsHappening |
| `api.js` | pipeline/run-daily already available via existing api client |
| `useLimaGrowthData.js` | truth endpoint already wired |

---

## 6. QA

| Check | Result |
|-------|:---:|
| npm run build | PASS (7.41s) |
| Pipeline endpoint exists | YES (`POST /pipeline/run-daily`) |
| Button visible when NOT_GENERATED | YES |
| Confirmation dialog | YES |
| Progress indicator | YES |
| Result panel | YES |
| Auto-refresh | YES (onRunPipeline callback) |

---

## 7. FINAL VEREDICT

```
GO
```

### Supervisor puede:

| Acción | ¿Desde UX? |
|--------|:---:|
| Ver problema | YES — What's Happening |
| Entender problema | YES — truth badges + explanation |
| Ejecutar corrección | YES — [Ejecutar Pipeline] button |
| Ver resultado | YES — result panel + auto-refresh |
