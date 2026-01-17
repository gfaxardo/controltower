# UNIFICACIÓN REAL - COMPLETADA

**Fecha:** 2026-01-17  
**Rama:** master  
**DB:** 168.119.226.236:5432/yego_integral (user: yego_user)

## RESUMEN EJECUTIVO

✅ **Sistema unificado para datos REAL**: El backend ahora lee desde `ops.mv_real_trips_monthly` (vista materializada basada en `public.trips_all`) en lugar de `bi.real_monthly_agg` (legacy).

✅ **Vistas comparativas creadas**: Se crearon las vistas faltantes de la migración 007:
- `ops.v_real_trips_monthly_latest`
- `ops.v_real_kpis_monthly`
- `ops.v_plan_vs_real_monthly_latest` (449 registros)
- `ops.v_plan_vs_real_alerts_monthly_latest`

✅ **Smoke test pasando**: Sistema verificado y funcionando correctamente.

## CAMBIOS REALIZADOS

### 1. Vistas Creadas

Las vistas de la migración 007 no existían en la BD aunque la migración estaba marcada como ejecutada. Se crearon manualmente usando el script `backend/scripts/create_missing_views.py`.

**Evidencia:**
- Q5: Vista comparativa existe con 449 registros
- Sample muestra datos correctos con status_bucket (matched/plan_only/real_only)

### 2. Parcheo de `backend/app/adapters/real_repo.py`

**Antes:**
- `get_real_monthly_data()` leía de `bi.real_monthly_agg + dim.dim_park`
- `get_ops_universe_data()` leía de `bi.real_monthly_agg + dim.dim_park`

**Después:**
- `get_real_monthly_data()` lee de `ops.mv_real_trips_monthly`
- `get_ops_universe_data()` lee de `ops.mv_real_trips_monthly`
- Mapeo de métricas:
  - `trips` → `trips_real_completed`
  - `revenue` → `revenue_real_proxy`
  - `active_drivers` → `active_drivers_real`
  - `avg_ticket` → `avg_ticket_real`
  - `trips_per_driver` → calculado dinámicamente

**Compatibilidad:** Se mantiene el mismo contrato de respuesta (campos) para no romper la UI.

### 3. Smoke Test

Creado `backend/scripts/smoke_plan_vs_real.py` que verifica:
- Plan latest existe (312 registros, 2026-01 a 2026-12)
- Real agregado existe (804 registros)
- Vista comparativa existe (449 registros)
- Sample de datos muestra estructura correcta

**Comando:**
```bash
cd backend
.\venv\Scripts\python.exe scripts\smoke_plan_vs_real.py
```

## ESTADO DE LA BASE DE DATOS

### Plan
- **Versión latest:** `ruta27_v2026_01_16_a`
- **Registros:** 312
- **Rango:** 2026-01-01 a 2026-12-01
- **Tabla:** `ops.plan_trips_monthly`
- **Vista latest:** `ops.v_plan_trips_monthly_latest`

### Real
- **Registros:** 804
- **Fuente canónica:** `public.trips_all` (filtro: `condicion='Completado'`)
- **Vista materializada:** `ops.mv_real_trips_monthly`
- **Vista latest:** `ops.v_real_trips_monthly_latest`

### Comparación
- **Registros:** 449
- **Vista:** `ops.v_plan_vs_real_monthly_latest`
- **Status buckets:** matched, plan_only, real_only

## ARCHIVOS MODIFICADOS

1. `backend/app/adapters/real_repo.py` - Parcheado para usar `ops.mv_real_trips_monthly`
2. `backend/scripts/create_missing_views.py` - Script para crear vistas faltantes
3. `backend/scripts/verify_db_structure.py` - Script de verificación
4. `backend/scripts/smoke_plan_vs_real.py` - Smoke test

## NOTAS IMPORTANTES

### Plan Legacy vs Nuevo

El sistema tiene DOS sistemas de plan coexistiendo:

1. **Legacy (`plan.plan_long_*`):**
   - Formato long con columnas: `period`, `metric`, `plan_value`
   - Usado por endpoints de upload (`/plan/upload_simple`)
   - Leído por algunos servicios legacy (`summary_service.py`, `core_service.py`)

2. **Nuevo (`ops.plan_trips_monthly`):**
   - Formato canónico con columnas: `projected_trips`, `projected_drivers`, etc.
   - Usado por vistas comparativas
   - Fuente canónica para Plan vs Real

**Recomendación futura:** Migrar servicios legacy para que lean de `ops.v_plan_trips_monthly_latest` en lugar de `plan.plan_long_valid`.

### Refresh de Materialized View

La vista `ops.mv_real_trips_monthly` se alimenta de `public.trips_all` y debe refrescarse manualmente cuando se actualicen datos:

```sql
REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_real_trips_monthly;
```

O usando la función:
```sql
SELECT ops.refresh_real_trips_monthly();
```

## VERIFICACIÓN

Ejecutar smoke test:
```bash
cd backend
.\venv\Scripts\python.exe scripts\smoke_plan_vs_real.py
```

Resultado esperado: `[OK] SMOKE TEST PASADO - Sistema funcionando correctamente`

## PRÓXIMOS PASOS (OPCIONAL)

1. Migrar `summary_service.py` y `core_service.py` para usar `ops.v_plan_trips_monthly_latest`
2. Considerar automatizar refresh de `ops.mv_real_trips_monthly` (cron job o trigger)
3. Deprecar endpoints que leen de `plan.plan_long_*` una vez migrada la UI
