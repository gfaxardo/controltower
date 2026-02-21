# Real LOB: Materialized Views y refresh

La vista **Real LOB** (observabilidad de viajes REAL por LOB, mensual/semanal) consume datos desde **Materialized Views** para responder en menos de 2 segundos.

## Tablas involucradas

- **ops.mv_real_trips_by_lob_month**: agregado mensual (country, city, lob_name, month_start, trips, revenue).
- **ops.mv_real_trips_by_lob_week**: agregado semanal (country, city, lob_name, week_start, trips, revenue).

Se crean con la migración Alembic **042_real_lob_materialized_views**.

## Cómo refrescar las MVs

Desde el directorio **backend/** del proyecto:

```bash
python -m scripts.refresh_real_lob_mvs
```

o:

```bash
python scripts/refresh_real_lob_mvs.py
```

El script ejecuta `REFRESH MATERIALIZED VIEW CONCURRENTLY` sobre ambas MVs (no bloquea lecturas). Timeout de la operación: 10 minutos.

## Frecuencia recomendada

- **Recomendado:** una vez al día (por ejemplo a las 02:00), después de que haya corrido la ingesta de datos reales.
- Si los datos reales se actualizan varias veces al día, ejecutar el refresh tras cada ingesta relevante.
- En desarrollo, ejecutar el refresh tras cargar nuevos datos en `trips_all` o tras cambiar `canon.map_real_to_lob`.

## Programación (opcional)

Si el proyecto tiene un scheduler (Celery, cron, etc.), registrar un job diario que ejecute:

```bash
cd /ruta/al/backend && python -m scripts.refresh_real_lob_mvs
```

Ejemplo crontab (todos los días a las 02:15):

```cron
15 2 * * * cd /ruta/al/YEGO-CONTROL-TOWER/backend && python -m scripts.refresh_real_lob_mvs >> /var/log/refresh_real_lob_mvs.log 2>&1
```

## Notas

- Real LOB es solo observabilidad de datos **Real**; no modifica ni depende de Plan vs Real REALKEY (`ops.v_plan_vs_real_realkey_final`).
- Los endpoints **GET /ops/real-lob/monthly** y **GET /ops/real-lob/weekly** leen únicamente de estas MVs.
