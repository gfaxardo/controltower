# Diagnóstico E2E: Bug B2B Park "Yego Pro" (Ene-2026)

**Caso:** Dashboard muestra B2B = 3 viajes para Park "Yego Pro" en Ene-2026; en `trips_all` la cantidad verificada manualmente es mayor.  
**Park Yego Pro ID:** `64085dd85e124e2c808806f70d527ea8`  
**Regla B2B canónica:** `pago_corporativo IS NOT NULL AND pago_corporativo > 0`.  
**Casteo seguro si `pago_corporativo` es texto:** usar `(NULLIF(REGEXP_REPLACE(TRIM(pago_corporativo::text), '[^0-9.-]', '', 'g'), '')::numeric)` para comparar con 0; si el resultado es NULL, considerar B2C.

---

## 1. Resumen del hallazgo

- **Objeto que alimenta el dashboard (Real LOB Drill):** `ops.mv_real_lob_drill_agg`, consumida por el endpoint `/ops/real-lob/drill` y children por PARK (frontend `RealLOBDrillView.jsx` con `USE_DRILL_PRO = true`).
- **Causa raíz más probable:** En `ops.mv_real_lob_drill_agg` (y en `ops.mv_real_rollup_day`) el join con `public.parks` es por **igualdad exacta** `p.id::text = NULLIF(TRIM(t.park_id::text), '')`. Si `parks.id` es UUID con guiones (ej. `64085dd8-5e12-4e2c-8088-06f70d527ea8`) y en `trips_all.park_id` el valor viene **sin guiones** (`64085dd85e124e2c808806f70d527ea8`), el join no hace match → esas filas quedan con `country = 'unk'` y se **excluyen** por `WHERE v.country IN ('co','pe')`, reduciendo el B2B mostrado.
- **Regla B2B en las MVs:** Se usa `pago_corporativo IS NOT NULL` (sin `> 0`). Para alinear con la regla canónica debe usarse `(pago_corporativo IS NOT NULL AND pago_corporativo > 0)` en todas las capas.
- **Recomendación:** (A) Normalizar el join a parks con `LOWER(TRIM(REPLACE(..., '-', '')))` en ambos lados para UUID con/sin guiones; (B) Unificar regla B2B a `IS NOT NULL AND > 0`; (C) Añadir guardrails SQL y monitoreo semanal.

---

## 2. SQL ejecutable (por fases)

### FASE 1 — Inspección de esquema (NO adivinar)

```sql
-- 1) Columnas relevantes en public.trips_all (park, corpor, b2b, company, client, tipo, completed, created, status, condicion)
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'trips_all'
  AND (
    column_name ILIKE '%park%' OR column_name ILIKE '%corpor%' OR column_name ILIKE '%b2b%'
    OR column_name ILIKE '%company%' OR column_name ILIKE '%client%' OR column_name ILIKE '%tipo%'
    OR column_name ILIKE '%completed%' OR column_name ILIKE '%created%' OR column_name ILIKE '%status%'
    OR column_name ILIKE '%condicion%'
  )
ORDER BY ordinal_position;

-- 2) Columnas que puedan ser park id (UUID/MD5/text)
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'trips_all'
  AND (column_name ILIKE '%park%' OR column_name ILIKE '%_id%' AND column_name ILIKE '%park%')
ORDER BY ordinal_position;

-- 3) Campo de fecha para corte mensual (prioridad completed_at; alternativas)
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'trips_all'
  AND (column_name ILIKE '%fecha%' OR column_name ILIKE '%completed%' OR column_name ILIKE '%created%' OR column_name ILIKE '%date%')
ORDER BY ordinal_position;

-- 4) Existencia y tipo de pago_corporativo
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'trips_all'
  AND column_name ILIKE '%pago_corporativo%';
```

**Nota:** En el codebase ya se usan `park_id`, `fecha_inicio_viaje`, `condicion`, `pago_corporativo`. Si tu instancia tiene nombres distintos, ajusta los bloques siguientes con los nombres devueltos aquí.

---

### FASE 2 — “Ground truth” en trips_all (Enero 2026, Yego Pro)

**Park_id Yego Pro:** `64085dd85e124e2c808806f70d527ea8`. En algunas tablas el UUID puede estar con guiones; se prueba por igualdad normalizada.

```sql
-- 5a) Conteo total viajes completados (Ene-2026, park Yego Pro)
-- Asumiendo columna fecha = fecha_inicio_viaje y condicion = 'Completado'. Si no, reemplaza por lo detectado en Fase 1.
SELECT COUNT(*) AS total_completed
FROM public.trips_all t
WHERE (DATE_TRUNC('month', t.fecha_inicio_viaje)::date) = '2026-01-01'
  AND t.condicion = 'Completado'
  AND (
    NULLIF(TRIM(t.park_id::text), '') = '64085dd85e124e2c808806f70d527ea8'
    OR LOWER(REPLACE(TRIM(t.park_id::text), '-', '')) = '64085dd85e124e2c808806f70d527ea8'
  );

-- 5b) Conteo B2B (pago_corporativo IS NOT NULL AND pago_corporativo > 0). Si pago_corporativo es texto, usar: NULLIF(REGEXP_REPLACE(TRIM(pago_corporativo), '[^0-9.]', '', 'g'), '')::numeric
SELECT COUNT(*) AS trips_b2b
FROM public.trips_all t
WHERE (DATE_TRUNC('month', t.fecha_inicio_viaje)::date) = '2026-01-01'
  AND t.condicion = 'Completado'
  AND (
    NULLIF(TRIM(t.park_id::text), '') = '64085dd85e124e2c808806f70d527ea8'
    OR LOWER(REPLACE(TRIM(t.park_id::text), '-', '')) = '64085dd85e124e2c808806f70d527ea8'
  )
  AND t.pago_corporativo IS NOT NULL
  AND (t.pago_corporativo::numeric) > 0;

-- 5c) B2C-like (pago_corporativo IS NULL OR = 0)
SELECT COUNT(*) AS trips_b2c_like
FROM public.trips_all t
WHERE (DATE_TRUNC('month', t.fecha_inicio_viaje)::date) = '2026-01-01'
  AND t.condicion = 'Completado'
  AND (
    NULLIF(TRIM(t.park_id::text), '') = '64085dd85e124e2c808806f70d527ea8'
    OR LOWER(REPLACE(TRIM(t.park_id::text), '-', '')) = '64085dd85e124e2c808806f70d527ea8'
  )
  AND (t.pago_corporativo IS NULL OR (t.pago_corporativo::numeric) = 0);

-- 6) Breakdown por día (detectar huecos)
SELECT DATE_TRUNC('day', t.fecha_inicio_viaje)::date AS trip_day,
       COUNT(*) AS total,
       SUM(CASE WHEN t.pago_corporativo IS NOT NULL AND (t.pago_corporativo::numeric) > 0 THEN 1 ELSE 0 END) AS b2b
FROM public.trips_all t
WHERE (DATE_TRUNC('month', t.fecha_inicio_viaje)::date) = '2026-01-01'
  AND t.condicion = 'Completado'
  AND (
    NULLIF(TRIM(t.park_id::text), '') = '64085dd85e124e2c808806f70d527ea8'
    OR LOWER(REPLACE(TRIM(t.park_id::text), '-', '')) = '64085dd85e124e2c808806f70d527ea8'
  )
GROUP BY DATE_TRUNC('day', t.fecha_inicio_viaje)::date
ORDER BY trip_day;

-- 7) Sample 50 filas B2B (orden desc por fecha)
SELECT t.fecha_inicio_viaje,
       t.park_id,
       t.pago_corporativo,
       t.id AS trip_id
FROM public.trips_all t
WHERE (DATE_TRUNC('month', t.fecha_inicio_viaje)::date) = '2026-01-01'
  AND t.condicion = 'Completado'
  AND t.pago_corporativo IS NOT NULL AND (t.pago_corporativo::numeric) > 0
  AND (
    NULLIF(TRIM(t.park_id::text), '') = '64085dd85e124e2c808806f70d527ea8'
    OR LOWER(REPLACE(TRIM(t.park_id::text), '-', '')) = '64085dd85e124e2c808806f70d527ea8'
  )
ORDER BY t.fecha_inicio_viaje DESC
LIMIT 50;
-- Si no existe t.id, usar cualquier columna id de viaje (order_id, ride_id, etc.) detectada en Fase 1.

-- 8) Si hay 2 campos de park: repetir conteo con OR (validar campo que usa el tablero)
-- Ejemplo si existiera park_uuid además de park_id:
-- AND (t.park_id::text = '...' OR t.park_uuid::text = '...')
-- En el schema actual solo se usa park_id; el OR ya incluye variante con/sin guiones arriba.
```

---

### FASE 3 — Objetos que alimentan el dashboard

```sql
-- 9) Vistas y MVs que referencian pago_corporativo o B2B o park
SELECT n.nspname AS schema_name,
       c.relname AS object_name,
       CASE c.relkind WHEN 'v' THEN 'view' WHEN 'm' THEN 'materialized view' END AS object_type
FROM pg_depend d
JOIN pg_rewrite r ON r.oid = d.objid
JOIN pg_class c ON c.oid = r.ev_class
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_class t ON t.oid = d.refobjid
JOIN pg_namespace tn ON tn.oid = t.relnamespace
WHERE tn.nspname = 'public' AND t.relname = 'trips_all'
  AND c.relkind IN ('v','m')
  AND n.nspname IN ('ops','bi','public','canon')
ORDER BY n.nspname, c.relname;

-- Alternativa por definición (buscar pago_corporativo o b2b en el texto de la definición)
SELECT n.nspname AS schema_name,
       c.relname AS object_name,
       CASE c.relkind WHEN 'v' THEN 'view' WHEN 'm' THEN 'mv' END AS tipo
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname IN ('ops','bi','public','canon')
  AND c.relkind IN ('v','m')
  AND EXISTS (
    SELECT 1 FROM pg_views v
    WHERE v.schemaname = n.nspname AND v.viewname = c.relname
    UNION ALL
    SELECT 1 FROM pg_matviews m
    WHERE m.schemaname = n.nspname AND m.matviewname = c.relname
  );

-- 10) Definición de candidatos clave (usar nombre exacto de la MV/vista)
SELECT pg_get_viewdef('ops.mv_real_lob_drill_agg'::regclass, true);  -- no aplica a MV; para MV ver abajo
-- Para MV obtener definición desde migración o:
SELECT pg_get_viewdef((SELECT oid FROM pg_class WHERE relname = 'mv_real_lob_drill_agg' AND relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'ops')), true);
```

Las definiciones relevantes están en el codebase:
- **ops.mv_real_lob_drill_agg** (053): fuente `trips_all` + `LEFT JOIN public.parks p ON p.id::text = NULLIF(TRIM(t.park_id::text), '')`, filtro `condicion = 'Completado'`, y `WHERE v.country IN ('co','pe')`. B2B: `CASE WHEN v.pago_corporativo IS NOT NULL THEN 'B2B'` y `SUM(CASE WHEN v.pago_corporativo IS NOT NULL THEN 1 ELSE 0 END)`.
- **ops.v_real_trips_with_lob_v2** (047): `JOIN public.parks p ON LOWER(TRIM(p.id::text)) = LOWER(TRIM(t.park_id::text))` (join más robusto). B2B: mismo `IS NOT NULL` sin `> 0`.

---

### FASE 4 — Comparación trips_all vs objeto del dashboard

```sql
-- 11–12) Base = agregados desde trips_all (Ene-2026, park Yego Pro). Dash = desde ops.mv_real_lob_drill_agg (mes, park_key = Yego Pro).
-- Base (ground truth)
WITH params AS (
  SELECT '2026-01-01'::date AS month_start,
         '64085dd85e124e2c808806f70d527ea8' AS park_literal
),
base AS (
  SELECT
    (DATE_TRUNC('month', t.fecha_inicio_viaje)::date) AS month_start,
    COUNT(*) AS base_trips_total,
    SUM(CASE WHEN t.pago_corporativo IS NOT NULL AND (t.pago_corporativo::numeric) > 0 THEN 1 ELSE 0 END) AS base_trips_b2b
  FROM public.trips_all t, params p
  WHERE t.condicion = 'Completado'
    AND t.fecha_inicio_viaje IS NOT NULL
    AND t.tipo_servicio IS NOT NULL
    AND LENGTH(TRIM(t.tipo_servicio::text)) < 100
    AND t.tipo_servicio::text NOT LIKE '%->%'
    AND (NULLIF(TRIM(t.park_id::text), '') = p.park_literal OR LOWER(REPLACE(TRIM(t.park_id::text), '-', '')) = p.park_literal)
    AND (DATE_TRUNC('month', t.fecha_inicio_viaje)::date) = p.month_start
  GROUP BY DATE_TRUNC('month', t.fecha_inicio_viaje)::date
),
dash AS (
  SELECT
    period_start AS month_start,
    SUM(viajes) AS dash_trips_total,
    SUM(viajes_b2b) AS dash_trips_b2b
  FROM ops.mv_real_lob_drill_agg
  WHERE period_type = 'month'
    AND period_start = '2026-01-01'::date
    AND (park_key::text = '64085dd85e124e2c808806f70d527ea8'
         OR LOWER(REPLACE(COALESCE(park_key::text, ''), '-', '')) = '64085dd85e124e2c808806f70d527ea8')
  GROUP BY period_start
)
SELECT
  COALESCE(b.month_start, d.month_start) AS month_start,
  b.base_trips_total,
  b.base_trips_b2b,
  d.dash_trips_total AS dash_trips_total,
  d.dash_trips_b2b AS dash_trips_b2b,
  (b.base_trips_b2b - COALESCE(d.dash_trips_b2b, 0)) AS diff_b2b
FROM base b
FULL OUTER JOIN dash d ON b.month_start = d.month_start;
```

Si `diff_b2b > 0`, el dashboard está mostrando menos B2B que la base. Comprobar en la misma BD si `parks.id` para Yego Pro tiene guiones y si `trips_all.park_id` para esos viajes viene sin guiones:

```sql
-- Ver formato de parks.id para Yego Pro (por nombre)
SELECT id, id::text AS id_text, name, city
FROM public.parks
WHERE name ILIKE '%yego%pro%' OR id::text LIKE '%64085dd8%';

-- Viajes Ene-2026 con park_id que no hace match exacto con parks.id
SELECT DISTINCT t.park_id, t.park_id::text AS park_id_text,
       p.id AS parks_id, p.id::text AS parks_id_text
FROM public.trips_all t
LEFT JOIN public.parks p ON p.id::text = NULLIF(TRIM(t.park_id::text), '')
WHERE (DATE_TRUNC('month', t.fecha_inicio_viaje)::date) = '2026-01-01'
  AND t.condicion = 'Completado'
  AND (NULLIF(TRIM(t.park_id::text), '') = '64085dd85e124e2c808806f70d527ea8'
       OR LOWER(REPLACE(TRIM(t.park_id::text), '-', '')) = '64085dd85e124e2c808806f70d527ea8')
  AND p.id IS NULL;
```

---

### FASE 5 — Diagnóstico y fix

- **14) Conclusión:** Si la comparación muestra `base_trips_b2b > dash_trips_b2b` y la query de “viajes sin match” devuelve filas, el fallo es de **transformación**: el join a `parks` en `ops.mv_real_lob_drill_agg` (y en `ops.mv_real_rollup_day`) excluye viajes cuando `park_id` no coincide exactamente con `parks.id` (ej. UUID sin guiones vs con guiones), y al quedar `country = 'unk'` se filtran por `WHERE v.country IN ('co','pe')`.

- **15) Fix mínimo viable**

  **Transformación (join + regla B2B):**

  1. **Join robusto a parks** (igual que en `ops.v_real_trips_with_lob_v2`): normalizar ambos lados para ignorar guiones y mayúsculas, por ejemplo:
     - `LOWER(REPLACE(TRIM(p.id::text), '-', '')) = LOWER(REPLACE(NULLIF(TRIM(t.park_id::text), ''), '-', ''))`
  2. **Regla B2B unificada:** usar en todas las MVs/vistas:
     - `(pago_corporativo IS NOT NULL AND (pago_corporativo::numeric) > 0)` para segmento B2B y conteo `viajes_b2b`.

  Cambios concretos en el código (Alembic):

  - En la definición de **ops.mv_real_lob_drill_agg** (y donde se use el mismo patrón):
    - Reemplazar  
      `LEFT JOIN public.parks p ON p.id::text = NULLIF(TRIM(t.park_id::text), '')`  
      por  
      `LEFT JOIN public.parks p ON LOWER(REPLACE(TRIM(p.id::text), '-', '')) = LOWER(REPLACE(NULLIF(TRIM(t.park_id::text), ''), '-', ''))`
    - Reemplazar `CASE WHEN v.pago_corporativo IS NOT NULL THEN 'B2B'` por  
      `CASE WHEN (v.pago_corporativo IS NOT NULL AND (v.pago_corporativo::numeric) > 0) THEN 'B2B'`
    - Reemplazar `SUM(CASE WHEN v.pago_corporativo IS NOT NULL THEN 1 ELSE 0 END)` por  
      `SUM(CASE WHEN (v.pago_corporativo IS NOT NULL AND (v.pago_corporativo::numeric) > 0) THEN 1 ELSE 0 END)`
  - En **ops.mv_real_rollup_day** (053): mismo cambio de join a `parks` y misma regla B2B para `segment_tag` y `b2b_trips`.
  - Crear una **nueva migración Alembic** que haga `DROP MATERIALIZED VIEW ... CASCADE`, `CREATE MATERIALIZED VIEW ...` con los cambios anteriores y vuelva a crear índices/vistas dependientes según corresponda.

  **Refresh:** Tras aplicar la migración, ejecutar:

  ```sql
  REFRESH MATERIALIZED VIEW ops.mv_real_rollup_day;
  REFRESH MATERIALIZED VIEW ops.mv_real_lob_drill_agg;
  ```

  Si se usa `REFRESH MATERIALIZED VIEW CONCURRENTLY`, mantener los índices únicos existentes. Estrategia: cron diario o tras ingesta de Real (ver `backend/scripts/refresh_real_lob_drill_pro_mv.py`). Para auditar última actualización de una MV no hay columna estándar; se puede registrar en una tabla de control o ejecutar `SELECT MAX(last_trip_ts) FROM ops.mv_real_lob_drill_agg WHERE period_type = 'month'` como proxy.

  **Ingesta:** Si tras el fix la comparación base vs dash sigue con diferencias, ejecutar la query de Fase 2 por día (breakdown) y la de sample para ver si hay huecos por fecha o valores raros de `pago_corporativo`; y revisar pipeline de carga para que no trunque o pierda filas y que `pago_corporativo` se persista con tipo numérico coherente.

---

## 3. Causa raíz (1 párrafo)

El dashboard Real LOB Drill toma los datos de **ops.mv_real_lob_drill_agg**, que se construye desde **trips_all** con un **LEFT JOIN a public.parks** por igualdad exacta `p.id::text = NULLIF(TRIM(t.park_id::text), '')`. Cuando el identificador del park en **trips_all** viene en un formato distinto al de **parks.id** (por ejemplo UUID sin guiones vs UUID con guiones), el join no hace match, las filas quedan con `country = 'unk'` (salvo que exista en **ops.park_country_fallback**) y se **excluyen** por el filtro `WHERE v.country IN ('co','pe')`, reduciendo el conteo de viajes y de B2B mostrado para ese park. La regla B2B en las MVs usa solo `pago_corporativo IS NOT NULL`; para alineación con la regla canónica debe añadirse `AND pago_corporativo > 0`.

---

## 4. Fix propuesto (pasos exactos)

1. **Nueva migración Alembic** que:
   - En **ops.mv_real_lob_drill_agg**: (a) sustituya el join a `public.parks` por la condición normalizada con `LOWER(REPLACE(..., '-', ''))` en ambos lados; (b) defina B2B como `(pago_corporativo IS NOT NULL AND (pago_corporativo::numeric) > 0)` en el segmento y en el `SUM(viajes_b2b)`.
   - En **ops.mv_real_rollup_day**: (a) mismo join normalizado a `parks`; (b) mismo criterio B2B para `segment_tag` y `b2b_trips`.
   - Recrear índices y vistas que dependan de estas MVs si el `DROP ... CASCADE` las elimina.
2. **Ejecutar** `alembic upgrade head` en el entorno afectado.
3. **Refrescar** las MVs: `REFRESH MATERIALIZED VIEW ops.mv_real_rollup_day;` y `REFRESH MATERIALIZED VIEW ops.mv_real_lob_drill_agg;` (o el script `refresh_real_lob_drill_pro_mv.py`).
4. **Verificar** con la query comparativa de Fase 4 que `diff_b2b` sea 0 para Ene-2026 y Park Yego Pro.

---

## 5. Guardrails

**Tests SQL (asserts):** que B2B del dashboard coincida con trips_all por mes y park dentro de tolerancia 0.

```sql
-- Assert: B2B por (month, park_key) en mv_real_lob_drill_agg = trips_all (mismo periodo y filtros)
WITH base AS (
  SELECT
    (DATE_TRUNC('month', t.fecha_inicio_viaje)::date) AS month_start,
    NULLIF(TRIM(t.park_id::text), '') AS park_key,
    SUM(CASE WHEN (t.pago_corporativo IS NOT NULL AND (t.pago_corporativo::numeric) > 0) THEN 1 ELSE 0 END) AS base_b2b
  FROM public.trips_all t
  WHERE t.condicion = 'Completado'
    AND t.fecha_inicio_viaje IS NOT NULL
    AND t.tipo_servicio IS NOT NULL
    AND LENGTH(TRIM(t.tipo_servicio::text)) < 100
    AND t.tipo_servicio::text NOT LIKE '%->%'
  GROUP BY DATE_TRUNC('month', t.fecha_inicio_viaje)::date, NULLIF(TRIM(t.park_id::text), '')
),
dash AS (
  SELECT period_start AS month_start,
         park_key,
         SUM(viajes_b2b) AS dash_b2b
  FROM ops.mv_real_lob_drill_agg
  WHERE period_type = 'month' AND country IN ('co','pe')
  GROUP BY period_start, park_key
)
SELECT b.month_start, b.park_key,
       b.base_b2b, d.dash_b2b,
       (b.base_b2b - COALESCE(d.dash_b2b, 0)) AS diff
FROM base b
LEFT JOIN dash d ON b.month_start = d.period_start
  AND LOWER(REPLACE(COALESCE(b.park_key, ''), '-', '')) = LOWER(REPLACE(COALESCE(d.park_key::text, ''), '-', ''))
WHERE b.park_key IS NOT NULL AND b.park_key <> ''
  AND (b.base_b2b - COALESCE(d.dash_b2b, 0)) <> 0;
-- Esperado: 0 filas. Si hay filas, el test falla.
```

**Monitoreo semanal (alertar si diff != 0):**

```sql
-- Ejecutar semanalmente; si devuelve filas, hay desvío B2B por mes/park.
WITH base AS (
  SELECT
    (DATE_TRUNC('month', t.fecha_inicio_viaje)::date) AS month_start,
    NULLIF(TRIM(t.park_id::text), '') AS park_key,
    SUM(CASE WHEN (t.pago_corporativo IS NOT NULL AND (t.pago_corporativo::numeric) > 0) THEN 1 ELSE 0 END) AS base_b2b
  FROM public.trips_all t
  WHERE t.condicion = 'Completado'
    AND t.fecha_inicio_viaje IS NOT NULL
    AND t.tipo_servicio IS NOT NULL
    AND LENGTH(TRIM(t.tipo_servicio::text)) < 100
    AND t.tipo_servicio::text NOT LIKE '%->%'
    AND t.fecha_inicio_viaje >= DATE_TRUNC('month', CURRENT_DATE - interval '3 months')::date
  GROUP BY DATE_TRUNC('month', t.fecha_inicio_viaje)::date, NULLIF(TRIM(t.park_id::text), '')
),
dash AS (
  SELECT period_start AS month_start, park_key, SUM(viajes_b2b) AS dash_b2b
  FROM ops.mv_real_lob_drill_agg
  WHERE period_type = 'month' AND country IN ('co','pe')
    AND period_start >= DATE_TRUNC('month', CURRENT_DATE - interval '3 months')::date
  GROUP BY period_start, park_key
)
SELECT b.month_start, b.park_key, b.base_b2b, d.dash_b2b, (b.base_b2b - COALESCE(d.dash_b2b, 0)) AS diff
FROM base b
LEFT JOIN dash d ON b.month_start = d.period_start
  AND LOWER(REPLACE(COALESCE(b.park_key, ''), '-', '')) = LOWER(REPLACE(COALESCE(d.park_key::text, ''), '-', ''))
WHERE b.park_key IS NOT NULL AND b.park_key <> '' AND (b.base_b2b - COALESCE(d.dash_b2b, 0)) <> 0;
```

Recomendación: ejecutar el assert tras cada refresh de las MVs (o en CI si hay acceso a BD de prueba) y la query de monitoreo semanal con alerta cuando el resultado tenga al menos una fila.
