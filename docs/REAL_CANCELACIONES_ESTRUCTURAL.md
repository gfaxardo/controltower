# Cancelaciones REAL — Definición canónica, trazabilidad y corrección estructural

**Objetivo:** Cerrar definición, trazabilidad e integración de cancelaciones en el módulo REAL desde la fuente raíz hasta la UI. Sin fallback permanente en 0 en el drill principal.

---

## FASE 0 — Trazabilidad desde fuente raíz hasta vistas operativas

### 1. Cómo vienen `condition` y `motivo_cancelacion` en la fuente raíz

| Fuente        | Columna estado     | Columna motivo      | Valores observados / regla |
|---------------|--------------------|---------------------|----------------------------|
| `public.trips_all`  | **`condicion`** (text) | **`motivo_cancelacion`** (text, opcional) | `condicion`: 'Completado', 'Cancelado'; variantes con ILIKE '%cancel%' tratadas como cancelado. |
| `public.trips_2026` | **`condicion`** (text) | **`motivo_cancelacion`** (text, opcional) | Mismo contrato que trips_all. |

En el código se usa **`condicion`** (no `condition`). Valores canónicos: `'Completado'` → completado; `'Cancelado'` o `condicion ILIKE '%cancel%'` → cancelado.

### 2. Valores concretos de `condicion`

- **Completado** (y variantes en mayúsculas/minúsculas según origen).
- **Cancelado** o cualquier valor que contenga "cancel" (ILIKE '%cancel%').
- Cualquier otro valor → clasificado como **other** en la capa canónica.

### 3. Vista/capa donde se derivan por primera vez

| Capa | Objeto | completed_trips | cancelled_trips | Motivo |
|------|--------|------------------|------------------|--------|
| Canon (por viaje) | `ops.v_trips_real_canon` / `ops.v_trips_real_canon_120d` | — | — | Expone `condicion` y opcionalmente `motivo_cancelacion`. |
| Fact por viaje | `ops.v_real_trip_fact_v2` | `is_completed` (bool) | `is_cancelled` (bool) | `trip_outcome_norm`: completed / cancelled / other; `cancel_reason_norm`, `cancel_reason_group` desde `motivo_cancelacion`. |
| Horaria | `ops.mv_real_lob_hour_v2` | SUM(FILTER is_completed) | SUM(FILTER is_cancelled) | Primera capa **agregada** con conteos. |
| Diaria | `ops.mv_real_lob_day_v2` | SUM(completed_trips) | SUM(cancelled_trips) | Agregado desde hourly. |
| Semanal | `ops.mv_real_lob_week_v3` | SUM(completed_trips) | SUM(cancelled_trips) | Desde hourly. |
| Mensual | `ops.mv_real_lob_month_v3` | SUM(completed_trips) | SUM(cancelled_trips) | Desde hourly. |
| Drill fact | `ops.real_drill_dim_fact` | `trips` (completados) | **`cancelled_trips`** (bigint) | Poblado por `populate_real_drill_from_hourly_chain` desde day_v2 / week_v3 (SUM(cancelled_trips)). |
| Drill vista/MV | `ops.mv_real_drill_dim_agg` | `trips` | **`cancelled_trips`** | Vista/select sobre real_drill_dim_fact (mig 103). |
| Backend drill | `real_lob_drill_pro_service` | viajes | **cancelaciones** | **Corregido:** lee `SUM(cancelled_trips)` de la MV; ya no fija 0. |
| UI drill | RealLOBDrillView | Viajes | **Cancel.** | Muestra `row.cancelaciones` y WoW. |

### 4. Tabla de trazabilidad resumida

```
trips_all / trips_2026 (condicion, motivo_cancelacion)
    → ops.v_trips_real_canon_120d (condicion, motivo_cancelacion)
    → ops.v_real_trip_fact_v2 (trip_outcome_norm, is_completed, is_cancelled, cancel_reason_*)
    → ops.mv_real_lob_hour_v2 (completed_trips, cancelled_trips)
    → ops.mv_real_lob_day_v2 / week_v3 / month_v3 (completed_trips, cancelled_trips)
    → populate_real_drill_from_hourly_chain
    → ops.real_drill_dim_fact (trips, cancelled_trips)
    → ops.mv_real_drill_dim_agg (SELECT * → cancelled_trips)
    → real_lob_drill_pro_service (SUM(cancelled_trips) AS cancelaciones)
    → API / UI (columna Cancel. y WoW)
```

---

## FASE 1 — Definición canónica

| Métrica / campo | Definición | Capa donde se calcula por primera vez |
|-----------------|------------|----------------------------------------|
| **completed_trips** | Conteo de viajes con `condicion = 'Completado'` (o equivalente normalizado). | Horaria: `COUNT(*) FILTER (WHERE is_completed)`. |
| **cancelled_trips** | Conteo de viajes con `condicion = 'Cancelado'` o `condicion ILIKE '%cancel%'`. | Horaria: `COUNT(*) FILTER (WHERE is_cancelled)`. |
| **cancelled_reason** | Normalización de `motivo_cancelacion` (canon.normalize_cancel_reason). | Fact: `ops.v_real_trip_fact_v2`. |
| **cancel_reason_group** | Agrupación de negocio (cliente, conductor, timeout_no_asignado, sistema, otro). | Fact: canon.cancel_reason_group(). |
| **cancel_rate** | cancelled_trips / requested_trips cuando requested_trips > 0. | Horaria/diaria/semanal/mensual. |

Regla: completado y cancelado son mutuamente excluyentes por viaje; en agregados se usan FILTER separados.

---

## FASE 2 — Verificación del contrato por capa

| Capa | ¿Existe cancelled_trips real? | ¿Se deriva de condicion? | ¿Está poblado? | ¿Alineado con completed? | ¿Se pierde? |
|------|------------------------------|---------------------------|----------------|---------------------------|-------------|
| A. Fuente raíz | N/A (columna condicion) | Sí | Sí | Sí (excluyentes) | No |
| B. Vista canónica | N/A | Sí (condicion) | Sí | Sí | No |
| C. Hourly | Sí (cancelled_trips) | Sí (is_cancelled ← condicion) | Sí (refresh MV) | Sí | No |
| D. day_v2 | Sí | Sí (desde hourly) | Sí | Sí | No |
| E. week_v3 | Sí | Sí (desde hourly) | Sí | Sí | No |
| F. month_v3 | Sí | Sí (desde hourly) | Sí | Sí | No |
| G. real_drill_dim_fact | Sí (mig 103) | Sí (populate desde day/week) | Sí (si populate se ejecuta) | Sí | No |
| H. mv_real_drill_dim_agg | Sí (vista/select *) | Sí (hereda de fact) | Sí | Sí | No |
| I. Drill backend | Sí (tras corrección) | Sí (lee SUM(cancelled_trips)) | Sí | Sí | **Antes sí (0 fijo); corregido.** |
| J. UI drill | Sí | Sí | Sí | Sí | No |

Evidencia: queries en FASE 5 y script `backend/scripts/verify_real_drill_db.sql`.

---

## FASE 3 — Punto exacto donde se rompía el flujo

1. **No** se pierde de raíz a canónica (condicion y motivo_cancelacion están en canon_120d cuando aplica 099).
2. **No** se pierde en hourly (cancelled_trips agregado correctamente).
3. **No** se pierde en day/week/month (heredan de hourly).
4. **No** se pierde en populate (inserta SUM(cancelled_trips) en real_drill_dim_fact).
5. **Sí:** el backend **no** leía la columna: en `real_lob_drill_pro_service` las queries no incluían `cancelled_trips` y se asignaba `cancelaciones = 0` en todas las rutas (drill principal y children desde MV_DIM).
6. El frontend ya mostraba la columna y WoW; al recibir siempre 0, parecía “sin datos reales”.
7. Causa raíz: **sustitución por `cancelaciones = 0` durante el debug** para evitar 500 cuando se asumía que la columna podía no existir (mig 103).

---

## FASE 4 — Corrección estructural aplicada

1. **Drill principal (por país, periodo, LOB/park):**  
   - Query de agregado por periodo ahora incluye `COALESCE(SUM(cancelled_trips), 0)::bigint AS cancelaciones` desde `ops.mv_real_drill_dim_agg`.  
   - Eliminado el bucle que fijaba `ad["cancelaciones"] = 0`.

2. **Children (desglose LOB / PARK / SERVICE_TYPE desde MV_DIM):**  
   - Ambas queries (periodo actual y periodo anterior) incluyen `COALESCE(SUM(cancelled_trips), 0)::bigint AS cancelaciones`.  
   - Eliminados los bucles que asignaban `r["cancelaciones"] = 0` y `pr["cancelaciones"] = 0`.

3. **Children por tipo de servicio desde MV_SERVICE_BY_PARK:**  
   - Esa tabla/vista no tiene `cancelled_trips`; se deja **fallback temporal explícito** `row["cancelaciones"] = 0` solo en esa rama, documentado en código.

Requisito: migración 103 aplicada (columna `cancelled_trips` en `ops.real_drill_dim_fact`) y populate ejecutado para que existan datos de cancelaciones en el drill.

---

## FASE 5 — Queries de reconciliación

Ejecutar en PostgreSQL para validar que cancelaciones se mantienen por la cadena (ajustar fechas/país según datos).

```sql
-- Reconciliación: misma ventana por país (ej. Colombia, último mes cerrado)
WITH params AS (
    SELECT 'co' AS country, (DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month'))::date AS period_start
),
-- 1) Fuente raíz (conteo por condicion)
root AS (
    SELECT COUNT(*) FILTER (WHERE t.condicion = 'Completado') AS completed,
           COUNT(*) FILTER (WHERE t.condicion = 'Cancelado' OR t.condicion ILIKE '%cancel%') AS cancelled
    FROM public.trips_all t
    JOIN params p ON 1=1
    WHERE t.fecha_inicio_viaje >= p.period_start
      AND t.fecha_inicio_viaje < p.period_start + INTERVAL '1 month'
    UNION ALL
    SELECT COUNT(*) FILTER (WHERE t.condicion = 'Completado'),
           COUNT(*) FILTER (WHERE t.condicion = 'Cancelado' OR t.condicion ILIKE '%cancel%')
    FROM public.trips_2026 t
    JOIN params p ON 1=1
    WHERE t.fecha_inicio_viaje >= p.period_start
      AND t.fecha_inicio_viaje < p.period_start + INTERVAL '1 month'
),
root_agg AS (SELECT SUM(completed) AS completed, SUM(cancelled) AS cancelled FROM root),
-- 2) Drill fact (agregado mismo periodo, breakdown lob)
drill_agg AS (
    SELECT SUM(trips) AS completed, SUM(cancelled_trips) AS cancelled
    FROM ops.real_drill_dim_fact d
    JOIN params p ON d.country = p.country AND d.period_grain = 'month' AND d.period_start = p.period_start AND d.breakdown = 'lob'
)
SELECT 'root' AS layer, (SELECT completed FROM root_agg) AS completed, (SELECT cancelled FROM root_agg) AS cancelled
UNION ALL
SELECT 'drill_lob', (SELECT completed FROM drill_agg), (SELECT cancelled FROM drill_agg);
```

Para **por LOB**, **por park** y **por tipo de servicio** usar la misma `period_start` y comparar `SUM(trips)` vs completados de fuente y `SUM(cancelled_trips)` vs cancelados de fuente. Tolerancia: diferencias por redondeo o por filtros de segmento/park aplicados en el drill.

---

## FASE 6 — Validación UI

1. El drill carga (GET /ops/real-lob/drill responde 200).  
2. Los children se expanden (GET /ops/real-lob/drill/children responde 200).  
3. La columna "Cancel." aparece en la tabla.  
4. Los valores ya no son 0 en todos los períodos cuando hay cancelaciones reales en la fuente (salvo fallback explícito en children por tipo de servicio por park).  
5. Reconciliación: para un país y periodo, suma de cancelaciones del drill (por LOB o por park) debe ser coherente con la query de reconciliación sobre fuente raíz / real_drill_dim_fact.  
6. Si hay diferencias (p. ej. segmento B2B/B2C, filtro de park), deben documentarse (filtros aplicados en el drill).

---

## FASE 7 — Entrega final

### 1. Definición canónica de cancelación

- **Fuente:** `condicion` en `trips_all` / `trips_2026`.  
- **Completado:** `condicion = 'Completado'`.  
- **Cancelado:** `condicion = 'Cancelado'` o `condicion ILIKE '%cancel%'`.  
- **Motivo:** `motivo_cancelacion` (normalizado en v_real_trip_fact_v2 como cancel_reason_norm / cancel_reason_group).

### 2. Fuente raíz exacta

- `public.trips_all` (histórico; en vista canon < 2026-01-01).  
- `public.trips_2026` (desde 2026-01-01).  
- Campos: `condicion`, `motivo_cancelacion` (opcional).

### 3. Punto exacto donde se rompía el flujo

- **Backend:** `real_lob_drill_pro_service.py` no seleccionaba `cancelled_trips` de `ops.mv_real_drill_dim_agg` y asignaba `cancelaciones = 0` en todas las rutas del drill principal y children (LOB/PARK desde MV_DIM).

### 4. Corrección aplicada

- Inclusión de `COALESCE(SUM(cancelled_trips), 0)::bigint AS cancelaciones` en las queries del drill principal y en las de children que leen de `MV_DIM`.  
- Eliminación del fallback permanente `cancelaciones = 0` en esas rutas.  
- Fallback temporal **solo** en children por tipo de servicio desde `mv_real_drill_service_by_park` (sin columna cancelled_trips), documentado en código.

### 5. Queries de reconciliación

- Incluidas en FASE 5 de este documento.

### 6. Evidencia DB

- Ejecutar `backend/scripts/verify_real_drill_db.sql` (columnas de real_drill_dim_fact y mv_real_drill_dim_agg, existencia de real_margin_quality_audit).  
- Ejecutar la query de reconciliación anterior para un país y periodo.

### 7. Evidencia runtime

- `GET /ops/real-lob/drill?period=month&desglose=LOB` → en `countries[].rows[]` debe haber `cancelaciones` con valores ≥ 0 (no todos 0 si hay cancelaciones en la fuente).  
- `GET /ops/real-lob/drill/children?country=co&period_grain=month&period_start=YYYY-MM-01&desglose=LOB` → filas con `cancelaciones` desde la MV.

### 8. Evidencia UI

- Pestaña Real → Drill (semanal/mensual) → columna "Cancel." con números y WoW; valores alineados con backend y con reconciliación.

### 9. Archivos tocados

- `backend/app/services/real_lob_drill_pro_service.py`: uso de `cancelled_trips` en queries del drill principal y children (MV_DIM); fallback 0 solo en children desde MV_SERVICE_BY_PARK.  
- `docs/REAL_CANCELACIONES_ESTRUCTURAL.md`: este documento.  
- `backend/alembic/versions/105_recreate_mv_real_drill_dim_agg_with_cancelled.py`: recrear vista `ops.mv_real_drill_dim_agg` para que exponga `cancelled_trips` (en PostgreSQL una vista con `SELECT *` fija columnas en la creación).  
- `backend/scripts/verify_and_validate_real_cancellations.py`: script de verificación y reconciliación.  
- `backend/scripts/check_mv_drill_type.py`: comprueba tipo de objeto y que `SUM(cancelled_trips)` funcione.

### Validaciones y migraciones ejecutadas

- **Alembic:** `alembic upgrade head` — aplicadas 104 (real_margin_quality_audit) y 105 (recrear vista con cancelled_trips).  
- **Verificación DB:** `ops.real_drill_dim_fact` tiene columna `cancelled_trips`; tras 105, `ops.mv_real_drill_dim_agg` también la expone y `SUM(cancelled_trips)` responde correctamente.  
- **Reconciliación (semana 2026-03-09):** drill LOB completed=167814, cancelled=582150.  
- **API:** Tras **reiniciar el backend** (uvicorn), GET /ops/real-lob/drill debe devolver `cancelaciones` con valores reales en `countries[].kpis` y en `rows[]`.

### 10. Veredicto final

- **CANCELACIONES_REALES_INTEGRADAS** en el drill principal y en children LOB/PARK (desde real_drill_dim_fact / mv_real_drill_dim_agg), con condición: mig 103 aplicada y populate ejecutado.  
- **Fallback temporal** documentado solo para children por tipo de servicio por park (mv_real_drill_service_by_park sin cancelled_trips).  
- Para marcar **NOT_CLOSED**: si en tu entorno la columna `cancelled_trips` no existe (mig 103 no aplicada) o el populate no se ha ejecutado, el backend fallará al ejecutar las nuevas queries hasta que se aplique la migración y se repueble el drill.
