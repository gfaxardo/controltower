# CT-REAL-LOB-CANONICALIZATION — Mapa técnico del sistema afectado

## 1. Fuentes crudas

| Fuente | Campo(s) | Uso |
|--------|----------|-----|
| `public.trips_all` | `tipo_servicio` | Viajes reales; valor crudo por viaje. |
| `ops.v_trips_real_canon` | `tipo_servicio` (heredado) | Vista filtrada de viajes reales completados; usada por capa LOB. |

## 2. Capa canónica existente (punto único a modificar)

| Objeto | Descripción |
|--------|-------------|
| **`canon.normalize_real_tipo_servicio(raw text)`** | Función única raw → clave normalizada. **Aquí se centraliza el fix:** ampliar para unificar confort+/confort plus, tuk_tuk/tuk-tuk, express/mensajería → delivery. |
| **`canon.dim_real_service_type_lob`** | Tabla: `service_type_norm` (PK), `lob_group`, `mapping_source`, `is_active`, `notes`, `updated_at`. Lookup para LOB desde clave normalizada. |
| **`canon.map_real_tipo_servicio_to_lob_group`** | Legacy; se mantiene por compatibilidad. No es fuente de verdad desde 070. |

## 3. Vistas SQL que consumen la capa canónica

| Vista | Consume | Columnas expuestas |
|-------|---------|--------------------|
| `ops.v_real_trips_service_lob_resolved` | `canon.normalize_real_tipo_servicio`, `canon.dim_real_service_type_lob` | tipo_servicio_raw, tipo_servicio_norm, lob_group_resolved |
| `ops.v_real_trips_with_lob_v2` | Wrapper sobre v_real_trips_service_lob_resolved | real_tipo_servicio_norm, lob_group |

## 4. Vistas materializadas (MVs) REAL LOB

| MV | Fuente | Columnas LOB/servicio |
|----|--------|------------------------|
| `ops.mv_real_lob_month_v2` | v_real_trips_with_lob_v2 | lob_group, real_tipo_servicio_norm |
| `ops.mv_real_lob_week_v2` | v_real_trips_with_lob_v2 | lob_group, real_tipo_servicio_norm |
| `ops.mv_real_trips_by_lob_month` | (legacy) | lob |
| `ops.mv_real_trips_by_lob_week` | (legacy) | lob |

## 5. Fact / drill (backfill)

| Objeto | Fuente de normalización | Uso |
|--------|-------------------------|-----|
| `ops.real_drill_dim_fact` | Rellenado por `backfill_real_lob_mvs.py` usando **canon.normalize_real_tipo_servicio** + **canon.dim_real_service_type_lob** | Drill PRO: breakdown lob, park, service_type |
| `ops.mv_real_drill_dim_agg` | Vista sobre `ops.real_drill_dim_fact` | API drill lee esta vista |
| `ops.real_rollup_day_fact` | Mismo backfill; usa canon.normalize_real_tipo_servicio | Rollup diario |

## 6. Servicios backend afectados

| Servicio | Endpoint(s) | Dependencia |
|----------|-------------|-------------|
| `real_lob_service.py` | GET /ops/real-lob/monthly, weekly | mv_real_trips_by_lob_* (columna `lob`) |
| `real_lob_service_v2.py` | GET /ops/real-lob/monthly-v2, weekly-v2 | MVs v2 → real_tipo_servicio_norm, lob_group |
| `real_lob_v2_data_service.py` | GET /ops/real-lob/v2/data | MVs v2 → real_tipo_servicio_norm, lob_group |
| `real_lob_filters_service.py` | GET /ops/real-lob/filters | DISTINCT real_tipo_servicio_norm, lob_group desde MVs v2 |
| `real_lob_drill_pro_service.py` | GET /ops/real-lob/drill, drill/children, drill/parks | mv_real_drill_dim_agg (dimension_key = lob_group o tipo_servicio_norm) |
| `real_lob_daily_service.py` | GET /ops/real-lob/daily/* | (revisar si usa tipo_servicio/lob) |
| `real_strategy_service.py` | GET /ops/real-strategy/country, lob, cities | Vistas strategy (pueden depender de agregados por LOB) |

## 7. Endpoints REAL impactados

- `/ops/real-lob/monthly`, `/ops/real-lob/weekly`
- `/ops/real-lob/monthly-v2`, `/ops/real-lob/weekly-v2`
- `/ops/real-lob/v2/data`
- `/ops/real-lob/filters`
- `/ops/real-lob/drill`, `/ops/real-lob/drill/children`, `/ops/real-lob/drill/parks`
- `/ops/real-lob/comparatives/weekly`, `/ops/real-lob/comparatives/monthly`
- `/ops/real-lob/daily/summary`, `/ops/real-lob/daily/comparative`, `/ops/real-lob/daily/table`
- `/ops/real-strategy/country`, `/ops/real-strategy/lob`, `/ops/real-strategy/cities`

## 8. Componentes frontend REAL

| Componente | Datos LOB/servicio |
|-----------|--------------------|
| `RealLOBView.jsx` | Filtros: lob_groups, tipo_servicio; tablas: lob_group, real_tipo_servicio_norm. Usa getRealLobFilters, getRealLobV2Data. |
| `RealLOBDrillView.jsx` | Drill por lob / park / service_type; dimension_key, lob_group, service_type. |
| `RealLOBDailyView.jsx` | getRealLobDailyTable con group_by: 'lob'. |
| `PlanVsRealView.jsx` | real_tipo_servicio, lob_base (contexto Plan vs Real). |

No hay hotfix de renaming en frontend: se usan directamente `lob_group` y `real_tipo_servicio_norm` del API.

## 9. Lógica duplicada (a eliminar vía capa canónica)

- **070**: `canon.normalize_real_tipo_servicio` con CASE limitado (no unifica "confort plus", "tuk_tuk", "mensajería"/"express").
- **053**: `mv_real_lob_drill_agg` tiene CASE inline propio (legacy; el drill activo usa real_drill_dim_fact + backfill con canon).
- **051**: `mv_real_rollup_day` tiene CASE inline + map (legacy).
- **064/047**: v_real_trips_with_lob_v2 ya delegada a v_real_trips_service_lob_resolved (070).

Tras el fix canónico, la única normalización es `canon.normalize_real_tipo_servicio`; las MVs que lean de v_real_trips_with_lob_v2 y el backfill propagarán valores unificados.

## 10. Queries de diagnóstico (valores actuales en BD)

Para ejecutar en BD y obtener variantes reales de tipo_servicio (antes del fix):

```sql
-- Top tipo_servicio RAW (últimos 90d)
SELECT TRIM(COALESCE(tipo_servicio::text,'')) AS raw_val, COUNT(*) AS trips
FROM ops.v_trips_real_canon t
WHERE t.fecha_inicio_viaje::date >= (current_date - 90)
  AND tipo_servicio IS NOT NULL
GROUP BY TRIM(COALESCE(tipo_servicio::text,''))
ORDER BY trips DESC;

-- Valores que devuelve hoy canon.normalize_real_tipo_servicio (muestra fragmentación)
SELECT canon.normalize_real_tipo_servicio(tipo_servicio::text) AS norm, COUNT(*) AS trips
FROM ops.v_trips_real_canon t
WHERE t.fecha_inicio_viaje::date >= (current_date - 90)
  AND tipo_servicio IS NOT NULL
GROUP BY canon.normalize_real_tipo_servicio(tipo_servicio::text)
ORDER BY trips DESC;
```

## 11. Decisión canónica (resumen)

- **Catálogo canónico de claves** (service_type_norm): economico, comfort, comfort_plus, tuk_tuk, minivan, premier, delivery, cargo, moto, standard, start, xl, UNCLASSIFIED.
- **Reglas de equivalencia**: confort+/confort plus/comfort+/comfort plus → comfort_plus; tuk_tuk/tuk-tuk → tuk_tuk; express/mensajería/mensajeria/expres/envios → delivery.
- **Normalización robusta**: unaccent, lower, trim; + → _plus; espacios y guiones → _; luego mapeo a clave canónica.
- **display_label**: opcional en API; si se añade, será en contrato (ej. comfort_plus → "Comfort Plus"). Por ahora el frontend puede formatear desde canonical_key.

### Tabla raw → canonical (080)

| Valor crudo (ejemplos) | Clave canónica |
|------------------------|----------------|
| económico, economico | economico |
| confort, comfort | comfort |
| confort+, confort plus, comfort+, comfort plus | comfort_plus |
| tuk-tuk, tuk_tuk | tuk_tuk |
| express, mensajería, mensajeria, expres, envíos, envios | delivery |
| minivan, premier, standard, start, xl, economy | (misma clave) |
| cargo, moto, taxi_moto | (misma clave) |
| Otros válidos (< 30 chars, sin coma) | clave normalizada tal cual |
| NULL, vacío, >30 chars, con coma | NULL / UNCLASSIFIED |

## 12. Pasos post-migración (080)

1. **Aplicar migración:** `alembic upgrade head`
2. **Refrescar MVs v2** para que datos ya reflejen claves canónicas:
   - `REFRESH MATERIALIZED VIEW ops.mv_real_lob_month_v2;`
   - `REFRESH MATERIALIZED VIEW ops.mv_real_lob_week_v2;`
   (O ejecutar script existente de refresh si lo hay.)
3. **Opcional — backfill drill:** Para que el drill (real_drill_dim_fact) use ya claves canónicas en datos históricos:  
   `python -m scripts.backfill_real_lob_mvs --from YYYY-MM-01 --to YYYY-MM-01`
4. **Cache de filtros:** El servicio de filtros (real_lob_filters_service) tiene cache 5 min; tras refresh de MVs, en la siguiente carga los filtros mostrarán valores canónicos sin duplicados.
