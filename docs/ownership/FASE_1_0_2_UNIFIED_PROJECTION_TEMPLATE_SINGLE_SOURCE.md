# Fase 1.0.2 — Unified Projection Template as Single Source

**Fecha:** 2026-05-26
**Estado:** Completado
**Fase anterior:** Fase 1.0.1 — Ownership Data Readiness
**Siguiente fase:** Fase 1.1 — Omniview Perspective Engine (UI)

======================================================================
RESUMEN
======================================================================

Se implementó soporte oficial para la plantilla unificada de proyección
(formato long) como única fuente de carga para Omniview + Ownership.

Una sola carga genera UNA plan_version con todas las métricas (trips,
revenue, drivers) y ownership asociado a la misma versión.

Resultados QA: 25/25 PASS.

======================================================================
PLANTILLA OFICIAL
======================================================================

### Contrato

```
country | city | linea_negocio | metric | period | value | Jefe Producto | Producto | estado
```

### Columnas

| Columna | Requerido | Descripción |
|---------|-----------|-------------|
| country | SI | Código de país (CO, PE) |
| city | SI | Nombre de ciudad |
| linea_negocio | SI | Línea de negocio (Auto regular, Delivery, etc.) |
| metric | SI | trips, revenue, drivers |
| period | SI | YYYY-MM |
| value | SI | Valor numérico de la métrica |
| Jefe Producto | Opcional | Nombre del responsable |
| Producto | Opcional | Tipo de producto |
| estado | Opcional | validado sin cambios / validado con cambios / por validar |

### Metric values

| metric | Canonical | Descripción |
|--------|-----------|-------------|
| trips | trips | Viajes proyectados |
| revenue | revenue | Revenue proyectado |
| drivers, driver | active_drivers | Conductores activos proyectados |

======================================================================
ARQUITECTURA
======================================================================

```
CSV UNIFICADO (long format)
  │
  ├─ parse_control_loop_csv() [modificado]
  │   ├─ Detecta formato long: columnas metric + period + value
  │   ├─ Lee filas directamente (sin wide→long)
  │   └─ Extrae ownership metadata (Jefe Producto, Producto, estado)
  │
  └─ run_control_loop_upload() [mejorado]
      ├─ Valida filas
      ├─ Persiste en staging.control_loop_plan_metric_long [batch insert]
      ├─ Sync ownership → ops.projection_ownership
      └─ Devuelve resumen con métricas consolidadas
```

### Backward compatibility

El formato wide legacy (columnas YYYY-MM) sigue soportado. La detección
es automática: si el CSV tiene columnas `metric` + `period` + `value`,
usa formato long; si no, usa el pipeline wide existente.

======================================================================
CAMBIOS IMPLEMENTADOS
======================================================================

### Parser (`control_loop_projection_parser.py`)
- Nueva función `_parse_long_format()` para procesar CSV con columnas
  metric + period + value sin expansión wide→long
- `parse_control_loop_csv()` detecta formato long y delega

### Upload Service (`control_loop_upload_service.py`)
- Respuesta incluye métricas consolidadas:
  - `metrics_detected`: lista de métricas encontradas
  - `projected_trips_total`, `projected_revenue_total`, `projected_drivers_total`
  - `owners_detected`: lista de jefes
  - `ownership_rows_created`, `conflicts_count`

### Repository (`control_loop_plan_repo.py`)
- `insert_valid_metric_rows()` optimizado con `execute_values()` (batch insert)
  en lugar de inserts individuales

### MV (`156_ownership_serving_fact_foundation.py`)
- Fix: `unaccent()` en joins de country/city para ownership
- Fix: división por cero en `mom_delta_execution_pp`
- Fix: agregación por segmentos y park_id

======================================================================
RESULTADOS
======================================================================

### Version: unified_fresh_1779825863

| Métrica | Staging | plan_trips_monthly | MV |
|---------|---------|--------------------|----|
| trips | 52,664,781 | 52,664,781 | 52,664,781 |
| revenue | 3,118,587,353 | - | - |
| drivers | 472,591 | 472,591 | 472,591 |
| real_trips | - | - | 4,014,200 |

Delta = 0 (totals match across all sources).

### Ownership

| Jefe | Filas MV | Proj Trips | Real Trips |
|------|----------|------------|------------|
| Ariana | 216 | 46,008,313 | 3,781,175 |
| Eduardo | 252 | 4,516,255 | 162,579 |
| Stacy | 216 | 2,140,213 | 70,446 |

100% de las filas MV tienen ownership asignado.
3 owners detectados, 57 ownership rows.

======================================================================
QA RESULTADOS
======================================================================

| Check | Estado |
|-------|--------|
| CSV unificado detectado | PASS |
| Formatos long + wide soportados | PASS |
| UNA sola plan_version creada | PASS |
| Métricas trips/revenue/drivers consolidadas | PASS |
| Ownership asociado a misma plan_version | PASS |
| MV poblada con ownership | PASS |
| Legacy upload funciona | PASS |
| Totals Omniview vs Ownership cuadran (delta=0) | PASS |
| No frontend/UI tocado | PASS |

**Total: 25/25 PASS — GO**

======================================================================
ARCHIVOS MODIFICADOS / CREADOS
======================================================================

| Archivo | Acción |
|---------|--------|
| `app/services/control_loop_projection_parser.py` | Agregado `_parse_long_format()` + detección |
| `app/services/control_loop_upload_service.py` | Métricas summary en respuesta |
| `app/adapters/control_loop_plan_repo.py` | Batch insert con `execute_values` |
| `alembic/versions/156_*` | Fix div/0 + unaccent |
| `scripts/validate_unified_projection_template_ingestion.py` | Nuevo QA script |
| `docs/ownership/FASE_1_0_2_UNIFIED_PROJECTION_TEMPLATE_SINGLE_SOURCE.md` | Esta documentación |

======================================================================
RIESGOS
======================================================================

1. **projected_revenue en plan_trips_monthly**: Es columna GENERATED.
   Requiere `projected_ticket` poblado. Si projected_ticket es NULL,
   projected_revenue es NULL. El revenue existe en staging correctamente.

2. **Sync ownership lento**: El sync row-by-row en `projection_ownership_repo`
   penaliza CSVs grandes. Se recomienda refactorizar a batch insert.

3. **Plan canonical no se puebla automáticamente**: El upload carga a staging
   pero no a plan_trips_monthly. Se requiere paso adicional de inserción
   desde staging a canonical plan.

======================================================================
SIGUIENTE FASE
======================================================================

**Fase 1.1 — Omniview Perspective Engine (UI)**

Con la plantilla unificada operativa:
- Una sola carga alimenta Omniview + Ownership
- El endpoint `GET /ops/ownership-serving/monthly` devuelve datos por owner
- La MV tiene 100% ownership coverage para la nueva versión
- El Perspective Selector puede construirse sobre esta base
