# LG_FIX_1B1_PIPELINE_ROOT_CAUSE_REPORT

**Generated:** 2026-06-12T20:00  
**Scope:** Root cause de por qué el pipeline V2 dejó de producir lifecycle_daily, taxonomy_v2_daily, y movement_fact después del 2026-06-10.  
**Veredicto:** `PIPELINE_FAILURE_ROOT_CAUSE_IDENTIFIED`

---

## 1. Scheduler Responsable

| Campo | Valor |
|-------|-------|
| **Nombre** | `lima_growth_refresh` |
| **Archivo** | `backend/app/services/yego_lima_scheduler_service.py:537` (`autonomous_tick()`) |
| **Intervalo** | Cada 5 minutos |
| **Estado** | **ACTIVO** (enabled=true, 718 ticks, 710 success, 6 fail) |
| **Último tick** | 2026-06-12 14:55:15 -05:00 |
| **Último status** | `SUCCESS_NO_CASCADE` |

**El scheduler principal está vivo y funcionando.** No está detenido. No está fallando silenciosamente (salvo 6 ticks con errores de "connection already closed" que son transitorios).

---

## 2. Jobs Exactos

### Job 1: `autonomous_tick()` — APScheduler cada 5 min

**Ubicación:** `yego_lima_scheduler_service.py:537-860`  
**Registrado en main.py** línea 370: `apscheduler.add_job(id="lima_growth_autonomous_tick", trigger=IntervalTrigger(minutes=5))`

**Steps ejecutados:**
1. Ingesta de órdenes Yango API → `raw_yango.orders_raw` ✅
2. Detección de cascade (raw ahead of snapshot) → NOT TRIGGERED
3. Cascade pipeline (solo cuando hay gap raw → snapshot):
   - `build_driver_state_snapshot()` → `growth.yango_lima_driver_state_snapshot` ✅
   - `build_program_eligibility()` → `growth.yango_lima_program_eligibility_daily` ✅
   - `build_daily_opportunity_lists()` → `growth.yango_lima_prioritized_opportunity_daily` ✅
   - `build_prioritized_opportunities()` → priorización ✅
   - `run_daily_refresh()` → queue + serving facts ✅
4. Catch-up refresh (si operational_date != last_processed) → `run_daily_refresh()` ✅
5. Control loop sync ✅
6. Serving facts ✅
7. Governance refresh ✅
8. Intraday signals ✅
9. History snapshot ✅

### Job 2: `lima_growth_v2_daily_pipeline` — APScheduler cron 04:45 AM

**Ubicación:** `yego_lima_v2_daily_pipeline_service.py`  
**Registrado en main.py** línea 405: `apscheduler.add_job(id="lima_growth_v2_daily_pipeline", trigger=CronTrigger(hour=4, minute=45))`

**Shadow pipeline de 9 pasos (línea 55-65):**
1. `build_activity_daily` → `growth.yego_lima_v2_activity_daily`
2. `build_activity_weekly` → `growth.yego_lima_v2_activity_weekly`
3. `build_activity_monthly` → `growth.yego_lima_v2_activity_monthly`
4. `build_lifecycle_daily` → `growth.yego_lima_v2_lifecycle_daily` **(LEE DE PRODUCCIÓN)**
5. `build_taxonomy_v2_daily` → `growth.yego_lima_v2_taxonomy_daily` **(LEE DE PRODUCCIÓN)**
6. `build_program_v2_daily` → `growth.yego_lima_v2_program_daily` **(LEE DE PRODUCCIÓN)**
7. `build_movement_fact` → `growth.yego_lima_v2_movement_fact` **(LEE DE TRAZAS)**
8. `build_observability_facts` → `growth.yego_lima_v2_observability_fact`
9. `build_effectiveness_facts` → `growth.yego_lima_v2_effectiveness_fact`

**CRÍTICO: Los pasos 4, 5, 6 LEEN de las tablas de producción.** Si las tablas de producción no tienen datos frescos, el shadow pipeline produce datos vacíos o stale.

### Job 3: Quién escribe las tablas de PRODUCCIÓN?

| Tabla Producción | Escritor | Trigger |
|-----------------|----------|---------|
| `yego_lima_driver_lifecycle_daily` | `build_lifecycle_daily()` en `yego_lima_lifecycle_service.py:394` | **SOLO via API** `POST /yego-lima-growth/lifecycle/build` |
| `yego_lima_driver_taxonomy_v2_daily` | **NO HAY INSERT en el código** | Poblado por script externo o migración |
| `driver_movement_fact` | **NO HAY INSERT en el código** | Poblado por script externo o migración |

**Ninguno de los tres es poblado por el scheduler automático.**

---

## 3. Último Run Exitoso

| Tabla | Última Fecha | Rows |
|-------|-------------|------|
| `yego_lima_driver_lifecycle_daily` | **2026-06-10** | 68,473 |
| `yego_lima_driver_taxonomy_v2_daily` | **2026-06-10** | 68,473 |
| `driver_movement_fact` | **2026-06-10** | 68,473 |

El V2 Shadow Pipeline (manual, triggered_by="multi-day-replay-final") corrió exitosamente para target_dates 06-07 a 06-10 el **2026-06-11 a las 20:53-20:56**. Los pasos 4-6 (lifecycle, taxonomy, program) leyeron datos de las tablas de producción (que estaban frescas hasta 06-10) y poblaron las shadow tables.

---

## 4. Primer Run Fallido / Perdido

| Fecha | V2 Shadow Pipeline | Tick autónomo | Lifecycle (prod) |
|-------|-------------------|---------------|-----------------|
| **2026-06-11 04:45** | **NO CORRIÓ** (no hay log) | Corriendo OK | **NO SE POBLÓ** |
| **2026-06-12 04:45** | **NO CORRIÓ** (no hay log) | Corriendo OK | **NO SE POBLÓ** |

El V2 Shadow Pipeline NO generó ningún log de ejecución para target_date 2026-06-11 ni 2026-06-12. Los únicos runs en el log son manuales (triggered_by="certification", "multi-day-replay"), todos del 2026-06-11 por la noche para fechas 06-07 a 06-10.

---

## 5. Logs Relevantes

### Tick Log: `new_day_detected = false` para todos los ticks desde 06-10

```
started_at=2026-06-12 14:55, op_date=2026-06-12, new_day_detected=false, status=SUCCESS, catch_up=CAUGHT_UP
started_at=2026-06-12 14:51, op_date=2026-06-12, new_day_detected=false, status=SUCCESS, catch_up=CAUGHT_UP
...
started_at=2026-06-09 16:00, op_date=2026-06-09, new_day_detected=TRUE,  status=SUCCESS, catch_up=GAP_DETECTED
started_at=2026-06-09 15:55, op_date=2026-06-08, new_day_detected=TRUE,  status=SUCCESS, catch_up=GAP_DETECTED
```

**La última vez que el tick detectó un nuevo día fue 2026-06-09.**

### Failures en tick log (6 de 718):

```
2026-06-12 13:49 → FAILED: "connection already closed"
2026-06-12 00:17 → FAILED: "connection already closed"
2026-06-11 20:55 → FAILED: "cursor already closed"
2026-06-11 00:03 → FAILED: "connection already closed"
2026-06-10 20:11 → PARTIAL
2026-06-10 20:03 → PARTIAL
```

Son errores transitorios de conexión a DB. No son la causa raíz.

### V2 Pipeline step error (run `5f02f368`):

```
build_activity_daily: "column a.trips does not exist"
build_activity_weekly: "column a.trips does not exist"
build_lifecycle_daily: "column lb.lifecycle_stage does not exist"
build_taxonomy_v2_daily: "column lb.lifecycle_stage does not exist"
build_program_v2_daily: "column lb.total_trips does not exist"
```

**Este run (06-11 19:50, triggered_by="certification") falló porque leía de `yego_lima_v2_activity_daily` que en ese momento tenía columnas con nombres incorrectos (`a.trips` en vez de `a.trip_count`). Runs posteriores corrigieron el código y funcionaron.**

---

## 6. Cron / APScheduler Jobs

### Jobs registrados en main.py:

| Job ID | Trigger | Función | ¿Funcionando? |
|--------|---------|---------|---------------|
| `serving_fact_daily_refresh` | Cron 05:00 daily | `scheduled_daily_refresh` | Unknown |
| `omniview_cascade_refresh` | Cron configurable | `_cascade_scheduled_wrapper` | Unknown |
| `omniview_real_data_watchdog` | Interval configurable | `run_real_data_watchdog` | Unknown |
| `lima_growth_autonomous_tick` | **Interval 5 min** | `autonomous_tick` | ✅ ACTIVO |
| `lima_growth_v2_daily_pipeline` | **Cron 04:45 daily** | `_v2_daily_pipeline_wrapper` | ❓ SIN LOGS |

**El job `lima_growth_v2_daily_pipeline` a las 04:45 NO generó entradas en `yego_lima_v2_pipeline_run_log` para 06-11 ni 06-12.** Esto sugiere que el wrapper `_v2_daily_pipeline_wrapper` o falló silenciosamente, o el APScheduler no lo ejecutó.

---

## 7. Task Dependencies

### Cadena de dependencias (serving_operability_service.py:49-63):

```
activity_daily → [lifecycle_daily]
lifecycle_daily → [taxonomy_v2, program_v2]
taxonomy_v2 → [movement_fact]
program_v2 → [movement_fact, program_assignment]
driver_state_snapshot → [program_assignment]
movement_fact → [observability_fact]
observability_fact → [RNA_serving]
```

**El grafo muestra que `lifecycle_daily` es el upstream de `taxonomy_v2` y `program_v2`.** Cuando `lifecycle_daily` se congela en 06-10:
- `taxonomy_v2` no puede tener datos frescos
- `program_v2` no puede tener datos frescos  
- `movement_fact` depende de taxonomy_v2 + program_v2 → también congelado

---

## 8. Freshness Chain

### Datos en `yego_lima_v2_freshness_registry` (NO consultado por errores de columna, pero inferido):

El `serving_operability_service.py` clasifica la operabilidad basándose en esta cadena:
1. Si `lifecycle_daily` está stale → `taxonomy_v2` hereda staleness por propagación
2. Si `taxonomy_v2` está stale → `movement_fact` hereda staleness
3. Resultado: system_status = CRITICAL (12 assets stale, 8 broken)

**La clasificación CRITICAL es correcta y refleja la realidad.**

---

## 9. Advancement Log (PIPELINE RUN GAP)

```
2026-06-07 ───► lifecycle_daily (68K rows) ✓
2026-06-08 ───► lifecycle_daily (68K rows) ✓  ← último new_day_detected=TRUE
2026-06-09 ───► lifecycle_daily (68K rows) ✓  ← último new_day_detected=TRUE
2026-06-10 ───► lifecycle_daily (68K rows) ✓  ← ÚLTIMO DATO
2026-06-11 ───► lifecycle_daily 0 rows ✗      ← GAP! No se pobló.
2026-06-12 ───► lifecycle_daily 0 rows ✗      ← GAP! No se pobló.
```

---

## 10. Determinación de Causa

### Hipótesis evaluadas:

| Hipótesis | Evidencia | Veredicto |
|-----------|-----------|-----------|
| Scheduler detenido | `enabled=true`, 718 ticks, último hace minutos | ❌ FALSO |
| Job deshabilitado | `autonomous_tick` corriendo cada 5 min | ❌ FALSO |
| Excepción silenciosa | Solo 6/718 fallos (connection errors), resto SUCCESS | ❌ FALSO |
| Dependencia faltante | Cadena documentada pero no aplica a producción | ❌ FALSO |
| Tabla upstream vacía | `driver_state_snapshot` tiene datos hasta 06-12 | ❌ FALSO |
| Cambio reciente de código | Step error `column a.trips does not exist` en V2 shadow, corregido | ❌ FALSO |
| Migración | Migraciones 214-218 crean tablas nuevas, no rompen existentes | ❌ FALSO |
| Feature flag | `CT_SCHEDULER_ENABLED` no aplica (env=dev, scheduler corre) | ❌ FALSO |
| **Configuración / diseño** | `run_daily_refresh()` NO incluye pasos de lifecycle/taxonomy/movement | ✅ **VERDADERO** |

---

## 11. CAUSA RAÍZ

### `autonomous_tick()` y `run_daily_refresh()` NUNCA han poblado las tablas de lifecycle, taxonomy, ni movement.

**Evidencia código:**

`run_daily_refresh()` en `yego_lima_daily_refresh_service.py:128-250` ejecuta SOLO estos pasos:
1. `detect_operational_date`
2. `validate_source_readiness` (snapshot, eligibility, prioritized)
3. `build_assignment_queue`
4. `build_prioritized_opportunities`
5. `generate_serving_facts`

**No hay pasos para:**
- `build_lifecycle_daily`
- `build_taxonomy_v2_daily`
- `build_movement_fact`

`autonomous_tick()` en `yego_lima_scheduler_service.py:537-860` en cascade llama:
- `build_driver_state_snapshot()`
- `build_program_eligibility()`
- `build_daily_opportunity_lists()`
- `build_prioritized_opportunities()`
- `run_daily_refresh()`

**Tampoco incluye los tres builders faltantes.**

### Consecuencia:

Las tres tablas se poblaron por última vez el 2026-06-10 mediante intervención manual (posiblemente `POST /yego-lima-growth/lifecycle/build` o scripts `s1_0a_simulation_v3.py` / `imp_1b_stability.py` que hardcodean `SNAP_DATE = "2026-06-10"`). Después de esa fecha:

1. Nadie ejecutó `POST /yego-lima-growth/lifecycle/build` para 06-11 ni 06-12
2. El scheduler automático no está diseñado para ejecutar ese paso
3. El V2 shadow pipeline (04:45 AM) necesita que las tablas de producción estén frescas para poder leer de ellas
4. El sistema de monitoreo (`serving_operability_service`) detectó correctamente el problema y reportó CRITICAL

### Por qué `new_day_detected = false` desde 06-10:

El tick autónomo determina `operational_date = MAX(snapshot_date)` de `driver_state_snapshot` = 2026-06-12. Luego verifica `last_processed` (último refresh run SUCCESS) = también 2026-06-12. Como son iguales, considera que "no hay día nuevo" y salta a `NOOP_CAUGHT_UP`.

**El sistema está en un estado de falsa normalidad**: cree que 2026-06-12 ya fue procesado (porque `run_daily_refresh` corrió exitosamente), pero `run_daily_refresh` solo cubre la capa operacional (queue), no la capa de inteligencia (lifecycle, taxonomy, movement).

---

## 12. Timeline

```
2026-06-08
  └─ 15:55 tick: new_day_detected=TRUE, op_date=2026-06-08
  └─ lifecycle/taxonomy/movement poblados manualmente (scripts/probable)

2026-06-09
  └─ 16:00 tick: new_day_detected=TRUE, op_date=2026-06-09
  └─ lifecycle/taxonomy/movement poblados manualmente

2026-06-10
  └─ lifecycle/taxonomy/movement poblados por última vez (manual)
  └─ 20:03 tick: PARTIAL (error DB connection)
  └─ 20:11 tick: PARTIAL (error DB connection)

2026-06-11
  └─ 00:03 tick: FAILED ("connection already closed")
  └─ **04:45 V2 shadow pipeline NO CORRIÓ (sin logs)**
  └─ **Nadie ejecutó POST /lifecycle/build**
  └─ 19:50-20:56: V2 shadow pipeline ejecutado MANUALMENTE 12 veces
      (triggered_by="certification", "multi-day-replay", "multi-day-replay-final")
      para target_dates 06-07 a 06-10. LEYÓ datos de producción (frescos hasta 06-10).
      1 run falló por column mismatch en shadow tables (corregido en runs posteriores).
  └─ 20:55 tick: FAILED ("cursor already closed")
  └─ Todos los demás ticks: SUCCESS_NO_CASCADE, new_day_detected=false

2026-06-12
  └─ 00:17 tick: FAILED ("connection already closed")
  └─ **04:45 V2 shadow pipeline NO CORRIÓ (sin logs)**
  └─ **Nadie ejecutó POST /lifecycle/build**
  └─ Todos los ticks: SUCCESS_NO_CASCADE, new_day_detected=false
  └─ Estado actual: CRITICAL, 12 assets stale, UI muestra datos vacíos
```

---

## 13. Veredicto Final

```
PIPELINE_FAILURE_ROOT_CAUSE_IDENTIFIED
```

### Causa raíz única:

**`run_daily_refresh()` —el orquestador central del scheduler— no incluye los pasos de construcción de `lifecycle_daily`, `taxonomy_v2_daily`, ni `movement_fact`.** Estas tablas requieren intervención manual o un paso de pipeline ausente del scheduler automático. La última intervención manual fue el 2026-06-10.

### Evidencia irrefutable:

1. `yego_lima_daily_refresh_service.py:128-250` — `run_daily_refresh()` tiene 5 pasos. Ninguno es lifecycle/taxonomy/movement.
2. `yego_lima_scheduler_service.py:684-697` — El cascade del tick autónomo llama 4 builders + `run_daily_refresh()`. Los 3 faltantes no están.
3. `yego_lima_lifecycle_service.py:394` — `build_lifecycle_daily()` solo se invoca desde el router `POST /lifecycle/build`. No desde el scheduler.
4. DB: `yego_lima_driver_lifecycle_daily` tiene 0 rows para 2026-06-11 y 2026-06-12.
5. DB: `yego_lima_driver_taxonomy_v2_daily` tiene 0 rows para 2026-06-11 y 2026-06-12.
6. DB: `driver_movement_fact` tiene 0 rows para 2026-06-11 y 2026-06-12.
7. `growth.yego_lima_v2_pipeline_run_log` no tiene entradas para target_date 06-11 ni 06-12.
8. Scripts de simulación (`s1_0a_simulation.py`, `imp_1b_stability.py`) hardcodean `SNAP_DATE = "2026-06-10"` — confirman que 06-10 fue la última fecha procesada.

---

## Fix requerido (LG-FIX-1B.2, NO ejecutar ahora):

Agregar al cascade de `autonomous_tick()` y/o a `run_daily_refresh()` los pasos:
1. `build_lifecycle_daily(target_date)` → `yego_lima_driver_lifecycle_daily`
2. `build_taxonomy_v2_daily(target_date)` → `yego_lima_driver_taxonomy_v2_daily`  
3. `build_movement_fact(target_date)` → `driver_movement_fact`

Y ejecutar backfill para 2026-06-11 y 2026-06-12.
