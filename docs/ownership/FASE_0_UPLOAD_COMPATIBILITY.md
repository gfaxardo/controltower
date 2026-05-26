# Fase 0.0 — Projection Upload Compatibility for Ownership Fields

**Fecha:** 2026-05-25
**Estado:** Implementado
**Siguiente fase recomendada:** Fase 0.1 — Ownership Engine Foundation

======================================================================
RESUMEN EJECUTIVO
======================================================================

Se validó y se hizo forward-compatible el pipeline de carga de proyección
para aceptar los nuevos campos: `Jefe Producto` y `estado` sin romper
ningún contrato existente.

La nueva plantilla versionada mantiene el contrato base y agrega 3 columnas:
- Jefe Producto (nombre del responsable)
- Producto (agrupación de producto)
- estado (validado sin cambios | validado con cambios | por validar)

======================================================================
DECISIÓN TOMADA
======================================================================

**OPCIÓN B — Persistencia controlada mínima en staging.**

Los campos ownership se persisten en `staging.control_loop_plan_metric_long`
como columnas TEXT nullable.

NO se persisten en `ops.plan_trips_monthly` (canónica).
NO se exponen en vistas de serving.
NO se incluyen en MVs ni Omniview.

Los parsers se hicieron forward-compatible:
- Columnas extra se aceptan sin error
- Se pasan como metadata raw a staging
- Uploads legacy siguen funcionando sin cambios

======================================================================
ESTRATEGIA DE PERSISTENCIA
======================================================================

Tabla: `staging.control_loop_plan_metric_long`
Nuevas columnas (todas nullable TEXT):
  - jefe_producto
  - producto
  - estado

Tabla canónica `ops.plan_trips_monthly`: **SIN cambios**.

Vistas `ops.v_plan_projection_control_loop`: **SIN cambios**.

======================================================================
FLUJOS AFECTADOS
======================================================================

### Flujo A: Control Loop CSV Upload (`/plan/upload_control_loop_projection`)

Archivo: `control_loop_projection_parser.py`
Cambios:
- `parse_control_loop_csv()`: metric ahora es opcional si se puede inferir
  del nombre del archivo (ej. "DRIVERS.csv" → active_drivers)
- `_extract_ownership_metadata()`: extrae Jefe Producto, Producto, estado
  de cada fila y los pasa como metadata
- `_dataframe_to_long()`: mismo tratamiento para hojas Excel

### Flujo B: Control Tower Multi-Sheet Template (`/plan/upload_ruta27_ui`)

Archivo: `plan_template_parser_service.py`
Cambios:
- `parse_control_tower_template()`: extrae columnas ownership de la hoja
  TRIPS antes del melt y las re-une después del merge
- Las columnas se incluyen en el dict de salida pero `ingest_control_tower_rows()`
  no las persiste en `ops.plan_trips_monthly` (solo usa columnas conocidas)

### Flujo C: Repo de staging

Archivo: `control_loop_plan_repo.py`
Cambios:
- `insert_valid_metric_rows()`: INSERT ahora incluye columnas
  jefe_producto, producto, estado (nullable)

### Flujo D: Upload Service

Archivo: `control_loop_upload_service.py`
Cambios:
- `run_control_loop_upload()`: pasa metadata ownership del parser al repo

======================================================================
COMPATIBILIDAD LEGACY
======================================================================

- Uploads sin columnas ownership funcionan sin cambios
- Columnas son nullable → no afectan UNIQUE constraints
- ON CONFLICT DO NOTHING mantiene append-only
- Plan versions anteriores intactas
- Omniview sin alterar
- Plan vs Real sin alterar
- WoW/MoM sin alterar

======================================================================
MIGRACIÓN ALEMBIC
======================================================================

Archivo: `alembic/versions/154_projection_ownership_compatibility.py`
down_revision: `153_yango_loyalty_operating_layer`

Aplica:
  ALTER TABLE staging.control_loop_plan_metric_long
    ADD COLUMN IF NOT EXISTS jefe_producto TEXT
    ADD COLUMN IF NOT EXISTS producto TEXT
    ADD COLUMN IF NOT EXISTS estado TEXT

======================================================================
CSV NUEVO
======================================================================

Archivo: `plantilla proyeccion Control Tower - DRIVERS.csv`

Columnas:
  country, city, linea_negocio, 2026-01...2026-12,
  Jefe Producto, Producto, estado

El CSV contiene solo métrica de active_drivers.
Usa el endpoint `/plan/upload_control_loop_projection`.

El parser auto-detecta la métrica desde el nombre del archivo
("DRIVERS" → active_drivers) si no hay columna `metric` explícita.

======================================================================
RIESGOS
======================================================================

1. **CSV sin columna metric ni nombre descriptivo**: fallará con error
   claro. El usuario debe renombrar el archivo o agregar columna metric.

2. **Columnas ownership con nombres distintos**: si cambian los nombres
   en futuras plantillas, habrá que actualizar `_OWNERSHIP_COLS_RAW`.

3. **Multi-sheet template**: las columnas ownership se extraen solo de
   la hoja TRIPS. Si solo aparecen en REVENUE o DRIVERS, se perderán.

======================================================================
SIGUIENTE FASE RECOMENDADA (0.1)
======================================================================

- Crear tabla `ops.projection_ownership` con FK a plan_version + LOB
- Implementar ownership engine (resolución de responsable por LOB)
- Agregar endpoint GET `/plan/ownership-summary`
- NO implementar todavía: scoreboard, rankings, gamificación, AI
