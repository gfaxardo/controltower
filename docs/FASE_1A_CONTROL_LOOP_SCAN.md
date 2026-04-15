# FASE 1A — Diagnóstico Control Loop / Proyección agregada

Fecha: 2026-04-14. Solo lectura del repo; orientación para integración **aditiva**.

## Estructura existente para ingesta de plan

- **Plantilla long** (`/plan/upload_simple`): CSV/XLSX con columnas `period, country, city, line_of_business, metric, plan_value` → `plan.plan_long_*` vía `parse_simple_template` + `save_plan_rows*`. Opcionalmente escribe `staging.plan_projection_raw` (trips/revenue en columnas anchas de esa tabla).
- **Plantilla legacy “Proyección”** (`/plan/upload`): Excel complejo vía `parse_proyeccion_sheet_legacy`.
- **Ruta 27** (`/plan/upload_ruta27`): CSV → `ops.plan_trips_monthly` con `plan_version` (append o `replace_all`).

## Mejor punto de integración aditivo

- **No** reutilizar `plan.plan_long_valid` ni `ops.plan_trips_monthly` para esta plantilla agregada (granularidad distinta: país/ciudad/línea Excel vs universo park/segment del Ruta 27).
- Añadir **nuevo pipeline** en `staging` + vistas `ops` dedicadas: tablas `staging.control_loop_plan_metric_long`, rechazos en `staging.control_loop_plan_reject`, vista materializada lógica `ops.v_plan_projection_control_loop` y capa real `ops.v_real_monthly_control_loop_*` sin tocar `ops.v_plan_vs_real_realkey_final` ni Omniview Matrix.

## Llave real recomendada en esta fase

- **Plan cargado**: `(plan_version, period YYYY-MM, country_norm, city_norm, linea_negocio_canonica, metric)` con `metric ∈ {trips, revenue, active_drivers}`.
- **Real (comparación) — actualizado en Fase 1B**: la comparación operativa debe usar **`ops.v_real_monthly_control_loop_from_tajadas`** (agregado desde **`ops.v_real_trips_business_slice_resolved`**, misma lógica de tajadas que Omniview). Las vistas LOB genéricas del MVP inicial (`ops.v_real_monthly_control_loop_trips_revenue`, etc.) quedan como legado en BD pero **ya no alimentan** `GET /ops/control-loop/plan-vs-real` tras la minifase de realineamiento (ver `docs/FASE_1B_TAJADAS_REALIGNMENT_SCAN.md`).

## Mapeo `linea_negocio` Excel → universo real

- Catálogo explícito en `backend/app/config/control_loop_lob_mapping.py` (aliases Excel → clave canónica `snake_case`).
- Reglas SQL paralelas en migración para vistas (comentario de sincronía en código).
- Ejemplos: **Auto regular** → agregado `lob_group = auto taxi`; **Tuk Tuk** → `tuk tuk`; **Delivery** → tipos `express` + `mensajería`; **Carga** → tipo `cargo`; **PRO / YMA / YMM** → claves reservadas sin filas en reglas SQL → `NOT_MAPPED` / sin real hasta ampliar mapping.

## Endpoints que no deben modificarse (contrato / Omniview)

- `GET /ops/business-slice/omniview` y servicios de **Omniview Matrix** (`business_slice_omniview_service`, integridad matrix).
- `GET /ops/plan-vs-real/monthly` y vistas `ops.v_plan_vs_real_realkey_final` / `_canonical` (solo lectura desde nuevo endpoint).
- Rutas frontend existentes `/operacion/omniview-matrix`, `/operacion/omniview` sin cambiar comportamiento.

## Tablas/vistas existentes consultadas (solo lectura en diseño)

- `plan.plan_long_raw`, `staging.plan_projection_raw`, `ops.plan_trips_monthly`, `staging.plan_projection_realkey_raw`, `ops.v_plan_vs_real_realkey_final`.
- Real LOB: `ops.mv_real_trips_by_lob_month`, `ops.mv_real_lob_month_v2`, `canon.map_real_tipo_servicio_to_lob_group`, `ops.v_trips_real_canon`.
