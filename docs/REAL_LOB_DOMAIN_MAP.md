# REAL LOB — Mapa técnico del dominio (Fase 1)

**Objetivo:** Mapear todas las apariciones de service_type / tipo_servicio / lob en el sistema para canonicalización REAL.

---

## 1. Origen del dato crudo

| Fuente | Campo(s) | Uso |
|--------|----------|-----|
| `public.trips_all` | `tipo_servicio` | Viajes reales; valor crudo por viaje. |
| `ops.v_trips_real_canon` | `tipo_servicio` (heredado) | Vista filtrada de viajes reales completados; usada por capa LOB. |

---

## 2. Punto único de normalización (capa canónica)

| Objeto | Descripción |
|--------|-------------|
| **`canon.normalize_real_tipo_servicio(raw text)`** | Función única raw → clave canónica (comfort_plus, tuk_tuk, delivery, etc.). Definida en migración 080. |
| **`canon.dim_real_service_type_lob`** | Tabla: service_type_norm (PK), lob_group, is_active, etc. Lookup LOB desde clave canónica. |
| **`canon.map_real_tipo_servicio_to_lob_group`** | Legacy; compatibilidad. No es fuente de verdad. |

---

## 3. Vistas SQL que consumen la capa canónica

| Vista | Consume | Columnas expuestas |
|-------|---------|--------------------|
| `ops.v_real_trips_service_lob_resolved` | canon.normalize_real_tipo_servicio, canon.dim_real_service_type_lob | tipo_servicio_raw, tipo_servicio_norm, lob_group_resolved |
| `ops.v_real_trips_with_lob_v2` | Wrapper sobre v_real_trips_service_lob_resolved | real_tipo_servicio_norm, lob_group |

---

## 4. Vistas materializadas (MVs) REAL LOB

| MV | Fuente | Columnas LOB/servicio |
|----|--------|------------------------|
| `ops.mv_real_lob_month_v2` | v_real_trips_with_lob_v2 | lob_group, real_tipo_servicio_norm |
| `ops.mv_real_lob_week_v2` | v_real_trips_with_lob_v2 | lob_group, real_tipo_servicio_norm |
| `ops.mv_real_trips_by_lob_month` / `_week` | (legacy) | lob |

---

## 5. Fact / drill

| Objeto | Fuente de normalización |
|--------|-------------------------|
| `ops.real_drill_dim_fact` | backfill_real_lob_mvs.py → canon.normalize_real_tipo_servicio + canon.dim_real_service_type_lob |
| `ops.mv_real_drill_dim_agg` | Vista sobre real_drill_dim_fact (dimension_key, lob_group, service_type) |
| `ops.real_rollup_day_fact` | Mismo backfill; canon.normalize_real_tipo_servicio |

---

## 6. Backend — Servicios y endpoints afectados

| Servicio | Endpoint(s) | Dependencia |
|----------|-------------|-------------|
| real_lob_service.py | /ops/real-lob/monthly, weekly | mv_real_trips_by_lob_* (lob) |
| real_lob_service_v2.py | /ops/real-lob/monthly-v2, weekly-v2 | MVs v2 → real_tipo_servicio_norm, lob_group |
| real_lob_v2_data_service.py | /ops/real-lob/v2/data | MVs v2 → real_tipo_servicio_norm, lob_group |
| real_lob_filters_service.py | /ops/real-lob/filters | DISTINCT real_tipo_servicio_norm, lob_group desde MVs v2 |
| real_lob_drill_pro_service.py | /ops/real-lob/drill, drill/children, drill/parks | mv_real_drill_dim_agg (dimension_key, lob_group, service_type) |
| real_lob_daily_service.py | /ops/real-lob/daily/* | group_by lob |
| real_strategy_service.py | /ops/real-strategy/country, lob, cities | Vistas strategy por LOB |

**Contratos:** `data_contract.py` — añadir REAL_SERVICE_TYPES y REAL_SERVICE_TYPE_DISPLAY (canonical → display UI).

---

## 7. Frontend — Componentes dependientes

| Componente | Uso de LOB / tipo_servicio |
|------------|----------------------------|
| **RealLOBView.jsx** | Filtros: lob_groups, tipo_servicio (filterOptions.tipo_servicio); tablas: lob_group, real_tipo_servicio_norm. getRealLobFilters, getRealLobV2Data. groupBy lob_group | real_tipo_servicio_norm. |
| **RealLOBDrillView.jsx** | Drill por lob / park / service_type; dimension_key, lob_group, service_type; label service_type: r.service_type ?? r.dimension_key. |
| **RealLOBDailyView.jsx** | getRealLobDailyTable con group_by: 'lob'. |
| **PlanVsRealView.jsx** | real_tipo_servicio, lob_base en filtros y columnas. |
| **api.js** | getRealLobV2Data (country, city, park_id, lob_group, real_tipo_servicio, segment_tag); getRealLobFilters (tipo_servicio en opciones). |

**Regla:** El frontend NO debe normalizar; solo renderizar. Para mostrar etiquetas en mayúsculas (CONFORT_PLUS, TUK_TUK, DELIVERY) se usa un mapeo de visualización (canonical_key → display_label) en un solo lugar.

---

## 8. Resumen de flujo

```
trips_all.tipo_servicio (crudo)
    → canon.normalize_real_tipo_servicio()
    → tipo_servicio_norm / real_tipo_servicio_norm (canónico)
    → v_real_trips_with_lob_v2 → MVs v2 / real_drill_dim_fact
    → API (real_tipo_servicio_norm, lob_group)
    → Frontend (render; opcional display_label vía mapeo)
```
