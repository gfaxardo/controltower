# Real vs Proyección — Diccionario de métricas

**Objetivo:** Inventario de métricas reales disponibles hoy en Control Tower para alimentar el comparativo Real vs Proyección, y métricas derivadas/faltantes.

---

## 1. Métricas reales disponibles (existentes)

| metric_name | exists_yes_no | direct_or_derived | source_table_or_view | grain | dimensions_available | formula_if_derived | confidence_level | comments |
|-------------|---------------|-------------------|----------------------|-------|----------------------|--------------------|------------------|----------|
| trips_real | yes | direct | ops.mv_real_trips_monthly (trips_real_completed) | month | country, city_norm, lob_base, segment, park_id | — | high | Fuente canónica Plan vs Real y real_repo. |
| revenue_real | yes | direct | ops.mv_real_trips_monthly (revenue_real_yego) | month | country, city_norm, lob_base, segment, park_id | — | high | comision_empresa_asociada. |
| active_drivers_real | yes | direct | ops.mv_real_trips_monthly (active_drivers_real) | month | country, city_norm, lob_base, segment, park_id | — | high | COUNT(DISTINCT conductor_id). |
| avg_ticket_real | yes | direct | ops.mv_real_trips_monthly (avg_ticket_real) | month | country, city_norm, lob_base, segment, park_id | — | medium | Basado en precio_yango_pro donde no null. |
| trips (Real LOB) | yes | direct | ops.mv_real_lob_month_v2 (trips) | month | country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag | — | high | Segmentación LOB v2 (no igual a mv_real_trips_monthly). |
| revenue (Real LOB) | yes | direct | ops.mv_real_lob_month_v2 (revenue) | month | country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag | — | high | |
| avg_trips_per_driver_real | yes | derived | ops.mv_real_trips_monthly | month | country, city_norm, lob_base, segment | total_trips / active_drivers | high | real_repo y Phase2b ya calculan trips/active_drivers. |
| revenue_per_trip_real | yes | derived | ops.mv_real_trips_monthly | month | idem | revenue / trips | high | |
| drivers_real (weekly) | yes | direct | Phase2b weekly views (active_drivers_real) | week | country, city, etc. | — | high | Para comparativo semanal. |
| productividad_real (weekly) | yes | derived | Phase2b (trips_real / drivers_real) | week | idem | — | high | |

---

## 2. Métricas derivadas desde las existentes (para comparativo)

| metric_name | exists_yes_no | direct_or_derived | source | formula | confidence |
|-------------|---------------|-------------------|--------|--------|------------|
| avg_trips_per_driver_real | yes | derived | mv_real_trips_monthly | total_trips / active_drivers_real | high |
| avg_ticket_real (alternativo) | yes | derived | mv_real_trips_monthly | revenue_real_yego / trips_real_completed | high |
| revenue_per_driver_real | yes | derived | mv_real_trips_monthly | revenue_real_yego / active_drivers_real | high |
| revenue_per_trip_real | yes | derived | mv_real_trips_monthly | revenue_real_yego / trips_real_completed | high |

---

## 3. Métricas que no existen hoy y serán necesarias para el comparativo

| metric_name | propósito | resolución |
|-------------|-----------|------------|
| required_drivers_for_target | Conductores necesarios para alcanzar target de viajes | target_trips / real_avg_trips_per_driver (derivado cuando tengamos target) |
| required_trips_for_target | Viajes necesarios para target revenue | target_revenue / real_avg_ticket (derivado) |
| drivers_delta_needed | Diferencia de conductores vs meta | required_drivers - drivers_real |
| trips_delta_needed | Diferencia de viajes vs meta | target_trips - trips_real |
| ticket_delta_needed | Diferencia ticket vs meta | target_avg_ticket - avg_ticket_real |
| gap_explained_by_driver_count | Parte de la brecha explicada por número de conductores | Descomposición (driver vs productividad vs ticket) |
| gap_explained_by_productivity | Parte por productividad (viajes/conductor) | Idem |
| gap_explained_by_ticket | Parte por ticket medio | Idem |

Estas se implementan en la **capa de comparativo** (vistas/endpoints Real vs Proyección) cuando existan plan/target; no requieren nuevas tablas de hecho.

---

## 4. Dimensiones disponibles para segmentar

- **Desde mv_real_trips_monthly:** country, city_norm, lob_base, segment (b2b/b2c), park_id, month.
- **Desde mv_real_lob_month_v2:** country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag, month_start.
- **Proyección Excel:** Por definir (ciudad, país, vertical/LOB, service type, categoría). Se resolverá con **mapping** a dimensiones canónicas del sistema.

---

## 5. Fuentes clave resumidas

- **Comparativo mensual Plan vs Real (realkey):** `ops.mv_real_trips_monthly` + `ops.v_plan_vs_real_realkey_final` (trips_plan, trips_real, revenue_plan, revenue_real, period_date, park_id, real_tipo_servicio).
- **Real LOB (drill por LOB/parque):** `ops.mv_real_lob_month_v2`, `ops.mv_real_lob_week_v2` (trips, revenue, margin_total; sin active_drivers en esa MV).
- **Conductores activos mensuales:** Solo en `ops.mv_real_trips_monthly` (grain park + lob + segment + month).
