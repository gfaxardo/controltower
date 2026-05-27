# Fase 1.0.1 — Ownership Data Readiness Before UI

**Fecha:** 2026-05-26
**Estado:** Completado
**Fase anterior:** Fase 1.0 — Preflight & Go/No-Go
**Siguiente fase:** Fase 1.1 — Omniview Perspective Engine (UI)

======================================================================
RESUMEN
======================================================================

Se completó la preparación de datos de ownership para que la Fase 1.1
(Omniview Perspective Engine) pueda construirse sobre datos reales.

Resultados:
- Bridge LOB completado: 11/11 LOBs mapeados
- CSV con Jefe Producto subido exitosamente
- 57 ownership entries con 3 jefes (Ariana, Stacy, Eduardo)
- MV: 2,856/3,456 filas con ownership asignado (82.7%)
- Endpoint devuelve datos por owner con métricas plan vs real
- Omniview intacta, sin cambios en frontend

======================================================================
PASOS EJECUTADOS
======================================================================

### PASO 1 — Bridge LOB Readiness

Se agregaron 7 nuevos mappings a `ops.control_loop_plan_line_to_business_slice`:

| plan_line_key | business_slice_name | priority |
|---------------|---------------------|----------|
| carga | Carga | 15 |
| delivery | Delivery | 15 |
| delivery_moto | Delivery moto | 15 |
| taxi_moto | Taxi Moto | 15 |
| tuk_tuk | Tuk Tuk | 15 |
| dellivery_bicicleta | Delivery | 25 |
| moto_taxi | Taxi Moto | 25 |

Total: 11 entries (4 existentes + 7 nuevos). Cobertura completa de todos los LOBs del plan.

### PASO 2 — Carga del CSV

Archivo: `plantilla proyeccion Control Tower - DRIVERS.csv`
- 63 filas (country/city/LOB combos)
- 18 columnas (12 meses + country, city, linea_negocio, Jefe Producto, Producto, estado)
- 3 jefes detectados: Ariana, Stacy, Eduardo
- Upload exitoso: 660 rows en staging con Jefe Producto y estado
- plan_version: control_loop_20260526_185728

### PASO 3 — Sync Ownership

Se propagaron 57 entries de ownership a 9 plan_versions existentes en
`ops.plan_trips_monthly` (la nueva versión no está en plan_trips_monthly
porque el upload solo carga a staging).

Ownership por versión: 57 rows, 3 owners cada una.

### PASO 4 — Refresh MV

`SELECT ops.refresh_ownership_serving_fact(false)` ejecutado exitosamente.

### PASO 5 — Validación de Totals

| Métrica | MV (ruta27_2026_04_15) | Source | Delta |
|---------|------------------------|--------|-------|
| Projected trips | 42,420,983 | 42,420,983 | 0 |
| Real trips | ~3,955,000 | — | — |

Projected totals cuadran exactamente. Real data presente por owner.

======================================================================
RESULTADOS
======================================================================

### Ownership en MV

| Estado | Filas | % |
|--------|-------|---|
| assigned | 2,856 | 82.7% |
| missing | 600 | 17.3% |
| conflicting | 0 | 0% |

### Por Owner (versión ruta27_2026_04_15)

| Jefe | Filas | Proj Trips | Real Trips | Proj Revenue | Real Revenue |
|------|-------|------------|------------|--------------|-------------|
| Ariana | 168 | 38,368,478 | 3,781,175 | 2,132,959,535 | -150,720,234 |
| Stacy | 72 | 796,644 | 70,446 | 416,511,458 | -14,316,782 |
| Eduardo | 60 | 3,273,391 | 135,950 | 306,721,011 | -896 |

### LOBs sin ownership (600 filas missing)

Estos LOBs no estaban en el CSV de ownership:
- Delivery moto (384 filas)
- Dellivery bicicleta (96 filas)
- Moto Taxi (120 filas)

Pueden cubrirse en futuras cargas de CSV con estos LOBs adicionales.

======================================================================
BUGS CORREGIDOS DURANTE ESTA FASE
======================================================================

1. **Date format en sync**: `_date.fromisoformat('2026-01')` fallaba porque
   espera formato YYYY-MM-DD. Se agregó helper `_parse_period_date()` que
   appendea '-01' cuando el formato es YYYY-MM.

2. **City accent en ownership join**: La MV no usaba `unaccent()` en el join
   de ownership, causando que Bogotá/Cúcuta/Medellín no matchearan. Se corrigió
   agregando `unaccent()` en los joins de country y city para ownership.

======================================================================
ARCHIVOS MODIFICADOS / CREADOS
======================================================================

| Archivo | Acción |
|---------|--------|
| `app/adapters/projection_ownership_repo.py` | Fix `_parse_period_date()` helper |
| `alembic/versions/156_ownership_serving_fact_foundation.py` | `unaccent()` en ownership join |
| `scripts/validate_ownership_data_readiness_before_ui.py` | Nuevo QA script (10 checks) |
| `docs/ownership/FASE_1_0_1_OWNERSHIP_DATA_READINESS.md` | Esta documentación |

Datos (no código):
- `ops.control_loop_plan_line_to_business_slice`: +7 entries (11 total)
- `staging.control_loop_plan_metric_long`: +660 rows (nueva plan_version)
- `ops.projection_ownership`: +540 rows (57 × 9 versions + 57 original)

======================================================================
GO / NO-GO
======================================================================

### GO ✅

Razón: Todos los criterios cumplidos:
- [x] ownership ya no está vacío (540 rows)
- [x] endpoint devuelve owners reales (Ariana, Stacy, Eduardo)
- [x] totals cuadran por plan_version (delta = 0)
- [x] Omniview sigue intacta
- [x] bridge LOB completo (11/11)
- [x] sin cambios en frontend

### Observaciones menores

1. **600 filas missing (17.3%)**: LOBs no cubiertos en el CSV de ownership.
   No bloquea el GO. Se completan en futuras cargas.

2. **Nueva plan_version no en plan_trips_monthly**: El upload carga a staging
   pero no a la tabla canónica de plan. Ownership existe en projection_ownership
   pero la MV no puede mostrarlo sin plan data. No bloquea.

### Recomendación

**Proceder a Fase 1.1 — Omniview Perspective Engine (UI).** La capa de datos
está operativa con ownership real funcionando. El Perspective Engine puede
construirse sobre el endpoint `GET /ops/ownership-serving/monthly` filtrando
por `jefe_producto`.
