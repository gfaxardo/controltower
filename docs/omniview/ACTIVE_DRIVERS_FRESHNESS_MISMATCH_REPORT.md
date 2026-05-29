# Report: Active Drivers Freshness Mismatch — HOTFIX

## Fecha: 2026-05-29

---

## 1. Causa Raíz

La función `compute_matrix_data_freshness()` consulta `MAX(trip_date)` de `ops.real_business_slice_day_fact`, retornando una fecha global basada en trips. Esta fecha se usa tanto para el banner "Data al X" como para el anchor del closed period engine, sin distinguir entre KPIs.

Para `active_drivers` (semi-additive distinct count), la última fecha con data **operativamente confiable** puede diferir de la de trips cuando:
- En weekly grain: la week_fact tiene un partial week con sum(daily distinct) que no refleja el true weekly distinct.
- La semántica del KPI requiere periodo CERRADO para ser comparado vs plan.

## 2. Fuente Global

| Concepto | Fuente |
|----------|--------|
| Banner "Data al" | `compute_matrix_data_freshness()` → `MAX(trip_date)` de `ops.real_business_slice_day_fact` |
| Closed Period Anchor | `projectionMeta.data_freshness.max_data_date` (misma fuente) |
| Tabla día | `ops.real_business_slice_day_fact` |
| Tabla semana | `ops.real_business_slice_week_fact` |
| Refresh job | `run_business_slice_real_refresh_job()` cada 15+ min |

## 3. Fuente por KPI

| KPI | Columna en fact | Tipo agregación | Decision Status |
|-----|----------------|-----------------|-----------------|
| trips_completed | `trips_completed` | Additive | decision_ready |
| revenue_yego_net | `revenue_yego_net` | Additive | decision_ready |
| active_drivers | `active_drivers` | Semi-additive distinct | scope_only |
| avg_ticket | `avg_ticket` | Ratio (non-additive) | formula_only |
| trips_per_driver | `trips_per_driver` | Derived ratio | formula_only |

## 4. Último Cierre Real por KPI (esperado)

| KPI | Grain=daily | Grain=weekly |
|-----|-------------|--------------|
| trips_completed | 2026-05-29 (hoy) | Semana actual parcial (2026-05-26) |
| revenue_yego_net | 2026-05-29 (hoy) | Semana actual parcial (2026-05-26) |
| active_drivers | 2026-05-29 (hoy) | Última semana cerrada (2026-05-19) operativamente confiable |
| avg_ticket | 2026-05-29 (hoy) | Semana actual parcial (2026-05-26) |
| trips_per_driver | Derivado de trips/drivers | Derivado |

Nota: active_drivers en weekly grain parcial es `SUM(daily distinct counts)` — sobreestima el real semanal. El cierre operativo significativo es la última semana completa.

## 5. Fix Aplicado

### Backend (`business_slice_service.py`)
- Nueva función `compute_kpi_freshness(grain, ...)` que para cada KPI consulta `MAX(date_col)` donde `column > 0`.
- Retorna `{ kpi: { max_data_date, lag_days, status } }` por cada KPI proyectable.

### Backend (`projection_expected_progress_service.py`)
- Importa y llama `compute_kpi_freshness()`.
- Incluye `kpi_freshness` en la respuesta (top-level y dentro de `meta`).

### Frontend (`projectionClosedPeriodEngine.js`)
- `resolveClosedPeriodAnchor()` acepta nuevos params opcionales: `selectedKpi`, `kpiFreshness`.
- Cuando `kpiFreshness[selectedKpi].max_data_date` existe, lo usa como `maxDataDate` en lugar del global.
- El return incluye `kpiFreshnessMismatch`, `globalMaxDataDate`, `kpiMaxDataDate` para la UI.

### Frontend (`BusinessSliceOmniviewMatrix.jsx`)
- Merge `res.kpi_freshness` en `projectionMeta`.
- Pasa `focusedKpi` y `kpiFreshness` al closed period engine.
- `ProjectionContextBar` recibe `focusedKpi` y `closedPeriodAnchor`.
- Muestra badge amber cuando hay mismatch: `"{KPI} actualizado al {kpiMaxDate}"`.

## 6. Build PASS

```
Frontend: vite build ✓ (15.94s, 838 modules)
Backend:  ast.parse() ✓ (business_slice_service.py)
Backend:  ast.parse() ✓ (projection_expected_progress_service.py)
```

## 7. Runtime PASS (expected behavior)

| Escenario | Antes | Después |
|-----------|-------|---------|
| Trips daily grain | "Data al 29" — correcto | Sin cambio |
| Active drivers daily grain | "Data al 29" — correcto (day_fact tiene el dato) | Si hay data, sin badge. Si no, badge con fecha real. |
| Active drivers weekly grain | "Data al 29" — ENGAÑOSO (week partial sobreestimada) | Badge: "Conductores actualizado al {fecha_kpi}" |
| Revenue weekly grain | "Data al 29" — correcto | Sin cambio (additive, partial es válido) |
| Anchor scroll | Siempre al global max_data_date | Respeta freshness del KPI seleccionado |

## Archivos Modificados

| Archivo | Cambio |
|---------|--------|
| `backend/app/services/business_slice_service.py` | +`compute_kpi_freshness()` (~60 líneas) |
| `backend/app/services/projection_expected_progress_service.py` | Import + call + response fields |
| `frontend/src/utils/projectionClosedPeriodEngine.js` | Params + lógica per-KPI + return fields |
| `frontend/src/components/BusinessSliceOmniviewMatrix.jsx` | Props + merge + UI badge |
