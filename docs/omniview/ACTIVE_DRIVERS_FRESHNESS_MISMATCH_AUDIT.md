# Audit: Active Drivers Freshness Mismatch

## Fecha: 2026-05-29

## Hallazgos

### 1. Fuente del banner "Data al 2026-05-29"

- **Archivo**: `backend/app/services/business_slice_service.py` :: `compute_matrix_data_freshness()`
- **Query**: `SELECT MAX(trip_date) FROM ops.real_business_slice_day_fact WHERE ...`
- **Semántica**: MAX de trip_date en la day_fact — refleja disponibilidad de VIAJES, no de KPIs individuales.
- **Resultado**: Siempre devuelve la fecha más reciente con registros de viajes.

### 2. Fuente del Closed Period Engine

- **Archivo**: `frontend/src/utils/projectionClosedPeriodEngine.js` :: `resolveClosedPeriodAnchor()`
- **Input**: `projectionMeta?.data_freshness?.max_data_date` (la misma query global de trips)
- **Semántica ANTES del fix**: Usaba `max_data_date` global sin considerar el KPI seleccionado.
- Para grain=daily: anchor = `maxDataDate` directamente.
- Para grain=weekly: anchor = última semana con `weekState === 'closed'`.
- Para grain=monthly: anchor = último mes con `comparisonBasis === 'full_month'`.

### 3. Fuente de displayProjMatrix

- **Archivo**: `frontend/src/components/omniview/projectionMatrixUtils.js` :: `buildProjectionMatrix()`
- Construye la matriz pivoteando rows del backend. Para `active_drivers`:
  - En totals: se marca como `null` (línea 461-462) porque es semi-additive.
  - En per-line: conserva el valor real del backend.

### 4. Fuente específica de KPI `active_drivers`

- **Backend query**: `active_drivers AS real_active_drivers` desde:
  - `ops.real_business_slice_day_fact` (grain=daily)
  - `ops.real_business_slice_week_fact` (grain=weekly)
  - `ops.real_business_slice_month_fact` (grain=monthly)
- **Computación en day_fact**: `COUNT(DISTINCT driver_id) FILTER (WHERE completed_flag)` por día.
- **Computación en week_fact**: `SUM(COALESCE(d.active_drivers, 0))` — suma de daily distinct counts (NO es true weekly distinct; es un proxy).
- **Refresh**: `run_business_slice_real_refresh_job()` refresca day_fact + week_fact cada 15 min+ (cooldown).

### 5. Endpoint usado por Omniview Proyección

- **API**: `getOmniviewProjection()` → `POST /ops/business-slice/omniview-projection`
- **Backend**: `projection_expected_progress_service.py` :: `get_omniview_projection()`
- La data_freshness en la respuesta viene de `compute_matrix_data_freshness()` — siempre day_fact trips.

---

## Respuestas a las preguntas clave

| Pregunta | Respuesta |
|----------|-----------|
| Freshness global usa trips? | **SI**. `MAX(trip_date)` de `ops.real_business_slice_day_fact`. |
| active_drivers diario viene de otra tabla? | **NO**. Está en la misma day_fact como columna. Pero en weekly grain viene de week_fact (rollup de daily). |
| Hay datos reales para 26, 27, 28, 29 mayo? | **Para trips: SI** (day_fact tiene rows). **Para active_drivers: DEPENDE** del grain. En day_fact SI debería estar. En week_fact, la semana 2026-05-26 puede estar con datos parciales (solo Mon-Thu). |
| Hay plan pero no real? | No aplica — si day_fact tiene row, tiene active_drivers (es columna computada en el mismo INSERT). |
| Se está mostrando último cierre incorrecto? | **SI**. El banner dice "Data al 2026-05-29" para TODOS los KPIs, pero en weekly grain active_drivers del partial week es un proxy no confiable. El anchor del closed period engine usaba freshness global sin considerar la semántica semi-additive de active_drivers. |

---

## Causa Raíz

`compute_matrix_data_freshness()` es un singleton global basado en trips. No tiene granularidad por KPI. El closed period engine y el banner usaban esa fecha sin cualificar que active_drivers (semi-additive) tiene una fecha de cierre operativo DIFERENTE en weekly grain.

## Fix Aplicado

1. Backend: nueva función `compute_kpi_freshness()` que consulta per-KPI el `MAX(date)` donde `column > 0`.
2. Backend: incluido en respuesta de projection como `kpi_freshness`.
3. Frontend: `resolveClosedPeriodAnchor()` acepta `selectedKpi` y `kpiFreshness` para override.
4. Frontend: `ProjectionContextBar` muestra badge de warning cuando el KPI activo tiene freshness distinto al global.
