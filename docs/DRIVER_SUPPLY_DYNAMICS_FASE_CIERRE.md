# Driver Supply Dynamics — Cierre de mejoras estructurales (Fase maduración)

Documentación de la fase de cierre: segmentación configurable, refresh trazable, trend estructural, freshness en UI.

Véase también: [DRIVER_SUPPLY_DYNAMICS_MAPA_ARQUITECTURA.md](DRIVER_SUPPLY_DYNAMICS_MAPA_ARQUITECTURA.md).

---

## 1. Tabla de configuración de segmentos: `ops.driver_segment_config`

- **Migraciones:** `065_driver_segment_config_and_mv_rebuild.py` (tabla + función + MVs con función), `067_mv_driver_segments_weekly_join_config.py` (MV reconstruida por JOIN, sin llamada a función por fila).
- **Propósito:** Dejar de depender del `CASE` hardcodeado en SQL; la segmentación sale de una tabla versionable por fecha.

**Estructura:**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | SERIAL | PK |
| segment_code | TEXT | FT, PT, CASUAL, OCCASIONAL, DORMANT |
| segment_name | TEXT | Nombre legible |
| min_trips_week | INT | Cota inferior (inclusive) |
| max_trips_week | INT | Cota superior (inclusive); NULL = abierto |
| ordering | INT | Orden para comparación (5=FT … 1=DORMANT) |
| is_active | BOOLEAN | Vigente |
| effective_from | DATE | Vigencia desde |
| effective_to | DATE | Vigencia hasta (NULL = indefinido) |
| created_at, updated_at | TIMESTAMPTZ | Auditoría |

**Seed actual (comportamiento vigente):**

- FT: min 60, max NULL (≥60)
- PT: 20–59
- CASUAL: 5–19
- OCCASIONAL: 1–4
- DORMANT: 0 (min 0, max 0)

**Implementación final (desde migración 067):** La MV `ops.mv_driver_segments_weekly` **no** invoca la función por fila; hace un **JOIN directo** con `ops.driver_segment_config` para evitar coste row-by-row:

- Condiciones del JOIN: `c.is_active`, `c.effective_from <= s.week_start`, `(c.effective_to IS NULL OR c.effective_to >= s.week_start)`, `s.trips_completed_week >= c.min_trips_week`, `(c.max_trips_week IS NULL OR s.trips_completed_week <= c.max_trips_week)`.
- Se toma una sola fila de config por `(driver_key, week_start)` con `DISTINCT ON (s.driver_key, s.week_start) ... ORDER BY s.driver_key, s.week_start, c.ordering DESC` (el segmento de mayor `ordering` que aplica).

La función `ops.get_driver_segment(BIGINT, DATE)` se mantiene en BD por compatibilidad (p. ej. downgrade de 067); la MV desde 067 usa solo el JOIN.

---

## 2. Regla de trend (overview y composition)

- **Dónde:** `supply_service._add_rolling_and_trend()` (overview); composition en `get_supply_composition()`.
- **Regla documentada:**
  - Serie ordenada por periodo **descendente** (más reciente primero).
  - **Rolling 4w / 8w:** media de las últimas 4 u 8 observaciones (semanas).
  - **trend_direction:** se compara la media de las **últimas 4 semanas** con la media de las **4 semanas anteriores** (índices 0:4 vs 4:8). Si media(0:4) > media(4:8) → `up`; si menor → `down`; si igual → `flat`. Se requiere al menos 8 períodos; si no hay suficientes, `trend_direction` es `null`.
  - Shares (FT_share, weak_supply_share): solo se promedian filas con valor no nulo; si en una ventana hay menos de 4/8 valores, el rolling es `null`.

---

## 3. Estrategia de refresh y trazabilidad

- **Función BD:** `ops.refresh_supply_alerting_mvs()` hace REFRESH CONCURRENTLY de: `mv_driver_segments_weekly`, `mv_supply_segments_weekly`, `mv_supply_segment_anomalies_weekly`, `mv_supply_alerts_weekly`.
- **Backend:** `refresh_supply_alerting_mvs()` en `supply_service` llama a esa función y luego `log_supply_refresh_done("ok")` para registrar la corrida.
- **Tabla de log:** `ops.supply_refresh_log` (migración 066). Columnas: id, started_at, finished_at, status ('running'|'ok'|'error'), error_message, created_at.
- **Script:** `backend/scripts/run_supply_refresh_pipeline.py`:
  - Inserta una fila con status='running'.
  - Llama a `refresh_supply_alerting_mvs()`.
  - Actualiza la fila con finished_at, status='ok' (o 'error' y error_message).
  - Imprime freshness al final (last_week_available, last_refresh, status).
- **Programación:** No hay scheduler en repo; se puede programar el script vía cron (Linux) o Task Scheduler (Windows). Documentar en despliegue.

---

## 4. Freshness (endpoint y UI)

- **Endpoint:** `GET /ops/supply/freshness`. No requiere parámetros.
- **Respuesta:**
  - `last_week_available`: última semana presente en `ops.mv_supply_segments_weekly` (MAX(week_start)).
  - `last_refresh`: timestamp de la última fila en `ops.supply_refresh_log` con status='ok'.
  - `status`: `fresh` | `stale` | `unknown`.
- **Regla de status (final, basada en semana esperada):**
  - `expected_week` = lunes de la semana actual (floor_to_week(now), ISO: `today - timedelta(days=today.weekday())`).
  - **Fresh:** `last_week_available >= expected_week - 7 días` **y** `last_refresh >= ahora - 36 h`.
  - **Stale:** hay datos pero no se cumple lo anterior.
  - **Unknown:** falta last_week o last_refresh (p. ej. tabla de log no existe o sin corridas).

En la UI (Driver Supply Dynamics) se muestra una franja superior con: Última semana, Último refresh, Estado (Fresh / Stale / Unknown).

---

## 5. Campos nuevos en endpoints

### Migration (`GET /ops/supply/migration`)

Por fila, además de los existentes:

- **drivers_in_from_segment_previous_week:** conteo de conductores en `from_segment` la semana anterior (desde `ops.mv_supply_segments_weekly`, semana = week_start - 7 días).
- **migration_rate:** `drivers_migrated / drivers_in_from_segment_previous_week` cuando el denominador existe y es > 0; si no, `null`. Permite interpretar la magnitud real de la migración (p. ej. 0.05 = 5% del segmento de origen migró). No se crea MV nueva; se calcula en el servicio con un LEFT JOIN a la MV de segmentos.

### Overview enhanced (`GET /ops/supply/overview-enhanced`)

En `summary` (solo cuando grain=weekly):

- `rolling_4w_active_drivers`, `rolling_8w_active_drivers`
- `rolling_4w_trips`, `rolling_8w_trips`
- `rolling_4w_FT_share`, `rolling_8w_FT_share`
- `rolling_4w_weak_supply_share`, `rolling_8w_weak_supply_share`
- `trend_direction`: `up` | `down` | `flat` | null

### Composition (`GET /ops/supply/composition`)

Por fila (week_start, segment_week):

- `rolling_4w_drivers_count`, `rolling_8w_drivers_count`
- `trend_direction`: `up` | `down` | `flat` | null

### Alerts (`GET /ops/supply/alerts`)

Por fila:

- `baseline_window_weeks`: 8 (fijo).
- `current_vs_rolling_4w_delta`: null (no calculado).
- `current_vs_rolling_8w_delta`: mismo que `delta_pct` (vs baseline 8w).
- `trend_context`: `sustained_deterioration` | `abrupt_change` | `recovery` | `stable` (derivado de alert_type y |delta_pct|).
- `abrupt_change`: true si |delta_pct| ≥ 0.25.
- `sustained_deterioration`: true si alert_type = segment_drop.
- `recovery`: true si alert_type = segment_spike.
- `stable`: false en alertas.
- `weeks_in_same_direction`: null (sin historial multi-semana).

---

## 6. Validación (check script)

`backend/scripts/check_supply_driver_dynamics.py` comprueba:

- Existencia de `ops.driver_segment_config` y seed con al menos 5 segmentos.
- Existencia de las MVs: supply_weekly, supply_monthly, supply_segments_weekly, driver_segments_weekly, supply_segment_anomalies_weekly, supply_alerts_weekly.
- Unicidad esperada en `mv_driver_segments_weekly` (week_start, park_id, driver_key).
- Existencia de `ops.supply_refresh_log` (opcional; si no está, SKIP).
- Que la query de freshness (MAX week en segments) funcione.
- Conteo de filas en `mv_supply_segments_weekly` (park not null).
- **EXPLAIN ANALYZE** de `SELECT * FROM ops.mv_driver_segments_weekly LIMIT 1000`: se extrae *Execution Time* (ms). Si supera un umbral razonable (p. ej. 1000 ms en local), se emite **WARN** para revisar índices o uso de JOIN vs función. No hace fallar el check.

Salida: OK o FAIL; exit 0 solo si no hay FAIL (los WARN no cambian el exit code).
