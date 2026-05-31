# CLOSED PERIOD ENGINE — FINAL AUDIT

**Fecha**: 2026-05-30
**Motor**: Control Foundation
**Archivo**: `frontend/src/utils/projectionClosedPeriodEngine.js`

---

## 1. Parámetros Auditados

### 1.1 `resolveClosedPeriodAnchor()` firma

```javascript
resolveClosedPeriodAnchor({
  allPeriods,     // string[] — period keys del rango
  grain,          // 'daily' | 'weekly' | 'monthly'
  projectionMeta, // Object|null — meta del endpoint
  periodInfoMap,  // Map|null — [OPCIONAL] periodKey → { weekState, comparisonBasis, hasReal }
  selectedKpi,    // string|null — KPI activo
  kpiFreshness,   // Object|null — { kpi: { max_data_date, lag_days, status } }
})
```

| Parámetro | ¿Pasado desde la UI? | Estado |
|-----------|---------------------|--------|
| `allPeriods` | Sí (`displayProjMatrix.allPeriods`) | ✅ |
| `grain` | Sí (prop del componente) | ✅ |
| `projectionMeta` | Sí (estado React) | ✅ |
| `periodInfoMap` | **NO** | ❌ HIGH — Nunca construido |
| `selectedKpi` | Sí (`focusedKpi`) | ✅ |
| `kpiFreshness` | Sí (`projectionMeta.kpi_freshness`) | ✅ |

---

## 2. Lógica de Anclaje Auditada

### 2.1 Daily

```
1. maxDataDate = kpiMaxDataDate || globalMaxDataDate
2. Buscar maxDataKey en allPeriods
3. Si no está, buscar el más cercano atrás
4. Fallback: yesterday → last_in_range
```

| Check | Estado | Nota |
|-------|--------|------|
| Ancla a último día con data real | ✅ | `maxDataDate` del freshness engine |
| Respeta per-KPI freshness | ✅ | `kpiMaxDataDate` tiene prioridad sobre `globalMaxDataDate` |
| No ancla a período sin data | ✅ | Línea 63-73: búsqueda descendente ≤ maxDataKey |
| Hoy tratado como partial si > maxDataDate | ✅ | Línea 94-95: `isCalendarCurrentPartial` |
| Fallback yesterday válido | ✅ | Línea 77-91 |

### 2.2 Weekly

```
1. Buscar desde el final: weekState === 'closed' en periodInfoMap
2. Fallback: penúltima semana
3. Fallback: última en rango
```

| Check | Estado | Nota |
|-------|--------|------|
| Ancla a última semana cerrada | ❌ | `periodInfoMap` no construido → usa fallback penúltimo |
| Semana actual parcial etiquetada | ❌ | Misma razón |
| Fallback penúltimo razonable | ✅ | Línea 111-119 |
| Respeta per-KPI freshness | ❌ | Weekly no usa `maxDataDate` para anclar. Debería. |

**Issue**: El anclaje weekly depende exclusivamente de `periodInfoMap` para encontrar semanas cerradas. Sin ese mapa, siempre cae en `penultimate_week_fallback`. La semana actual (parcial) no se distingue de una cerrada.

### 2.3 Monthly

```
1. Buscar desde el final: comparisonBasis === 'full_month' en periodInfoMap
2. Fallback: penúltimo mes
3. Fallback: último en rango
```

| Check | Estado | Nota |
|-------|--------|------|
| Ancla a último mes full | ❌ | `periodInfoMap` no construido → usa fallback penúltimo |
| Mes parcial etiquetado | ❌ | Misma razón |
| Fallback penúltimo razonable | ✅ | Línea 141-149 |
| Respeta per-KPI freshness | ❌ | Monthly no usa `maxDataDate` para anclar. |

---

## 3. Funciones Auxiliares Auditadas

### 3.1 `classifyPeriodStatus()`

| Input | Lógica | Estado |
|-------|--------|--------|
| `weekState === 'future'` | → `'future'` | ✅ |
| `periodKey === anchorPeriodKey` | → `'current'` | ✅ |
| `periodKey === calendarCurrentPeriodKey && ≠ anchor` | → `'partial'` | ✅ |
| `comparisonBasis` contiene `partial_` | → `'partial'` | ✅ |
| `periodKey < anchorPeriodKey` | → `'past'` | ✅ |
| `periodKey > calendarCurrentPeriodKey` | → `'future'` | ✅ |
| Default | → `'closed'` | ✅ |

**Estado**: Lógica correcta. **Nunca llamada desde componentes React.** (Gap de integración.)

### 3.2 `getPeriodVisualClass()`

Retorna estilos Tailwind para `current` / `partial` / `past` / `future` / `closed`. Correcto. No usado en UI.

### 3.3 `getPeriodBadge()`

Retorna label para badge según grain. Correcto. No usado en UI.

### 3.4 `getAnchorButtonLabel()`

Usado en `ProjectionContextBar` para el botón "Ir al cierre" / "Ir a hoy". ✅

### 3.5 Flag `kpiFreshnessMismatch`

```javascript
const kpiFreshnessMismatch = kpiMaxDataDate && globalMaxDataDate && kpiMaxDataDate !== globalMaxDataDate
```

Calculado correctamente. Retornado en la respuesta del engine pero **no usado en el ContextBar** (el ContextBar recalcula `hasFreshnessMismatch` independientemente).

### 3.6 Flag `kpiNoData`

```javascript
const kpiNoData = selectedKpi && globalMaxDataDate && !kpiMaxDataDate
```

Calculado correctamente. Señala KPIs sin data real. El ContextBar lo recalcula independientemente.

---

## 4. Hallazgos

### Críticos

| ID | Descripción | Fix |
|----|-------------|-----|
| CE-1 | `periodInfoMap` nunca construido ni pasado. Weekly/Monthly anclaje usa fallback penúltimo en vez de `weekState === 'closed'` o `comparisonBasis === 'full_month'`. | Construir `periodInfoMap` desde filas de proyección. |
| CE-2 | `classifyPeriodStatus` / `getPeriodVisualClass` / `getPeriodBadge` no se usan en la UI. Las columnas de la matriz no reciben tratamiento visual de closed/partial/future desde el engine. | Integrar en header y cells. |

### No bloqueantes

| ID | Descripción | Severidad |
|----|-------------|-----------|
| CE-3 | `kpiFreshnessMismatch` flag en engine no usado por componentes (recalculan su propia lógica) | LOW |
| CE-4 | `kpiNoData` flag en engine no usado por componentes (recalculan su propia lógica) | LOW |
| CE-5 | Weekly/Monthly no usan `maxDataDate` para refinar anclaje. Podrían usar el per-KPI freshness como tiebreaker cuando `periodInfoMap` esté ausente. | LOW |

---

## 5. Veredicto

**CONDITIONAL GO** — Engine correcto en lógica. Daily funciona. Weekly/Monthly funcionan con fallback razonable pero sin `periodInfoMap` no pueden anclar al último período operativo cerrado. Fix requerido: CE-1 + CE-2.

