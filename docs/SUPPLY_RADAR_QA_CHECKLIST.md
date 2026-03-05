# Supply (Real) — Radar — Checklist QA

## Backend (FastAPI)

| # | Verificación | Cómo comprobar |
|---|--------------|----------------|
| 1 | GET /ops/supply/geo | `GET /ops/supply/geo` → `{ countries, cities, parks }`. Con `?country=X` ciudades y parks filtrados. |
| 2 | GET /ops/supply/segments/series | `?park_id=...&from=...&to=...` → week_start DESC, segment_week, drivers_count, trips_sum. `format=csv` → text/csv. |
| 3 | GET /ops/supply/alerts | `?park_id=...&from=...&to=...&severity=P0` → alertas. `format=csv` → CSV con headers. |
| 4 | GET /ops/supply/alerts/drilldown | `?park_id=...&week_start=...&segment_week=...&alert_type=...&format=csv` → lista drivers, orden baseline_trips_4w_avg desc. |
| 5 | POST /ops/supply/refresh-alerting | Con `SUPPLY_REFRESH_ALLOWED=true` → 200. Sin env → 403. |

## Frontend (SupplyView)

| # | Verificación | Cómo comprobar |
|---|--------------|----------------|
| 1 | Filtros cascada | País → Ciudad → Park. Al cambiar país se resetean ciudad y park. Al cambiar ciudad se resetea park. |
| 2 | Park obligatorio | Sin park seleccionado no se cargan Overview/Segments/Alerts; mensaje "Selecciona un park". |
| 3 | Siempre park_name, city, country | En dropdown park se muestra "park_name · city · country". En modal drilldown título con park_name, city, country. |
| 4 | Tab Overview | Cards (activations, churned, reactivated, net growth, active drivers, churn rate). Tabla serie por periodo. Download CSV. |
| 5 | Tab Segments | Tabla week_start DESC × segment_week (drivers_count, trips_sum, share_of_active). Download CSV. |
| 6 | Tab Alerts | Lista con badges P0..P3, tipo (Caída/Spike), baseline, actual, Δ%, mensaje. "Ver drivers" abre modal. "CSV" descarga drilldown. |
| 7 | Modal Drilldown | Tabla: driver_key, prev_segment, current_segment, trips_week, baseline_4w_avg, change_type. Export CSV. Placeholder "Enviar a equipo ops". |
| 8 | Orden week_start | Todas las tablas/series con semana más reciente arriba (DESC). |
| 9 | Refrescar MVs | Botón "Refrescar MVs" (solo con park); confirmación; al terminar recarga alertas y drilldown si estaba abierto. |

## Verificación con datos reales

- Probar con un **park que tenga data** en `ops.mv_supply_weekly` y `ops.mv_supply_segments_weekly`.
- Confirmar que al cambiar **country/city** el listado de parks se actualiza (cascada).
- Confirmar que **Alerts** solo muestra filas cuando existen anomalías (mv_supply_alerts_weekly).
- Confirmar que el **drilldown** de una alerta coincide: mismos week_start, park_id, segment_week que la alerta; conductores con downshift/drop.

## Capturas sugeridas

1. Filtros + Tab Overview con cards y tabla.
2. Tab Segments con tabla pivot por semana/segmento.
3. Tab Alerts con badges P0/P1 y botones Ver drivers / CSV.
4. Modal Drilldown abierto con tabla de conductores y botón Export CSV.
