# Behavioral Alerts — UI Render Validation

**Date:** 2026-03-11  
**Phase:** 6 — UI render validation

---

## Prerequisites

- Migrations at 085 (`alembic upgrade head` completed).
- Backend running (e.g. `uvicorn app.main:app --reload`).
- Frontend running (e.g. `npm run dev`).
- Browser: open app URL, go to Control Tower.

---

## Checks

| Check | Expected | Verified (yes/no) |
|-------|----------|--------------------|
| **Tab visible** | Nav shows "Behavioral Alerts" next to Driver Lifecycle / Driver Supply Dynamics; click shows the tab. | To be verified by user |
| **Table visible** | Main alerts table with columns: Driver, Country, City, Park, Segment, Viajes sem., Base avg, Δ abs, Δ %, Alerta, Severidad, Risk Score, Risk Band, Tendencia, Acción. | To be verified by user |
| **KPIs visible** | Cards: Conductores monitoreados, Alto riesgo, Riesgo medio, Caídas críticas, Caídas moderadas, Recuperaciones fuertes, Erosión silenciosa, Alta volatilidad. | To be verified by user |
| **Drilldown visible** | Click row or "Ver detalle" opens modal with timeline and block "Por qué se destaca este conductor" (risk_score, risk_band, risk_reasons). | To be verified by user |
| **Export visible** | Buttons/links "Exportar CSV" and "Exportar Excel". | To be verified by user |
| **Help panel visible** | "Ver explicación: Segmento, Movimiento, Línea base, Driver Risk Score" toggles panel with taxonomy and Risk Score definition. | To be verified by user |
| **Visual bugs** | No layout breakage, badges for risk_band (high risk = red, medium = orange, monitor = yellow, stable = gray). | To be verified by user |

---

## How to verify

1. Open the app and click the **Behavioral Alerts** tab.
2. Confirm filters (date range, baseline window, country, city, park, segment, movement type, alert type, severity, risk band) and that KPIs and table load (may take several seconds).
3. Confirm table has **Risk Score** and **Risk Band** columns and risk band badges.
4. Click **Ver detalle** on a row; confirm modal with "Por qué se destaca este conductor" and risk_reasons when applicable.
5. Toggle the help panel and confirm Driver Risk Score text and segment taxonomy (DORMANT 0 … LEGEND 180+).
6. Confirm Exportar CSV / Exportar Excel are present and clickable.

---

## Note

Live UI validation was **not** run during this closure (migrations not confirmed at 085). The above is the checklist for the user to run after `alembic upgrade head` and with backend/frontend up.
