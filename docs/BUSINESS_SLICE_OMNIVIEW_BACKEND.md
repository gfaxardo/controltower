# Business Slice Omniview — backend

## API

`GET /ops/business-slice/omniview` — expone el servicio sin reemplazar `/business-slice/monthly|weekly|daily`.

Parámetros: `granularity` (requerido), `period`, `country` (obligatorio weekly/daily), `city`, `business_slice`, `fleet`, `subfleet`, `include_subfleets`, `daily_window_days` (1–120), `limit_rows`, `include_previous_only_rows`.

Errores de validación del servicio: **422** con `detail` texto. Violaciones de Query (p. ej. `daily_window_days` > 120): **422** con `detail` estilo FastAPI.

## Módulo

`backend/app/services/business_slice_omniview_service.py` — función principal `get_business_slice_omniview(...)`.

## Fuentes y V1

| Granularidad | Fuente | Métricas |
|--------------|--------|----------|
| `monthly` | `ops.real_business_slice_month_fact` (detalle) + `ops.v_real_trips_business_slice_resolved` (subtotales país y total) | Viajes, cancelaciones, conductores, ticket, revenue, comisión %, viajes/conductor, cancel rate % |
| `weekly` / `daily` | Solo `v_real_trips_business_slice_resolved` agregado | Igual, con `SUM(total_fare)` y `SUM(revenue)` para `commission_pct` alineado al loader mensual |

## Comparativos

- **MoM**: mes civil `current` vs mes anterior.
- **WoW**: `trip_week` = lunes ISO (misma convención que `date_trunc('week', ...)` en enriched).
- **Daily**: `trip_date` vs `trip_date - 7 días`.

## Guardrails

- `country` obligatorio para `weekly` y `daily` (reduce coste y evita scans globales).
- `daily_window_days` entre 1 y 120 (validado; reservado para extensiones multi-día; el V1 actual compara un solo día vs su par -7).

## Por qué no se promedian ratios

`commission_pct`, `avg_ticket` agregados y `cancel_rate_pct` deben calcularse desde **sumas de componentes** (o `COUNT`/`SUM` en SQL), no como promedio de ratios por fila. Los subtotales por país y el total global usan agregación SQL sobre `V_RESOLVED` con la misma fórmula de comisión que el loader (`SUM(revenue)` / `SUM(total_fare)` con los mismos filtros de completados y `total_fare > 0`).

## Limitaciones V1

- Cobertura por tajada: no hay fuente a ese grano; `meta.coverage_note` lo indica.
- `mixed_currency_warning` si `granularity=monthly` sin `country` y hay agregación monetaria implícita multi-país.
- Conexión por defecto `get_db_drill` para tolerar consultas pesadas sobre la vista resuelta.

## Contrato de respuesta (resumen)

- Campos de periodo y flags en raíz: `granularity`, `comparison_rule`, `current_period_*`, `previous_period_*`, `is_*_partial`, `mixed_currency_warning`, `warnings`.
- `meta`: `detail_source`, `totals_source`, `subtotals_source`, `units` (p. ej. `commission_pct` en ratio 0–1), `coverage_level`, `coverage_reference`, `daily_window_days`.
- `rows` / `subtotals` / `totals` con métricas, deltas, `signals` (direction + signal), `flags` (`not_comparable`, `coverage_unknown`, …).

## Tests

- `backend/tests/test_business_slice_omniview_service.py` — lógica pura y guardrails.
- `backend/tests/test_ops_business_slice_omniview.py` — endpoint (requiere `httpx` para `TestClient`).
