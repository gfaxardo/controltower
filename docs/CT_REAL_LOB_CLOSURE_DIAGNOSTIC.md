# CT-REAL-LOB-CLOSURE — Diagnóstico

## 1. Estado de Alembic

### Heads (divergentes)

| Head | Descripción |
|------|-------------|
| **090_real_dimension_governance** | Dimensiones canónicas REAL (dim_lob_group, dim_lob_real, dim_service_type); vistas refactorizadas. |
| **092_observability_registry** | Registro de artefactos y log de refresh (observability). |

### Current en BD (ejemplo típico)

En entornos donde se aplicó la rama LOB y luego la rama fleet/observability, `alembic current` puede mostrar dos revisiones (rama):

- `090_real_dimension_governance (head)`
- `091_fleet_leakage_snapshot`

Es decir: la BD tiene aplicadas dos líneas que divergen desde 079.

### Cadenas exactas

**Rama A — REAL LOB / dimension governance**

```
079_driver_segment_migrations_weekly_views
  -> 080_real_lob_canonical_service_type_unified
  -> 090_real_dimension_governance
```

**Rama B — Driver / fleet / observability**

```
079_driver_segment_migrations_weekly_views
  -> 080_mv_driver_segment_migrations_weekly_optional
  -> 081_driver_behavior_baseline_weekly
  -> ... -> 089_driver_behavior_deviation_last_trip
  -> 090_behavioral_alerts_sudden_stop
  -> 091_fleet_leakage_snapshot
  -> 092_observability_registry
```

**Conclusión:** Hay dos “090” distintos (090_real_dimension_governance y 090_behavioral_alerts_sudden_stop). El merge debe unir **090_real_dimension_governance** y **092_observability_registry**.

---

## 2. Objetos en BD (existencia por entorno)

Objetos que **pueden existir o no** según qué migraciones se aplicaron:

| Objeto | Creado en | Rama | Uso |
|--------|-----------|------|-----|
| canon.dim_lob_group | 090_real_dimension_governance | A | Labels LOB group |
| canon.dim_lob_real | 090_real_dimension_governance | A | LOB por grupo |
| canon.dim_service_type | 090_real_dimension_governance | A | Service type canónico |
| canon.dim_real_service_type_lob | 070 | común (antes de 079) | Legacy; 090 lo sincroniza |
| ops.v_real_trips_service_lob_resolved | 070 / 090 | A o común | Vista por viaje resuelta |
| ops.v_real_trips_with_lob_v2 | 070 / 090 | A o común | Contrato API (real_tipo_servicio_norm, lob_group) |
| ops.mv_real_lob_month_v2 | 044, 047 | Rama con 044/047 | Filtros y datos v2 |
| ops.mv_real_lob_week_v2 | 044, 047 | Rama con 044/047 | Filtros y datos v2 |
| ops.real_drill_dim_fact | 051, 064 | Rama con 064 | Drill PRO |
| ops.mv_real_drill_dim_agg | 064 | Rama con 064 | Vista sobre real_drill_dim_fact |
| ops.real_rollup_day_fact | 064 | Rama con 064 | Daily KPIs |

**Importante:** En entornos que solo tienen aplicada la rama A (079 -> 080_real_lob -> 090) **no** tienen 044/047/064 de la rama “real lob v2 original”, por lo que **no existen** `ops.mv_real_lob_month_v2` ni `ops.mv_real_lob_week_v2`. Las vistas `v_real_trips_*` sí pueden existir si 070 y 090 están aplicadas.

---

## 3. Consumo real del frontend

| Componente | Endpoints | Objeto backend que alimenta |
|------------|-----------|-----------------------------|
| RealLOBView (Observabilidad) | getRealLobFilters, getRealLobV2Data, getRealLobMonthlyV2, getRealLobWeeklyV2 | MVs v2 (filters, v2/data, monthly-v2, weekly-v2) |
| RealLOBDrillView | getRealLobDrillPro, getRealLobDrillProChildren, getRealLobDrillParks, getRealLobComparatives* | mv_real_drill_dim_agg, real_drill_dim_fact |
| RealLOBDailyView | getRealLobDailySummary, getRealLobDailyComparative, getRealLobDailyTable | real_rollup_day_fact |
| Strategy | getRealStrategyCountry, getRealStrategyLob, getRealStrategyCities | Vistas ops.v_real_country_* |
| Legacy real-drill | getRealDrillSummary, getRealDrillByLob, getRealDrillByPark, ... | real_drill_* / rollup |

**Ruta de datos hasta UI (v2):**

- **Con MVs v2:** trips_all → normalize → dim_service_type / dim_lob_group → v_real_trips_service_lob_resolved → v_real_trips_with_lob_v2 → **mv_real_lob_month_v2 / mv_real_lob_week_v2** → real_lob_filters_service / real_lob_v2_data_service → API → frontend.
- **Sin MVs v2:** Las vistas v_real_trips_* existen y son consultables, pero los endpoints que leen de las MVs v2 (filters, v2/data, monthly-v2, weekly-v2) fallan o no devuelven datos hasta que existan y se refresquen esas MVs.

---

## 4. Endpoints impactados y dependencias

| Endpoint | Servicio | Objeto BD | Si no existe el objeto |
|----------|----------|-----------|-------------------------|
| GET /ops/real-lob/filters | real_lob_filters_service | mv_real_lob_month_v2, mv_real_lob_week_v2 | Error o vacío |
| GET /ops/real-lob/v2/data | real_lob_v2_data_service | mv_real_lob_month_v2, mv_real_lob_week_v2 | Error |
| GET /ops/real-lob/monthly-v2, weekly-v2 | real_lob_service_v2 | MVs v2 | Error |
| GET /ops/real-lob/monthly, weekly | real_lob_service | mv_real_trips_by_lob_month/week | Error si no existen |
| GET /ops/real-lob/drill, drill/children, drill/parks | real_lob_drill_pro_service | mv_real_drill_dim_agg (vista sobre real_drill_dim_fact) | Error si no existe |
| GET /ops/real-lob/daily/* | real_lob_daily_service | real_rollup_day_fact | Error si no existe |
| GET /ops/real-strategy/* | real_strategy_service | v_real_country_* | Error si no existen |

---

## 5. Riesgos detectados

1. **Heads divergentes:** Dos heads (090_real_dimension_governance y 092_observability_registry) impiden un único `alembic upgrade head` y generan confusión en deploy.
2. **MVs v2 ausentes:** En entornos que solo tienen la rama 079→080_real_lob→090, no existen MVs v2; cualquier refresh o endpoint que las use falla.
3. **Ruta de datos dual:** Observabilidad REAL depende de MVs v2; si no existen, la UI REAL (filtros, tablas v2, drill que use MVs) no puede funcionar sin fallback o sin aplicar la rama que crea 044/047/064.
4. **Legacy dim_real_service_type_lob:** Debe seguir sincronizado con dim_service_type (090 lo hace) para scripts que aún lo usan.

---

## 6. Resumen para cierre

| Tema | Acción |
|------|--------|
| Alembic | Merge explícito 093 que una 090_real_dimension_governance y 092_observability_registry. |
| Objetos BD | Script de cierre que detecte qué existe y refresque solo eso; no asumir MVs v2. |
| Compatibilidad | Documentar y codificar: si MVs v2 existen → usarlas y refrescarlas; si no → aviso claro y no fallar por refresco de MVs inexistentes. |
| Ruta canónica | Confirmada: trips_all → normalize_real_tipo_servicio → dim_service_type + dim_lob_group → v_real_trips_* → (MVs v2 si existen) → API. |

---

## 7. Solución implementada (cierre)

- **Merge 093:** `backend/alembic/versions/093_merge_real_lob_governance_and_observability.py` — une 090_real_dimension_governance y 092_observability_registry; sin cambios de schema. Tras aplicar: `alembic heads` → un solo head.
- **Script de cierre:** `backend/scripts/close_real_lob_governance.py` — inspección Alembic, comprobación de objetos BD, refresh solo de MVs existentes (mv_real_lob_month_v2, mv_real_lob_week_v2), validaciones y resumen. No falla si las MVs v2 no existen.
- **Documentación:** `docs/CT_REAL_LOB_CLOSURE_RUNBOOK.md`, `docs/CT_REAL_LOB_CLOSURE_VALIDATION.md`.

### Ruta canónica consolidada (FASE D)

- **Única normalización:** `canon.normalize_real_tipo_servicio(raw)` → service_type_key.
- **Único lookup LOB/labels:** `canon.dim_service_type` + `canon.dim_lob_group` (vistas 090).
- **Legacy:** `canon.dim_real_service_type_lob` se mantiene sincronizado desde dim_service_type en 090; scripts que lo lean siguen funcionando.
- **UNCLASSIFIED:** Solo como fallback cuando no hay fila en dim_service_type; controlado en la vista (COALESCE(..., 'UNCLASSIFIED')).
- **Sin CASEs duplicados:** La lógica de normalización y de resolución LOB está en la función canónica y en las dimensiones; las vistas solo hacen JOIN.
