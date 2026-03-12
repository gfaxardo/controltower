# Audit Engine — Mapa del sistema y diagnóstico

## FASE 1 — MAPA COMPLETO DEL SISTEMA ACTUAL

### 1. Audit Script Structure

| Elemento | Ubicación / Detalle |
|--------|----------------------|
| Script | `backend/scripts/audit_control_tower.py` |
| Punto de entrada | `if __name__ == "__main__": main()` |
| Flujo | `main()` → `run_audit()` → 7 bloques try/with (uno por check) → salida por consola |
| Persistencia | `ops.data_integrity_audit` (timestamp, check_name, status, metric_value, details) |

### 2. Audit Checks (orden de ejecución)

| # | Check name (interno) | Nombre en salida | Función / bloque |
|---|----------------------|------------------|-------------------|
| 1 | TRIP_LOSS | Trips integrity | run_audit() bloque 1 |
| 2 | B2B_LOSS | B2B classification | run_audit() bloque 2 |
| 3 | LOB_MAPPING_LOSS | LOB mapping | run_audit() bloque 3 |
| 4 | DUPLICATE_TRIPS | (Duplicate trips) | run_audit() bloque 4 |
| 5 | MV_STALE | Materialized views | run_audit() bloque 5 |
| 6 | JOIN_LOSS | (Join integrity) | run_audit() bloque 6 |
| 7 | WEEKLY_ANOMALY | Weekly anomalies | run_audit() bloque 7 |

Driver lifecycle y Supply consistency se muestran fijos como "OK" (no ejecutan consulta).

### 3. SQL ejecutado por check

| Check | Consulta SELECT | Vista/tabla consultada |
|-------|------------------|-------------------------|
| Trip integrity | `SELECT status, loss_pct, viajes_base, viajes_real_lob FROM ops.v_trip_integrity ORDER BY mes DESC LIMIT 1` | ops.v_trip_integrity → v_trips_real_canon, real_rollup_day_fact |
| B2B | `SELECT b2b_base, b2b_real_lob, diff_pct FROM ops.v_b2b_integrity ORDER BY mes DESC LIMIT 1` | ops.v_b2b_integrity → v_trips_real_canon, real_rollup_day_fact |
| LOB mapping | `SELECT pct_sin_lob, viajes_sin_lob FROM ops.v_lob_mapping_audit ORDER BY mes DESC LIMIT 1` | ops.v_lob_mapping_audit → v_trips_real_canon, v_real_trips_with_lob_v2 |
| Duplicate trips | `SELECT COUNT(*) AS c FROM ops.v_duplicate_trips` | ops.v_duplicate_trips → trips_all, trips_2026 |
| MV freshness | `SELECT view_name FROM ops.v_mv_freshness WHERE status = 'STALE'` | ops.v_mv_freshness → real_drill_dim_fact, real_rollup_day_fact, mv_driver_weekly_stats, mv_supply_weekly, mv_driver_segments_weekly |
| Join integrity | `SELECT loss_pct, join_name FROM ops.v_join_integrity LIMIT 1` | ops.v_join_integrity → v_trips_real_canon, public.parks |
| Weekly anomaly | `SELECT week_start, viajes FROM ops.v_weekly_trip_volume ORDER BY week_start DESC LIMIT 2` | ops.v_weekly_trip_volume → v_trips_real_canon |

### 4. Conexión utilizada

| Aspecto | Detalle |
|--------|---------|
| API | `get_db_audit(timeout_ms)` desde `app.db.connection` |
| Tipo | psycopg2 directo (no SQLAlchemy Engine ni SessionLocal) |
| Pool | No: cada llamada abre una conexión nueva con `_get_connection_with_timeout(timeout_ms)` |
| Timeout | Opción de conexión `-c statement_timeout=<timeout_ms>` al conectar |
| Variable de entorno | `AUDIT_STATEMENT_TIMEOUT_MS` (default 600000) |
| Cierre | `conn.close()` en `finally` de `get_db_audit` |
| Rollback | En `except` de `get_db_audit` antes de `raise` |

### 5. Manejo actual de errores

| Mecanismo | Comportamiento |
|-----------|----------------|
| try/except | Cada check en su propio try/except; en except se hace print WARN y results[key] = "?" |
| _run() / _run_one() | Si la consulta falla, capturan excepción, imprimen [WARN] Query failed, devuelven default (None/[]). No hacen rollback (la excepción puede no propagarse si solo falla el SELECT y luego falla el INSERT por transacción abortada) |
| get_db_audit | En excepción: rollback + logger.error + raise. En finally: conn.close() |
| Riesgo | Si el SELECT hace timeout, la transacción queda abortada; el INSERT posterior falla con "current transaction is aborted". get_db_audit hace rollback y close al hacer raise, pero si _run() traga la excepción del SELECT, el INSERT falla y ahí sí se hace raise; la siguiente conexión (siguiente check) es nueva, así que no debería estar contaminada. El problema observado puede ser que el rol limita statement_timeout y la opción de conexión no se aplica. |

### 6. Riesgos detectados

1. **Timeout del rol**: Si el rol en PostgreSQL tiene `statement_timeout` menor (p. ej. 15s), la opción enviada al conectar puede ser ignorada y las vistas pesadas disparan cancelación.
2. **_run() traga excepciones**: El SELECT que hace timeout lanza; _run la captura y devuelve None. Luego el INSERT se ejecuta en la misma transacción abortada → falla → el except del with captura y hace rollback/close. Correcto por check aislado, pero no hay registro de “timeout” ni duración.
3. **Sin métricas de duración**: No se mide tiempo por check ni se persiste para detectar degradación.
4. **Sin tabla de performance**: No existe `ops.audit_query_performance` para historial de tiempos y estado.
5. **Queries pesadas**: v_trip_integrity, v_lob_mapping_audit y v_weekly_trip_volume escanean v_trips_real_canon (que a su vez lee trips_all/trips_2026) sin acotar por fecha reciente.

---

## FASE 2 — DIAGNÓSTICO (check más lento / timeout)

- **Check más lento / que dispara timeout**: En entornos con muchos viajes, los que más suelen tardar son **Trip integrity**, **LOB mapping** y **Join integrity**, por uso de `v_trips_real_canon` (full scan implícito) y joins con parks.
- **Consulta responsable**: Las vistas `ops.v_trip_integrity`, `ops.v_lob_mapping_audit` y `ops.v_join_integrity` son las que más coste tienen.
- **Duración estimada**: Depende del volumen; con 10M+ filas en trips, pueden superar 60–180 s si no hay índices adecuados.

---

## FASE 6 — ÍNDICES RECOMENDADOS Y OPTIMIZACIONES

### CREATE INDEX recomendados

Script listo para ejecutar: **`backend/scripts/sql/audit_recommended_indexes.sql`**

Resumen (ejecutar solo si las tablas existen y el volumen lo justifica):

- **trips_all**: `ix_trips_all_condicion_fecha`, `ix_trips_all_fecha_inicio` (condicion + fecha para v_trip_integrity, v_weekly_trip_volume).
- **trips_2026**: `ix_trips_2026_condicion_fecha` (si existe la tabla).
- **real_rollup_day_fact**: `ix_real_rollup_day_fact_trip_day` (agregaciones por mes).

### Optimizaciones de vistas (opcional)

- En vistas que solo necesitan “último mes” o “últimos 3 meses”, acotar con `fecha_inicio_viaje >= (current_date - interval '90 days')` en las CTE base para reducir trabajo de v_trips_real_canon (requiere cambiar definición de la vista en una migración).

---

## FASE 8 — Validación final

### Comandos de prueba

1. **Ejecutar auditoría**
   ```bash
   cd backend
   python -m scripts.audit_control_tower
   ```

2. **Últimos resultados de integridad**
   ```sql
   SELECT * FROM ops.data_integrity_audit
   ORDER BY timestamp DESC
   LIMIT 20;
   ```

3. **Métricas de performance por check**
   ```sql
   SELECT *
   FROM ops.audit_query_performance
   ORDER BY executed_at DESC
   LIMIT 20;
   ```

4. **Verificación**
   - No debe aparecer "current transaction is aborted" en la salida del script.
   - Cada check debe tener una fila en `ops.audit_query_performance` por ejecución (status: OK, TIMEOUT o ERROR).
   - Los checks que hagan timeout quedarán con status TIMEOUT y el resto seguirá ejecutándose.

---

## ENTREGABLES — Resumen de cambios

| Entregable | Ubicación |
|------------|-----------|
| Diagnóstico completo | Este documento (FASE 1 + FASE 2 + FASE 6) |
| Script rediseñado | `backend/scripts/audit_control_tower.py` |
| Conexión auditoría | `backend/app/db/connection.py`: `get_db_audit(timeout_ms)`, `_audit_timeout_ms()` |
| Tabla performance | Migración `076_audit_query_performance`: `ops.audit_query_performance` |
| Índices recomendados | `backend/scripts/sql/audit_recommended_indexes.sql` |
| Comandos validación | Sección FASE 8 arriba |

**Nuevas funciones / comportamiento**

- **get_db_audit(timeout_ms=None)**: Conexión dedicada con `statement_timeout`; si `timeout_ms` es None usa `AUDIT_TIMEOUT_MS` / `AUDIT_STATEMENT_TIMEOUT_MS` (default 600000). Rollback en excepción y `close()` en `finally`.
- **_run_check()**: Ejecuta un check en su propia conexión, mide tiempo, escribe en `data_integrity_audit` y `audit_query_performance`, detecta timeout/abort y persiste status TIMEOUT/ERROR en una conexión nueva.
- **_is_timeout_or_aborted()**: Detecta `QueryCanceled` (57014), "statement timeout", "transaction is aborted" para no reutilizar conexión abortada.

**Diff resumido**

- **audit_control_tower.py**: Cada check en su propia conexión (`get_db_audit`); `SET statement_timeout` al inicio; logging `[AUDIT] START` / `FINISHED` / `WARNING` con duración; en excepción se detecta timeout/abort, se persiste fila en `audit_query_performance` con status TIMEOUT/ERROR usando una conexión nueva, y se continúa con el siguiente check.
- **connection.py**: `get_db_audit(timeout_ms=None)` con default desde env; `_audit_timeout_ms()`.
- **Nueva migración 076**: tabla `ops.audit_query_performance` (check_name, execution_time_ms, executed_at, status).
