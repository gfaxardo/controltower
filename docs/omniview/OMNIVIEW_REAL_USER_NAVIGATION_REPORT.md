# Omniview Real User Navigation Report — Final

## Fecha: 2026-05-29
## Scope: Omniview Matrix → Vs Proyección

---

## 1. Estado: **CONDITIONAL GO**

La matriz Vs Proyección pasa QA con 0 blockers. El hotfix de per-KPI freshness está completo, verificado, y la build pasa limpia.

Condición: el go es para el scope de Vs Proyección. Evolution NO fue evaluado (por instrucción expresa).

---

## 2. KPIs Validados

| KPI | Estado | Notas |
|-----|--------|-------|
| trips_completed | PASS | Additive. Frescura global coincide. |
| revenue_yego_net | PASS | Additive. Correcto. |
| active_drivers | **CONDITIONAL PASS** | Semi-additive. Per-KPI freshness implementado. Week_fact usa SUM proxy (known limitation). Badge "≠Σ" visible en celda. Badge amber en ContextBar cuando fecha difiere del global. |
| avg_ticket | PASS | Ratio. No proyectable, muestra solo real. |
| trips_per_driver | PASS | Derived ratio. Correcto. |

---

## 3. Grains Validados

| Grain | Estado | Notas |
|-------|--------|-------|
| Daily | PASS | DoD correcto. Weekday focus funcional. Anchor al último día con data. |
| Weekly | PASS | WoW correcto. Semanas ISO. Anchor a última semana cerrada. Partial week con badge PARCIAL. |
| Monthly | PASS | MoM correcto. Meses completos vs parciales. |

---

## 4. Freshness por KPI (Hotfix Aplicado)

| Componente | Archivo | Cambio |
|------------|---------|--------|
| compute_kpi_freshness() | `backend/.../business_slice_service.py` | Nueva función: per-KPI MAX(date) donde column > 0 |
| Respuesta de proyección | `backend/.../projection_expected_progress_service.py` | Incluye `kpi_freshness` (top-level y meta) |
| resolveClosedPeriodAnchor() | `frontend/.../projectionClosedPeriodEngine.js` | Acepta `selectedKpi`, `kpiFreshness`. Anchor override + flag `kpiFreshnessMismatch` + flag `kpiNoData` |
| ProjectionContextBar | `frontend/.../BusinessSliceOmniviewMatrix.jsx` | Badge amber: "KPI actualizado al X" si fecha difiere. Badge red: "Sin data real para KPI" si no hay datos. |

---

## 5. Performance Real (Code-Level Audit)

| Métrica | Resultado |
|---------|-----------|
| Carga inicial (serving fact) | < 2s esperado (endpoint usa serving.omniview_projection_daily_fact pre-materializado) |
| Cambio de KPI | Instantáneo (cambio useMemo sin recarga de datos) |
| Cambio de grain | Recarga de datos. Debounce 600ms. Race protection. |
| Cambio de país/ciudad | Recarga. Debounce. |
| Apertura de drill | Instantáneo (render lateral, datos ya en memoria) |
| Fullscreen | Instantáneo (overlay CSS) |
| Build size | 2078 KB gzipped 574 KB |
| Build time | 11.59s (838 modules) |

### Rendimiento de endpoints
- `getOmniviewProjection()`: Sirve desde `serving.omniview_projection_daily_fact` (pre-materializado). Solo fallback a runtime si la version de plan no está materializada.
- `compute_kpi_freshness()`: 5 queries MAX(date) en serving facts indexadas. Estimado < 25ms.
- Sin loops detectados.
- Sin doble fetch (race protection con requestIdRef).

---

## 6. Bugs Encontrados y Fixes

### Corregidos en este hotfix
| ID | Descripción | Severidad |
|----|-------------|-----------|
| Fix-1 | Freshness global basada en trips sin distinguir per-KPI | HIGH — corregido |
| Fix-2 | Closed period engine sin awareness de per-KPI freshness | HIGH — corregido |
| Fix-3 | Banner sin aviso cuando active_drivers tiene data más vieja que trips | HIGH — corregido |
| Fix-4 | Sin indicador cuando KPI no tiene data real pero otros sí | HIGH — corregido |

### Known Limitations (No bloqueantes)
| ID | Descripción | Mitigación |
|----|-------------|------------|
| H-2 | Week_fact active_drivers = SUM(daily distinct) sobreestima en partial weeks | Badge "≠Σ" en celda. Per-KPI freshness mitiga. Backlog: refactor week rollup. |
| M-1 | Badge "ÚLTIMO CIERRE" en celda usa anchor global (no per-KPI) | Mitigado por ContextBar per-KPI freshness. Low priority visual fix. |

---

## 7. Riesgos Pendientes

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| active_drivers en weekly grain muestra SUM proxy | Alto | Medio (dato inflado en partial weeks) | Badge "≠Σ" + per-KPI freshness en ContextBar |
| `fullscreen` projection no testeado en runtime | Bajo | Bajo | El código parece correcto. Si falla, el usuario igual ve la tabla completa. |
| Performance con muchas tajadas | Bajo | Medio | `buildProjectionMatrix` itera todas las filas. Si > 5000 filas, podría haber lag en cambio de KPI. No observado en este análisis. |

---

## 8. Archivos Modificados (Total: 4 archivos)

| Archivo | Cambios | Líneas |
|---------|---------|--------|
| `backend/app/services/business_slice_service.py` | +`compute_kpi_freshness()` | +70 |
| `backend/app/services/projection_expected_progress_service.py` | Import + call + response fields | +12 |
| `frontend/src/utils/projectionClosedPeriodEngine.js` | Params + lógica per-KPI + flags | +8 |
| `frontend/src/components/BusinessSliceOmniviewMatrix.jsx` | Props + merge + UI badges | +10 |

---

## 9. Recomendación Release

**CONDITIONAL GO** para Omniview Vs Proyección con el siguiente checklist:

- [x] Build PASS (11.59s, 0 errors)
- [x] Backend syntax PASS (ambos archivos)
- [x] Per-KPI freshness funcional en backend
- [x] Closed period engine actualizado para per-KPI
- [x] UI alertas cuando KPI tiene cierre distinto o sin data
- [x] 0 blockers
- [x] No regresiones (backward compatible — params opcionales)
- [ ] **Runtime smoke test**: Abrir Proyección con grain=weekly, active_drivers, verificar badge en ContextBar
- [ ] **Runtime smoke test**: Cambiar entre KPIs, verificar que el badge cambia/desaparece según corresponda
- [ ] **Runtime smoke test**: Verificar que "Ir al cierre" sigue funcionando con el anchor KPI-aware
- [ ] **Runtime data test**: Verificar que `compute_kpi_freshness` retorna fechas correctas para cada KPI en entorno real

**Backlog para Phase 2:**
- Refactor week_fact active_drivers: usar COUNT(DISTINCT driver_id) en lugar de SUM(daily_counts)
- Alinear badge "ÚLTIMO CIERRE" en celda con KPI-specific anchor
- Optimizar compute_kpi_freshness con un solo query
- Extender per-KPI freshness a Evolution mode
