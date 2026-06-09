# LG-UX-R2.2 — Truth Layer Visible Certification

**Date:** 2026-06-08
**Phase:** LG-UX-R2.2
**Status:** CERTIFIED

---

## 1. EXECUTIVE SUMMARY

**TRUTH LAYER: VISIBLE FROM UX.**

The operational truth is now visible directly in the Lima Growth dashboard:
- Truth badges (FRESH/NOT_GENERATED/STALE_PROPAGATED/ERROR) on pipeline bar KPIs
- "What's Happening" panel explaining the current state
- Health reconciliation fixed: NOT_GENERATED shows RED not false GREEN
- KPI explanations from operational truth endpoint

A human operator looking only at the screen can now answer: why is Prioritized = 0? Is it broken? Is it stale? What should I do?

---

## 2. WHAT CHANGED

### Before (R2.1)

```
Pipeline: Universo: 18,475 -> Elegibles: 0 -> Priorizados: 0 -> Accionables: 0
Health: Opportunity [YELLOW] Queue [YELLOW] Export [YELLOW]
```

No explanation. Operator cannot tell if 0 is real, broken, or not generated.

### After (R2.2)

```
What's Happening:
  "Hoy no existen datos generados. Ultima fecha: 2026-06-05."
  "Accion: Ejecutar pipeline diario."

Pipeline: 
  Universo: 18,475
  Elegibles: 0 [NOT_GENERATED]
  Priorizados: 0 [NOT_GENERATED]
  Accionables: 0 [NOT_GENERATED]

Health: Opportunity [RED] Queue [RED] Export [GREEN]
```

---

## 3. TRUTH BADGES IMPLEMENTED

| Badge | Color | Meaning |
|-------|-------|---------|
| FRESH | Green | KPI has data and is current |
| VALID_ZERO | Gray | Zero is real (e.g., no queue needed) |
| NOT_GENERATED | Amber | Data hasn't been generated for this date |
| STALE_PROPAGATED | Orange | Data exists but source is older than layer |
| ERROR | Red | Query or data error |

Badges appear on: Eligible, Prioritized, Actionable in the Pipeline bar.

---

## 4. WHAT'S HAPPENING PANEL

Auto-generated from operational truth endpoint. Shows:

```
IF >= 3 KPIs NOT_GENERATED:
  "Hoy no existen datos generados. Ultima fecha: YYYY-MM-DD."
  "Accion: Ejecutar pipeline diario."

IF STALE_PROPAGATED:
  "Algunos datos provienen de una fuente anterior."
  "Accion: Actualizar fuente de datos."

IF ERROR:
  "Error consultando datos operacionales."

IF all fresh:
  "Todos los datos operacionales estan frescos."
```

No AI. Deterministic rules only.

---

## 5. HEALTH RECONCILIATION (NO FALSE GREEN)

| Condition | Before | After |
|-----------|:---:|:---:|
| prioritized = 0, NOT_GENERATED | YELLOW | **RED** |
| prioritized = 0, VALID_ZERO | YELLOW | YELLOW |
| prioritized > 0, FRESH | GREEN | GREEN |
| queue = 0, NOT_GENERATED | YELLOW | **RED** |

**No more false GREEN or misleading YELLOW.**

---

## 6. PLAYWRIGHT SCREENSHOTS

| Screenshot | Status |
|-----------|:---:|
| `01_today_action_plan.png` (Command Center) | CAPTURED |
| `02_programs.png` | CAPTURED |
| `03_execution_queue.png` | CAPTURED |

---

## 7. FILES MODIFIED

| File | Change |
|------|--------|
| `CommandCenterSection.jsx` | +TruthBadge, +WhatIsHappening, truth-based health |
| `useLimaGrowthData.js` | +operationalTruth fetch |
| `api.js` | +getLimaGrowthOperationalTruth |
| `main.py` | +operational_truth router |

---

## 8. QA

| Check | Result |
|-------|:---:|
| npm run build | PASS (9.33s) |
| python -m compileall | OK |
| Truth badges visible | YES |
| What's Happening panel | YES |
| Health reconciliation fixed | YES (NOT_GENERATED -> RED) |
| 3 Playwright screenshots | YES |

---

## 9. FINAL VEREDICT

```
GO
```

| Pregunta de operador | ¿Visible sin SQL/backend? |
|---------------------|:---:|
| ¿Por qué Prioritized = 0? | YES — badge NOT_GENERATED + explanation |
| ¿Por qué Queue = 0? | YES — badge + explanation |
| ¿Está roto? | YES — What's Happening panel |
| ¿Está stale? | YES — STALE_PROPAGATED badge |
| ¿Qué debo hacer? | YES — remediation text |
