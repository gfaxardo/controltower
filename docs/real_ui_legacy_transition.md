# REAL — Transición UI y legacy

## Camino principal (nuevo)

- **Real Operacional** (Hoy/Ayer/Semana, comparativos, por día, por hora, cancelaciones): fuente **mv_real_lob_day_v2**, **mv_real_lob_hour_v2** (arquitectura hourly-first). Es la vista principal dentro de la pestaña Real.
- **Real LOB** (monthly/weekly v2, drill): cuando el drill use datos recientes, debe apoyarse en la misma cadena donde corresponda (day_v2 / week_v3 / month_v3).

## Unificación hourly-first (CT-HOURLY-FIRST-FINAL-UNIFICATION)

- **real_rollup_day_fact**: desde migración 101 es **vista** derivada de **ops.mv_real_lob_day_v2** (v_real_rollup_day_from_day_v2). Ya no se alimenta por backfill desde fact.
- **real_drill_dim_fact**: tabla poblada por **scripts.populate_real_drill_from_hourly_chain** desde **mv_real_lob_day_v2** (day) y **mv_real_lob_week_v3** (week). Ya no se alimenta por backfill desde v_trips_real_canon.
- El pipeline principal (run_pipeline_refresh_and_audit) ya no ejecuta backfill_real_lob_mvs; ejecuta populate_real_drill_from_hourly_chain tras el refresh de la cadena hourly-first.

## Legacy / deprecated

- **scripts.backfill_real_lob_mvs**: deprecated para el camino principal; queda para compatibilidad o recuperación. No participa del flujo oficial REAL.
- Vistas o endpoints que lean **mv_real_lob_week_v2** o **mv_real_lob_month_v2** (anteriores a v3): sustituidos por **week_v3** y **month_v3** derivados de hourly.
- **trips_base** en freshness: marcado como legacy (fuente histórica cortada; fuente viva trips_2026).

## UI

- La pestaña **Real** muestra por defecto **Operacional** (snapshot, comparativos, día, hora, cancelaciones). El drill "Real LOB Drill" sigue disponible para desglose LOB/park/servicio; sus datos provienen de day_v2/week_v3 (un solo universo).
- Operacional y Drill comparten la misma columna vertebral: FACT → hour_v2 → day_v2 → week_v3/month_v3; rollup = vista desde day_v2; drill = tabla poblada desde day_v2/week_v3.
