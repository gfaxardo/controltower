# OMNIVIEW MATRIX Aggregation Closure

## Problema raíz detectado

La Omniview Matrix combinaba dos errores de agregación:

1. `week_fact` se construía desde `day_fact` con `SUM(active_drivers)` y ratios no canónicos.
2. El frontend generaba totales y KPIs ejecutivos sumando o promediando filas ya agregadas.

Eso rompía la consistencia entre `daily`, `weekly` y `monthly`, especialmente en:

- `active_drivers`
- `avg_ticket`
- `commission_pct`
- `cancel_rate_pct`
- `trips_per_driver`

## Qué quedó corregido

### Reglas formales

Se centralizó la semántica de agregación en:

- `backend/app/config/kpi_aggregation_rules.py`

### Backend

- `backend/app/services/business_slice_incremental_load.py`
  - `week_fact` ya no se define matemáticamente como rollup desde `day_fact`
  - se añadieron componentes canónicos persistibles para ratios
- `backend/app/services/business_slice_service.py`
  - `weekly` pasa por un camino canónico desde `resolved`
  - comparativos parciales `weekly/monthly` ya no reconstruyen desde `FACT_DAILY`
  - `meta` expone totales canónicos por periodo y comparativos equivalentes
  - bucket `UNMAPPED` usa reconstrucción canónica por periodo

### Frontend

- `frontend/src/components/BusinessSliceOmniviewMatrix.jsx`
  - usa `meta.period_totals` / `meta.comparison_period_totals`
  - alinea KPIs ejecutivos al periodo actual
  - deja de depender como fuente principal de la agregación local para totales

### Base de datos

- se añadió la migración:
  - `backend/alembic/versions/130_omniview_matrix_canonical_aggregation.py`

## Archivos modificados

- `backend/app/config/kpi_aggregation_rules.py`
- `backend/app/services/business_slice_incremental_load.py`
- `backend/app/services/business_slice_service.py`
- `backend/alembic/versions/130_omniview_matrix_canonical_aggregation.py`
- `backend/scripts/audit_omniview_kpi_consistency.py`
- `backend/tests/test_omniview_matrix_aggregation_rules.py`
- `frontend/src/components/BusinessSliceOmniviewMatrix.jsx`
- `docs/omniview_matrix_kpi_aggregation_audit.md`
- `docs/OMNIVIEW_KPI_CONSISTENCY_REPORT.md`
- `docs/OMNIVIEW_MATRIX_AGGREGATION_CLOSURE.md`

## Validaciones ejecutadas

- `python -m py_compile ...`
  - `ok`
- `python -m pytest backend/tests/test_business_slice_omniview_service.py backend/tests/test_omniview_matrix_aggregation_rules.py`
  - `28 passed`
- `npm run build`
  - `ok`
- `python -m alembic upgrade head`
  - `ok`
- `python -m scripts.refresh_business_slice_mvs --month 2026-04 --no-daily --chunk-grain city`
  - `ok`
- `python -m scripts.backfill_business_slice_daily --from-date 2026-04 --to-date 2026-04 --no-week --chunk-grain city`
  - `ok`
- `python -m scripts.refresh_business_slice_mvs --backfill-from 2026-03 --backfill-to 2026-04 --chunk-grain city`
  - `parcial útil`: marzo `month_fact` y `day_fact` quedaron recalculados antes del error detectado en el SQL semanal antiguo

## Evidencia de corrección

- `weekly` ya no depende en runtime del rollup que duplicaba `drivers`.
- Las reglas críticas quedaron cubiertas por tests:
  - `active_drivers` no sumable
  - `avg_ticket` requiere componentes canónicos
  - `week_fact` SQL ya no usa `sum(d.active_drivers)`
- El frontend ya prioriza totales canónicos entregados por backend.
- La base quedó en `130_omniview_matrix_canonical_aggregation (head)`.
- `month_fact` abril y `day_fact` abril quedaron recalculados para la Matrix actual.

## Riesgos pendientes

1. El backfill histórico completo de `week_fact` todavía puede requerir una corrida dedicada si otro consumidor fuera de Omniview Matrix depende de esa tabla persistida.
2. La auditoría amplia contra la vista resuelta sigue siendo costosa; el script quedó listo para ejecuciones batch fuera de la ventana interactiva.

## Backlog residual

1. Ejecutar un backfill semanal histórico completo si se quiere alinear también `ops.real_business_slice_week_fact` como persistencia de largo plazo.
2. Programar la auditoría completa `backend/scripts/audit_omniview_kpi_consistency.py` como tarea batch/offline.

## Cierre

La corrección estructural de agregación quedó implementada en código, centralizada, desplegada en esquema y operativa para la Omniview Matrix actual. El residual pendiente es de endurecimiento batch/histórico, no de corrección funcional inmediata de la vista.
