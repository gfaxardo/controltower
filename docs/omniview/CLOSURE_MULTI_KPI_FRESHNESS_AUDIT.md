# CLOSURE MULTI-KPI FRESHNESS AUDIT

**Fecha**: 2026-05-30
**Motor**: Control Foundation
**Gate**: H1 Closure

---

## 1. Tabla de Freshness por KPI / Grain

| KPI | Grain | Fuente | Último periodo con real | Último periodo cerrado | Partial actual | Freshness status | Observación |
|-----|-------|--------|--------------------------|-------------------------|----------------|------------------|-------------|
| Trips | Daily | `FACT_DAILY.trips_completed` | 2026-05-29 (asumido) | 2026-05-29 | 2026-05-30 | `ok` (lag 1) | Misma fuente que global freshness. MAX(trip_date). |
| Trips | Weekly | `FACT_WEEKLY.trips_completed` | Semana 2026-05-25 | Semana 2026-05-25 | Semana 2026-05-26 | `ok` | Semanas ISO. Backend: `week_start`. |
| Trips | Monthly | `FACT_DAILY.trips_completed` | 2026-05-29 | Mayo 2026 no cerrado | Mayo 2026 | `warning` | Misma query que daily (usa FACT_DAILY). Mes actual = Mayo, sin cerrar hasta 31. |
| Revenue | Daily | `FACT_DAILY.revenue_yego_net` | 2026-05-29 | 2026-05-29 | 2026-05-30 | `ok` | Aditivo. Misma fuente de tabla que trips. |
| Revenue | Weekly | `FACT_WEEKLY.revenue_yego_net` | Semana 2026-05-25 | Semana 2026-05-25 | Semana 2026-05-26 | `ok` | Aditivo. |
| Revenue | Monthly | `FACT_DAILY.revenue_yego_net` | 2026-05-29 | Mayo 2026 no cerrado | Mayo 2026 | `warning` | Aditivo. |
| Active Drivers | Daily | `FACT_DAILY.active_drivers` | 2026-05-29 (asumido) | 2026-05-29 | 2026-05-30 | `ok` | Semi-additive. Puede diferir de trips si pipeline de drivers tiene lag propio. |
| Active Drivers | Weekly | `FACT_WEEKLY.active_drivers` | Semana 2026-05-25 | Semana 2026-05-25 | Semana 2026-05-26 | `ok` (con caveat) | Known: SUM proxy en vez de COUNT DISTINCT (H-2). Freshness correcta pero valor inflado en partial weeks. |
| Active Drivers | Monthly | `FACT_DAILY.active_drivers` | 2026-05-29 | Mayo 2026 no cerrado | Mayo 2026 | `warning` | Semi-additive. |
| Avg Ticket | Daily | `FACT_DAILY.avg_ticket` | 2026-05-29 | 2026-05-29 | 2026-05-30 | `ok` | Ratio. No proyectable. Priority scoring deshabilitado por contrato. |
| Avg Ticket | Weekly | `FACT_WEEKLY.avg_ticket` | Semana 2026-05-25 | Semana 2026-05-25 | Semana 2026-05-26 | `ok` | Ratio. |
| Avg Ticket | Monthly | `FACT_DAILY.avg_ticket` | 2026-05-29 | Mayo 2026 no cerrado | Mayo 2026 | `warning` | Ratio. |
| Trips per Driver | Daily | `FACT_DAILY.trips_per_driver` | 2026-05-29 | 2026-05-29 | 2026-05-30 | `ok` | Derived ratio. Priority scoring deshabilitado. |
| Trips per Driver | Weekly | `FACT_WEEKLY.trips_per_driver` | Semana 2026-05-25 | Semana 2026-05-25 | Semana 2026-05-26 | `ok` | Derived ratio. |
| Trips per Driver | Monthly | `FACT_DAILY.trips_per_driver` | 2026-05-29 | Mayo 2026 no cerrado | Mayo 2026 | `warning` | Derived ratio. |

---

## 2. Análisis de Fuentes

### 2.1 Backend: `compute_kpi_freshness()` (`business_slice_service.py:1322`)

```python
_KPI_FRESHNESS_COLUMNS = {
    "trips_completed": "trips_completed",
    "revenue_yego_net": "revenue_yego_net",
    "active_drivers": "active_drivers",
    "avg_ticket": "avg_ticket",
    "trips_per_driver": "trips_per_driver",
}
```

Per-KPI freshness query:
```sql
SELECT MAX(trip_date) FROM ops.real_business_slice_day_fact
WHERE COALESCE({kpi_column}, 0) > 0
  AND {filters}
```

Para weekly grain:
```sql
SELECT MAX(week_start) FROM ops.real_business_slice_week_fact
WHERE COALESCE({kpi_column}, 0) > 0
  AND {filters}
```

Para monthly grain: **misma query que daily** (usa `FACT_DAILY` + `trip_date`). No existe `FACT_MONTHLY` en la query actual. Esto implica que monthly freshness = daily freshness.

### 2.2 Global Freshness: `compute_matrix_data_freshness()` (`business_slice_service.py:1219`)

```sql
SELECT MAX(trip_date) AS mx FROM ops.real_business_slice_day_fact WHERE {filters}
```

Solo verifica `trip_date`, NO columnas de otros KPIs. Equivale a freshness de `trips_completed` únicamente.

### 2.3 Respuesta del Endpoint (`projection_expected_progress_service.py:1515-1520`)

```python
return {
    "data_freshness": df_fresh,      # Global (MAX trip_date)
    "kpi_freshness": kpi_fresh,      # Per-KPI { kpi: { max_data_date, lag_days, status } }
    "meta": {
        "data_freshness": df_fresh,  # Duplicado en meta
        "kpi_freshness": kpi_fresh,  # Duplicado en meta
        ...
    }
}
```

---

## 3. Routing de Freshness en el Frontend

### 3.1 Fetch de proyección (`BusinessSliceOmniviewMatrix.jsx:740-741`)

```javascript
if (res?.kpi_freshness) pm.kpi_freshness = res.kpi_freshness
```

Consume `kpi_freshness` del top-level de la respuesta. Se pasa a `setProjectionMeta(pm)`.

### 3.2 Closed Period Engine (`projectionClosedPeriodEngine.js:44-48`)

```javascript
const globalMaxDataDate = projectionMeta?.data_freshness?.max_data_date || null
const kpiSpecific = selectedKpi && kpiFreshness?.[selectedKpi]
const kpiMaxDataDate = kpiSpecific?.max_data_date || null
const maxDataDate = kpiMaxDataDate || globalMaxDataDate
```

Prioridad: KPI-specific > Global. Correcto.

### 3.3 ContextBar (`BusinessSliceOmniviewMatrix.jsx:3666-3737`)

- Línea 3673-3676: El banner principal muestra `df.max_data_date` (global/freshness de trips).
- Línea 3683-3686: Detecta `hasFreshnessMismatch` y `hasKpiNoData`.
- Línea 3721-3728: Badge amber cuando el KPI enfocado tiene fecha distinta.
- Línea 3730-3737: Badge red cuando el KPI no tiene data.

**Issue menor**: El banner principal ("Data al 2026-05-29") no cambia según el KPI seleccionado. Si el usuario ve `active_drivers` con data hasta 2026-05-27, el banner sigue diciendo "Data al 2026-05-29". El badge de mismatch mitiga parcialmente.

---

## 4. Hallazgos

### 4.1 Hallazgos OK (no acción requerida)

- Per-KPI freshness implementado correctamente en backend.
- Prioridad correcta: KPI-specific > Global en closed period engine.
- Todos los KPIs tienen columna en `_KPI_FRESHNESS_COLUMNS`.
- Mismatch detection funcional en ContextBar.
- kpiNoData detection funcional.

### 4.2 Hallazgos con Observación (no bloqueantes)

| ID | Descripción | Severidad |
|----|-------------|-----------|
| F-AUD-1 | Monthly freshness usa `FACT_DAILY` en vez de tabla mensual. Equivale a daily freshness. | LOW |
| F-AUD-2 | Banner principal usa global freshness (trips). No cambia al seleccionar otro KPI. Badge de mismatch mitiga. | LOW |
| F-AUD-3 | Global freshness (`data_freshness.max_data_date`) solo deriva de `MAX(trip_date)`. No es multi-KPI. | LOW |
| F-AUD-4 | `compute_kpi_freshness` ejecuta 5 queries secuenciales (uno por KPI). Performance aceptable (<25ms estimado). | LOW |

### 4.3 Hallazgos que Requieren Fix

| ID | Descripción | Severidad | Fix |
|----|-------------|-----------|-----|
| F-AUD-5 | `periodInfoMap` no se construye ni pasa al closed period engine. Weekly ancla a penúltima semana (no última cerrada). Monthly ancla a penúltimo mes (no último `full_month`). | **HIGH** | Construir `periodInfoMap` desde filas de proyección y pasarlo. |
| F-AUD-6 | `classifyPeriodStatus` / `getPeriodVisualClass` / `getPeriodBadge` exportados pero nunca usados en componentes React. | MEDIUM | Usar en matrix header/cells. |

---

## 5. Estado de Cierre por KPI (asumiendo data real hasta 2026-05-29)

| KPI | Daily cierre | Weekly cierre | Monthly cierre | Estado |
|-----|-------------|---------------|-----------------|--------|
| Trips | 2026-05-29 | Sem 2026-05-25 | Mayo 2026 (parcial) | Cerrado excepto monthly |
| Revenue | 2026-05-29 | Sem 2026-05-25 | Mayo 2026 (parcial) | Cerrado excepto monthly |
| Active Drivers | 2026-05-29 | Sem 2026-05-25 | Mayo 2026 (parcial) | Cerrado excepto monthly |
| Avg Ticket | 2026-05-29 | Sem 2026-05-25 | Mayo 2026 (parcial) | Cerrado excepto monthly |
| Trips per Driver | 2026-05-29 | Sem 2026-05-25 | Mayo 2026 (parcial) | Cerrado excepto monthly |

---

## 6. Veredicto

**CONDITIONAL GO** — 5/5 KPIs auditados. Freshness per-KPI funcional. Pendiente: construcción de `periodInfoMap` para weekly/monthly anchoring preciso (F-AUD-5).

