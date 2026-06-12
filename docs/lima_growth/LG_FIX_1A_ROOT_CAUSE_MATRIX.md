# LG_FIX_1A_ROOT_CAUSE_MATRIX — Root Cause Matrix

**Generated:** 2026-06-12T19:36

---

## Clasificación por Tab

### FreshnessBanner
| Diagnóstico | Evidencia |
|-------------|-----------|
| **TRUE_CRITICAL** | `/growth/health` devuelve `system_status: "CRITICAL"`, 12 stale assets, 8 broken assets. No es false positive. |

---

### Overview
| Diagnóstico | Evidencia |
|-------------|-----------|
| **PAYLOAD_MISMATCH** | `drivers_with_program` y `active_programs` no existen en el payload de operational-summary. Los fallbacks a operational-truth también fallan porque truth devuelve array de KPIs, no objeto plano. |
| DATE_MISMATCH (parcial) | operational-truth reporta effective_source_date=2026-06-09 para varios KPIs, aunque esto no es la causa principal de los 0s. |

**Root cause primario:** El backend cambió el schema del endpoint `operational-summary` (ahora usa `eligible_total`, `by_program[]`, dejó de exponer `drivers_with_program`, `drivers_without_program`, `active_programs`, `program_distribution`). La UI no fue actualizada.

---

### Programs
| Diagnóstico | Evidencia |
|-------------|-----------|
| **PAYLOAD_MISMATCH** | La UI espera `eligible_drivers`, `prioritized`, `queue_count` por programa. El backend devuelve `eligible_total`, `prioritized_total`, `queued_total`. Los fallbacks (`drivers`, `count`, `queued`) tampoco existen en el payload real. |

**Root cause primario:** Rename de campos en el backend sin sincronizar la UI. Los 4 programas tienen `eligible_total > 0` real (17685, 7774, 2669, 0).

---

### Segments
| Diagnóstico | Evidencia |
|-------------|-----------|
| **DATE_MISMATCH** (primario) + **PAYLOAD_MISMATCH** (secundario) | La tabla `yego_lima_driver_taxonomy_v2_daily` tiene último dato 2026-06-10. Para 2026-06-11/12, `total_drivers: 0`. Además, la UI espera `lifecycle_distribution` pero el backend devuelve `distributions`. |

**Root cause primario:** Pipeline no corrió para 2026-06-11/12 → taxonomy/summary devuelve 0s.  
**Root cause secundario:** Payload shape mismatch impide leer datos aunque existieran.

---

### Movement
| Diagnóstico | Evidencia |
|-------------|-----------|
| **DATE_MISMATCH** (primario) + **ENDPOINT_ERROR** (secundario) | `movement/summary` devuelve 0s porque `driver_movement_fact` tiene último dato 2026-06-10. `movement/records` devuelve 404. `movement-analytics/winners` y `losers` devuelven 500 porque `v2_movement_fact` está vacía (0 rows). |
| **Nota:** movement-analytics/stats y matrix FUNCIONAN (usan movement_fact con 68K rows hasta 06-10). | |

**Root cause primario:** Pipeline no corrió para 2026-06-11/12.  
**Root cause secundario:** `v2_movement_fact` nunca se ha poblado (0 rows) → winners/losers 500.  
**Root cause terciario:** `/movement/records` no está registrado como ruta en el backend (404).

---

### RNA
| Diagnóstico | Evidencia |
|-------------|-----------|
| **WRONG_ENDPOINT** (primario) + **ENDPOINT_FAILING** (secundario) | La UI consume `yango-loyalty/summary` y `yango-loyalty/kpis` esperando campos RNA (`total_rna`, `rna_new`, ...). Estos endpoints son del dominio Yango Loyalty (KPIs mensuales: AD, Supply Hours, Calls, UFC, etc.) y **no contienen campos RNA**. El endpoint correcto `/rna-priority/summary` devuelve 500 porque las tablas `rna_priority_fact` y `rna_pilot_measurement_fact` **no existen en la DB**. |

**Root cause primario:** Las tablas RNA nunca se crearon en la DB.  
**Root cause secundario:** La UI cableó Yango Loyalty como fuente de datos RNA (wrong domain).

---

### Driver Explorer
| Diagnóstico | Evidencia |
|-------------|-----------|
| **NEEDS_FILTER** | Por diseño. La UI no carga datos hasta que el usuario aplica filtros. Sin embargo, `/drivers/activity-summary` tarda **21 segundos** en responder — inaceptable para UX. |

**Root cause:** Endpoint lento (21s). La UI funciona correctamente al aplicar filtros.

---

### Effectiveness
| Diagnóstico | Evidencia |
|-------------|-----------|
| **MISSING_TABLE + 500** | `program_effectiveness_fact` tiene solo 10 rows. `yego_lima_v2_effectiveness_fact` tiene 0 rows. El endpoint `/effectiveness/summary` lanza 500 al intentar computar efectividad sobre tablas sin datos suficientes. |

**Root cause:** Las tablas de effectiveness nunca se poblaron adecuadamente. El servicio no maneja el caso de tabla vacía (debería devolver `{ programs: [], message: "No data" }` en vez de 500).

---

## Matriz de Clasificación

| Tab | Clasificación | P0/P1/P2 |
|-----|-------------|----------|
| FreshnessBanner | TRUE_CRITICAL | P1 |
| Overview | PAYLOAD_MISMATCH | P1 |
| Programs | PAYLOAD_MISMATCH | P1 |
| Segments | DATE_MISMATCH + PAYLOAD_MISMATCH | P0/P1 |
| Movement | DATE_MISMATCH + ENDPOINT_ERROR | P0 |
| RNA | WRONG_ENDPOINT + ENDPOINT_FAILING | P1 |
| Driver Explorer | NEEDS_FILTER (by design, but SLOW) | P2 |
| Effectiveness | MISSING_TABLE + 500 | P0 |

---

## Root Cause Unificada

**Tres causas raíz principales:**

1. **Pipeline V2 no ejecutado para 2026-06-11/12.** Las tablas `lifecycle_daily`, `taxonomy_v2_daily`, `movement_fact` tienen datos hasta 2026-06-10. Esto rompe Segments, Movement, y Effectiveness.

2. **Backend ↔ Frontend schema drift.** El backend cambió nombres de campos (`eligible_total` vs `eligible_drivers`, `distributions` vs `lifecycle_distribution`) sin actualizar la UI. Esto rompe Overview, Programs, y Segments.

3. **Tablas y endpoints faltantes.** `rna_priority_fact`, `rna_pilot_measurement_fact` no existen. `v2_effectiveness_fact`, `v2_movement_fact` existen pero vacías. `/movement/records` no registrado. Esto rompe RNA, Movement Analytics (winners/losers), y Effectiveness.
