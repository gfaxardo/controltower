# FASE 1B + FASE 2A — Salida ejecutiva final

**Proyecto:** YEGO Control Tower  
**Fecha:** 2025-03-14  

---

## A. ¿En qué punto real quedó el sistema tras cambiar de máquina?

El código traído de la rama remota está **coherente y completo** en backend, frontend, migraciones y scripts. No se detectaron imports rotos ni artefactos clave faltantes. La cadena de migraciones llega hasta **096** (real_lob_mvs_partial_120d). La incertidumbre restante es **solo de runtime**: si en esta máquina se ejecutó `alembic upgrade head` y si las MVs (por ejemplo `ops.mv_real_trips_monthly`, `ops.mv_real_lob_month_v2`) existen y están refrescadas. Eso se comprueba con `alembic current` y consultando las tablas/vistas en la BD.

---

## B. ¿La Fase 1 quedó viva, parcial o rota?

**Fase 1 (observability) quedó viva en código e integrada.** El servicio, router, migraciones 092/093, vistas de observability y el frontend System Health están implementados y conectados. El script `refresh_real_lob_mvs_v2.py` escribe en `observability_refresh_log`. Si en esta máquina no se han aplicado las migraciones, la UI mostrará “sin módulos” hasta ejecutar `alembic upgrade head`. No se ha roto ni rediseñado la observabilidad.

---

## C. ¿Qué métricas reales ya existen para el comparativo?

- **Directas:** trips_real (trips_real_completed), revenue_real (revenue_real_yego), active_drivers_real, avg_ticket_real desde **ops.mv_real_trips_monthly** (grain: month, country, city_norm, lob_base, segment, park_id). Desde **ops.mv_real_lob_month_v2**: trips, revenue por LOB/parque/segment_tag (sin conductores en esa MV).
- **Derivadas (ya calculables):** avg_trips_per_driver_real = trips / active_drivers, revenue_per_trip_real, revenue_per_driver_real. La vista **ops.v_real_metrics_monthly** (migración 097) expone estas métricas para el comparativo.

---

## D. ¿Qué métricas faltaban y cómo las resolviste?

Faltaban una **vista unificada de métricas reales mensuales** para comparar con proyección y campos para **brecha y palancas** (required_drivers_for_target, gap_explained_by_*). Se resolvió con la migración **097**: se creó **ops.v_real_metrics_monthly** (desde mv_real_trips_monthly) con drivers_real, trips_real, revenue_real, avg_ticket_real, avg_trips_per_driver_real, revenue_per_trip_real, revenue_per_driver_real; y las vistas comparativas **v_real_vs_projection_system_segmentation** y **v_real_vs_projection_projection_segmentation** con columnas para plan, gaps y gap_explained_by_driver_count/productivity/ticket. Esas métricas derivadas (required_drivers_for_target, etc.) se podrán rellenar cuando existan datos de proyección en las vistas.

---

## E. ¿Cómo quedará el modelo Real vs Proyección?

- **Real:** se lee de **ops.v_real_metrics_monthly** (a su vez de ops.mv_real_trips_monthly). No se mezcla con Plan en la misma fuente.
- **Proyección:** carga cruda en **ops.projection_upload_staging**; normalización vía **ops.projection_dimension_mapping** (raw_label → target_canonical_label). Vistas comparativas: **v_real_vs_projection_system_segmentation** (grain del sistema) y **v_real_vs_projection_projection_segmentation** (grain de la proyección). Comparación y brechas se calculan en esa capa, no en las fuentes base.

---

## F. ¿Cómo se resolverá el casamiento de nomenclaturas?

Con la tabla **ops.projection_dimension_mapping**: dimension_type, source_raw_label, normalized_label, target_canonical_label, matching_status, confidence, manual_override. La proyección (Excel) puede usar otros nombres de ciudad/país/LOB; se mapean a los canónicos del sistema sin tocar Real ni Plan. La capa de vistas comparativas consume la proyección ya mapeada (cuando exista pipeline de normalización desde staging).

---

## G. ¿Quedó lista una estructura para cargar la proyección Excel?

Sí. **ops.projection_upload_staging** (period, period_type, raw_country, raw_city, raw_line_of_business, raw_segment, drivers_plan, trips_plan, revenue_plan, avg_ticket_plan, source_file_name, uploaded_at) y **ops.projection_dimension_mapping** para el mapping. El contrato esperado del Excel está documentado en **docs/projection_template_contract.md** (placeholder hasta que el usuario entregue la plantilla real). Endpoint/script de carga (upload/parser) se implementará cuando exista el Excel final.

---

## H. ¿Qué endpoints, tablas, vistas o docs creaste?

- **Migración 097:** ops.projection_upload_staging, ops.projection_dimension_mapping, ops.v_real_metrics_monthly, ops.v_real_vs_projection_system_segmentation, ops.v_real_vs_projection_projection_segmentation.
- **Backend:** app/services/real_vs_projection_service.py, app/routers/real_vs_projection.py; rutas bajo **/ops/real-vs-projection/** (overview, dimensions, mapping-coverage, real-metrics, projection-template-contract, system-segmentation-view, projection-segmentation-view).
- **Frontend:** components/RealVsProjectionView.jsx; subtab “Real vs Proyección” en Plan y validación; funciones en api.js (getRealVsProjectionOverview, getRealVsProjectionDimensions, etc.).
- **Docs:** docs/fase1b_rescan_post_machine_change.md, docs/real_vs_projection_metric_dictionary.md, docs/fase2a_real_vs_projection_foundation.md, docs/projection_template_contract.md, docs/fase2a_salida_ejecutiva.md.
- **Tests:** backend/tests/test_real_vs_projection.py (estructura de respuestas del servicio).

---

## I. ¿Qué UI quedó preparada?

Una **subtab “Real vs Proyección”** dentro de **Plan y validación**, con la vista **RealVsProjectionView**: estado del comparativo (readiness, proyección cargada, métricas reales disponibles), dimensiones del sistema, cobertura de mapping, muestra de métricas reales (tabla), contrato de plantilla Excel y un bloque placeholder que explica que cuando se suba la proyección se mostrarán las comparaciones por segmentación. No se han añadido aún gráficos ni tablas comparativas complejas.

---

## J. ¿Qué exactamente habrá que hacer cuando el usuario suba la plantilla de proyección?

1. **Ajustar el contrato** en docs/projection_template_contract.md a las columnas y valores reales del Excel.
2. **Implementar el parser de carga:** endpoint POST (p. ej. /ops/real-vs-projection/upload) o script (load_projection_from_excel.py) que lea el archivo, valide columnas y escriba en **ops.projection_upload_staging**.
3. **Definir o poblar mapping:** reglas en **ops.projection_dimension_mapping** para raw_country, raw_city, raw_line_of_business, etc. → canónicos del sistema (manual o semiautomático desde valores distintos del Excel).
4. **Crear o actualizar vista normalizada:** si se usa ops.projection_normalized, rellenarla desde staging + mapping.
5. **Actualizar las vistas comparativas** (v_real_vs_projection_system_segmentation y v_real_vs_projection_projection_segmentation) para que hagan JOIN con la proyección normalizada y calculen drivers_gap, trips_gap, revenue_gap y gap_explained_by_* con datos reales.
6. **Probar** con datos de ejemplo y validar coherencia de métricas y brechas en la UI.
