# Mapa de lineage: Freshness & Coverage — Fuentes base y derivadas

**Proyecto:** YEGO CONTROL TOWER  
**Objetivo:** Trazabilidad completa entre fuente base → vista canónica → MV/fact derivada → UI. No asumir que `trips_all` es la fuente vigente.

---

## 0. Fuente viva real (evidencia)

- **Fuente viva:** `public.trips_2026` (hasta la fecha más reciente; en auditoría 2026-03-08).
- **Legacy/parcial:** `public.trips_all` (cortada; en auditoría hasta 2026-01-31). No usar como única fuente para datos recientes.
- **Tablas particionadas activas:** `trips_2026` (y opcionalmente `trips_2025` si existe en schema).
- El audit compara `max_date` en ventana reciente (RECENT_DAYS), `rows` últimos 7/30 días y gaps vía status (SOURCE_STALE, DERIVED_STALE, etc.).

---

## 1. Fuentes base de viajes (tablas reales)

| Objeto | Tipo | Es fuente base | Columna temporal principal | Grain | Notas |
|--------|------|----------------|----------------------------|-------|--------|
| `public.trips_all` | table | **Sí** | `fecha_inicio_viaje` | día | Histórico; puede estar cortado (ej. hasta ene). No asumir vigente. |
| `public.trips_2026` | table | **Sí** | `fecha_inicio_viaje` | día | Partición/año 2026. Suele ser la más fresca para 2026. |
| `public.trips_2025` | table | **Sí** (si existe) | `fecha_inicio_viaje` | día | Partición 2025; inspeccionar en schema. |

**Regla de vigencia:** La fuente base vigente para una fecha dada es la que contiene esa fecha (trips_2026 para >= 2026-01-01, trips_all para < 2026-01-01 cuando hay UNION). La vista unificada `public.trips_unified` y la canónica `ops.v_trips_real_canon` encapsulan esta lógica.

---

## 2. Vistas canónicas (consolidan viajes)

| Objeto | Tipo | Fuente(s) | Columna temporal | Grain | Uso |
|--------|------|-----------|------------------|-------|-----|
| `public.trips_unified` | view | `trips_all` (< 2026-01-01) + `trips_2026` (>= 2026-01-01) | `fecha_inicio_viaje` | día | Driver Lifecycle, auditoría. |
| `ops.v_trips_real_canon` | view | `trips_all` + `trips_2026` (mismo corte); columnas mínimas + `source_table` | `fecha_inicio_viaje` | día | Real LOB: drill, rollup, freshness. |

---

## 3. Lineage por dataset principal

### 3.1 Real LOB (drill, rollup, UI)

| Capa | Objeto | Tipo | Fuente(s) | Columna temporal | Grain |
|------|--------|------|-----------|-------------------|-------|
| Canónica | `ops.v_trips_real_canon` | view | trips_all, trips_2026 | fecha_inicio_viaje | día |
| Con LOB | `ops.v_real_trips_with_lob_v2` | view | ops.v_trips_real_canon + parks + canon.map_* | fecha_inicio_viaje | día |
| Freshness | `ops.v_real_freshness_trips` | view | ops.v_trips_real_canon (condicion=Completado) | fecha_inicio_viaje | día (MAX por country) |
| Fact drill | `ops.real_drill_dim_fact` | table | ops.v_trips_real_canon (ventana REAL_LOB_RECENT_DAYS, backfill) | period_start, last_trip_ts | month, week |
| Fact rollup | `ops.real_rollup_day_fact` | table | ops.v_trips_real_canon (ventana reciente) | trip_day, last_trip_ts | día |
| Vista API drill | `ops.mv_real_drill_dim_agg` | view | ops.real_drill_dim_fact | period_start | month, week |
| Vista API rollup | `ops.mv_real_rollup_day` | view | ops.real_rollup_day_fact | trip_day | día |
| Coverage | `ops.v_real_data_coverage` | view | ops.mv_real_rollup_day | last_trip_date, last_month_with_data, last_week_with_data | por country |
| Coverage config | `ops.v_real_lob_coverage` | view | real_rollup_day_fact (min/max trip_day, recent_days_config) | trip_day | — |

**Fuente base real vigente para Real LOB:** la unión lógica en `ops.v_trips_real_canon` (trips_all + trips_2026 con corte por fecha). Freshness de fuente = MAX(fecha_inicio_viaje) desde canon. Freshness de derivado = MAX(period_start) / MAX(trip_day) en fact tables.

---

### 3.2 Driver Lifecycle

| Capa | Objeto | Tipo | Fuente(s) | Columna temporal | Grain |
|------|--------|------|-----------|-------------------|-------|
| Viajes completados | `ops.v_driver_lifecycle_trips_completed` | view | **public.trips_unified** | completion_ts, request_ts | día |
| Base | `ops.mv_driver_lifecycle_base` | matview | v_driver_lifecycle_trips_completed | last_completed_ts, activation_ts | conductor |
| Semanal | `ops.mv_driver_weekly_stats` | matview | v_driver_lifecycle_trips_completed (vía build) | week_start | week |
| Mensual | `ops.mv_driver_monthly_stats` | matview | mv_driver_lifecycle_base | month_start | month |
| Comportamiento | `ops.mv_driver_weekly_behavior` | matview | v_driver_lifecycle_trips_completed | week_start | week |

**Fuente base real vigente para Driver Lifecycle:** `public.trips_unified` (trips_all + trips_2026). Freshness fuente = MAX(completion_ts) en trips_unified (completados). Freshness derivado = MAX(last_completed_ts) en mv_driver_lifecycle_base; MAX(week_start) en mv_driver_weekly_stats.

---

### 3.3 Driver Supply Dynamics

| Capa | Objeto | Tipo | Fuente(s) | Columna temporal | Grain |
|------|--------|------|-----------|-------------------|-------|
| Semanal | `ops.mv_supply_weekly` | matview | mv_driver_weekly_stats, v_driver_weekly_churn_reactivation, dim.v_geo_park | week_start | week |
| Mensual | `ops.mv_supply_monthly` | matview | mv_driver_monthly_stats, dim.v_geo_park | month_start | month |
| Segmentos | `ops.mv_supply_segments_weekly` | matview | mv_driver_weekly_stats + config | week_start | week |
| Refresh log | `ops.supply_refresh_log` | table | — | finished_at | — |

**Fuente base real vigente para Supply:** en cadena: trips_unified → v_driver_lifecycle_trips_completed → mv_driver_lifecycle_base → mv_driver_weekly_stats → mv_supply_weekly / mv_supply_segments_weekly. Freshness Supply = MAX(week_start) en mv_supply_segments_weekly (o mv_supply_weekly) y last_refresh en supply_refresh_log.

---

### 3.4 Otras vistas/MVs relevantes

- **Plan vs Real, Real mensual, LOB hunt:** diversas vistas que leen de `trips_all` o de vistas que a su vez leen de trips; para consistencia con 2026 deben migrarse a usar `trips_unified` o `ops.v_trips_real_canon` donde aplique.
- **ops.mv_real_drill_service_by_park:** MV (o tabla alimentada por backfill) con mismo origen que real_drill_dim_fact; grain period_start (week/month).
- **ops.dim_city_country, ops.park_country_fallback, canon.map_real_tipo_servicio_to_lob_group:** dimensiones/config; no tienen freshness de evento, solo de carga.

---

## 4. Resumen: qué medir para freshness

| Dataset | Fuente base a inspeccionar | Objeto derivado a medir | Fecha en fuente | Fecha en derivado |
|---------|----------------------------|--------------------------|-----------------|-------------------|
| **Trips base (vigente)** | trips_all, trips_2026 (o canon) | — | MAX(fecha_inicio_viaje) por tabla | — |
| **Real LOB** | ops.v_trips_real_canon | ops.real_drill_dim_fact, ops.real_rollup_day_fact | MAX(fecha_inicio_viaje) canon | MAX(period_start), MAX(trip_day) |
| **Driver Lifecycle** | public.trips_unified | ops.mv_driver_lifecycle_base, ops.mv_driver_weekly_stats | MAX(completion_ts) en vista | MAX(last_completed_ts), MAX(week_start) |
| **Supply** | (cadena Driver Lifecycle) | ops.mv_supply_weekly, ops.mv_supply_segments_weekly | — | MAX(week_start), supply_refresh_log |

---

## 5. Reglas de expectativa de cobertura (resumen)

- **Diario:** normalmente se espera data hasta ayer (expected_delay_days = 1). Si hoy está abierto, periodo actual = parcial.
- **Semanal:** al menos hasta la última semana cerrada (lunes a domingo); semana actual = parcial.
- **Mensual:** al menos hasta el último mes cerrado; mes actual = parcial.

Detalle y estados (OK, PARTIAL_EXPECTED, LAGGING, MISSING_EXPECTED_DATA, SOURCE_STALE, DERIVED_STALE) en [data_freshness_monitoring.md](data_freshness_monitoring.md).

### Tabla resumen por dataset (audit)

| dataset_name | source_object | derived_object | temporal_column | grain | notes |
|--------------|---------------|----------------|-----------------|-------|-------|
| trips_base | public.trips_all | — | fecha_inicio_viaje | day | Fuente legacy; puede estar cortada. |
| trips_2026 | public.trips_2026 | — | fecha_inicio_viaje | day | Fuente viva para 2026. |
| real_lob | ops.v_trips_real_canon (proxy: trips_all+trips_2026) | ops.real_rollup_day_fact | trip_day | day | Drill diario. |
| real_lob_drill | ops.v_trips_real_canon (proxy: trips_all+trips_2026) | ops.real_drill_dim_fact | period_start | week | Drill semanal/mensual. |
| driver_lifecycle | ops.v_driver_lifecycle_trips_completed | ops.mv_driver_lifecycle_base | last_completed_ts | day | Viajes completados. |
| driver_lifecycle_weekly | ops.mv_driver_lifecycle_base | ops.mv_driver_weekly_stats | week_start | week | Semanal. |
| supply_weekly | ops.mv_driver_weekly_stats | ops.mv_supply_segments_weekly | week_start | week | Supply Dynamics. |

---

*Documento generado en el marco del sistema de Freshness & Coverage Control. Actualizar al añadir nuevas fuentes o derivados.*
