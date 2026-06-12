# CF-H2F — KPI INVENTORY (OMNIVIEW)

> **Fase:** CF-H2F — Metric Ownership Matrix
> **Motor:** Control Foundation
> **Fecha:** 2026-06-11
> **Park:** `08e20910d81d42658d4334d3f6d10ac0` (Lima)
> **Clasificación:** `CF_H2F_KPI_INVENTORY`

---

## 1. PURPOSE

Inventario exhaustivo de todos los KPIs usados actualmente por Omniview y sus serving facts (day/week/month/snapshots). Cada KPI documenta su fuente actual, grain, y qué vistas lo consumen.

---

## 2. INVENTORY

### 2.1 Core Operational KPIs

| # | kpi_name | description | current_source | grain | used_by |
|---|----------|-------------|----------------|-------|---------|
| C01 | `completed_trips` | Viajes completados | `ops.real_business_slice_day_fact.trips_completed` | Day, Week, Month | Omniview grid, Day/Week/Month facts, Revenue views |
| C02 | `cancelled_trips` | Viajes cancelados | `ops.real_business_slice_day_fact.trips_cancelled` | Day, Week, Month | Omniview grid, Day/Week/Month facts |
| C03 | `total_orders` | Suma de completados + cancelados | Derived: C01 + C02 | Day, Week, Month | Omniview grid (derived), Day/Week/Month facts |
| C04 | `active_drivers` | Conductores con al menos 1 viaje completado | `ops.real_business_slice_day_fact.active_drivers` / `COUNT(DISTINCT driver_id) FILTER (WHERE completed_flag)` | Day, Week, Month | Omniview grid, Day/Week/Month facts, Driver activity views |
| C05 | `revenue_yego_net` | Revenue YEGO neto (comisión real sin proxy) | `ops.real_business_slice_day_fact.revenue_yego_net` | Day, Week, Month | Omniview grid, Revenue views |
| C06 | `revenue_yego_final` | Revenue YEGO final (incluye proxy fallback) | `ops.real_business_slice_day_fact.revenue_yego_final` | Day, Week, Month | Omniview grid (legacy), Revenue views, KPI aggregation rules |
| C07 | `gmv` | Gross Merchandise Value | `raw_yango.transactions_raw` (Cash + Card + Corporate) / `ops.real_business_slice_day_fact` (efectivo+tarjeta+pago_corporativo = 0 en Lima) | Day, Week, Month | Omniview (pendiente), Revenue views |

### 2.2 Derived KPIs

| # | kpi_name | description | current_source | grain | used_by |
|---|----------|-------------|----------------|-------|---------|
| D01 | `avg_ticket` | Ticket promedio por viaje | `ops.real_business_slice_day_fact.avg_ticket` (AVG(ticket) FILTER completed) | Day, Week, Month | Omniview grid, Day/Week/Month facts |
| D02 | `trips_per_driver` | Viajes por conductor activo | Derived: trips_completed / active_drivers | Day, Week, Month | Omniview grid, Day/Week/Month facts, Driver activity views |
| D03 | `revenue_per_order` | Revenue YEGO por viaje | Derived: revenue_yego_final / trips_completed | Day, Week, Month | Omniview grid |
| D04 | `commission_pct` | Tasa de comisión (revenue / fare) | `ops.real_business_slice_day_fact.commission_pct` | Day, Week, Month | Omniview grid, Day/Week/Month facts |
| D05 | `cancel_rate_pct` | Tasa de cancelación | Derived: cancelled / (completed + cancelled) | Day, Week, Month | Omniview grid |

### 2.3 Driver Identity & Lifecycle KPIs

| # | kpi_name | description | current_source | grain | used_by |
|---|----------|-------------|----------------|-------|---------|
| L01 | `driver_identity` | Identidad del conductor (UUID, nombre, teléfono, licencia) | `public.drivers.driver_id` = `raw_yango.driver_profiles_raw.driver_profile_id` = `public.trips_2026.conductor_id` | Per-driver | Driver Explorer, RNA audits, Program eligibility |
| L02 | `new_drivers` | Conductores contratados recientemente | `public.drivers.hire_date` (CT bridge) | Day, Week, Month | Driver activity views, Growth dashboard |
| L03 | `reactivated_drivers` | Conductores que volvieron tras inactividad >15d | `growth.yego_lima_driver_lifecycle_daily` (CT bridge) | Day, Week, Month | Driver activity views, Growth dashboard, Program eligibility |
| L04 | `churned_drivers` | Conductores inactivos >15d | `growth.yego_lima_driver_lifecycle_daily` (CT bridge) | Day, Week, Month | Driver activity views, Growth dashboard, Risk panel |
| L05 | `supply_hours` | Horas online del conductor | Yango `GET /v2/parks/contractors/supply-hours` (per-driver) / `growth.yango_lima_driver_360_daily.supply_hours` | Day | Driver 360, Productivity views |

### 2.4 Dimensional KPIs

| # | kpi_name | description | current_source | grain | used_by |
|---|----------|-------------|----------------|-------|---------|
| G01 | `business_slice` | Segmento de negocio | `ops.real_business_slice_day_fact.business_slice_name` | Per-fact | Omniview rows, Day/Week/Month facts, Revenue views |
| G02 | `park` | Parque operativo | `dim.dim_park` + `api_park_credentials_registry` | Per-fact | Omniview filter, Serving facts |
| G03 | `city` | Ciudad | `dim.dim_park.city` | Per-fact | Omniview filter |
| G04 | `country` | País | `dim.dim_park.country` | Per-fact | Omniview filter |

### 2.5 Growth & Program KPIs

| # | kpi_name | description | current_source | grain | used_by |
|---|----------|-------------|----------------|-------|---------|
| P01 | `scout_attribution` | Campañas de adquisición atribuidas | CT bridge (growth schema program tables) | Day | Program explainability, Attribution views |
| P02 | `cohorts` | Cohortes de conductores por fecha de alta | CT bridge (public.drivers + trips_2026) | Month | Growth dashboard, RNA audits |
| P03 | `programs` | Programas activos y elegibilidad | `growth.yango_lima_program_eligibility_daily` + `growth.yego_lima_v2_program_daily` | Day | Program status, Assignment queue, Today action plan |

### 2.6 Yango-Only Serving KPIs (Shadow)

| # | kpi_name | description | current_source | grain | used_by |
|---|----------|-------------|----------------|-------|---------|
| Y01 | `orders_completed` | Órdenes completadas Yango | `raw_yango.mv_orders_day.orders_completed` | Day | Omniview V2 shadow, Yango reconciliation |
| Y02 | `orders_cancelled` | Órdenes canceladas Yango | `raw_yango.mv_orders_day.orders_cancelled` | Day | Omniview V2 shadow |
| Y03 | `unique_drivers` | Drivers únicos Yango | `raw_yango.mv_orders_day.unique_drivers` | Day | Omniview V2 shadow |
| Y04 | `revenue_partner_fee` | Partner fee Yango | `raw_yango.mv_revenue_day.revenue_partner_fee_amount` | Day | Omniview V2 shadow, Yango reconciliation |
| Y05 | `yango_revenue_per_order` | Revenue por orden Yango | `raw_yango.mv_revenue_day.revenue_per_order` | Day | Omniview V2 shadow |

---

## 3. SUMMARY BY TIER

| Tier | Count | KPIs |
|------|-------|------|
| Core Ops | 7 | C01-C07 |
| Derived | 5 | D01-D05 |
| Driver Identity & Lifecycle | 5 | L01-L05 |
| Dimensional | 4 | G01-G04 |
| Growth & Programs | 3 | P01-P03 |
| Yango Shadow | 5 | Y01-Y05 |
| **TOTAL** | **29** | |

---

## 4. USED-BY MATRIX

| Consumer | KPIs Consumed |
|----------|--------------|
| **Omniview Grid (Vs Proy)** | C01, C02, C03, C04, C05, C06, D01, D02, D03, D04, D05, G01, G02, G03, G04 |
| **Day Facts** | C01, C02, C04, C05, C06, D01, D02, D04, G01 |
| **Week Facts** | C01, C02, C04, C05, C06, D01, D02, D04, G01 |
| **Month Facts** | C01, C02, C04, C05, C06, D01, D02, D04, G01 |
| **Snapshots** | C01, C02, C04, L01, L05 |
| **Revenue Views** | C01, C05, C06, C07, D03, D04 |
| **Driver Activity Views** | C04, D02, L01, L02, L03, L04, L05 |
| **Program Views** | L01, L03, L04, P01, P02, P03 |
| **Omniview V2 Shadow** | Y01, Y02, Y03, Y04, Y05 |

---

*29 KPIs cataloged across 8 consumer views.*
