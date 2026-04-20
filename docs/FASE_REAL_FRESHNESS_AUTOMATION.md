# FASE — Freshness y automatización del REAL (Omniview Matrix)

## 1. Fuente REAL por grano (Omniview / Vs Proyección)

| Grano   | Tabla / objeto                         | Notas |
|---------|----------------------------------------|--------|
| Monthly | `ops.real_business_slice_month_fact`   | Carga incremental mensual (loader distinto). |
| Weekly  | `ops.real_business_slice_week_fact`    | Poblada por `load_business_slice_week_for_month` (rollup desde `ops.v_real_trips_business_slice_resolved`). |
| Daily   | `ops.real_business_slice_day_fact`     | Poblada por `load_business_slice_day_for_month` (materializa enriched + resolución). |

**No** se lee `bi.real_daily_enriched` directamente en la matriz slice: el pipeline materializa en las tablas `ops.real_business_slice_*_fact`.

**Causa típica de “corte en domingo”**: `MAX(trip_date)` en `day_fact` (y por extensión semanas incompletas en `week_fact`) quedaba viejo porque **el job de recarga no corría** tras el fin de semana. Los viajes pueden existir en raw/resuelto, pero las **facts pre-agregadas** no se habían vuelto a calcular.

## 2. Scheduler previo en el repo

- **No** había un scheduler dentro del proceso FastAPI para business slice day/week.
- Existen **scripts** sueltos (`scripts/backfill_business_slice_daily.py`, refrescos de MVs en `scripts/refresh_*.py`) pensados para **cron / ejecución manual**, no acoplados al arranque de la API.
- **Diagnóstico**: la automatización de **day_fact + week_fact** operativa para Omniview **no estaba garantizada** salvo que operaciones programara cron o ejecutara backfills.

## 3. Qué se implementó

1. **Servicio de freshness (upstream + agregado)**  
   - `app/services/business_slice_real_freshness_service.py` — `build_omniview_real_freshness_payload()`  
   - `app/services/upstream_real_status_service.py` — `get_upstream_real_status(conn)` (tabla configurable o modo `canon` → `ops.v_trips_real_canon`)  
   - Endpoint: `GET /ops/business-slice/real-freshness`  
   - Devuelve `upstream`, `aggregated` (day/week/month facts + `status` solo agregado), `status` global (**peor** entre upstream y agregado), `lag_days`, `lag_days_upstream`, `lag_days_aggregated`, `last_refresh_at`, `next_scheduled_run`, `next_watchdog_run`, y claves legacy en raíz (`day_fact`, `overall_status`, `lag_days_vs_today`, …).

2. **Job operacional de refresh**  
   - `app/services/business_slice_real_refresh_job.py`  
   - Recalcula **day_fact + week_fact** para **mes anterior y mes en curso** (cubre semanas que cruzan meses).  
   - Logs `REAL_REFRESH START/END`, preflight upstream + `before_max_trip_date`; **no ejecuta** si upstream `empty`; **cooldown** `OMNIVIEW_REAL_REFRESH_MIN_INTERVAL_MINUTES` salvo `force=True` (POST `?force=true`, CLI `--force`).

3. **Endpoints**  
   - `POST /ops/business-slice/real-refresh-omniview` — dispara el job (`?force=true` ignora cooldown).  
   - `GET /ops/business-slice/real-freshness` — estado para UI y alertas.

4. **APScheduler**  
   - Dependencia: `apscheduler>=3.10.0`  
   - `app/main.py`: scheduler si `OMNIVIEW_REAL_REFRESH_ENABLED` **o** `OMNIVIEW_REAL_WATCHDOG_ENABLED`.  
   - Refresh: intervalo `OMNIVIEW_REAL_REFRESH_INTERVAL_MINUTES` (mín. 15).  
   - Watchdog: `app/services/real_data_watchdog_service.py` — `run_real_data_watchdog()` cada `OMNIVIEW_REAL_WATCHDOG_INTERVAL_MINUTES`; log `REAL DATA STALE` si lag agregado > 2; **auto-recovery**: si upstream `fresh` y agregado `stale`/`critical`, llama al refresh (respeta cooldown); webhook opcional `REAL_FRESHNESS_ALERT_WEBHOOK`.  
   - `app/omniview_real_scheduler_info.py` expone `next_scheduled_run` / `next_watchdog_run` en el GET freshness.  
   - **Multi-worker**: con varios procesos uvicorn/gunicorn cada uno podría levantar scheduler; en producción usar un solo worker para el API que ejecute jobs o desactivar scheduler en réplicas secundarias.

5. **CLI**  
   - `python -m scripts.refresh_omniview_real_slice` / `--force`  
   - `python -m scripts.check_real_freshness` / `--fail-on critical empty`

6. **UI**  
   - Omniview Matrix (grano semanal/diario): banner informativo (🟢/🟡/🔴) según `status` global; línea extra si la fuente upstream no está `fresh`.

## 4. Variables de entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `OMNIVIEW_REAL_REFRESH_ENABLED` | `false` | Programa job de refresh. |
| `OMNIVIEW_REAL_REFRESH_INTERVAL_MINUTES` | `60` | Intervalo refresh (mín. 15). |
| `OMNIVIEW_REAL_REFRESH_MIN_INTERVAL_MINUTES` | `15` | Cooldown mínimo entre corridas (manual/scheduler/watchdog). |
| `OMNIVIEW_REAL_WATCHDOG_ENABLED` | `false` | Programa watchdog + auto-recovery. |
| `OMNIVIEW_REAL_WATCHDOG_INTERVAL_MINUTES` | `15` | Intervalo watchdog. |
| `OMNIVIEW_UPSTREAM_MODE` | `table` | `table` o `canon`. |
| `OMNIVIEW_UPSTREAM_TRIPS_TABLE` | `public.trips_2026` | Tabla para MAX(fecha) en modo table. |
| `OMNIVIEW_UPSTREAM_DATE_COLUMN` | `fecha_inicio_viaje` | Columna de fecha. |
| `OMNIVIEW_UPSTREAM_RECENT_DAYS` | `7` | Ventana para `row_count_recent`. |
| `REAL_FRESHNESS_ALERT_WEBHOOK` | vacío | POST JSON opcional en alertas. |
| `OMNIVIEW_REAL_REFRESH_TIMEOUT_MS` | `1800000` | Timeout SQL (30 min). |
| `OMNIVIEW_REAL_FRESH_LAG_STALE_DAYS` | `1` | Umbral “stale” en **agregado** (facts). |
| `OMNIVIEW_REAL_FRESH_LAG_CRITICAL_DAYS` | `2` | Umbral “critical” en **agregado**. |

## 5. Cómo correr el refresh manualmente

```bash
cd backend
python -m scripts.refresh_omniview_real_slice
python -m scripts.refresh_omniview_real_slice --force
python -m scripts.check_real_freshness
```

O vía HTTP (tras desplegar API):

```http
POST /ops/business-slice/real-refresh-omniview
POST /ops/business-slice/real-refresh-omniview?force=true
```

## 6. Cómo ver freshness

```http
GET /ops/business-slice/real-freshness
```

También existe el meta ligero `slice_max_trip_date` vía loaders de matriz; el nuevo endpoint es el contrato completo para operación.

## 7. Si queda `stale` o `critical`

1. Comprobar que el ETL/raw (`trips_all` / vistas enriched) tenga fechas recientes.  
2. Ejecutar el refresh manual o activar el scheduler.  
3. Revisar logs: `omniview_real_refresh_job START/END` y errores por mes.  
4. Si el job falla por timeout, subir `OMNIVIEW_REAL_REFRESH_TIMEOUT_MS` o ejecutar `scripts/backfill_business_slice_daily.py` por rango.

## 8. Criterio de éxito operativo

- `GET /ops/business-slice/real-freshness` → `day_fact.max_trip_date` cercano a “hoy” (según SLA de ingesta).  
- Semana en curso en Vs Proyección / Matrix muestra días recientes **después** de un refresh exitoso.  
- Producción: `OMNIVIEW_REAL_REFRESH_ENABLED=true` y/o cron llamando al CLI o al POST.
