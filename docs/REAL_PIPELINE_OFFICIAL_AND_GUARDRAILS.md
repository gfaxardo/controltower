# REAL — Ruta oficial del pipeline y guardrails

## Ruta oficial vigente (hourly-first)

1. **Refresh cadena:** `scripts.refresh_hourly_first_chain`  
   hour_v2 → day_v2 → week_v3 → month_v3 (desde `v_real_trip_fact_v2`).

2. **Rollup diario:** no requiere paso; `real_rollup_day_fact` es **vista** sobre `mv_real_lob_day_v2` (migración 101).

3. **Drill:** `scripts.populate_real_drill_from_hourly_chain`  
   Pobla `ops.real_drill_dim_fact` desde `mv_real_lob_day_v2` (day) y `mv_real_lob_week_v3` (week).  
   Debe ejecutarse **después** del refresh de la cadena. Ventana por defecto: 120 días, 18 semanas.

4. **Pipeline orquestado:** `scripts.run_pipeline_refresh_and_audit`  
   Ejecuta en orden: hourly-first → populate drill → driver lifecycle → supply → data freshness audit.  
   **No** ejecuta `backfill_real_lob_mvs`.

## Evitar doble inserción

- **Única escritura oficial en `real_drill_dim_fact`:** `populate_real_drill_from_hourly_chain`.  
- **`backfill_real_lob_mvs`:** deprecated. No debe usarse para el camino principal. Si se ejecuta con `--allow-write-drill`, puede escribir en la misma tabla y mezclar convención de signo (legacy (-1)* vs hourly ABS).  
- **Recomendación:** no ejecutar backfill para la misma ventana que alimenta el drill; o no usar `--allow-write-drill` salvo recuperación puntual documentada.

## Comprobaciones de auditoría

- **Duplicidad por grain:** script `scripts.audit_real_margin_and_coverage` incluye query de duplicados por (country, period_grain, period_start, segment, breakdown, dimension_key, dimension_id, city). Resultado esperado: 0 filas.  
- **Cobertura reciente:** mismo script reporta último `period_start` en `real_drill_dim_fact` por grain y muestra muestras de day_v2/week_v3 recientes.  
- **Signo de margen:** tras normalización (Fase 2), populate escribe `ABS(margin_total)`; el servicio de drill normaliza a positivo en lectura para filas legacy.

## Frescura

- Tras cada carga de viajes, ejecutar el pipeline (o al menos refresh hourly-first + populate drill) para que las semanas recientes tengan margen y totales en el drill.
