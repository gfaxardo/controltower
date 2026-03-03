# Driver Lifecycle — UI y API (serie por periodo + park name)

## Referencia FASE 1 — Mapeo Real LOB y columnas MVs

### Park name (Real LOB)
- **Archivo:** `backend/app/services/real_lob_filters_service.py`
- **Función:** `get_real_lob_filters(country, city)` → devuelve `parks` con `{ country, city, park_id, park_name }`.
- **Fuente:** `ops.mv_real_lob_month_v2` y `ops.mv_real_lob_week_v2` (ya tienen `park_name` en la MV; fallback `COALESCE(NULLIF(TRIM(park_name), ''), park_id::text)`).
- **Endpoint reutilizado para lista de parks:** `GET /ops/real-lob/filters` (usado por Real LOB). Para dropdown unificado se añadió **GET /ops/parks**, que devuelve la misma lista de parks (solo `park_id`, `park_name`) en el mismo orden (country, city, park_name).

### Lookup park_id → park_name (dim)
- **Tabla:** `dim.dim_park` (columnas: `park_id`, `park_name`, `city`, `country`, etc.).
- **Uso en Driver Lifecycle:** `driver_lifecycle_service._park_names_lookup(conn, park_ids)` consulta `dim.dim_park` para enriquecer respuestas (p. ej. `get_parks_summary` devuelve `park_name`).

### Columnas MVs (inspección real)
- **ops.mv_driver_lifecycle_weekly_kpis:** `week_start`, `activations`, `active_drivers`, `churn_flow`, `reactivated`.
- **ops.mv_driver_lifecycle_monthly_kpis:** `month_start`, `activations`, `active_drivers` (churn/reactivated se calculan en servicio desde `mv_driver_monthly_stats`).
- **ops.mv_driver_weekly_stats:** `driver_key`, `week_start`, `trips_completed_week`, `work_mode_week`, `park_id`, `tipo_servicio`, `segment`, `is_active_week`.
- **ops.mv_driver_monthly_stats:** `driver_key`, `month_start`, `trips_completed_month`, `work_mode_month`, `park_id`, etc.

---

## Cambios realizados

### Backend

1. **GET /ops/parks**  
   - **Router:** `backend/app/routers/ops.py`  
   - **Respuesta:** `{ "parks": [ { "park_id", "park_name" }, ... ] }`  
   - Misma fuente y orden que Real LOB (vía `get_real_lob_filters()`). La opción "Todos" se añade en frontend.

2. **GET /ops/driver-lifecycle/series**  
   - Parámetros: `from`, `to`, `grain` (weekly | monthly), `park_id` (opcional).  
   - Respuesta: `rows` por periodo (más reciente → más antiguo) con: `period_start`, `activations`, `active_drivers`, `churned`, `reactivated`, `churn_rate`, `reactivation_rate`, `net_growth`, `mix_ft_pt`.

3. **GET /ops/driver-lifecycle/summary**  
   - Parámetros: `from`, `to`, `grain`, `park_id` (opcional).  
   - Respuesta: cards: `activations_range`, `churned_range`, `reactivated_range`, `time_to_first_trip_avg_days`, `lifetime_avg_active_days`, `active_drivers_last_period` (primer periodo de `/series`).

4. **GET /ops/driver-lifecycle/drilldown**  
   - Sin cambios de contrato: `period_start`, `metric`, `park_id` (obligatorio para drilldown). La UI solo permite abrir drilldown cuando hay un park seleccionado.

5. **get_parks_summary**  
   - Enriquecido con `park_name` mediante `_park_names_lookup(conn, park_ids)` (dim.dim_park). Cada fila incluye `park_name` (fallback a `park_id` o "PARK_DESCONOCIDO").

### Frontend

1. **Dropdown Park**  
   - Consume **GET /ops/parks**. Opción "Todos" (value `""`) + lista con `park_name` (fallback `park_id`).

2. **Cards**  
   - Datos de **GET /ops/driver-lifecycle/summary** con `from`, `to`, `grain`, `park_id`.  
   - Active drivers “último periodo” = `summary.active_drivers_last_period`.

3. **Tabla principal: “Serie por Periodo”**  
   - Datos de **GET /ops/driver-lifecycle/series**.  
   - Columnas: Periodo, Activations, Active Drivers, Churn Rate, Reactivation Rate, Net Growth, Mix FT/PT.  
   - Orden: más reciente → más antiguo.  
   - Celdas clicables solo si hay park seleccionado; abren drilldown con `period_start` + métrica + `park_id`.

4. **Desglose por Park (opcional)**  
   - Visible solo con Park = "Todos". Botón "Ver desglose por Park" muestra tabla con `park_name` (y resto de columnas).  
   - Datos de **GET /ops/driver-lifecycle/parks-summary** (ya devuelve `park_name`).

5. **Cohortes**  
   - Selector de park de cohortes usa la misma lista de parks (park_id + park_name).

---

## Validación rápida

1. **Dropdown parks:** Muestra nombres (igual que Real LOB).  
2. **Seleccionar un park:** Cards y serie se filtran por ese park.  
3. **Orden:** Serie por periodo en orden descendente (más reciente primero).  
4. **Grain mensual:** Al cambiar a "Mensual", `grain=monthly`, columnas por `month_start`.  
5. **Consistencia:**  
   - `summary.activations_range` = suma de `series.rows[].activations`.  
   - `summary.active_drivers_last_period` = `series.rows[0].active_drivers` (si hay filas).  
6. **Drilldown:** Con park seleccionado, clic en una celda de la tabla abre modal con lista de drivers para ese periodo + métrica + park.  
7. **Real LOB:** No modificado; GET /ops/parks solo añade un endpoint que reutiliza la misma fuente.
