# OMNIVIEW POST-UX-H3 BACKLOG

**Motor:** Control Foundation  
**Fecha:** 2026-05-31  

---

## P1 — Revenue Detail Certification

**Problema:** TOTAL Revenue muestra valores pero el detalle city/line aparece vacío o con revenue = 0 para algunas ciudades. La causa raíz está en los serving facts (`revenue_yego_final` y `revenue_yego_net` pueden ser NULL simultáneamente en `ops.real_business_slice_*_fact`).

**Objetivo:** TOTAL Revenue = suma trazable de detalles o warning explícito "Revenue detail no certificado para esta ciudad/tajada".

**Fase:** Control Foundation. No maquillar frontend.

**Archivos relevantes:**
- `backend/app/services/projection_expected_progress_service.py`
- `serving.omniview_projection_daily_fact`
- `docs/omniview/REVENUE_DETAIL_SERVING_AUDIT.md`

**Diagnóstico pendiente:**
```sql
SELECT country, city, business_slice_name,
       COUNT(*) as rows,
       COUNT(CASE WHEN revenue_yego_final IS NULL AND revenue_yego_net IS NULL THEN 1 END) as null_revenue
FROM ops.real_business_slice_day_fact
WHERE trip_date >= CURRENT_DATE - 7
GROUP BY country, city, business_slice_name
HAVING COUNT(CASE WHEN revenue_yego_final IS NULL AND revenue_yego_net IS NULL THEN 1 END) > 0;
```

---

## P2 — KPI Semantic Layer

**Problema:** Avg Ticket y Trips per Driver no tienen colores/intensidad/outlier semantics visibles. El modelo de color actual trata todos los KPIs como numéricos sin contexto semántico (por ejemplo, un TPD alto no debería marcarse como "crítico" con rojo).

**Objetivo:** Unificar modelo visual semántico para Trips, Revenue, Active Drivers, Avg Ticket, TPD:
- Direccionalidad por KPI (ej. más viajes = bueno, más cancelaciones = malo)
- Thresholds por KPI
- No usar semáforo genérico

**Fase:** UX Hardening.

**Archivos relevantes:**
- `frontend/src/components/omniview/omniviewMatrixUtils.js` (signalColorForKpi)
- `frontend/src/utils/comparableDeltaDisplay.js`

---

## P3 — Present Focus Validation

**Problema:** Aunque existe "Ir a hoy", validar que el scroll centre realmente el último cierre + parcial en el viewport, no solo el día calendario. El `currentPeriodFocusEngine.js` ya tiene la lógica pero necesita verificación visual para diferentes grains y resoluciones.

**Objetivo:** Landing temporal operativo correcto: al abrir Omniview, el viewport debe mostrar `LATEST_CLOSED` + `CURRENT_PARTIAL` + `NEXT_FUTURE` (la "ventana presente").

**Fase:** UX Hardening.

**Archivos relevantes:**
- `frontend/src/utils/currentPeriodFocusEngine.js`
- `frontend/src/utils/projectionClosedPeriodEngine.js`

---

## P4 — Freshness Copy Refinement

**Problema:** El mensaje de freshness actual es técnico: "Serving facts desactualizadas. El RAW tiene datos, pero Omniview todavia no fue refrescado."

**Objetivo:** Lenguaje operacional para usuario no técnico:
- OK: "Datos al día"
- WARNING: "Algunas métricas tienen atraso leve"
- BLOCKED: "Datos nuevos detectados. La matriz todavía no fue actualizada." + botón "Actualizar Omniview"

**Fase:** UX Polish.

**Archivo:** `backend/app/services/omniview_freshness_governance_service.py:215-235`

---

## P5 — Header/Grid Width Alignment

**Problema:** El header (CommandHeader, filtros, controls) y la matriz se sienten visualmente desalineados. El root usa un hack de `100vw` con márgenes negativos.

**Objetivo:** Mismo ancho visual y composición coherente entre header y matriz.

**Fase:** UX Hardening.

**Archivos:** `BusinessSliceOmniviewMatrix.jsx:1408`

---

## P6 — Diagnostic Engine Backlog

**Problema:** Priority Layer dice dónde mirar ("▼ Bogotá Delivery -99%"), pero no explica por qué ocurrió. El operador necesita entender la causa raíz.

**Objetivo futuro:** Explicar drivers causales detrás de las prioridades operacionales.

**Fase:** Diagnostic Engine. NO en Control Foundation.
