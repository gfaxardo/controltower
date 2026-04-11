# Omniview Matrix KPI Aggregation Audit

## Diagnóstico raíz

La cadena de Omniview Matrix tenía dos problemas estructurales distintos pero acumulativos:

1. `weekly` se construía desde `ops.real_business_slice_day_fact` con un rollup inválido para KPIs semi-aditivos y ratios.
2. La UI recomponía totales y KPIs ejecutivos sumando o promediando filas ya agregadas por slice/flota/subflota.

El caso más visible era `active_drivers`:

- En `day_fact` el KPI se calcula correctamente como `COUNT(DISTINCT driver_id)` por día y dimensión.
- En `week_fact` se estaba haciendo `SUM(active_drivers)` sobre esa capa diaria.
- En el frontend, la fila total y los KPIs ejecutivos volvían a sumar `active_drivers` entre líneas visibles.

Resultado: duplicación o triplicación en `weekly` y riesgo equivalente en `monthly` cuando se recalculaban totales locales.

## Cadena de datos mapeada

### Frontend

- Vista principal: `frontend/src/components/BusinessSliceOmniviewMatrix.jsx`
- Tabla: `frontend/src/components/BusinessSliceOmniviewMatrixTable.jsx`
- Utilidades de matrix: `frontend/src/components/omniview/omniviewMatrixUtils.js`
- Endpoint mensual: `GET /ops/business-slice/monthly`
- Endpoint semanal: `GET /ops/business-slice/weekly`
- Endpoint diario: `GET /ops/business-slice/daily`
- Endpoint trust: `GET /ops/business-slice/matrix-operational-trust`
- Endpoint cobertura: `GET /ops/business-slice/coverage-summary`

### Backend

- Router: `backend/app/routers/ops.py`
- Servicio principal Matrix: `backend/app/services/business_slice_service.py`
- Loader facts: `backend/app/services/business_slice_incremental_load.py`
- Trust operacional: `backend/app/services/omniview_matrix_integrity_service.py`
- Registro de fuente: `backend/app/config/source_of_truth_registry.py`

### Capa SQL / facts

- Daily: `ops.real_business_slice_day_fact`
- Weekly: `ops.real_business_slice_week_fact`
- Monthly: `ops.real_business_slice_month_fact`
- Fuente atómica canónica: `ops.v_real_trips_business_slice_resolved`

## Hallazgos concretos

1. `backend/app/services/business_slice_incremental_load.py`
   `week_fact` se generaba desde `day_fact` y hacía `SUM(active_drivers)`; también recomponía ratios con `AVG(...)` o denominadores no canónicos.
2. `backend/app/services/business_slice_service.py`
   `_fetch_resolved_metrics_by_dims_for_range()` en realidad leía `FACT_DAILY` y agregaba otra vez desde una capa ya resumida, contaminando comparativos parciales `weekly/monthly`.
3. `frontend/src/components/omniview/omniviewMatrixUtils.js`
   La fila total sumaba `active_drivers` y promediaba `avg_ticket` / `commission_pct` entre filas visibles.
4. `frontend/src/components/BusinessSliceOmniviewMatrix.jsx`
   Los KPIs ejecutivos se derivaban de `rows` completos, mezclando periodos y manteniendo agregación local no canónica.
5. `backend/app/services/business_slice_service.py`
   El bucket `UNMAPPED` agregaba `weekly/monthly/daily` con `SUM/AVG` sobre facts, reproduciendo el mismo riesgo matemático.

## Matriz KPI por KPI

| KPI | Definición actual | Fuente actual | Grano actual | Método actual detectado | Estado | Riesgo | Corrección aplicada/propuesta |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `trips_completed` | Viajes completados | `resolved`, `day_fact`, `week_fact`, `month_fact` | daily/weekly/monthly | `COUNT(*)` atómico o `SUM(trips_completed)` | Correcto si la fuente es canónica | Bajo | Mantener como aditivo puro |
| `revenue_yego_net` | Revenue neto completado | mismas capas | daily/weekly/monthly | `SUM(revenue_yego_net)` | Correcto si la fuente base es canónica | Bajo | Mantener como aditivo puro |
| `trips_cancelled` | Viajes cancelados | mismas capas | daily/weekly/monthly | `COUNT(*)` o `SUM(trips_cancelled)` | Correcto si la fuente es canónica | Bajo | Mantener como aditivo puro |
| `active_drivers` | Conductores activos con viaje completado | `day_fact`, `week_fact`, `month_fact`, UI totals | daily/weekly/monthly | `COUNT(DISTINCT driver_id)` en daily, pero `SUM(active_drivers)` en weekly y totales UI | Incorrecto | Duplicación por días y por líneas visibles | Rebuild canónico desde `resolved`; prohibido rollup desde lower grain |
| `avg_ticket` | Ticket medio de viajes completados | facts + UI totals | daily/weekly/monthly | `AVG(ticket)` atómico correcto; pero UI promediaba promedios y weekly no tenía numerador persistido | Incorrecto en rollups | Promedio de promedios | Persistir `ticket_sum_completed` + `ticket_count_completed`; recalcular ratio |
| `commission_pct` | Revenue / total_fare positivo | facts + UI totals | daily/weekly/monthly | Atómico correcto; `weekly` antiguo promediaba porcentajes; UI también promediaba | Incorrecto en rollups | Sesgo por denominadores distintos | Persistir `total_fare_completed_positive_sum`; recalcular ratio |
| `cancel_rate_pct` | Cancelados / base relevante | facts + UI totals | daily/weekly/monthly | Algunas capas recalculan bien; otras hacían `AVG(cancel_rate_pct)` | Incorrecto en rollups locales | Ratio mal ponderado | Recalcular desde `trips_cancelled` y base relevante |
| `trips_per_driver` | Viajes / conductores activos | facts + UI totals | daily/weekly/monthly | Derivado con driver denominator inválido en weekly y UI totals | Incorrecto | Propaga error de drivers | Recalcular desde `trips_completed` y `active_drivers` canónicos |

## Reglas canónicas centralizadas

Se añadió `backend/app/config/kpi_aggregation_rules.py` con reglas explícitas por KPI:

- `aggregation_type`
- `atomic_formula`
- `daily_formula`
- `weekly_formula`
- `monthly_formula`
- `rebuild_from_atomic`
- `allowed_rollup_from_lower_grain`
- `rollup_components_required`

Clasificación final:

- Aditivos: `trips_completed`, `trips_cancelled`, `revenue_yego_net`
- Semi-aditivos: `active_drivers`
- No aditivos / ratios: `avg_ticket`, `commission_pct`, `cancel_rate_pct`
- Derivados: `trips_per_driver`

## Corrección implementada

### Backend

- `weekly` dejó de depender matemáticamente de `day_fact` para la lectura canónica del endpoint.
- `week_fact` loader quedó redefinido para agregarse desde `ops.v_real_trips_business_slice_resolved`.
- Se añadieron componentes canónicos persistibles:
  - `ticket_sum_completed`
  - `ticket_count_completed`
  - `total_fare_completed_positive_sum`
- Los comparativos parciales `weekly/monthly` ahora se reconstruyen desde `resolved`, no desde `FACT_DAILY`.
- El `meta` de Matrix ahora puede devolver:
  - `period_totals`
  - `comparison_period_totals`
  - `unmapped_period_totals`

### Frontend

- La Matrix consume totales canónicos del backend cuando están disponibles.
- Los KPIs ejecutivos se alinean al periodo actual canónico, no a la suma de todas las filas cargadas.
- Se evita seguir usando la agregación local como fuente principal de verdad.

## Estado operativo

La corrección quedó implementada y desplegada:

- se resolvieron los drift de migración en `126` y `127`,
- la base quedó en `130_omniview_matrix_canonical_aggregation (head)`,
- `month_fact` y `day_fact` del periodo actual quedaron refrescados,
- y la ruta semanal de Omniview Matrix ya opera desde la capa canónica `resolved`.

El remanente pendiente es de batch histórico completo, no de funcionamiento inmediato de la Matrix.
