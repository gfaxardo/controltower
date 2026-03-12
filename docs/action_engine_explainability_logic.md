# Action Engine + Behavioral Alerts — Explainability Logic

**Project:** YEGO Control Tower  
**Date:** 2026-03-11

---

## 1. Explainability model (three blocks)

### A) Current snapshot

- **trips_current_week:** Viajes de la última semana cerrada analizada.
- **segment_current:** Segmento del conductor en esa semana.
- **week_label / week_start:** Semana analizada (ej. S11-2026).

### B) Baseline comparison

- **avg_trips_baseline (baseline_avg):** Promedio de viajes en las N semanas previas (ventana baseline, ej. 6).
- **delta_abs:** Diferencia en valor absoluto (última semana − baseline).
- **delta_pct:** Diferencia en % respecto al baseline. Negativo = empeora; positivo = mejora.
- **Label sugerido:** "Última semana vs baseline N semanas".

### C) Trend / persistence

- **weeks_declining_consecutively:** Semanas consecutivas con caída vs su propio patrón.
- **weeks_rising_consecutively:** Semanas consecutivas recuperándose.
- **Persistence label:** "N semanas en deterioro" / "N semanas recuperándose" / "Sin tendencia sostenida".
- **alert_type (High Volatility):** Comportamiento volátil reciente.

---

## 2. Estado conductual (behavior direction)

Derivado en frontend (o backend) a partir de:

| Estado           | Regla (primera que aplique) |
|------------------|-----------------------------|
| **Empeorando**   | delta_pct &lt; −0.05 y weeks_declining_consecutively ≥ 2 (o alert_type Critical/Moderate Drop). |
| **Mejorando**    | delta_pct &gt; 0.05 y weeks_rising_consecutively ≥ 2 (o alert_type Strong Recovery). |
| **En recuperación** | delta_pct &gt; 0 y alert_type = Strong Recovery. |
| **Volátil**      | alert_type = High Volatility. |
| **Estable**      | Resto: |delta_pct| pequeño y sin muchas semanas consecutivas en una dirección. |

Valores mostrados en UI: Empeorando, Mejorando, En recuperación, Estable, Volátil.

---

## 3. Time decision context (labels)

- **"Última semana vs baseline 6 semanas"** — Cuando la decisión se basa en comparar la semana cerrada con el promedio de las 6 semanas anteriores.
- **"N semanas consecutivas en caída"** — Cuando weeks_declining_consecutively ≥ 1.
- **"N semanas recuperándose"** — Cuando weeks_rising_consecutively ≥ 1.
- **"Recuperación fuerte vs baseline"** — Cuando alert_type = Strong Recovery.
- **"Comportamiento volátil reciente"** — Cuando alert_type = High Volatility.

---

## 4. Persistence / "since when"

- Si weeks_declining_consecutively ≥ 1 → "X semanas en deterioro" (X = valor).
- Si weeks_rising_consecutively ≥ 1 → "X semanas recuperándose".
- Si ambos 0 → "—" o "Sin tendencia sostenida".
- Opcional: traducir a días aproximados (X*7 días) si se desea "Desde hace N días".

---

## 5. Color semantics

- **Empeorando / negative delta / critical / high risk:** rojo (red-600, red-100 bg).
- **Mejorando / En recuperación / positive delta / positive severity:** verde (green-600, green-100 bg).
- **Estable / neutral:** gris (gray-500, gray-100 bg).
- **Volátil:** violeta (purple-600, purple-100 bg).
- **Moderate concern / medium risk:** ámbar (amber-600, orange-100 bg).
- **Monitor:** azul/gris (blue-100 o gray-100).

Consistencia: mismas clases en tabla de alertas, cards, drilldown y badges.

---

## 6. Action rationale (short text)

Por cohort_type se puede mostrar:

- Alto valor en deterioro → "Proteger supply premium antes de mayor caída."
- Erosión silenciosa → "Detectar deterioro oculto antes de que colapse el segmento."
- Recuperables (mid) → "Acelerar conversión a mayor productividad."
- Cerca de subir segmento → "Fijar subida de segmento."
- Riesgo de bajada → "Evitar caída al segmento inferior."
- Volátiles → "Revisar patrón antes de contactar."
- Alto valor recuperables → "Reactivar de alto ROI."

Estos textos deben verse en cards y en drilldown (como objetivo o rationale).
