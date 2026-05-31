# CLOSURE MULTI-KPI FRESHNESS — H1 FINAL REPORT

**Fecha**: 2026-05-30
**Motor**: Control Foundation
**Gate**: Omniview H1 — Multi-KPI Freshness & Closed Period Audit

---

## 1. Estado: **GO**

Control Foundation cerrado formalmente. Multi-KPI freshness auditado y corregido. Priority Layer limpia. Build PASS.

---

## 2. Último Cierre por KPI/Grain

| KPI | Daily | Weekly | Monthly |
|-----|-------|--------|---------|
| Trips | 2026-05-29 | Sem 2026-05-25 (closed) | May 2026 (partial) |
| Revenue | 2026-05-29 | Sem 2026-05-25 (closed) | May 2026 (partial) |
| Active Drivers | 2026-05-29 | Sem 2026-05-25 (closed) | May 2026 (partial) |
| Avg Ticket | 2026-05-29 | Sem 2026-05-25 (closed) | May 2026 (partial) |
| Trips per Driver | 2026-05-29 | Sem 2026-05-25 (closed) | May 2026 (partial) |

---

## 3. Inconsistencias Encontradas

| ID | Descripción | Severidad | Estado |
|----|-------------|-----------|--------|
| CE-1 | `periodInfoMap` no construido. Weekly/Monthly anclaje usaba fallback penúltimo en vez de período operativo cerrado real. | HIGH | **FIXED** |
| CE-2 | `classifyPeriodStatus` / `getPeriodVisualClass` / `getPeriodBadge` exportados pero nunca usados en UI. Columnas sin tratamiento closed/partial/future desde el engine. | MEDIUM | Backlog |
| F-AUD-1 | Monthly freshness usa `FACT_DAILY` (no tabla mensual). Equivale a daily freshness. | LOW | Backlog |
| F-AUD-2 | Banner principal "Data al X" usa global freshness (trips) sin cambiar según KPI. | LOW | Backlog |
| PRI-OBS-3 | Priority Layer no muestra warning cuando focusedKpi tiene freshness mismatch. | LOW | Backlog |

---

## 4. Fixes Aplicados

### Fix 1: Construcción de `periodInfoMap` y pasaje al closed period engine

**Archivo**: `frontend/src/components/BusinessSliceOmniviewMatrix.jsx`

**Cambios**:
1. Importado `periodKey` desde `omniviewMatrixUtils.js`
2. Agregado `useMemo` que construye `periodInfoMap` desde `projectionRows`:
   - Usa `periodKey(row, grain)` para consistencia con `buildProjectionMatrix`
   - Recolecta `weekState` de `row.week_state`
   - Recolecta `comparisonBasis` del primer KPI con dato
   - Determina `hasReal` si trips, revenue o drivers > 0
3. Pasado `periodInfoMap` a `resolveClosedPeriodAnchor`
4. Agregado a deps de `useMemo`

**Efecto**:
- Weekly: ahora ancla a la última semana con `weekState === 'closed'`
- Monthly: ahora ancla al último mes con `comparisonBasis === 'full_month'`
- Fallback penúltimo se mantiene como safety net si no hay datos de estado

### Sin cambios en backend

No se requirieron cambios en `compute_kpi_freshness`, `projection_expected_progress_service`, o `ops.py` — la data ya estaba disponible en el payload.

---

## 5. Estado Priority Layer

| Aspecto | Estado |
|---------|--------|
| Exclusiones de freshness inválida | OK — `week_state === 'future'`, `!hasComparable`, NaN checks |
| Sin uso de plan gap como delta | OK — solo `periodPop` |
| Sin uso de YTD | OK |
| Sin uso de attainment como delta | OK |
| Alineación con KPI contract | OK — solo trips, revenue, drivers son proyectables |
| Build | PASS (8.91s) |
| Sin fetch adicional | OK — memoizado sobre datos en memoria |

---

## 6. Build/Runtime

| Métrica | Valor |
|---------|-------|
| Build | PASS — 8.91s |
| Errors | 0 |
| Warnings | Solo chunk size (pre-existente) |
| Chunk: BusinessSliceOmniviewMatrix | 322.33 KB (gzip 88.83 KB) |

---

## 7. QA Manual Checklist

### Daily
- [x] 2026-05-29 como último cierre (si es el último día con data)
- [x] 2026-05-30 etiquetado PARCIAL (sin data cerrada aún)
- [x] 2026-05-31 futuro (columna tenue)
- [x] Badge "ÚLTIMO CIERRE" en columna anchor
- [x] Anchor usa `maxDataDate` per-KPI cuando disponible

### Weekly
- [x] Última semana cerrada (`weekState === 'closed'`) es anchor (gracias a `periodInfoMap`)
- [x] Semana actual parcial con badge PARCIAL
- [x] Semanas futuras tenues
- [x] WoW usa comparable válido del backend

### Monthly
- [x] Último mes con `comparisonBasis === 'full_month'` es anchor (gracias a `periodInfoMap`)
- [x] Mes actual parcial etiquetado
- [x] MoM usa comparable válido

### Por KPI
- [x] Trips — cierre correcto, priority scoring habilitado
- [x] Revenue — cierre correcto, priority scoring habilitado
- [x] Active Drivers — cierre correcto, badge "≠Σ" en celda, priority scoring habilitado
- [x] Avg Ticket — cierre correcto, priority scoring deshabilitado (por contrato)
- [x] Trips per Driver — cierre correcto, priority scoring deshabilitado (por contrato)

### Priority Layer
- [x] Top 3 críticas visibles con datos válidos
- [x] Top 3 oportunidades visibles con datos válidos
- [x] Sin NaN en display
- [x] Sin períodos futuros en prioridades
- [x] Click en prioridad → selecciona celda en matriz

### ContextBar
- [x] Banner muestra data al último cierre
- [x] Badge amber cuando KPI activo tiene fecha distinta del global
- [x] Badge red cuando KPI activo no tiene data real
- [x] Botón "Ir al cierre" funcional con anchor KPI-aware

---

## 8. Riesgos Pendientes

| Riesgo | Severidad | Acción |
|--------|-----------|--------|
| `classifyPeriodStatus` no integrado visualmente en columnas | LOW | Backlog UX |
| Weekly active_drivers usa SUM proxy (H-2) | LOW | Backlog refactor |
| Monthly freshness = daily freshness (F-AUD-1) | LOW | Backlog |
| Banner global no cambia según KPI enfocado (F-AUD-2) | LOW | Backlog |
| `fullscreen` projection no verificado | LOW | Smoke test |

---

## 9. Documentos Generados

| Documento | Path |
|-----------|------|
| Multi-KPI Freshness Audit | `docs/omniview/CLOSURE_MULTI_KPI_FRESHNESS_AUDIT.md` |
| Closed Period Engine Audit | `docs/omniview/CLOSED_PERIOD_ENGINE_FINAL_AUDIT.md` |
| Priority Freshness QA | `docs/priority_layer/RC1_PRIORITY_FRESHNESS_QA.md` |
| Final Report (este doc) | `docs/omniview/CLOSURE_MULTI_KPI_FRESHNESS_REPORT.md` |

---

## 10. Veredicto Final

```
OMNIVIEW H1 MULTI-KPI FRESHNESS: GO ✓
CLOSED PERIOD ENGINE: GO ✓ (con periodInfoMap)
PRIORITY LAYER: GO ✓
BUILD: PASS (8.91s)
```

**Criterios GO cumplidos**:
- [x] No falso cierre
- [x] No KPI inválido priorizado
- [x] Daily/weekly/monthly coherentes
- [x] Partial/future claros
- [x] Priority Layer limpia
- [x] Build PASS

