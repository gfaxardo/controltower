# CT-REAL-DIMENSION-GOVERNANCE — Gobernanza de dimensiones REAL

## 1. Objetivo

Consolidar y gobernar las dimensiones canónicas del sistema REAL (service types, LOB, LOB groups) para eliminar nomenclatura inconsistente, duplicados y taxonomía dispersa. Se construye sobre la canonicalización ya implementada en `canon.normalize_real_tipo_servicio()` (080) y expone dimensiones oficiales reutilizables.

## 2. Arquitectura final

```
trips_all.tipo_servicio (raw)
         │
         ▼
canon.normalize_real_tipo_servicio(raw)  ──► service_type_key
         │
         ▼
canon.dim_service_type (service_type_key, service_type_label, lob_key, lob_group_key)
         │
         ├──► canon.dim_lob (lob_key, lob_label, lob_group_key)
         │
         └──► canon.dim_lob_group (lob_group_key, lob_group_label)
                    │
                    ▼
         v_real_trips_service_lob_resolved  ──► tipo_servicio_norm, lob_group_resolved (label)
                    │
                    ▼
         v_real_trips_with_lob_v2  ──► real_tipo_servicio_norm, lob_group (contrato API)
                    │
                    ▼
         mv_real_lob_month_v2 / mv_real_lob_week_v2  ──► filtros, tablas, drill
```

## 3. Dimensiones creadas (090)

### canon.dim_lob_group

| lob_group_key | lob_group_label |
|---------------|-----------------|
| auto_taxi | auto taxi |
| tuk_tuk | tuk tuk |
| delivery | delivery |
| taxi_moto | taxi moto |
| other | Other |

### canon.dim_lob

Relación 1:1 con grupo en la semilla: lob_key = lob_group_key, lob_label = lob_group_label.

### canon.dim_service_type

| service_type_key | service_type_label | lob_group_key |
|------------------|--------------------|---------------|
| economico | Económico | auto_taxi |
| comfort | Comfort | auto_taxi |
| comfort_plus | Comfort Plus | auto_taxi |
| tuk_tuk | Tuk Tuk | tuk_tuk |
| minivan, premier, standard, start, xl, economy | (idem) | auto_taxi |
| delivery | Delivery | delivery |
| cargo | Cargo | delivery |
| moto, taxi_moto | Moto, Taxi Moto | taxi_moto |

## 4. Mapas raw → canónico

- **tipo_servicio raw → service_type_key:** Ver `docs/CT_REAL_LOB_CANONICALIZATION_MAP.md` §11 (confort+/confort plus → comfort_plus; tuk_tuk/tuk-tuk → tuk_tuk; express/mensajería → delivery).
- **service_type_key → lob_group_key / label:** Lookup en `canon.dim_service_type` + `canon.dim_lob_group`.

## 5. Impacto en endpoints

- **Contrato preservado:** Los endpoints siguen devolviendo `lob_group` (label, ej. "auto taxi") y `real_tipo_servicio_norm` (service_type_key, ej. "comfort_plus"). No se añadieron campos nuevos.
- **/ops/real-lob/filters:** lob_groups y tipo_servicio provienen de las MVs v2, que a su vez leen de la vista alimentada por dimensiones; tras REFRESH de MVs los valores son canónicos y sin duplicados.
- **/ops/real-lob/v2/data, monthly-v2, weekly-v2:** Misma estructura; agrupaciones por real_tipo_servicio_norm y lob_group.
- **/ops/real-lob/drill, drill/children:** Siguen usando dimension_key (lob_group o service_type) desde real_drill_dim_fact; el backfill usa `canon.normalize_real_tipo_servicio` y `canon.dim_real_service_type_lob` (sincronizado desde dim_service_type en 090).
- **/ops/real-strategy/*:** Sin cambio de contrato; consumen lob_group desde vistas que ya usan dimensiones.

## 6. Impacto en UI

- **Filtros:** Valores únicos (lob_groups, tipo_servicio) sin duplicados equivalentes.
- **Tablas y breakdowns:** Columnas lob_group y real_tipo_servicio_norm con valores canónicos.
- **Drilldowns:** dimension_key y lob_group coherentes con dimensiones.
- **Sin renaming en frontend:** Se siguen usando los valores que devuelve el API.
- **Persistencia:** Tras recarga, cambio de filtros o de pestaña, los datos siguen viniendo del backend/MVs; la corrección persiste después de REFRESH de MVs.

## 7. Refresh y backfill (FASE G)

Después de aplicar la migración 090:

```sql
REFRESH MATERIALIZED VIEW ops.mv_real_lob_month_v2;
REFRESH MATERIALIZED VIEW ops.mv_real_lob_week_v2;
```

Para drill y rollup diario (opcional):

```bash
python -m scripts.backfill_real_lob_mvs --from YYYY-MM-01 --to YYYY-MM-01
```

Cache de filtros: 5 min; tras refresh de MVs, la siguiente carga devolverá valores canónicos.

## 8. Validación (FASE H)

1. **Conteo de categorías:** No deben existir a la vez confort+ y comfort_plus, tuk_tuk y tuk-tuk, express y mensajería en filtros/tablas.
2. **Totales:** El total de viajes debe mantenerse igual (solo se redistribuye entre claves equivalentes).
3. **Endpoints:** Probar /ops/real-lob/filters, /ops/real-lob/v2/data, /ops/real-lob/drill, /ops/real-strategy/lob.
4. **UI:** Verificar filtros, tablas, drilldowns y WoW en pestañas REAL.

## 9. Archivos tocados

| Archivo | Cambio |
|---------|--------|
| alembic/versions/090_real_dimension_governance.py | Crea dim_lob_group, dim_lob, dim_service_type; refactoriza v_real_trips_service_lob_resolved y v_real_trips_with_lob_v2; sincroniza dim_real_service_type_lob. |
| app/services/real_lob_filters_service.py | Comentario: valores canónicos desde dimensiones vía MVs. |
| docs/CT_REAL_DIMENSION_GOVERNANCE_MAP.md | Mapa del sistema (FASE A). |
| docs/CT_REAL_DIMENSION_GOVERNANCE.md | Este documento. |

Frontend: sin cambios (no había transformaciones manuales; se usan valores del API).

## 10. Criterios de éxito

- No existen duplicados de servicio en filtros/tablas.
- Las vistas REAL usan dimensiones (v_real_trips_service_lob_resolved usa dim_service_type y dim_lob_group).
- El frontend muestra solo valores canónicos (vía API).
- Los filtros no repiten categorías equivalentes.
- La corrección persiste después de refresh de MVs y recarga de UI.
- Los totales de viajes no cambian.
- Todo quedó documentado (mapa + este doc).
