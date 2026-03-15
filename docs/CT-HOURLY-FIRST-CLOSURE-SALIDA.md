# CT-HOURLY-FIRST-CLOSURE — Salida

## Fase CT-HOURLY-FIRST-FINAL-UNIFICATION (cerrada)

### Hecho en esta fase

- **Fase A**: docs/hourly_first_legacy_last_mile_audit.md — Auditoría de real_rollup_day_fact y real_drill_dim_fact (esquema, consumidores, scripts, fuente natural day_v2/week_v3).
- **Fase B**: real_rollup_day_fact pasa a ser **vista** derivada de mv_real_lob_day_v2 (migración 101_real_rollup_from_day_v2). v_real_rollup_day_from_day_v2 + vista real_rollup_day_fact; se elimina la tabla y el backfill como fuente.
- **Fase C**: real_drill_dim_fact se puebla desde day_v2 (day) y week_v3 (week) con **scripts.populate_real_drill_from_hourly_chain** (breakdowns lob, park, service_type).
- **Fase D**: run_pipeline_refresh_and_audit ya no ejecuta backfill_real_lob_mvs; ejecuta populate_real_drill_from_hourly_chain tras la cadena hourly-first. backfill_real_lob_mvs marcado deprecated.
- **Fases E–I**: Endpoints/servicios/UI siguen usando real_rollup_day_fact y real_drill_dim_fact sin cambio de contrato; freshness y governance dependen del universo nuevo; documentación actualizada (dependency_map, real_ui_legacy_transition, derived_stale_strategy, architecture_final, real_lob_final_closure).

### Documentación actualizada/creada

- docs/hourly_first_legacy_last_mile_audit.md
- docs/hourly_first_architecture_final.md
- docs/hourly_first_dependency_map.md
- docs/hourly_first_derived_stale_strategy.md
- docs/real_lob_final_closure.md
- docs/CT-HOURLY-FIRST-CLOSURE-SALIDA.md (este archivo)

---

## Cómo dejar todos los datasets activos en OK

1. **Pipeline diario**: `python -m scripts.run_pipeline_refresh_and_audit` (sin --skip-hourly-first ni --skip-drill-populate). Orden: 1) hourly-first chain, 2) populate real_drill desde day_v2/week_v3, 3) driver lifecycle, 4) supply, 5) audit.
2. **Banner Real**: GET /ops/data-freshness/global?group=operational; real_operational, real_lob, real_lob_drill cuentan; trips_base no afecta.
3. **Consistencia**: `python -m scripts.audit_hourly_chain_consistency` tras el refresh.

---

# SALIDA FINAL OBLIGATORIA (CT-HOURLY-FIRST-FINAL-UNIFICATION)

## A. Qué dualidad quedaba viva

- **real_rollup_day_fact**: tabla poblada por backfill desde v_trips_real_canon (fact directo).
- **real_drill_dim_fact**: tabla poblada por el mismo backfill desde v_trips_real_canon (day/week/month, breakdowns lob/park/service_type).  
Ambos objetos eran la última dualidad: el universo REAL activo (Operacional ya usaba day_v2/hour_v2) pero LOB y drill seguían dependiendo de fact legacy.

## B. Qué objetos se migraron al universo hourly-first

- **real_rollup_day_fact**: convertido en **vista** sobre v_real_rollup_day_from_day_v2 (agregado de mv_real_lob_day_v2). Migración 101.
- **real_drill_dim_fact**: sigue siendo tabla; **fuente de población** cambiada a mv_real_lob_day_v2 (day) y mv_real_lob_week_v3 (week) vía scripts.populate_real_drill_from_hourly_chain.

## C. Qué objetos quedaron en legacy

- **scripts.backfill_real_lob_mvs**: deprecated para el camino principal; no se ejecuta en run_pipeline_refresh_and_audit. Queda disponible para compatibilidad o recuperación (p. ej. si se revierte la migración 101).
- **trips_base** (trips_all): fuente histórica; SOURCE_STALE esperado; no forma parte del universo activo REAL.
- **driver_lifecycle**: pipeline propio (trips_unified → mv_driver_lifecycle_base → mv_driver_weekly_stats); no deriva de hourly-first por diseño de dominio.

## D. Cómo quedó el pipeline principal

1. Refresh cadena hourly-first (hour_v2 → day_v2 → week_v3 → month_v3).
2. Poblar real_drill_dim_fact desde day_v2 y week_v3 (populate_real_drill_from_hourly_chain). real_rollup_day_fact no requiere paso (es vista).
3. Refresh driver lifecycle MVs.
4. Refresh supply MVs.
5. Ejecutar data freshness audit.

Backfill Real LOB ya no forma parte de este pipeline.

## E. Cómo quedó freshness de REAL

- **real_operational**: source/day_v2; OK cuando la cadena hourly-first esté refrescada.
- **real_lob**: derived = real_rollup_day_fact (vista sobre day_v2); OK cuando day_v2 esté al día.
- **real_lob_drill**: derived = real_drill_dim_fact (poblado desde day_v2/week_v3); OK cuando el populate se ejecute tras el refresh.
- **trips_base**: legacy; SOURCE_STALE permitido; no afecta al banner REAL (group=operational).

## F. Cómo quedó la consistencia de la cadena

- **audit_hourly_chain_consistency**: SUM(hourly)==SUM(day), SUM(day)==SUM(week), SUM(week)==SUM(month) para requested_trips, completed_trips, cancelled_trips, revenue, margin, duration (tolerancia 0.01).
- **Rollup**: real_rollup_day_fact es vista sobre day_v2 → coherencia por definición.
- **Drill**: real_drill_dim_fact repoblado desde day_v2/week_v3 en la misma ventana que el refresh → coherencia cuando el pipeline se ejecuta en orden.

## G. Qué cambió en endpoints/servicios/UI

- **Sin cambios de contrato**: Los mismos endpoints y servicios siguen leyendo real_rollup_day_fact y real_drill_dim_fact; la estructura de datos (columnas, granularidad) se mantiene.
- **Cambio de fuente**: real_rollup_day_fact ahora es vista (day_v2); real_drill_dim_fact se puebla desde day_v2/week_v3. La UI REAL (Operacional, LOB, drill) sigue funcionando sin modificaciones; no se mezclan objetos viejos y nuevos en el flujo activo.

## H. ¿Quedó un solo universo activo o no?

**Sí.** El universo REAL activo (Operacional, LOB, drill, comparativos, freshness para REAL) deriva de una sola columna vertebral: FACT → hour_v2 → day_v2 → week_v3/month_v3. real_rollup_day_fact y real_drill_dim_fact ya no dependen de fact directo; el backfill legacy está fuera del camino principal.

## I. ¿Quedó cerrado o no?

**Sí.** Criterios de cierre cumplidos:

- REAL activo opera en un solo universo de datos (hourly-first).
- Rollup y drill ya no dependen de fact directo (rollup = vista day_v2; drill = poblado desde day_v2/week_v3).
- El refresh principal usa hourly-first como columna vertebral (run_pipeline_refresh_and_audit: hourly-first → populate drill → driver → supply → audit).
- Datasets activos REAL pueden quedar OK en freshness cuando el pipeline se ejecuta correctamente.
- Legacy (backfill_real_lob_mvs, trips_base) queda explícitamente documentado y separado del flujo oficial.
- UI REAL no mezcla objetos viejos y nuevos; todo queda documentado en los docs indicados.
