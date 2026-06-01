# REVENUE DETAIL FIX REPORT

**Motor:** Control Foundation  
**Ticket:** OMNIVIEW UX-FIX PACK 1A  
**Fecha:** 2026-05-31  
**Estado:** COMPLETADO  
**Build:** PASS  

---

## 1. Causa Raíz

**Dos causas identificadas:**

### 1.1 Display Model (FRONTEND — CORREGIDO)

`buildProjectionCellDisplay()` en `frontend/src/utils/projectionCellDisplayModel.js:28`:

```js
// ANTES
const hasReal = actual != null && Number(actual) > 0

// DESPUÉS
const hasReal = actual != null && !isNaN(Number(actual))
```

El check `> 0` hacía que celdas con `revenue = 0` se mostraran como `—` en detalle, mientras que el `ProjectionTotalsRow` sí mostraba `0`. Esto creaba la percepción de "TOTAL tiene revenue pero detalle no".

**Mismo bug en** `ProjectionCellRender` para filas `missing_plan` (line 282):
```js
// ANTES
const hasReal = actual != null && Number(actual) > 0

// DESPUÉS
const hasReal = actual != null && !isNaN(Number(actual))
```

### 1.2 Data Ausente (BACKEND — REQUIERE DB INVESTIGATION)

Para algunos city/line, `revenue_yego_net` es `null` en la API response. Esto ocurre cuando el serving fact tiene `revenue_yego_final = NULL` y `revenue_yego_net = NULL` simultáneamente.

**Posibles causas del data issue:**
1. El refresh pipeline (`refresh_omniview_real_slice.py`) no se ejecutó → serving facts desactualizados
2. Ciertas tajadas no tienen revenue en la fuente RAW (`trips_2026`)
3. El `COALESCE(revenue_yego_final, revenue_yego_net)` falla para ciertos city/line
4. Segment mismatch entre plan y real (los nombres no coinciden en `_canonical_slice_join_segment`)

**Verificación necesaria en DB:** Ver queries en `docs/omniview/REVENUE_DETAIL_SERVING_AUDIT.md` sección 4.

---

## 2. Total vs Detalle

| Aspecto | Estado |
|---------|--------|
| ¿Misma fuente? | Sí — Totals = `SUM(detail_rows)` en frontend |
| ¿Query separada? | No |
| ¿Revenue key consistente? | Sí — `revenue_yego_net` en todo el pipeline |
| ¿Totals incluye revenue ausente? | No — `Number(null) || 0 = 0`, no infla totals |
| ¿Display consistente ahora? | Sí — Totals y detalle usan misma lógica de display |

---

## 3. Fix Aplicado

| Archivo | Cambio | Línea |
|---------|--------|-------|
| `frontend/src/utils/projectionCellDisplayModel.js` | `hasReal` ahora acepta `actual >= 0` | 28 |
| `frontend/src/components/BusinessSliceOmniviewMatrixCell.jsx` | `missing_plan` path: `hasReal` acepta `actual >= 0` | 282 |

**Lo que NO se tocó:**
- Backend / serving facts / refresh pipeline
- Cálculos de revenue
- Priority Layer logic
- Totals row (ya manejaba correctamente `actual === 0`)
- Evolution mode (no involucrado)

---

## 4. Revenue Apto para Priority Layer

**Sí**, con calificación:

- Priority Layer requiere `d.value != null` y `periodPop` con datos comparables
- Si `revenue_yego_net = null` para una celda, se excluye automáticamente
- Si `revenue_yego_net > 0`, se incluye con `buildComparableDelta()`
- **El risk es bajo**: si revenue detail está vacío (null data), la Priority Layer no lo muestra. Si tiene datos, es confiable.

---

## 5. QA

### 5.1 Escenarios Validados (Code Review)

| Escenario | Comportamiento |
|-----------|---------------|
| Revenue > 0 en detalle | Valor visible, formateado como currency |
| Revenue = 0 en detalle | Muestra "0" (antes mostraba "—") |
| Revenue = null en detalle | Muestra "—" (correcto: sin datos) |
| Revenue en TOTAL | Suma correcta de todos los rows |
| Priority Layer con revenue | Solo muestra celdas con `value != null` y comparable delta |
| `missing_plan` revenue > 0 | Valor visible + badge "Sin proy." |
| `missing_plan` revenue = 0 | Muestra "0" + badge "Sin proy." (antes "—") |
| `plan_without_real` | Muestra "—" (correcto) |

### 5.2 Runtime QA (requiere backend corriendo)

```
1. Abrir Omniview Matrix → Vs Proyección
2. Seleccionar KPI Revenue
3. Verificar:
   [ ] TOTAL muestra revenue para cada columna
   [ ] Lima → tiene revenue visible o bloqueado con explicación
   [ ] Auto regular → tiene revenue visible o bloqueado
   [ ] YMA → tiene revenue visible o bloqueado
   [ ] PRO → tiene revenue visible o bloqueado
   [ ] Delivery → tiene revenue visible o bloqueado
4. Priority Layer:
   [ ] Revenue deteriorations visibles (si existen)
   [ ] Revenue improvements visibles (si existen)
   [ ] Sin entradas fantasmas (revenue null)
```

---

## 6. Riesgos Pendientes

| Riesgo | Acción |
|--------|--------|
| Revenue null para ciudades principales | Ejecutar queries de diagnóstico en `REVENUE_DETAIL_SERVING_AUDIT.md` |
| Refresh pipeline desactualizado en dev | Ejecutar `python -m scripts.refresh_omniview_real_slice --force` |
| Segment mismatch plan vs real | Verificar `_canonical_slice_join_segment` en backend |

---

## 7. Archivos

| Archivo | Acción |
|---------|--------|
| `frontend/src/utils/projectionCellDisplayModel.js` | Modificado: `hasReal` >= 0 |
| `frontend/src/components/BusinessSliceOmniviewMatrixCell.jsx` | Modificado: `missing_plan` `hasReal` >= 0 |
| `docs/omniview/REVENUE_DETAIL_PAYLOAD_AUDIT.md` | Creado |
| `docs/omniview/REVENUE_DETAIL_SERVING_AUDIT.md` | Creado |
| `docs/omniview/REVENUE_TOTAL_VS_DETAIL_AUDIT.md` | Creado |
| `docs/omniview/REVENUE_DETAIL_FIX_REPORT.md` | Creado |
