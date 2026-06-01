# REVENUE TOTAL VS DETAIL AUDIT

**Motor:** Control Foundation  
**Fecha:** 2026-05-31  

---

## 1. ¿TOTAL se calcula desde suma de detalle?

**Sí.** El TOTAL en el frontend (`ProjectionTotalsRow`) se calcula en `buildProjectionMatrix()` sumando todas las filas del mismo periodo:

```js
// projectionMatrixUtils.js:436-441
for (const kpi of PROJECTION_KPIS) {
  if (kpi === 'active_drivers') continue  // semi-aditivo → excluido
  tb[kpi].actual += Number(raw[kpi]) || 0  // revenue_yego_net incluido
}
```

No hay query separada para totals. Misma fuente, misma clave.

---

## 2. ¿Detalle se pierde por alguna de estas causas?

| Causa | ¿Aplica? | Evidencia |
|-------|----------|-----------|
| null city | No | El backend usa `_country_to_fact_name` y `_city_to_fact_name` para normalizar |
| null lob_base | No | `business_slice_name` viene del plan o real data |
| segment mismatch | Posible | Plan y real usan `_canonical_slice_join_segment` para hacer join. Si los nombres no coinciden exactamente, el join falla |
| metric key mismatch | No | `revenue_yego_net` es consistente en todo el pipeline |
| revenue field no propagado | Posible | Si `COALESCE(revenue_yego_final, revenue_yego_net)` es NULL para una tajada |
| formatter frontend | **Sí (corregido)** | `hasReal = actual > 0` ocultaba revenue = 0. Corregido a `actual != null && !isNaN(Number(actual))` |
| display model | **Sí (corregido)** | `buildProjectionCellDisplay` mostraba `—` para `actual = 0`. Corregido |

---

## 3. Análisis de los Tres Tipos de Fila

### 3.1 `comparison_status = "matched"` (plan + real)

- `revenue_yego_net` = real data revenue (del serving fact)
- Si `real_revenue = NULL` en serving → `revenue_yego_net = None` → celda muestra `—`
- **Display fix:** Si `actual = 0`, ahora muestra `0` en vez de `—`

### 3.2 `comparison_status = "missing_plan"` (real sin plan)

- `revenue_yego_net` = real data revenue
- Celda muestra valor real + badge "Sin proy."
- **Display fix:** Si `actual = 0`, ahora muestra `0` en vez de `—`

### 3.3 `comparison_status = "plan_without_real"` (plan sin real)

- `revenue_yego_net = None` (no hay real data para esta tajada)
- Celda muestra `—` (correcto: no hay datos reales)
- ¿Contribuye al TOTAL? `Number(null) || 0 = 0` → no afecta el total
- **Correcto:** No hay nada que mostrar

---

## 4. Priority Layer y Revenue

El `operationalPriorityEngine.js` itera sobre `PROJECTION_KPIS` (incluye `revenue_yego_net`) y para cada celda:

1. Verifica `d.isProjection === true` → revenue pasa
2. Verifica `d.value != null` → si revenue es null, se salta
3. Usa `buildComparableDelta(d, grain)` → requiere `periodPop` con revenue
4. Si `periodPop` no tiene revenue entries → `hasComparable = false` → se salta

**Conclusión:** Priority Layer NO muestra revenue invisible. Solo muestra revenue cuando `d.value != null` y `periodPop` tiene datos comparables.

---

## 5. Conclusión Final

| Pregunta | Respuesta |
|----------|-----------|
| ¿TOTAL usa fuente distinta? | No. Misma fuente, suma de detalle. |
| ¿Detalle se pierde en transform? | No. `buildProjectionMatrix` no filtra por KPI. |
| ¿Display model oculta revenue? | **Sí (corregido).** `hasReal > 0` ocultaba `actual = 0`. |
| ¿Revenue vacío para ciudades principales? | **Probable data issue en serving fact.** Verificar con queries de DB en `REVENUE_DETAIL_SERVING_AUDIT.md`. |
| ¿Priority Layer usa revenue invisible? | No. Requiere `d.value != null` y `periodPop` comparable. |
