# Action Engine + Behavioral Alerts — Explainability Render Validation (Phase 15)

**Project:** YEGO Control Tower  
**Date:** 2026-03-11

---

## Manual verification steps

### Behavioral Alerts tab

1. Open Control Tower → tab **Behavioral Alerts**.
2. **Time context:** Above the alerts table you should see a line like: "Última semana vs baseline 6 sem. · Semana analizada: semana cerrada en el rango seleccionado."
3. **Table columns:** Confirm columns: Conductor, País, Ciudad, Park, Segmento, Viajes sem., Base avg, **Δ %** (with red/green color for negative/positive), **Estado conductual** (badge: Empeorando, Mejorando, En recuperación, Estable, Volátil), **Persistencia** (e.g. "2 sem. en deterioro" or "—"), Alerta, Risk Score, Risk Band, Acción.
4. **Delta % color:** Negative delta in red, positive in green, near zero in gray.
5. **Help panel:** Click "Ver explicación: Segmento, Baseline, Delta, Tendencia, Riesgo". Panel must include: Segmento, Baseline, Delta, Tendencia/Estado conductual, Persistencia, Riesgo, Behavioral Alerts.
6. **Driver detail modal:** Click "Ver detalle" on a row. Modal must show: "Por qué se destaca" with Risk Score; **Estado conductual** and **Persistencia**; table with columns Semana, Viajes, Segmento, Base, Δ %, **Estado**, **Persistencia**, Alerta. Delta % with color.

**Expected:** User can answer quickly: Is this driver worsening or improving? (Estado conductual.) Compared to what? (Baseline N sem, label above table.) Since when? (Persistencia.)

### Action Engine tab

1. Open tab **Action Engine** → sub-tab **Cohortes y acciones**.
2. **Time context:** Line like "Última semana vs baseline 6 sem. · Cada cohorte corresponde a una semana cerrada en el rango."
3. **Recommended actions panel:** Each card shows: action name; cohort + size + **week**; **Base: Última semana vs baseline 6 sem. · Cambio promedio: X%**; **Rationale** (short text from COHORT_RATIONALE); priority badge; channel; "Ver cohorte".
4. **Cohort table:** Column "Objetivo / Rationale" shows short rationale text. Delta % column with red/green color.
5. **Drilldown:** Click "Ver" on a cohort. Modal header; below it a bar: "Última semana vs baseline 6 sem. · Acción sugerida: [rationale]". Table columns: Conductor, Segmento, Viajes sem., Baseline, Delta % (colored), **Estado conductual** (badge), **Persistencia**, Riesgo, Alerta (badge with color).
6. **Help panel:** "Ayuda — Segmento, Baseline, Delta, Tendencia, Riesgo, Action Engine". Content includes Segmento, Baseline, Delta, Tendencia, Riesgo, Action Engine, Behavioral Alerts, Top Driver Behavior.

**Expected:** User can answer: Is this cohort/driver worsening or improving? (Estado conductual in drilldown.) Why is this action suggested? (Rationale on cards and in drilldown header.) How urgent? (Priority badge.)

---

## Color semantics checklist

- **Empeorando / negative delta / high risk / Critical Drop:** red tones.
- **Mejorando / En recuperación / positive delta / Strong Recovery:** green tones.
- **Estable / neutral:** gray.
- **Volátil / High Volatility:** purple.
- **Medium risk / Moderate Drop:** amber/orange.

---

## Issues found

- None if migration 088 is applied and backend returns the new columns. If 088 is not applied, cohort_detail and export may fail (view missing weeks_rising_consecutively).
