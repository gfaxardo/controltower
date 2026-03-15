# REAL — Freshness y cobertura de datos

## Objetivo

Documentar cómo se determina la frescura y cobertura de datos para la pestaña REAL (vista operativa Hoy/Ayer/Semana, drill, LOB) y por qué el banner puede mostrar "Falta data" o una fecha distinta a la esperada.

## Capas y fuentes

| Capa | Objeto | Granularidad | Uso en UI |
|------|--------|--------------|-----------|
| Fuente canónica 120d | ops.v_trips_real_canon_120d | por viaje | Base para hourly-first |
| Hourly | ops.mv_real_lob_hour_v2 | (trip_date, trip_hour, ...) | Por hora, comparativos |
| Day | ops.mv_real_lob_day_v2 | trip_date | **Hoy/Ayer/Semana**, por día |
| Week | ops.mv_real_lob_week_v3 | week_start | Semanal |
| Month | ops.mv_real_lob_month_v3 | month_start | Mensual |
| Drill (legacy) | ops.real_drill_dim_fact | period_start (day/week) | Real LOB Drill |

La vista **Real Operacional** (Hoy/Ayer/Semana, comparativos, por día, por hora, cancelaciones) lee de **mv_real_lob_day_v2** y **mv_real_lob_hour_v2**. Esas MVs se refrescan con el pipeline hourly-first (bootstrap/refresh), no con el pipeline legacy que llena real_drill_dim_fact / real_rollup_day_fact.

## Expectativas de freshness

En `ops.data_freshness_expectations` existen:

- **real_operational**: derived = `ops.mv_real_lob_day_v2`, columna `trip_date`. Fuente: v_trips_real_canon_120d (a su vez trips_all + trips_2026). Es la que alimenta el panel Hoy/Ayer/Semana.
- **real_lob_drill**: derived = `ops.real_drill_dim_fact`, columna `period_start`. Alimentado por scripts de drill/backfill.

El **banner global** de frescura (GET /ops/data-freshness/global) usa la **fecha más reciente** entre `real_operational` y `real_lob_drill` (y otros fallbacks). Así, si al menos una de las dos capas tiene datos hasta ayer, el banner no mostrará "Falta data" por retraso de la otra.

## Regla "Falta data"

- **Falta data**: se muestra cuando `derived_max_date` es NULL o `<= current_date - 2` (es decir, la última fecha con datos es anterior a ayer).
- Si la última data es **ayer** o **hoy**: no se considera "Falta data"; el estado puede ser "Fresca" o "Parcial esperada".

## Por qué la UI puede mostrar "Falta data" o fecha 2026-03-09

1. **real_operational (mv_real_lob_day_v2)** no refrescada: si el REFRESH de las MVs hourly-first no se ha ejecutado tras nueva ingestión, `MAX(trip_date)` en mv_real_lob_day_v2 seguirá siendo antigua (ej. 2026-03-09).
2. **real_lob_drill (real_drill_dim_fact)** atrasado: el script que llena real_drill_dim_fact no ha corrido o no ha procesado días recientes; `MAX(period_start)` queda antigua.
3. **Fuente (trips_2026 / trips_all)** sin datos recientes: si el pipeline de ingestión no ha cargado viajes hasta ayer/hoy, tanto real_operational como real_lob_drill tendrán techo en la última fecha cargada.

Para que **Hoy/Ayer/Semana** muestre datos recientes:

1. Asegurar que **trips_2026** (y/o trips_all) tenga datos hasta ayer.
2. Ejecutar **refresh de las MVs hourly-first**: primero `mv_real_lob_hour_v2`, luego `mv_real_lob_day_v2` (y opcionalmente week_v3, month_v3). Ver scripts `bootstrap_hourly_first.py` / governance.
3. Ejecutar **run_data_freshness_audit** para que el banner use las nuevas fechas: `cd backend && python -m scripts.run_data_freshness_audit`.

## Auditoría

- Script: `python -m scripts.run_data_freshness_audit`
- Escribe en `ops.data_freshness_audit` una fila por dataset por ejecución (source_max_date, derived_max_date, status).
- Endpoints: GET `/ops/data-freshness`, GET `/ops/data-freshness/global`.

## Resumen

- La **fecha visible** en el banner viene de la auditoría (última ejecución) del dataset con **derived_max_date más reciente** entre real_operational y real_lob_drill.
- Para que el panel **Hoy/Ayer/Semana** tenga datos al día: ingestión al día + REFRESH de **mv_real_lob_day_v2** (y su dependencia mv_real_lob_hour_v2).
- Si solo real_lob_drill está al día pero real_operational no, el banner puede mostrar "Fresca" (por drill) pero el panel Hoy/Ayer/Semana puede seguir vacío o atrasado; en ese caso la causa es que las MVs hourly-first no se han refrescado.
