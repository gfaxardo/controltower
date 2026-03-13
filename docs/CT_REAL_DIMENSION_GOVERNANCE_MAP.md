# CT-REAL-DIMENSION-GOVERNANCE — Mapa del sistema

## 1. Fuentes crudas

| Fuente | Campo(s) | Uso |
|--------|----------|-----|
| `public.trips_all` | `tipo_servicio` | Viajes reales; valor crudo por viaje. |
| `ops.v_trips_real_canon` | `tipo_servicio` | Vista filtrada de viajes reales completados; usada por capa LOB. |
| Staging relacionado | — | No hay staging intermedio; la capa canónica lee de trips_all / v_trips_real_canon. |

## 2. Capa canónica existente

| Objeto | Descripción |
|--------|-------------|
| **`canon.normalize_real_tipo_servicio(raw text)`** | Función única raw → service_type_key (080: unaccent, +→_plus, espacios/guiones→_, mapeo a clave canónica). |
| **`canon.dim_real_service_type_lob`** | Tabla actual: service_type_norm (PK), lob_group (text), mapping_source, is_active, notes, updated_at. |
| **`canon.map_real_tipo_servicio_to_lob_group`** | Legacy; mapeo real_tipo_servicio → lob_group. Se mantiene por compatibilidad. |

## 3. Dimensiones canónicas a crear (FASE B)

| Dimensión | Columnas | Uso |
|-----------|----------|-----|
| **canon.dim_lob_group** | lob_group_key, lob_group_label, is_active | Grupos operativos: ride (auto taxi), delivery, micro_mobility (tuk/moto), other. |
| **canon.dim_lob** | lob_key, lob_label, lob_group_key, is_active | Líneas de negocio; FK a dim_lob_group. |
| **canon.dim_service_type** | service_type_key, service_type_label, lob_key, lob_group_key, is_active, created_at | Tipos de servicio; FK a dim_lob y dim_lob_group. Reemplaza uso directo de dim_real_service_type_lob en vistas. |

## 4. Vistas SQL impactadas

| Vista | Consume hoy | Tras gobernanza |
|-------|-------------|------------------|
| `ops.v_real_trips_service_lob_resolved` | canon.normalize_real_tipo_servicio, canon.dim_real_service_type_lob | normalize_real_tipo_servicio → service_type_key; JOIN canon.dim_service_type + canon.dim_lob_group para lob_group (label). |
| `ops.v_real_trips_with_lob_v2` | Wrapper sobre v_real_trips_service_lob_resolved | Sin cambio de contrato: real_tipo_servicio_norm, lob_group (label). |
| `ops.mv_real_lob_month_v2` | v_real_trips_with_lob_v2 | Sigue leyendo de la vista; columnas lob_group, real_tipo_servicio_norm (sin cambio). |
| `ops.mv_real_lob_week_v2` | v_real_trips_with_lob_v2 | Idem. |

## 5. Servicios backend

| Servicio | Endpoint(s) | Dependencia |
|----------|-------------|-------------|
| real_lob_service.py | /ops/real-lob/monthly, weekly | mv_real_trips_by_lob_* (lob) |
| real_lob_service_v2.py | /ops/real-lob/monthly-v2, weekly-v2 | MVs v2: real_tipo_servicio_norm, lob_group |
| real_lob_v2_data_service.py | /ops/real-lob/v2/data | MVs v2 |
| real_lob_filters_service.py | /ops/real-lob/filters | DISTINCT real_tipo_servicio_norm, lob_group desde MVs v2 |
| real_lob_drill_pro_service.py | /ops/real-lob/drill, drill/children, drill/parks | mv_real_drill_dim_agg (dimension_key, lob_group, service_type) |
| real_lob_daily_service.py | /ops/real-lob/daily/* | real_rollup_day_fact (lob_group) |
| real_strategy_service.py | /ops/real-strategy/country, lob, cities | Vistas strategy (lob_group) |

Regla: consumir service_type_key y labels desde dimensiones; no transformaciones manuales. Contratos API se mantienen (lob_group = label, real_tipo_servicio_norm = key).

## 6. Endpoints API

- /ops/real-lob/monthly, weekly, monthly-v2, weekly-v2, v2/data, filters  
- /ops/real-lob/drill, drill/children, drill/parks  
- /ops/real-lob/comparatives/weekly, comparatives/monthly  
- /ops/real-lob/daily/summary, comparative, table  
- /ops/real-strategy/country, lob, cities  
- /ops/real-drill/* (legacy)

Endpoints de lifecycle o supply que usen LOB: revisar scripts y vistas en backend/; no se encontraron endpoints específicos de lifecycle/supply que expongan LOB en el mismo formato REAL.

## 7. Frontend

| Componente | Uso LOB/servicio |
|------------|------------------|
| RealLOBView.jsx | Filtros lob_groups, tipo_servicio; tablas lob_group, real_tipo_servicio_norm. |
| RealLOBDrillView.jsx | drillBy lob / park / service_type; dimension_key, lob_group, service_type. |
| RealLOBDailyView.jsx | group_by lob. |
| PlanVsRealView.jsx | real_tipo_servicio, lob_base. |

Requisito: no renaming client-side; filtros únicos; breakdowns y tablas sin duplicados; validar recarga, cambio de filtros, tabs y drilldowns.

## 8. Mapa raw → canonical (referencia)

Ver docs/CT_REAL_LOB_CANONICALIZATION_MAP.md §11. Claves: economico, comfort, comfort_plus, tuk_tuk, minivan, premier, delivery, cargo, moto, standard, start, xl → service_type_key. Grupos: auto taxi, tuk tuk, delivery, taxi moto → lob_group_key / lob_group_label.
