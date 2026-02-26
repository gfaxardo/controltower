# FASE 2D — Hardening de estado dimensional

## Qué se cambió y por qué

Se estandarizó el manejo de **estado dimensional** y **drill** en la app para evitar state-leaks y cache collisions: al cambiar cualquier campo de dimensión (Desglose, periodo, segmento, filtros de rango) debe resetearse el drill (expanded + caché de subrows), cancelarse requests en vuelo y no aplicarse respuestas obsoletas.

**Cambios principales:**

1. **Helper único `frontend/src/utils/dimKey.js`**
   - `buildDimKey(dimObj)`: serialización estable (orden fijo de keys) para identificar la dimensión actual.
   - `buildDrillKey(dimObj, rowKey)`: clave completa drill = dim + fila; evita reutilizar caché de otra dimensión/fila.

2. **RealLOBDrillView**
   - Uso de `buildDrillKey` para la clave de expanded/subrows (en lugar de concatenación manual).
   - `resetDrillState()`: aborta el AbortController actual, vacía expanded y subrows; se llama al cambiar drillBy, periodType o segment.
   - **AbortController**: cada petición children usa el signal del ref; al cambiar dimensión se hace abort y se crea un nuevo controller.
   - **Guard**: antes de aplicar la respuesta de children se comprueba `activeDimKeyRef.current === buildDimKey(getDimObj())`; solo se hace setState si la dimensión no ha cambiado.

3. **API**
   - `getRealLobDrillProChildren` acepta `signal` en params y lo pasa a axios para cancelación.

4. **WeeklyPlanVsRealView**
   - Al cambiar `weekStartFrom`, `weekStartTo` o `alertFilter` se limpia `expandedRows` en el mismo useEffect que recarga datos.

5. **Backend**
   - Contrato de `/real-lob/drill/children` documentado en docstring: 400 si desglose=PARK y llega drill_lob_id, o desglose=LOB y llega drill_park_id (ya existía; solo se documentó).

---

## Pantallas auditadas + riesgo + acción

| Componente | Ruta / pantalla | Patrón | Riesgo | Acción aplicada |
|------------|------------------|--------|--------|------------------|
| **RealLOBDrillView** | Real LOB > Drill por país | expand/drill + Desglose (LOB/Park) + Mensual/Semanal + Segmento | **ALTO** | buildDrillKey, resetDrillState, AbortController, guard activeDimKeyRef, reset al cambiar segment |
| **WeeklyPlanVsRealView** | Fase 2B Semanal | expandedRows por fila; filtros week_start_from/to, alertFilter | **MEDIO** | Limpiar expandedRows en useEffect cuando cambian weekStartFrom, weekStartTo, alertFilter |
| **RealLOBView** | Real LOB Observabilidad | groupBy (lob_group / real_tipo_servicio), Mensual/Semanal | **BAJO** | Sin expand/drill; no requiere acción |
| **PlanVsRealView, MonthlyView, etc.** | Otras | Sin expand/drill con switch de dimensión | **BAJO** | Nada |

**Búsquedas realizadas (FASE 1):**
- `subrows|expanded|toggleExpand|children|drill|accordion|nested` → RealLOBDrillView.jsx, WeeklyPlanVsRealView.jsx, api.js, App.jsx.
- `Desglose|groupBy|periodType|Mensual|Semanal` → RealLOBDrillView.jsx, RealLOBView.jsx, MonthlyView.jsx, etc. (solo Drill tiene expand + switch dim).

No hay otros componentes con patrón “expand/drill + cambio de dimensión en la misma pantalla” además de RealLOBDrillView.

---

## Checklist manual de pruebas

- [ ] **Expand LOB → cambiar a Park:** Con Desglose=LOB, expandir un periodo. Cambiar a Park. Verificar: drill colapsado, no aparece SIN_CITY/SIN_PARK. Al expandir de nuevo con Park, datos correctos (ciudad/park).
- [ ] **Expand Park → cambiar a LOB:** Mismo flujo a la inversa; columnas LOB correctas al re-expandir.
- [ ] **Mensual con drill abierto → Semanal:** Cambiar a Semanal; drill colapsado; al expandir una semana, children de semana.
- [ ] **Semanal con drill abierto → Mensual:** Idem al revés.
- [ ] **Cambiar Segmento con drill abierto:** Segmento Todos → B2B (o B2C); drill colapsado; al expandir, datos del nuevo segmento.
- [ ] **Fase 2B Semanal:** Cambiar “Semana desde/hasta” o filtro de alertas; filas expandidas se cierran (expandedRows vacío).

---

## E2E (cuando exista framework)

No hay Playwright ni Cypress en el repo. Cuando se añadan, se recomienda un test mínimo:

1. Ir a Real LOB > Drill por país.
2. Desglose=LOB, expandir el primer periodo con datos.
3. Cambiar Desglose a Park.
4. Assert: no aparece el texto "SIN_CITY" ni "SIN_PARK" en la tabla; el drill está colapsado (o muestra datos Park correctos si se vuelve a expandir).

---

## Archivos tocados (resumen)

| Archivo | Cambio |
|---------|--------|
| `frontend/src/utils/dimKey.js` | **Nuevo**: buildDimKey, buildDrillKey. |
| `frontend/src/components/RealLOBDrillView.jsx` | buildDrillKey, resetDrillState, AbortController + signal, activeDimKeyRef guard, reset en segment change. |
| `frontend/src/services/api.js` | getRealLobDrillProChildren: extrae `signal` de params y lo pasa en config. |
| `frontend/src/components/WeeklyPlanVsRealView.jsx` | setExpandedRows({}) al inicio del useEffect [filters, weekStartFrom, weekStartTo, alertFilter]. |
| `backend/app/routers/ops.py` | Docstring de `/real-lob/drill/children` con contrato params por dimensión. |
| `docs/PHASE_2D_HARDENING.md` | Este documento. |

---

## Confirmación de cierre

**FASE 2D CERRADA: SÍ**

- Helper único de claves dimensionales (`dimKey.js`) creado y usado en RealLOBDrillView.
- Reset consistente en cambios de dimensión (drillBy, periodType, segment) y cancelación de requests (AbortController + guard).
- WeeklyPlanVsRealView con reset de expandedRows en cambios de filtros.
- Backend con contrato fail-fast documentado.
- Barrido realizado; solo RealLOBDrillView era riesgo ALTO; el resto documentado.
- Checklist manual definido; E2E pendiente de framework.
