# INCIDENTE 1H.2K — TEMPORAL COMPARATIVES REGRESSION

## Veredicto Final: GO

---

## 1. Causa Raíz

La infraestructura de comparativos temporales (DoD/WoW/MoM) ya existía en el código pero solo se ejecutaba en el **runtime path** (`get_omniview_projection` con `_allow_runtime_fallback=True`). El **serving fact path** (`_try_load_from_serving_fact`) cargaba los datos desde `serving.omniview_projection_daily_fact` y los devolvía sin calcular `period_over_period`.

### Cadena del bug

```
API request → _try_load_from_serving_fact → rows from DB
  → _serving_fact_row_to_display → display_rows (SIN period_over_period)
  → return response → frontend recibe rows SIN period_over_period
  → computeProjectionDeltas → delta.periodPop = null
  → celda no muestra DoD/WoW/MoM
```

### Fix

Se añadió `apply_period_over_period_inplace(display_rows, grain)` en `_try_load_from_serving_fact` después de convertir las filas de DB a display format. Esta función agrupa filas por línea (country+city+bsn), las ordena por período, y calcula la variación contra el período anterior para cada una. Es O(n log n) — milisegundos para 1500 filas.

---

## 2. Archivo Modificado

| Archivo | Cambio | Línea |
|---------|--------|-------|
| `projection_expected_progress_service.py` | `apply_period_over_period_inplace` en serving fact path | 1636 |
| `projection_expected_progress_service.py` | `period_over_period` y `metric_variations` en meta | 1676-1683 |

---

## 3. Contrato de Comparativos

| Grain | Label | Fórmula | Campo |
|-------|-------|---------|-------|
| daily | DoD | current_day vs current_day - 7 days | `period_over_period.metrics.{kpi}` |
| weekly | WoW | week_start vs week_start - 7 days | `period_over_period.metrics.{kpi}` |
| monthly | MoM | month vs previous month | `period_over_period.metrics.{kpi}` |

### Métricas comparadas

- `trips_completed` — abs + pct
- `revenue_yego_net` — abs + pct
- `active_drivers` — abs + pct
- `avg_ticket` — ratio derivado

### Estructura por fila

```json
{
  "period_over_period": {
    "kind": "wow",
    "label": "WoW",
    "prev_period": "2026-05-18",
    "comparable": true,
    "metrics": {
      "trips_completed": {"abs": -1250, "pct": -2.1, "cur_real": 58200, "prev_real": 59450},
      "revenue_yego_net": {"abs": -320.5, "pct": -1.8, ...},
      "active_drivers": {"abs": -5, "pct": -2.0, ...},
      "avg_ticket": {"abs": 0.15, "pct": 0.5, ...}
    }
  }
}
```

---

## 4. Pipeline End-to-End

| Etapa | Acción |
|-------|--------|
| API request | `GET .../omniview-projection?grain=weekly&year=2026` |
| Serving fact read | `_try_load_from_serving_fact` → DB query → 1470 rows |
| Display convert | `_serving_fact_row_to_display` → 1470 display rows |
| **PoP compute (NEW)** | `apply_period_over_period_inplace` → añade `period_over_period` a cada fila |
| API response | `data: [{...period_over_period: {...}}, ...]` |
| Frontend delta | `computeProjectionDeltas` → `delta.periodPop` = abs/pct |
| Frontend render | `ProjectionCellRender` → "WoW -2.1%" |

---

## 5. Frontend (sin cambios — ya implementado)

- `projectionMatrixUtils.js:582` — lee `cell.raw?.period_over_period`
- `projectionMatrixUtils.js:612` — mapea a `delta.periodPop`, `periodPopLabel`, `periodPopComparable`
- `projectionMatrixUtils.js:554` — `fmtPeriodPop` formatea abs o pct
- `BusinessSliceOmniviewMatrixCell.jsx:392` — renderiza label + valor

---

## 6. QA Script

```bash
python backend/scripts/validate_phase1h2k_temporal_comparatives.py
```

Valida:
- meta.period_over_period existe
- filas tienen period_over_period
- hay filas comparables (no primer período)
- prev_period, kind, metrics presentes
- trips_completed abs + pct calculados
- cross-country (Peru + Colombia)

---

## 7. GO / NO-GO

### GO:
- [x] Fix aplicado en 1 línea (+ meta fields)
- [x] `apply_period_over_period_inplace` ya existía y es ligero
- [x] Frontend ya renderiza periodPop (sin cambios)
- [x] No requiere migración de serving fact
- [x] No toca filtros, weekly ISO, ni plan logic
- [x] QA script creado

### Requiere:
- [ ] Reiniciar backend para aplicar el fix
- [ ] Ejecutar QA script
- [ ] Validar UI: DoD/WoW/MoM visibles en celda

### NO-GO:
- [ ] Ninguna estructural

**VEREDICTO: GO**
