# Auditoría Freshness: Driver Lifecycle

## Contexto

- **MV:** `ops.mv_driver_lifecycle_base` reporta `MAX(last_completed_ts) = '2026-02-01 01:05:52'`
- **Fuente:** `public.trips_all` con filtro `condicion = 'Completado'`

## Mapeo trips_all → completion_ts

| Columna | Tipo | Uso |
|---------|------|-----|
| fecha_finalizacion | timestamp without time zone | Fin real del viaje |
| fecha_inicio_viaje | timestamp without time zone | Inicio (fallback si finalizacion NULL) |

**Fórmula actual en `v_driver_lifecycle_trips_completed`:**
```sql
completion_ts = COALESCE(fecha_finalizacion, fecha_inicio_viaje)
```

**Filtro:** `condicion = 'Completado' AND conductor_id IS NOT NULL AND fecha_inicio_viaje IS NOT NULL`

## Cadena de derivación

```
trips_all (fecha_finalizacion, fecha_inicio_viaje)
    → v_driver_lifecycle_trips_completed (completion_ts = COALESCE(...))
        → mv_driver_lifecycle_base (last_completed_ts = MAX(completion_ts) por driver)
```

## Queries de auditoría

Ejecutar con `statement_timeout` alto (ej. 10 min):

```sql
-- 1) MAX en fuente (mismo filtro que la view)
SELECT MAX(COALESCE(fecha_finalizacion, fecha_inicio_viaje)) AS fuente_max
FROM public.trips_all
WHERE condicion = 'Completado' AND conductor_id IS NOT NULL AND fecha_inicio_viaje IS NOT NULL;

-- 2) MAX en MV
SELECT MAX(last_completed_ts) AS mv_max FROM ops.mv_driver_lifecycle_base;

-- 3) Comparación
WITH f AS (
  SELECT MAX(COALESCE(fecha_finalizacion, fecha_inicio_viaje)) AS m
  FROM public.trips_all
  WHERE condicion = 'Completado' AND conductor_id IS NOT NULL AND fecha_inicio_viaje IS NOT NULL
),
m AS (SELECT MAX(last_completed_ts) AS m FROM ops.mv_driver_lifecycle_base)
SELECT f.m AS fuente, m.m AS mv, CASE WHEN f.m = m.m THEN 'OK' ELSE 'DIFERENCIA' END FROM f, m;
```

## Diagnóstico si hay diferencia

| Causa | Acción |
|-------|--------|
| **MV desactualizada** | `REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_lifecycle_base` |
| **completion_ts mal derivado** | Revisar si `fecha_finalizacion` debe usarse sin COALESCE, o si hay otra columna |
| **Filtro distinto** | Verificar que `condicion = 'Completado'` sea el correcto |
| **Timezone** | Ambas columnas son `timestamp without time zone`; verificar que la app inserte en la misma zona |

## Fix mínimo (si completion_ts está mal)

Si se determina que debe usarse **solo** `fecha_finalizacion` (sin fallback a fecha_inicio_viaje):

```sql
-- En v_driver_lifecycle_trips_completed, cambiar:
-- completion_ts = COALESCE(fecha_finalizacion, fecha_inicio_viaje)
-- por:
-- completion_ts = fecha_finalizacion
-- Y añadir: AND fecha_finalizacion IS NOT NULL
```

**Importante:** Si se cambia la view, hay que:
1. `DROP VIEW ops.v_driver_lifecycle_trips_completed CASCADE`
2. Recrear la view
3. Recrear MVs dependientes (o REFRESH si la definición de la MV no cambia estructuralmente)

La MV `mv_driver_lifecycle_base` lee de la view; si cambiamos la view, el REFRESH usará la nueva definición.

## Script de auditoría

```powershell
cd backend
python -m scripts.audit_driver_lifecycle_freshness
```

(Requiere `statement_timeout` alto; el script usa 600s. Para tablas muy grandes, ejecutar las queries en `scripts/sql/audit_driver_lifecycle_freshness.sql` con psql.)

## E) Re-correr refresh y validar

Si la comparación da OK (fuente = MV) pero la MV está desactualizada, o si se aplicó un fix a la view:

```powershell
cd backend
python -m scripts.check_driver_lifecycle_and_validate
```

O solo refresh:
```sql
SELECT ops.refresh_driver_lifecycle_mvs();
```

Luego verificar:
```sql
SELECT MAX(last_completed_ts) FROM ops.mv_driver_lifecycle_base;
```
