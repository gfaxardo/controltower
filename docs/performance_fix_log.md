# Registro de fixes — Performance y robustez

## Fix crítico: GET /ops/driver-behavior/drivers con park_id (500)

**Error:** `missing FROM-clause entry for table "ra"`  
**Línea SQL:** `SELECT * FROM with_action WHERE 1=1  AND ra.park_id::text = %s`

**Causa:** La query principal hace `SELECT * FROM with_action`; el WHERE se construía con condiciones que usaban el alias `ra` (recent_agg), que no existe en el scope del SELECT final (solo existe `with_action` y sus columnas sin alias).

**Cambios (driver_behavior_service.py):**

1. **Filtros con un solo prefijo:** Todos los `having_parts` usan **cls.** (incluidos park_id y current_segment):
   - `cls.park_id::text = %s`
   - `cls.current_segment = %s`
   (Antes park_id y current_segment usaban `ra.`.)

2. **WHERE para la query principal:** Se construye `where_sql_main` quitando prefijos que no existen en `with_action`:
   - `where_sql.replace("cls.", "")`
   - `.replace("LOWER(TRIM(geo.country))", "LOWER(TRIM(country))")`
   - `.replace("LOWER(TRIM(geo.city))", "LOWER(TRIM(city))")`
   La query principal usa `WHERE 1=1 ` + `where_sql_main`.

3. **Query de count:** Hace `FROM cls`, por lo que usa `where_sql` sin modificar (con `cls.`).

**Validación:** Llamar a `GET /ops/driver-behavior/drivers?recent_weeks=4&baseline_weeks=16&park_id=<uuid>&limit=50&offset=0` debe devolver 200 y filas filtradas por park.

**Tests añadidos:** `backend/tests/test_driver_behavior_drivers_park_id.py`
- `test_driver_behavior_drivers_with_park_id_returns_200`: GET con park_id debe devolver 200 y `{ data, total, limit, offset }`.
- `test_driver_behavior_drivers_with_country_city_segment_returns_200`: filtros country, city, segment_current no deben provocar 500.
Ambos se saltan si no está definido `DATABASE_URL` (requieren DB).

---

## Instrumentación (Fase 1)

**Archivo:** backend/app/main.py

**Cambio:** Middleware HTTP que:
- Asigna o propaga `X-Request-ID` (header o generado).
- Mide tiempo de respuesta y lo registra en log.
- Para GET a `/ops/` registra un resumen de query params (period, desglose, park_id, recent_weeks, baseline_weeks, limit, offset) para detectar duplicados.
- Añade headers de respuesta: `X-Request-ID`, `X-Response-Time-Ms`.

**Objetivo:** Base de medición para comparar antes/después de optimizaciones y ver duplicados en logs.
