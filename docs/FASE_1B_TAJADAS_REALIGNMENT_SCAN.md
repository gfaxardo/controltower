# FASE 1B — Scan: realineamiento Control Loop ↔ tajadas Omniview

## 1. Fuente de verdad de las tajadas visibles (Omniview Matrix)

- **Reglas de negocio importadas** desde la plantilla `Plantillas_Control_Tower_Simplificadas_final.xlsx` hoja **`1_Config_Tajadas`** → tabla **`ops.business_slice_mapping_rules`** (`park_id`, `rule_type`, `tipo_servicio_values[]`, `works_terms_values[]`, `business_slice_name`, flota/subflota, `is_active`).
- **Asignación viaje → tajada** (misma prioridad que Omniview): vista **`ops.v_real_trips_business_slice_resolved`** (une `v_real_trips_enriched_base` con reglas activas; prioridad `park_plus_works_terms` > `park_plus_tipo_servicio` > `park_only`; desempate en conflicto).
- **Agregado mensual Matrix / Omniview**: tabla **`ops.real_business_slice_month_fact`** (carga incremental; granularidad incluye flota/subflota). Para **una tajada visible** a nivel “nombre de negocio”, el Control Loop debe alinearse al **mismo universo de viajes resueltos**, no a un `lob_group` genérico.

## 2. Tajadas que dependen solo de `park_id`

- Reglas con **`rule_type = 'park_only'`**: el viaje cae en la tajada si `park_id` matchea la regla (y pasa filtros base); no se exige `tipo_servicio` ni `work_term`.

## 3. Tajadas que dependen de `park_id` + `tipo_servicio`

- Reglas con **`rule_type = 'park_plus_tipo_servicio'`**: además del park, debe existir coincidencia entre `tipo_servicio` del viaje y **`tipo_servicio_values`** (vía `ops.normalized_service_type`).

## 4. Tajadas que dependen de `park_id` + work_term

- Reglas con **`rule_type = 'park_plus_works_terms'`**: además del park, **`works_terms`** del driver/viaje debe matchear **`works_terms_values`** (vía `ops.normalized_works_terms` y comparación LIKE acotada en la vista).

## 5. Qué tajadas de Control Loop estaban mal resueltas (Fase 1 previa)

- Comparación real basada en **`ops.mv_real_lob_month_v2`** + CASE sobre `lob_group` / `real_tipo_servicio_norm` (catálogo **Real LOB v2**), **no** en `business_slice_name` ni en reglas de `business_slice_mapping_rules`.
- **PRO / YMA / YMM** quedaron como **`NOT_MAPPED`** por no existir fila en ese CASE, aunque sí puedan existir tajadas homónimas en **`business_slice_mapping_rules`**.

## 6. Causa exacta del mismatch

- **Doble taxonomía**: plan de negocio (líneas tipo “Auto regular”, “PRO”) vs corte **Real LOB** (`lob_group`) vs corte **Business Slice / Omniview** (`business_slice_name` + reglas park/tipo/work_term).
- La Fase 1 inicial eligió el corte **LOB v2** para el real; Omniview Matrix consume **Business Slice** (`real_business_slice_month_fact` / resolved). Sin puente explícito **`linea Excel/plan → business_slice_name`**, las cifras no son comparables.

## 7. Componentes que **no** se tocan

- Rutas y componentes de **`/operacion/omniview-matrix`**, **`BusinessSliceOmniviewMatrix`**, **`GET /ops/business-slice/omniview`** (contrato intacto).
- **`ops.v_plan_vs_real_realkey_final`** y endpoints Plan vs Real **realkey** existentes.
- **Upload** de plan existentes (`/plan/upload_simple`, `/plan/upload_ruta27`).
- Tablas **`ops.business_slice_mapping_rules`** y vistas **`v_real_trips_business_slice_resolved`** (solo lectura; nueva vista agregada encima).

## Cierre

- **Corrección**: capa real de Control Loop sustituida por agregación mensual desde **`v_real_trips_business_slice_resolved`** agrupada por **`business_slice_name`**, con **`COUNT(DISTINCT driver_id)`** en el mismo grano (alineado a semántica de drivers a nivel tajada-mes).
- **Puente plan**: resolución **`linea_negocio_excel` / canónico → business_slice_name`** vía coincidencia con reglas activas por ciudad + tabla opcional **`ops.control_loop_plan_line_to_business_slice`**.

## 8. Capa de matching reemplazada (no borrada en BD)

- **Antes (MVP)**: `ops.mv_real_lob_month_v2` + CASE `lob_group` / `real_tipo_servicio_norm` + vistas `ops.v_real_monthly_control_loop_trips_revenue` / `ops.v_real_monthly_control_loop_drivers` / `ops.v_control_loop_trip_grain`.
- **Después (minifase)**: **`ops.v_real_monthly_control_loop_from_tajadas`** + resolución Python `control_loop_business_slice_resolve` contra **`ops.business_slice_mapping_rules`**.

## 9. Evidencia manual sugerida (3 casos)

| Caso | Plantilla (Excel) | Regla esperada | Verificación |
|------|-------------------|----------------|--------------|
| Lima / PRO / mes | línea PRO | `business_slice_name` = PRO en reglas activas para PE/Lima | `v_real_monthly_control_loop_from_tajadas` y endpoint |
| Lima / YMA o YMM | línea YMA o YMM | misma lógica park/tipo/work_term que Matrix | idem |
| Auto regular o Delivery | línea homónima | match texto Excel ↔ `business_slice_mapping_rules` | idem |

## 10. Omniview Matrix sin cambios

- No se modificaron rutas, componentes ni servicios de **`GET /ops/business-slice/omniview`** ni la pantalla **`/operacion/omniview-matrix`**.
