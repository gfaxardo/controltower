# Regla de presentación: no IDs en UI

**Regla no negociable** en YEGO CONTROL TOWER:

1. **NUNCA** mostrar IDs (park_id, driver_id, conductor_id, etc.) en la UI ni en exports/descargas.
2. **SIEMPRE** mostrar campos legibles:
   - **Park**: `park_name` + `city` + `country`
   - **Driver**: `driver_name` (y opcionalmente license si existe)
3. Los IDs se pueden usar **internamente** como `value` en selects o en joins/APIs, pero **JAMÁS** renderizarlos como texto visible.

## Implementación

### Base de datos
- **ops.v_dim_park_resolved**: vista canónica con `park_id`, `park_name`, `city`, `country` (fuente: dim.dim_park).
- **ops.v_dim_driver_resolved**: vista con `driver_id`, `driver_name` (fuente: trips_unified, conductor_id + MAX(conductor_nombre)). En BD la columna es `conductor_nombre`.
- Supply usa **dim.v_geo_park** con fallback a **ops.v_dim_park_resolved** si no hay datos.

### Backend (FastAPI)
- Respuestas de parques: incluir siempre `park_name`, `city`, `country`; `park_id` solo para valor interno en selects.
- Respuestas con breakdown por park: cada fila incluye `park_name`, `city`, `country` (enriquecido desde v_dim_park_resolved).
- Schemas: `ParkDisplay` y `DriverDisplay` con solo campos legibles (name, city, country / name).
- Exports CSV: no incluir columnas `park_id` ni `driver_id` en la salida visible; solo nombres y atributos legibles.

### Frontend (React)
- **Dropdown Park**: `label` = `${park_name} — ${city}` (y si hay country: `${park_name} — ${city} (${country})`). `value` = park_id (interno).
- **Tablas**: ninguna columna con cabecera `park_id` ni `driver_id`; usar `park_name`, `city`, `country` y `driver_name`.
- Modales y títulos: mostrar nombre del park/driver, no el id.

### Real LOB
- Se mantiene intacto; ya resuelve nombres en filtros y datos.

## Diagnóstico (FASE 1)

Script SQL de diagnóstico en `backend/scripts/sql/diagnostic_parks_trips_phase1.sql`:
- Comprueba `public.parks`, conteos en `trips_all`, join parks ↔ trips_all y ejemplos de campos legibles.

## Criterios de aceptación

1. En Driver Lifecycle, el dropdown de Park **no** contiene strings tipo hex/ID; solo nombres y ciudad/país.
2. En Supply (Real), el dropdown carga parks y al seleccionar uno aparece la serie semanal/mensual.
3. En ninguna tabla visible hay columna `park_id` ni `driver_id`.
4. El backend puede recibir `park_id` como parámetro; la respuesta incluye siempre `park_name`, `city`, `country`.
5. Real LOB queda intacto.
