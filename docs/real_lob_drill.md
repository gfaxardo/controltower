# Real LOB Drill-Down (Fase 2C+)

Vista jerárquica de observabilidad Real por país, con desglose por LOB o por Park, **Unit Economics** (margen) y **Uso** (distancia). **No mezcla Plan con Real** y es independiente del flujo Plan vs Real REALKEY.

## Definiciones (margen y distancia)

- **Margen**: basado en `trips_all.comision_empresa_asociada`.
  - **margin_total**: suma de comisión (por periodo/grupo). Nulls excluidos del SUM.
  - **margin_unit_avg** (Margen/trip): promedio por viaje; si hay nulls se excluyen del AVG pero el conteo de viajes no cambia. En totales globales: **margin_unit_avg_global** = margin_total / total_trips (promedio ponderado).
- **Distancia**: `trips_all.distancia_km` viene en **metros**; se convierte a km con `/1000.0`.
  - **distance_total_km**: suma de distancias en km (nulls tratados como 0 en la suma para coherencia con trips).
  - **distance_km_avg** (Km prom): distance_total_km / trips por fila; en totales: **distance_km_avg_global** = distance_total_km / total_trips (evita “promedio de promedios”).
- **B2B**: `pago_corporativo IS NOT NULL` → B2B; sino B2C. Se exponen **b2b_trips**, **b2b_margin_total**, **b2b_margin_unit_avg**, **b2b_distance_km_avg** (y totales km B2B) para filtrar o mostrar ratio cuando segmento = Todos.

## Comportamiento

1. **Vista principal**: timeline mensual o semanal por país (CO y PE separados), con totales globales, Margen/trip y Km prom por fila, y B2B (viajes y % si segmento = Todos).
2. **Doble click** en una fila (país + periodo) despliega subfilas por LOB o por Park con Viajes, Margen/trip, Km prom y B2B (si segmento = Todos).
3. **Controles**: Periodo (Mensual | Semanal), Desglose (LOB | Park), Segmento (Todos | B2B | B2C).

## Reglas UX

- Orden: periodo DESC; subfilas por trips DESC.
- Desglose solo al doble click (expand/collapse).
- **Calendario completo**: se listan todos los meses/semanas ISO hasta el periodo actual (inclusive), aunque no haya datos (trips = 0).
- **Estados de periodo**: CERRADO (verde), ABIERTO (azul), FALTA_DATA (rojo; falta data hasta cierre de ayer), VACIO (gris).
- **Cobertura**: se muestra "Último día con data" y "Último periodo con data" por país (endpoint `/ops/real-drill/coverage`).
- **Drill por Park**: nombres resueltos con `park_name_resolved`; bucket auditables: OK, SIN_PARK_ID, PARK_NO_CATALOG (estos dos se muestran en badge rojo). No se ocultan filas sin park_id o sin catálogo.
- Mostrar "—" cuando trips = 0 o valor null; evitar dividir por cero.

## Backend

### Capa de datos (051: MV rollup diaria)

- **ops.dim_city_country**: Mapping `city_norm` → `country` (co/pe/unk). Country se deriva de city, no de `parks.city`.
- **ops.mv_real_rollup_day**: MV agregada diaria desde `trips_all` + `parks` + `dim_city_country`. Grano: (trip_day, country, city, park_id, lob_group, segment_tag). Métricas: trips, b2b_trips, margin_total, distance_total_km, last_trip_ts. **Refresh diario recomendado**.
- **ops.v_real_data_coverage**: Por país desde MV: `last_trip_date`, `last_trip_ts`, `min_month`, `min_week`, `last_month_with_data`, `last_week_with_data`.
- **ops.v_real_drill_country_month/week**: Calendario completo (countries × calendar) hasta periodo actual. Columnas: `country`, `period_start`, `trips`, `b2b_trips`, `margin_total`, `margin_unit_avg`, `distance_total_km`, `distance_km_avg`, `b2b_pct`, `last_trip_ts`, `expected_last_date`, `falta_data`, `estado` (CERRADO | ABIERTO | FALTA_DATA | VACIO).
- **ops.v_real_drill_lob_month/week**: Agregado por LOB desde MV.
- **ops.v_real_drill_park_month/week**: Agregado por park con `park_name_resolved`, `park_bucket` desde MV.

### API

- **GET /ops/real-drill/summary**  
  Params: `period_type` (monthly|weekly), `segment` (Todos|B2B|B2C), `limit_periods`.  
  Devuelve: `country`, `period_start`, `trips`, `b2b_trips`, `margin_total`, `margin_unit_avg`, `distance_total_km`, `distance_km_avg`, `b2b_pct`, `last_trip_ts`, `expected_last_date`, `falta_data`, `estado`. Calendario completo incluye meses/semanas vacías.

- **GET /ops/real-drill/by-lob**  
  Params: `period_type`, `country`, `period_start`, `segment`.  
  Devuelve: `lob_group`, `trips`, `b2b_trips`, `margin_total`, `margin_unit_avg`, `distance_total_km`, `distance_km_avg`.

- **GET /ops/real-drill/by-park**  
  Params: `period_type`, `country`, `period_start`, `segment`.  
  Devuelve: `city`, `park_id`, `park_name_resolved`, `park_bucket`, `trips`, `b2b_trips`, `margin_total`, `margin_unit_avg`, `distance_total_km`, `distance_km_avg`.

- **GET /ops/real-drill/totals**  
  Params: `period_type`, `segment`, `limit_periods`.  
  Devuelve: `total_trips`, `total_b2b_trips`, `b2b_ratio_pct`, `margin_total`, `margin_unit_avg_global`, `distance_total_km`, `distance_km_avg_global`, `last_trip_ts`.

- **GET /ops/real-drill/coverage**  
  Devuelve: `[{ country, last_trip_date, last_month_with_data, last_week_with_data }]` desde `ops.v_real_data_coverage`. Si la vista no existe, retorna `[]` (sin error).

- **POST /ops/real-drill/refresh**  
  Refresca la MV `ops.mv_real_rollup_day` (CONCURRENTLY si hay índice único). Uso interno: cron diario o admin.

### Migración y refresh

```bash
cd backend && alembic upgrade head
```

**Refresh diario recomendado** (cron o tarea programada):

```sql
REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_real_rollup_day;
```

O vía API: `POST /ops/real-drill/refresh`

## Frontend

- **RealLOBDrillView**: KPIs (Total viajes, Margen total, Margen/trip, Km prom, Viajes B2B y %B2B si segmento = Todos). Tabla principal con columnas Margen/trip y Km prom; subfilas con Viajes, Margen/trip, Km prom y B2B (solo si segmento = Todos). Valores "—" cuando no aplica.

## Migración / límites

- Requiere migración **051** (MV rollup + dim_city_country) y predecesoras (050, 044–049 para canon.map_real_tipo_servicio_to_lob_group y esquema).
- Los endpoints antiguos (`/ops/real-lob/monthly-v2`, etc.) se mantienen; la UI del tab Real LOB usa solo `/ops/real-drill/*`.
- **Robustez**: Si una vista no existe, el API hace `rollback()` y retorna `[]` para evitar "transaction is aborted".
