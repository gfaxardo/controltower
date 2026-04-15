# FASE 3.1 — Diagnóstico Funcional y Técnico: Omniview Projection Mode

## 1. Componentes UI que se reutilizan

| Componente | Ruta | Qué se reutiliza |
|---|---|---|
| `BusinessSliceOmniviewMatrix.jsx` | `frontend/src/components/` | Contenedor principal: filtros, grano, KPI focus, layout, estado. Se extiende con `viewMode` y `planVersion`. |
| `BusinessSliceOmniviewMatrixTable.jsx` | `frontend/src/components/` | Estructura de tabla: ciudades colapsables, líneas/tajadas, columnas por periodo. Se crea variante `ProjectionTable` con la misma estructura. |
| `BusinessSliceOmniviewMatrixHeader.jsx` | `frontend/src/components/` | Cabecera de periodos + KPI label. Se reutiliza directamente. |
| `BusinessSliceOmniviewMatrixCell.jsx` | `frontend/src/components/` | Referencia visual para la nueva celda de proyección. |
| `omniviewMatrixUtils.js` | `frontend/src/components/omniview/` | `MATRIX_KPIS`, `periodKey`, `periodLabel`, `PERIOD_STATES`, `fmtValue`, `sortLineEntries`. |
| `OmniviewFilterPrimitives.jsx` | `frontend/src/components/omniview/` | `FilterSelect`, `YearSelect`, `MonthSelect`. |
| `api.js` | `frontend/src/services/` | `getControlLoopPlanVersions()` ya existente para listar versiones de plan. |

## 2. Dónde agregar la subpestaña/modo sin romper Omniview

Se agrega un **modo interno** dentro de `BusinessSliceOmniviewMatrix.jsx` (no una ruta nueva):
- Estado `viewMode`: `'evolucion'` (default, comportamiento actual) | `'proyeccion'` (nuevo).
- Toggle visual en la barra de controles, junto al toggle Data/Insight existente.
- El modo Evolución no se modifica en absoluto.

NO se agrega nueva entrada en `OPERACION_SUBTABS` ni nueva ruta en `ROUTE_MAP`.

## 3. Fuentes reales para mensual/semanal/diario

| Grano | Fact table (real) | Uso |
|---|---|---|
| Mensual | `ops.real_business_slice_month_fact` | Real acumulado del mes |
| Semanal | `ops.real_business_slice_week_fact` | Real acumulado de la semana |
| Diario | `ops.real_business_slice_day_fact` | Real del día |

Curva estacional: `ops.real_business_slice_day_fact` (últimos 3 meses históricos).

## 4. Cómo se obtiene la proyección mensual vigente

- Vista: `ops.v_plan_projection_control_loop`
- Columnas: `plan_version`, `period_date`, `country`, `city`, `linea_negocio_canonica`, `linea_negocio_excel`, `projected_trips`, `projected_revenue`, `projected_active_drivers`
- Selección de versión: `getControlLoopPlanVersions()` → `SELECT DISTINCT plan_version FROM staging.control_loop_plan_metric_long ORDER BY plan_version DESC`
- Resolución a tajada: `control_loop_business_slice_resolve.py` (ya existente)

## 5. Cómo se deriva el plan esperado no lineal

Motor de curva estacional (`seasonality_curve_engine.py`):
1. Consulta `ops.real_business_slice_day_fact` para los últimos N meses (default 3).
2. Calcula distribución acumulada intra-mes por día (qué fracción del total mensual se acumula al día D).
3. Pondera meses históricos (más reciente = más peso: 0.5, 0.3, 0.2).
4. El `expected_ratio_to_date` resultante se multiplica por el plan mensual total.
5. Refleja estacionalidad por día de semana y semana del mes.

## 6. Fallback de curva permitido

| Nivel | Scope | Método | Confianza |
|---|---|---|---|
| 1 | Misma ciudad + misma tajada + mismo KPI | `city_slice_3m` | high |
| 2 | Misma ciudad, todas las tajadas | `city_all_3m` | medium |
| 3 | Mismo país, misma tajada | `country_slice_3m` | medium |
| 4 | Mismo país, todas las tajadas | `country_all_3m` | low |
| 5 | Lineal simple (día/días_mes) | `linear_fallback` | fallback |

Cada fila retorna `curve_method`, `fallback_level` y `curve_confidence` para trazabilidad.

## 7. Qué NO se toca

- Endpoints existentes: `/ops/business-slice/monthly`, `/weekly`, `/daily`, `/omniview`
- Servicios existentes: `business_slice_omniview_service.py`, `control_loop_plan_vs_real_service.py`
- Tablas/facts de base de datos: ninguna alteración DDL
- Migraciones Alembic: cero migraciones nuevas
- Lógica de tajadas/resolución: se reutiliza tal cual
- Componentes UI existentes: no se modifican destructivamente
- Rutas/tabs en `App.jsx`: no se agregan nuevas rutas

## Archivos creados (todos aditivos)

| Archivo | Propósito |
|---|---|
| `backend/app/services/seasonality_curve_engine.py` | Motor de curva estacional con fallback jerárquico |
| `backend/app/services/projection_expected_progress_service.py` | Servicio orquestador plan vs real con curva |
| `frontend/src/components/omniview/projectionMatrixUtils.js` | Utils de matriz para modo proyección |
| `frontend/src/components/BusinessSliceOmniviewProjectionCell.jsx` | Celda con semáforo y attainment |
| `frontend/src/components/BusinessSliceOmniviewProjectionTable.jsx` | Tabla de proyección reutilizando header/layout |

## Archivos modificados (aditivos, no destructivos)

| Archivo | Cambio |
|---|---|
| `backend/app/routers/ops.py` | Endpoint `GET /ops/business-slice/omniview-projection` |
| `frontend/src/services/api.js` | Función `getOmniviewProjection` |
| `frontend/src/components/BusinessSliceOmniviewMatrix.jsx` | viewMode, planVersion, bifurcación carga/render |
