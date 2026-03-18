# REAL Driver Segmentation — Implementación E2E

**Veredicto:** `REAL_DRIVER_SEGMENTATION_IMPLEMENTED`

## 1. Definición final de segmentación

| Segmento | Condición | Descripción |
|----------|-----------|-------------|
| **activos** | `completed_cnt > 0` | Conductor con al menos 1 viaje completado en el periodo |
| **solo_cancelan** | `completed_cnt = 0` AND `cancelled_cnt > 0` | Al menos 1 cancelación y 0 completados |
| **conductores_con_actividad** | `completed_cnt > 0` OR `cancelled_cnt > 0` | Cualquier actividad |
| **%_solo_cancelan** | `cancel_only_drivers / activity_drivers` | Porcentaje solo cancelan |

No existe el concepto de "mixtos". Un conductor se clasifica como activo o solo_cancelan por periodo.

## 2. Capa donde nace la métrica

- **Origen:** `ops.v_trips_real_canon` (conductor_id, condicion, fecha, park_id, tipo_servicio).
- **Vista por viaje:** `ops.v_real_driver_segment_trips` — todos los viajes (completados y cancelados) con conductor_id, condicion, country, city, park_id, lob_group, service_type_norm, segment_tag (B2C/B2B). Misma lógica country/LOB/service_type que REAL (parks + canon.map_real_tipo_servicio_to_lob_group).
- **Conductor por periodo:** `ops.v_real_driver_segment_driver_period` — grano (driver_key, period_grain, period_start, country, segment_tag) con dimensión dominante (park, lob, service_type) y conteos completed_cnt, cancelled_cnt; flags is_active, is_cancel_only, is_activity.
- **Agregado por tajada:** `ops.v_real_driver_segment_agg` — grano (country, period_grain, period_start, segment_tag, breakdown, dimension_key, dimension_id, city) con active_drivers, cancel_only_drivers, activity_drivers, cancel_only_pct.
- **Persistencia:** Columnas en `ops.real_drill_dim_fact`: active_drivers, cancel_only_drivers, activity_drivers, cancel_only_pct. Pobladas por `populate_real_drill_from_hourly_chain` vía UPDATE desde `v_real_driver_segment_agg`.

## 3. Reconciliación entre tajadas

- Un conductor cuenta en **una sola** celda por breakdown (LOB, Park, Service_type) usando la dimensión **dominante** (mayor actividad en el periodo). Así, la suma de active_drivers por LOB = suma por Park = total activos por país+periodo (sin doble conteo).
- Script de validación: `backend/scripts/sql/validate_real_driver_segmentation.sql`.

## 4. Cadena REAL afectada

- **Daily / Weekly / Monthly:** real_drill_dim_fact se puebla con day/week/month desde mv_real_lob_day_v2, week_v3, month_v3; después se actualizan las 4 columnas de segmentación desde v_real_driver_segment_agg.
- **Drill principal:** GET /ops/real-lob/drill — devuelve active_drivers, cancel_only_drivers, activity_drivers, cancel_only_pct por periodo y en KPIs por país.
- **Children:** GET /ops/real-lob/drill/children — mismas métricas en cada fila de desglose (LOB, Park, Service_type). SERVICE_TYPE por park (mv_real_drill_service_by_park) no tiene segmentación; se devuelve null.
- **Vista:** ops.mv_real_drill_dim_agg recreada en migración 106 para exponer las 4 columnas.

## 5. Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `backend/alembic/versions/106_real_driver_segmentation_canonical.py` | Nueva migración: vistas v_real_driver_segment_trips, v_real_driver_segment_driver_period, v_real_driver_segment_agg; columnas en real_drill_dim_fact; recreación mv_real_drill_dim_agg |
| `backend/scripts/populate_real_drill_from_hourly_chain.py` | UPDATE de active_drivers, cancel_only_drivers, activity_drivers, cancel_only_pct desde v_real_driver_segment_agg tras INSERT day/week/month |
| `backend/app/services/real_lob_drill_pro_service.py` | SELECT y KPIs con active_drivers, cancel_only_drivers, activity_drivers, cancel_only_pct; children con las mismas métricas |
| `frontend/src/components/RealLOBDrillView.jsx` | Columnas Activos, Solo cancelan, % Solo cancelan en tabla principal y subfilas; KPIs superiores por país con Activos, Solo cancelan, % Solo cancelan; colSpan 18 |
| `backend/scripts/sql/validate_real_driver_segmentation.sql` | Validación SQL de reglas de segmentación y reconciliación |
| `docs/REAL_DRIVER_SEGMENTATION_IMPLEMENTED.md` | Este memo |

## 6. Evidencia DB

- Tras `alembic upgrade head`: existen v_real_driver_segment_trips, v_real_driver_segment_driver_period, v_real_driver_segment_agg y columnas en real_drill_dim_fact.
- Ejecutar `validate_real_driver_segmentation.sql` (o `python -m scripts.run_validate_real_driver_segmentation`) para comprobar is_active / is_cancel_only y reconciliación por tajada. **Nota:** En bases grandes las vistas pueden tardar; usar `statement_timeout` alto o materializar si hace falta.

## 7. Evidencia runtime

- Reiniciar backend.
- Llamar: GET /ops/real-lob/drill?period=month&desglose=LOB (y week, PARK, SERVICE_TYPE). Comprobar que el payload incluye active_drivers, cancel_only_drivers, activity_drivers, cancel_only_pct en rows y en kpis.
- Llamar: GET /ops/real-lob/drill/children con country, period, period_start, desglose. Comprobar que las filas incluyen las mismas métricas (o null para service_type por park).

## 8. Evidencia UI

- En Real LOB > Drill: tabla con columnas Activos, Solo cancelan, % Solo cancelan; KPIs superiores con Activos, Solo cancelan, % Solo cancelan; al expandir periodo, subfilas con las mismas columnas.

## 9. Validación post-restart

- Backend reiniciado; endpoints sin 500; UI sin spinner infinito; sin regresión en cancelaciones ni margen.

## 10. Guardrails

- **SQL:** validate_real_driver_segmentation.sql comprueba conductor activo (completed>0 → is_active), conductor solo_cancelan (completed=0 y cancelled>0 → is_cancel_only) y reconciliación por periodo.
- **Backend:** tests/test_real_coherence.py::test_get_drill_returns_driver_segmentation_metrics y test_get_drill_children_park_rows_have_park_label (incluyen assert de active_drivers, cancel_only_drivers, activity_drivers, cancel_only_pct en respuesta).
- **Alertas sugeridas (opcionales):** activity_drivers = 0 en ventana esperada con datos; cancel_only_pct > 90% de forma masiva.

## 11. Condición de viaje

- **Completado:** `condicion = 'Completado'`.
- **Cancelado:** `condicion = 'Cancelado'` OR `condicion ILIKE '%cancel%'`.

Implementación lista para persistencia DB → backend → API → UI y validación post-restart.
