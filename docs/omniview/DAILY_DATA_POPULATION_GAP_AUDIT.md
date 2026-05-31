# DAILY DATA POPULATION GAP AUDIT

**Fecha**: 2026-05-30
**Motor**: Control Foundation
**Gate**: H1-B Hotfix

---

## 1. Scope

Auditar por qué en Omniview Daily los días 25-28 de mayo aparecen sin datos reales mientras el día 29 aparece con cierre completo. Trazar la pipeline de datos desde source tables hasta la UI.

---

## 2. Pipeline End-to-End

### 2.1 Source → Enriched View

```
public.trips_2026 (UNION ALL) → ops.v_real_trips_enriched_base
public.trips_all (WHERE trip_date < '2026-01-01')
    + JOIN dim.dim_park (country, city, park)
    + JOIN public.drivers (works_terms)
    + DISTINCT ON (trip_id) with trips_2026 priority
```

**Archivo**: `backend/alembic/versions/126_business_slice_trips_unified_trust.py` (lines 169-252)

**Punto de fallo potencial #1**: Si `public.trips_2026` no contiene filas para May 25-28, el enriched view estará vacío para esos días. Esto es upstream — fuera del control del omniview refresh job.

### 2.2 Enriched View → Temp Table → Fact Table

```
v_real_trips_enriched_base
  → _materialize_enriched_for_month() [incremental_load.py:934]
    → CREATE TEMP TABLE _bs_enriched_month AS SELECT ... FROM enriched WHERE trip_date IN [mes]
  → load_business_slice_day_for_month() [incremental_load.py:1172]
    → DELETE FROM day_fact WHERE trip_date >= month_start AND trip_date <= month_end
    → Per chunk: INSERT INTO day_fact ... FROM _bs_enriched_month
```

**Archivos**:
- `backend/app/services/business_slice_incremental_load.py`

**Punto de fallo potencial #2**: Si `_materialize_enriched_for_month` devuelve `mat_rows == 0`, el loader sale temprano sin insertar nada. Pero si devuelve > 0, debería tener todos los días con datos.

**Punto de fallo potencial #3**: El DELETE borra TODO el mes. Si el INSERT solo repone algunos días (porque la temp table solo tiene ciertos días), los días sin source data quedan sin fila en day_fact.

### 2.3 Refresh Job Scheduling

```
APScheduler @ 04:00 UTC diario:
  run_business_slice_real_refresh_job()
    → months = [prev_month, current_month]
    → load_business_slice_day_for_month(cur, month, conn, keep_enriched=True)
    → load_business_slice_week_for_month(cur, month, conn)
    → (opcional) load_business_slice_month(cur, month, conn)
```

**Archivos**:
- `backend/app/services/business_slice_real_refresh_job.py`
- `backend/app/main.py` (lines 131-212)

**Punto de fallo potencial #4**: El refresh job puede fallar (error, timeout) sin completar. Si falla después de borrar pero antes de insertar, day_fact queda vacío para el mes entero.

**Punto de fallo potencial #5**: Si `OMNIVIEW_REAL_REFRESH_ENABLED = False` o el scheduler no se inicia, el job nunca corre. El único refresh sería manual.

### 2.4 Fact Table → Projection API

```
FACT_DAILY (ops.real_business_slice_day_fact)
  → _load_real_daily() [projection_expected_progress_service.py:2807]
    → SELECT trip_date, country, city, business_slice_name, trips_completed, ...
      FROM ops.real_business_slice_day_fact
      WHERE (NOT is_subfleet OR is_subfleet IS NULL)
        AND EXTRACT(YEAR FROM trip_date) = 2026
        AND EXTRACT(MONTH FROM trip_date) = 5
        AND {filtros de país, ciudad, tajada}
  → Merge con plan data
  → Return in API response as data[i].trips_completed, etc.
```

**Archivos**:
- `backend/app/services/projection_expected_progress_service.py`
- `backend/app/routers/ops.py` (endpoint `/ops/business-slice/omniview-projection`)

**Punto de fallo potencial #6**: El filtro `(NOT is_subfleet OR is_subfleet IS NULL)` excluye filas de subfleet. Si datos para 25-28 existen solo como subfleet, serían excluidos. (Poco probable — la granularidad de agregación incluye también filas fleet-level).

### 2.5 API → Frontend Matrix

```
GET /ops/business-slice/omniview-projection?grain=daily&year=2026&month=5&country=peru&city=lima...
  → buildProjectionMatrix(response.data, 'daily')
    → cell.projection.trips_completed.{actual, projected_expected, attainment_pct, signal}
  → computeProjectionDeltas(linePeriods, allPeriods)
    → delta.trips_completed.{value, isProjection, periodPop, week_state}
  → displayProjMatrix
  → Render in cells
```

**Archivos**:
- `frontend/src/components/omniview/projectionMatrixUtils.js`
- `frontend/src/components/BusinessSliceOmniviewMatrix.jsx`

**Punto de fallo potencial #7**: Si el backend retorna filas para 25-28 pero con `actual == 0` o `actual == null`, el frontend puede mostrarlas como "vacías". La función `fmtValue` muestra '—' para valores null/undefined.

---

## 3. Diagnóstico por Fecha (Expected vs Actual)

### Para Trips, Lima, Perú — Mayo 2026

| Fecha | Día | Source esperada | FACT_DAILY esperada | Proyección esperada |
|-------|-----|-----------------|---------------------|---------------------|
| 2026-05-24 | Dom | Viajes normales | Sí (refresh full month) | Real + Plan |
| 2026-05-25 | Lun | **¿Presente?** | **¿Presente?** | **Verificar** |
| 2026-05-26 | Mar | **¿Presente?** | **¿Presente?** | **Verificar** |
| 2026-05-27 | Mié | **¿Presente?** | **¿Presente?** | **Verificar** |
| 2026-05-28 | Jue | **¿Presente?** | **¿Presente?** | **Verificar** |
| 2026-05-29 | Vie | Viajes normales | Sí | Real + Plan |
| 2026-05-30 | Sáb | Parcial | Sí (refresh full month) | Real + Plan (parcial) |
| 2026-05-31 | Dom | Futuro | N/A | Solo Plan |

---

## 4. SQL de Diagnóstico

Para ejecutar en la base de datos y confirmar el gap:

### 4.1 Verificar fact diario para el rango

```sql
SELECT trip_date, country, city, business_slice_name,
       trips_completed, revenue_yego_net, active_drivers,
       refreshed_at, loaded_at
FROM ops.real_business_slice_day_fact
WHERE trip_date BETWEEN '2026-05-24' AND '2026-05-30'
  AND lower(trim(country)) = 'peru'
  AND lower(trim(city)) = 'lima'
ORDER BY trip_date, business_slice_name;
```

### 4.2 Verificar source trips para el rango

```sql
SELECT trip_date, count(*) as total_trips,
       count(DISTINCT driver_id) as drivers
FROM public.trips_2026
WHERE trip_date BETWEEN '2026-05-24' AND '2026-05-30'
GROUP BY trip_date
ORDER BY trip_date;
```

### 4.3 Verificar última ejecución del refresh job

```sql
SELECT MAX(refreshed_at), MAX(loaded_at)
FROM ops.real_business_slice_day_fact
WHERE trip_date >= '2026-05-01';
```

### 4.4 Verificar projection endpoint response

```bash
curl "http://localhost:8000/ops/business-slice/omniview-projection?plan_version=ruta27&grain=daily&country=peru&city=lima&year=2026&month=5" | jq '.data[] | select(.trip_date >= "2026-05-24") | {trip_date, trips_completed, trips_completed_projected_expected, trips_completed_attainment_pct, trips_completed_signal}'
```

---

## 5. Hipótesis de Root Cause (ordenadas por probabilidad)

### H1: Fuente upstream sin datos para 25-28 (ALTA)
- `public.trips_2026` no tiene filas para May 25-28
- El refresh job corrió normalmente (DELETE + INSERT full month)
- Solo 24, 29 aparecen porque son los únicos días con source data
- **Validación**: Ejecutar SQL 4.2

### H2: Refresh job no corrió completo (MEDIA)
- El job corrió pero falló a mitad (por timeout, lock, error)
- Solo ciertos días fueron re-insertados
- **Validación**: Ejecutar SQL 4.3, revisar logs de backend

### H3: Refresh job corrió con mes incorrecto (MEDIA)
- Si `today` se calcula mal, el job podría haber procesado un rango incorrecto
- Pero la lógica `[prev_month, current_month]` es sólida
- **Validación**: Revisar logs del APScheduler

### H4: Filtro en proyección excluye datos (BAJA)
- El filtro `NOT is_subfleet` podría excluir filas válidas
- Pero si los datos existen en day_fact como fleet-level, no debería importar
- **Validación**: Comparar SQL 4.1 con SQL 4.4

### H5: Frontend malinterpreta null como vacío (BAJA)
- Si el backend retorna `actual = 0`, el frontend podría mostrar '—'
- Pero el valor debería ser > 0 si hay viajes
- **Validación**: Inspeccionar network tab o console logs

---

## 6. Check de Código — ¿Hay algo en el código que pueda causar este gap?

| Nivel | Archivo | Hallazgo | ¿Puede causar gap? |
|-------|---------|----------|---------------------|
| Source | `trips_2026` table | Fuera del scope del código | **SÍ — upstream** |
| View | `v_real_trips_enriched_base` | UNION + DISTINCT ON, sin filtros de fecha extra | No |
| Loader | `incremental_load.py:1201` | DELETE full month, re-INSERT from temp | No (si source OK) |
| Loader | `incremental_load.py:934` | Materializa por mes calendario completo | No |
| Refresh | `real_refresh_job.py:113-116` | Procesa `[prev_month, current_month]` | No |
| Scheduler | `main.py:171-186` | Corre a las 04:00 diario | No (si está habilitado) |
| Backend API | `projection_expected_progress_service.py:2807` | `is_subfleet` filter | No (fleet-level rows unaffected) |
| Backend API | `projection_expected_progress_service.py:2823` | Month filter `EXTRACT(MONTH)` | No |
| Frontend | `projectionMatrixUtils.js:326` | `buildProjectionMatrix` itera todas las filas | No |
| Frontend | `projectionMatrixUtils.js:572` | `computeProjectionDeltas` procesa cada período | No |

**Conclusión del code audit**: El código no tiene bug que cause selectivamente omisión de días intermedios. El problema está en los datos fuente. La pipeline de refresh es sólida (DELETE + INSERT full month).

---

## 7. Veredicto

La causa más probable es **gap en la fuente upstream** (`public.trips_2026`) para los días 25-28 de mayo. El código de refresh (DELETE + INSERT full month) es correcto. El código de proyección (unión plan + real) es correcto.

**Acción requerida**: Ejecutar los SQL de diagnóstico (sección 4) en la base de datos de producción para confirmar la hipótesis.

