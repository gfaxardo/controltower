# Fix: State leak al cambiar Desglose en Real LOB Drill

## Resumen

**Bug:** En Real LOB > Drill por país, si se expande un periodo con Desglose = LOB y luego se cambia Desglose a Park, aparecían SIN_CITY / SIN_PARK o detalle inconsistente.

**Causa raíz:** La clave de caché del drill (expanded + subrows) era solo `country|period_start`. No incluía `drillBy` (LOB vs PARK) ni `periodType` (Mensual vs Semanal). Al cambiar Desglose se limpiaban expanded y subrows, pero: (1) una petición children en vuelo con desglose=LOB podía completarse después del cambio y volver a escribir en `subrows[key]`; (2) si el usuario volvía a expandir el mismo periodo ya con Desglose=Park, se reutilizaba la caché de ese key y se mostraban datos LOB en columnas Park → city/park_name quedaban undefined → fallback SIN_CITY/SIN_PARK.

**Solución aplicada:** (A) Clave de drill que incluye `drillBy` y `periodType`: `subrowKey = ${drillBy}|${periodType}|${country}|${periodStart}`. Así la caché de LOB nunca se reutiliza para PARK. (B) Al cambiar Desglose se mantiene el reset (colapsar expanded y limpiar subrows). (C) Al cambiar Mensual/Semanal se hace el mismo reset para evitar detalle obsoleto. (D) Backend ya validaba drill_lob_id vs drill_park_id según desglose (fail-fast 400); se documentó en el docstring.

---

## Archivos tocados

| Archivo | Cambio |
|---------|--------|
| `frontend/src/components/RealLOBDrillView.jsx` | Clave de cache por drillBy+periodType; reset al cambiar periodo; handler `handlePeriodTypeChange` |
| `backend/app/routers/ops.py` | Docstring en `/real-lob/drill/children` (fail-fast) |
| `docs/FIX_DRILL_GROUPBY_STATE_LEAK.md` | Este documento (diagnóstico, checklist, barrido) |

---

## Diff resumido

### RealLOBDrillView.jsx

- **subrowKey:** Nueva función `subrowKey(country, periodStart)` que devuelve `drillBy|periodType|country|normalizedPeriod`. Usada para `expanded` y `subrows` en lugar de solo `country|period_start`.
- **handlePeriodTypeChange:** Nuevo handler que al cambiar Mensual/Semanal hace `setExpanded(new Set())`, `setSubrows({})` y luego `setPeriodType`. Los botones Mensual/Semanal llaman a este handler en lugar de `setPeriodType` directo.
- **toggleExpand:** Usa solo `subrowKey` para key (eliminado rawKey alternativo). Comprueba `subrows[key]?.data` antes de no refetch.
- **Tabla:** Cada fila calcula `rowId` (estable para React key del Fragment) y `key = subrowKey(...)` para expanded/sr. `sr = subrows[key]` (sin fallback a key antigua).

### ops.py

- En el endpoint `get_real_lob_drill_children_endpoint` se añadió docstring indicando la validación fail-fast (drill_lob_id solo con desglose=LOB, drill_park_id solo con desglose=PARK). La lógica 400 ya existía.

---

## Checklist de pruebas manuales

- [ ] **Expand LOB → cambiar a Park:** Con Desglose=LOB, expandir un periodo. Cambiar Desglose a Park. Verificar: drill colapsado (no se muestra detalle) y no aparecen SIN_CITY/SIN_PARK. Al expandir de nuevo ese periodo con Park, se cargan datos Park correctos (ciudad/park visibles o vacío coherente).
- [ ] **Expand Park → cambiar a LOB:** Con Desglose=Park, expandir un periodo. Cambiar Desglose a LOB. Verificar: drill colapsado. Al expandir de nuevo con LOB, se ven columnas LOB (lob_group, etc.) correctas.
- [ ] **Mensual con drill abierto → cambiar a Semanal:** Con Mensual, expandir un mes. Pulsar Semanal. Verificar: drill colapsado y tabla pasa a semanas; al expandir una semana se pide children para semana.
- [ ] **Semanal con drill abierto → cambiar a Mensual:** Idem a la inversa; al cambiar a Mensual el drill se cierra y al expandir un mes se pide children para mes.

---

## Barrido: pantallas con patrón similar

| Componente | Patrón | ¿Resetea drill al cambiar dimensión/granularidad? | ¿Cache key incluye dimension? | ¿Params incompatibles backend? | Hallazgo |
|------------|--------|--------------------------------------------------|-------------------------------|---------------------------------|----------|
| **RealLOBDrillView** | Desglose LOB/Park, Mensual/Semanal, drill expand | Sí (tras fix) | Sí (tras fix: drillBy + periodType en key) | Sí (400 si drill_lob_id con PARK o drill_park_id con LOB) | **Corregido.** |
| **RealLOBView** | groupBy (lob_group / real_tipo_servicio_norm), Mensual/Semanal, sin drill expand | N/A (no hay filas expandibles) | Los datos se piden con effectiveFilters; groupBy solo afecta orden/agrupación en cliente | N/A | **Sin riesgo.** No hay estado de expand reutilizable entre dimensiones. |
| **WeeklyPlanVsRealView** | Expand por fila (descomposición revenue/palancas), filtros semana/alerta | No limpia `expandedRows` al cambiar week_start_from/to o alertFilter | La key de fila incluye week_start, country, city_norm, lob_base, segment, idx | N/A | **Riesgo bajo.** Al cambiar filtros los datos cambian y las keys de fila son distintas; las keys viejas en expandedRows no matchean filas nuevas. Opcional: limpiar expandedRows cuando cambien weekStartFrom/To o alertFilter para evitar estado huérfano. |

No se encontraron otros componentes con "Desglose" / "GroupBy" / "Dimension" que combinen drill expand + cambio de dimensión en la misma pantalla.

---

## E2E (si se añaden tests)

Sugerencia para un test E2E (Playwright/Cypress):

1. Ir a Real LOB > Drill por país.
2. Con Desglose=LOB, expandir el primer periodo con datos.
3. Cambiar Desglose a Park.
4. Comprobar que no aparece el texto "SIN_CITY" o "SIN_PARK" en la tabla de detalle (y que el drill está colapsado).
5. Expandir de nuevo el mismo periodo con Desglose=Park y comprobar que las columnas son Ciudad / Park (no LOB).

Equivalente para el flujo Park → LOB y para cambio Mensual ↔ Semanal con drill abierto.
