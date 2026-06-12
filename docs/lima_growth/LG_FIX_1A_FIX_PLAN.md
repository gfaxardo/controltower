# LG_FIX_1A_FIX_PLAN — Fix Plan

**Generated:** 2026-06-12T19:36  
**Target Phase:** LG-FIX-1B (execution)  
**Rule:** NO aplicar fixes en esta fase. Solo plan.

---

## P0 — CRITICAL (rompe funcionalidad completamente)

### P0.1: Effectiveness 500
| Item | Detail |
|------|--------|
| **Problema** | `GET /yego-lima-growth/effectiveness/summary` → 500 |
| **Causa** | `program_effectiveness_fact` tiene solo 10 rows. `v2_effectiveness_fact` está vacía (0 rows). El servicio no maneja tabla vacía. |
| **Fix Backend** | Modificar `yego_lima_effectiveness_service.py` para devolver `{ programs: [], total_drivers_tracked: 0, message: "No effectiveness data available. Pipeline has not accumulated enough snapshots." }` cuando las tablas estén vacías, en vez de lanzar 500. |
| **Fix DB** | Poblar `program_effectiveness_fact` ejecutando el builder de effectiveness. Script: `backend/scripts/imp_1b_stability.py`. |
| **Fix Pipeline** | Asegurar que el scheduler diario incluya el paso de effectiveness. |

### P0.2: Movement timeout + 404 + 500
| Item | Detail |
|------|--------|
| **Problema** | `movement/records` → 404, `movement-analytics/winners` → 500, `movement-analytics/losers` → 500 |
| **Causa records 404** | La ruta `/yego-lima-growth/movement/records` no está registrada en `backend/app/routers/yego_lima_movement_analytics.py` o similar. |
| **Causa winners/losers 500** | `yego_lima_v2_movement_fact` está vacía (0 rows). |
| **Fix 404** | Agregar ruta `GET /movement/records` al router de movement analytics. |
| **Fix 500** | Poblar `yego_lima_v2_movement_fact` o hacer que winners/losers lean de `driver_movement_fact` (que sí tiene 68K rows). |
| **Fix Pipeline** | Asegurar que el scheduler diario corra el pipeline V2 para las fechas faltantes. |

### P0.3: Pipeline V2 no ejecutado para 2026-06-11/12
| Item | Detail |
|------|--------|
| **Problema** | `lifecycle_daily`, `taxonomy_v2_daily`, `movement_fact` congelados en 2026-06-10. |
| **Causa** | El scheduler o el pipeline diario no se ejecutó. |
| **Fix** | Ejecutar pipeline V2 manualmente para 2026-06-11 y 2026-06-12. Scripts: `backend/scripts/s1_0a_simulation_v3.py` (taxonomy), `backend/scripts/imp_1b_stability.py` (movement), pipeline scheduler: `backend/scripts/cf_h2d_scheduler.py`. |
| **Fix permanente** | Verificar que el scheduler esté configurado para correr diariamente. Revisar `yego_lima_scheduler_status` y logs. |

---

## P1 — HIGH (datos visibles incorrectos o vacíos)

### P1.1: Overview — Payload Mismatch
| Item | Detail |
|------|--------|
| **Problema** | `drivers_with_program`, `active_programs`, `program_distribution`, `channel_utilization` muestran 0. |
| **Causa** | Backend cambió el schema de `operational-summary`. Las keys nuevas son `eligible_total`, `by_program[]`. Las viejas (`drivers_with_program`) ya no existen. |
| **Fix Frontend (OverviewTab.jsx)** | Cambiar: `driversWithProgram = overview?.eligible_total ?? 0`, `activePrograms = overview?.by_program?.length ?? 0`, `programDistribution = overview?.by_program || []`. |
| **O Fix Backend** | Agregar `drivers_with_program` y `active_programs` como alias en la respuesta de `operational-summary`. |

### P1.2: Programs — Payload Mismatch
| Item | Detail |
|------|--------|
| **Problema** | `eligible_drivers`, `prioritized`, `queue_count` muestran 0. |
| **Causa** | Backend devuelve `eligible_total`, `prioritized_total`, `queued_total`. UI espera nombres distintos. |
| **Fix Frontend (ProgramsTab.jsx)** | Cambiar fallbacks: `program.eligible_total ?? program.eligible_drivers ?? 0`, `program.prioritized_total ?? program.prioritized ?? 0`, `program.queued_total ?? program.queue_count ?? 0`. |

### P1.3: Segments — Payload Mismatch + Date Mismatch
| Item | Detail |
|------|--------|
| **Problema** | "No hay datos de distribución de lifecycle". |
| **Causa** | (a) Payload: key real es `distributions` (no `lifecycle_distribution`). (b) Date: `total_drivers: 0` para 2026-06-11. |
| **Fix Frontend (SegmentsTab.jsx)** | Leer de `taxonomy.distributions.operational_segment` en vez de `taxonomy.lifecycle_distribution`. Mapear cada capa: `operational_status`, `operational_segment`, `value_overlay`, `momentum`. |
| **Fix Pipeline** | P0.3 cubre el date mismatch. |

### P1.4: RNA — Wrong Endpoint + Tablas Inexistentes
| Item | Detail |
|------|--------|
| **Problema** | Total RNA = 0, sin datos de prioridad, contactabilidad vacía. |
| **Causa** | (a) La UI consume `yango-loyalty/summary` que es KPIs mensuales, no RNA. (b) `rna_priority_fact` y `rna_pilot_measurement_fact` no existen en DB. |
| **Fix Backend** | Crear tablas `growth.rna_priority_fact` y `growth.rna_pilot_measurement_fact`. Implementar servicios `yego_lima_rna_priority_service.py` y `yego_lima_rna_pilot_measurement_service.py`. Poblar con datos de RNA desde taxonomy + program eligibility. |
| **Fix Frontend (RNATab.jsx)** | Cambiar fuente de datos de `yango-loyalty/summary` a `yego-lima-growth/rna-priority/summary` (cuando esté implementado). O crear un endpoint dedicado `/yego-lima-growth/rna/summary` que agregue los datos necesarios. |
| **Workaround temporal** | Si los datos RNA se pueden derivar de taxonomy (RNA = drivers con `operational_status = 'REGISTERED_NOT_ACTIVATED'`), usar taxonomy/summary como fuente temporal. |

### P1.5: FreshnessBanner — TRUE_CRITICAL (no false)
| Item | Detail |
|------|--------|
| **Problema** | Banner muestra CRITICAL con 12 assets broken. |
| **Causa** | Real: hay 12 assets stale/broken. El pipeline no corrió. |
| **Fix** | P0.3 (ejecutar pipeline) debería resolver los assets broken. El banner se actualizará a HEALTHY o DEGRADED automáticamente cuando los assets se refreshen. |

---

## P2 — LOW (mejoras de UX)

### P2.1: Driver Explorer lento (21s)
| Item | Detail |
|------|--------|
| **Problema** | `GET /drivers/activity-summary` tarda 21 segundos. |
| **Causa** | Query pesada sin índices o sin límite de fecha. |
| **Fix** | Agregar `date` como parámetro requerido. Optimizar query en el backend. Agregar índices a `driver_activity_daily` por fecha. |

### P2.2: Driver Explorer empty-by-default
| Item | Detail |
|------|--------|
| **Problema** | La UI no muestra datos hasta que el usuario aplica filtros. |
| **Causa** | Diseño intencional — pero confunde al usuario. |
| **Fix** | Cargar primeras 20 filas automáticamente al montar el tab (sin filtros). |

### P2.3: Labels inconsistentes
| Item | Detail |
|------|--------|
| **Problema** | Programs tab usa `PROGRAM_LABELS` hardcodeados que no cubren todos los programas posibles. |
| **Fix** | Usar `program.program_name` del payload (ya viene en la respuesta). |

---

## Orden de Ejecución Recomendado (LG-FIX-1B)

```
1. P0.3  → Ejecutar Pipeline V2 para 2026-06-11 y 2026-06-12
2. P1.2  → Fix ProgramsTab payload keys (rápido, solo frontend)
3. P1.1  → Fix OverviewTab payload keys (rápido, solo frontend)
4. P1.3  → Fix SegmentsTab payload keys (rápido, solo frontend)
5. P0.1  → Fix Effectiveness: backend manejo de tabla vacía + poblar tabla
6. P0.2  → Fix Movement: agregar ruta /records, poblar v2_movement_fact o redirigir
7. P1.4  → RNA: crear tablas y endpoints, redirigir UI
8. P1.5  → Verificar que el banner baje a HEALTHY post-pipeline
9. P2.1  → Optimizar Driver Explorer
10. P2.2 → Auto-cargar primeras filas en Driver Explorer
11. P2.3 → Usar program_name del payload
```
