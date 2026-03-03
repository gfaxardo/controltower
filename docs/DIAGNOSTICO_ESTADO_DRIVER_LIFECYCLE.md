# Diagnóstico: estado repo + DB — trips_unified y Driver Lifecycle

**Fecha:** 2026-03-03  
**Objetivo:** Saber exactamente dónde estás parado (repo + DB) y qué aplicar.

---

## PASO A — AUDITORÍA

### A1) Repo (esta máquina)

| Check | Resultado |
|-------|-----------|
| **Branch** | `master` |
| **Último commit** | `077160b` — Driver Lifecycle GO/NO-GO, serie por periodo, park names, GET /ops/parks |
| **Migraciones 054/055/056 en disco** | **SÍ** — archivos presentes en `backend/alembic/versions/` (054, 055, 056) |
| **Migraciones en HEAD (git)** | **NO** — 054/055/056 están sin commit (??) |
| **alembic current** | `053_real_lob_drill_pro` |
| **alembic heads** | `056_driver_lifecycle_pro_mvs` (y otro head `012_plan_financials` en otra rama) |

**Conclusión A1:** En esta máquina las migraciones 054–056 **no están aplicadas en la BD**. La BD está en 053. Los archivos 054/055/056 existen en el repo pero no se ha ejecutado `alembic upgrade head` (hasta 056).

### A2) DB (ejecutar auditoría)

Ejecuta en tu entorno (con BD accesible):

```bash
cd backend && python -m scripts.audit_trips_unified_and_driver_lifecycle
```

**Checklist A2 (rellenar tras ejecutar el script):**

| Objeto | Esperado si 054–056 aplicadas | Estado |
|--------|-------------------------------|--------|
| public.trips_all | EXISTE | (script) |
| public.trips_2026 | EXISTE o NO EXISTE (modo sin 2026) | (script) |
| public.trips_unified | EXISTE (VIEW) | (script) |
| ops.v_driver_lifecycle_trips_completed | EXISTE y lee de **trips_unified** | (script) |
| ops.mv_driver_lifecycle_base | EXISTE | (script) |
| ops.mv_driver_weekly_stats | EXISTE | (script) |
| trips_unified definition | UNION/corte 2026 cuando aplica | (script) |
| MAX(last_completed_ts) base | Refleja feb/mar si hay datos 2026 | (script) |

**Si no has aplicado 054–056:**  
- trips_unified **no existirá**.  
- v_driver_lifecycle_trips_completed seguirá leyendo de **trips_all** (definición anterior).  
- Driver Lifecycle **no** incluye trips_2026 hasta aplicar 054, 055 y refrescar MVs.

**Ejemplo de salida del script de auditoría (con 053 aplicada, sin 054–056):**  
- trips_all: EXISTE | trips_2026: EXISTE (o NO) | trips_unified: **NO EXISTE**  
- v_driver_lifecycle_trips_completed: Lee de trips_unified: **False**, Lee de trips_all: **True**  
- MAX(last_completed_ts) puede ser feb 2026 si los datos vienen solo de trips_all; tras 054+055+refresh, si hay datos en trips_2026 hasta mar, freshness subirá.

---

## Estado resumido (antes de aplicar 054–056)

1. **¿Migraciones 054–056 aplicadas?** → **NO** (current = 053).
2. **¿Existe public.trips_2026?** → Ver script A2 (o `information_schema.tables`).
3. **¿Existe public.trips_unified?** → **NO** hasta aplicar 054.
4. **¿Driver Lifecycle lee de trips_unified?** → **NO** hasta aplicar 055.
5. **¿UI usa parks por nombre (dim.dim_park)?** → **SÍ** en código (GET /ops/driver-lifecycle/parks desde servicio que usa dim.dim_park con fallback).

---

## Pasos para quedar al día (local)

1. **Opcional:** Crear `public.trips_2026` con la misma estructura que `trips_all` si quieres datos 2026 (si no, 054 creará trips_unified = solo trips_all).
2. **Aplicar migraciones:** se añadió la migración de **merge 057** (une 012_plan_financials y 056_driver_lifecycle_pro_mvs), así que ya hay un único head. Puedes usar:
   ```bash
   cd backend
   alembic upgrade head
   ```
   Eso aplica 054, 055, 056 y 057 (057 no toca la BD). Alternativa: `alembic upgrade 056_driver_lifecycle_pro_mvs` para quedarte en 056 sin aplicar el merge.
3. **Refrescar Driver Lifecycle:**  
   `SELECT ops.refresh_driver_lifecycle_mvs();`
4. **Refrescar MVs PRO (opcional):**  
   `REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_weekly_behavior;`  
   (y resto según docs/DRIVER_LIFECYCLE_PRO_VERIFICACION.md)
5. **Levantar backend/frontend** y probar: selector park obligatorio, serie por periodo del park, cards en el rango visible.

---

## PASO D — trips_2026 en Driver Lifecycle (sin duplicar)

- **Si public.trips_2026 existe:** La migración 054 crea `trips_unified` con corte por fecha:
  - `trips_all` → solo filas con `fecha_inicio_viaje IS NULL OR fecha_inicio_viaje < '2026-01-01'`
  - `trips_2026` → solo `fecha_inicio_viaje >= '2026-01-01'`
  Así no hay duplicados aunque trips_all tenga datos 2026.
- **Índices:** La migración 054 crea índices en `trips_all` y (si existe) en `trips_2026`. En tablas muy grandes, para no bloquear, puedes crear los mismos índices con `CONCURRENTLY` a mano y luego no ejecutar esa parte de la migración (o ya estarán creados con IF NOT EXISTS). Ejemplo:
  ```sql
  CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_trips_all_fecha_inicio ON public.trips_all (fecha_inicio_viaje);
  CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_trips_2026_fecha_inicio ON public.trips_2026 (fecha_inicio_viaje);
  ```
- **Refresco y freshness:** Tras `SELECT ops.refresh_driver_lifecycle_mvs();`, `MAX(last_completed_ts)` en `ops.mv_driver_lifecycle_base` debe reflejar feb/mar 2026 si hay viajes completados en `trips_2026` en ese rango.

---

## PASO E — Comandos de verificación (copiables)

### SQL: counts y consistencia

```sql
-- Counts (ejecutar por separado si trips_2026 no existe)
SELECT COUNT(*) AS n_all FROM public.trips_all;
SELECT COUNT(*) AS n_2026 FROM public.trips_2026;  -- falla si la tabla no existe
SELECT COUNT(*) AS n_unified FROM public.trips_unified;
```

### SQL: v_driver_lifecycle_trips_completed usa trips_unified

```sql
SELECT definition FROM pg_views
WHERE schemaname = 'ops' AND viewname = 'v_driver_lifecycle_trips_completed';
-- En definition debe aparecer "trips_unified".
```

### SQL: filas y unicidad MVs

```sql
SELECT 'mv_driver_lifecycle_base' AS mv, COUNT(*) AS filas FROM ops.mv_driver_lifecycle_base
UNION ALL SELECT 'mv_driver_weekly_stats', COUNT(*) FROM ops.mv_driver_weekly_stats;

-- Unicidad (debe devolver 0 filas)
SELECT driver_key, week_start, COUNT(*) AS cnt
FROM ops.mv_driver_weekly_stats
GROUP BY driver_key, week_start
HAVING COUNT(*) > 1;
```

### SQL: parks coverage y park_name

```sql
SELECT COUNT(*) AS total FROM dim.dim_park;
SELECT column_name FROM information_schema.columns
WHERE table_schema = 'dim' AND table_name = 'dim_park' AND column_name IN ('park_id','park_name','name');
```

### Curl: endpoints /parks y /park/series

```bash
# Lista de parks (park_id, park_name)
curl -s "http://localhost:8000/ops/driver-lifecycle/parks"

# Serie por park (park_id obligatorio, from, to, grain)
curl -s "http://localhost:8000/ops/driver-lifecycle/park/series?park_id=TU_PARK_ID&from=2025-12-01&to=2026-03-01&grain=weekly"
# O el alias con query series:
curl -s "http://localhost:8000/ops/driver-lifecycle/series?park_id=TU_PARK_ID&from=2025-12-01&to=2026-03-01&grain=weekly"
```

Ajusta `localhost:8000` por tu base URL del backend.
