# LG_CAN_1B_MOVEMENT_BUILDER_AUDIT — Movement Builder Audit

**Generated:** 2026-06-12T21:30

---

## 1. BUILDER: `_build_movement_fact`

| Atributo | Valor |
|----------|-------|
| **Archivo** | `backend/app/services/yego_lima_v2_daily_pipeline_service.py:663-719` |
| **Pipeline step** | 7 de 9 |
| **Tabla destino** | `growth.yego_lima_v2_movement_fact` |
| **Timeout** | 120,000ms |

### Fuentes leídas:

| Query | Tabla | Condición | Datos 06-10 | Datos 06-11 | Datos 06-12 |
|-------|-------|-----------|-------------|-------------|-------------|
| STATE_CHANGE | `yego_lima_state_transition_trace` | `snapshot_after = target_date` | **0 rows** | **0 rows** | **0 rows** |
| PROGRAM_CHANGE | `yego_lima_program_decision_trace` | `snapshot_date = target_date` | **0 rows** | **0 rows** | **0 rows** |

### ¿Por qué produce 0 rows?

**Las dos tablas fuente están congeladas en 2026-06-05:**
- `state_transition_trace`: 1,205 rows total, max 2026-06-05
- `program_decision_trace`: 5,558 rows total, max 2026-06-05

Sus writers (`write_decision_traces`, `write_transition_traces` en `diagnostic_trace_writer.py`) están definidos pero **nunca son llamados** desde ningún scheduler, pipeline, ni router. Son dead code.

### ¿Por qué marca SKIPPED_NO_NEW_DATA?

Pipeline runner (línea 241):
```python
if rows_after == 0 and rows_before == 0:
    step_status = STATUS_SKIPPED_NO_NEW_DATA
```

La builder se ejecuta (no es saltada por freshness), pero al no encontrar datos en las fuentes para la fecha solicitada, INSERTa 0 rows. Como `rows_before=0` y `rows_after=0`, el runner la marca como SKIPPED.

### ¿Falla silenciosamente?

No falla (no lanza excepción). La función retorna 0 correctamente. Pero el resultado práctico es que `yego_lima_v2_movement_fact` nunca se puebla, lo que causa que los endpoints movement devuelvan arrays vacíos.

---

## 2. FIX PROPUESTO

Agregar fallback a `_build_movement_fact`: cuando las trace tables no tienen datos para la fecha, computar movement directamente desde las tablas V2 shadow:

| Movement Type | Source para fallback | Lógica |
|--------------|---------------------|--------|
| STATE_CHANGE | `yego_lima_v2_taxonomy_daily` (dos fechas consecutivas) | Comparar segment entre `target_date - 1` y `target_date` |
| PROGRAM_CHANGE | `yego_lima_v2_program_daily` | Leer `program_code` de hoy, comparar con ayer |

Esto permite que el movement_fact se construya incluso sin traces, usando los datos ya existentes en las tablas canónicas V2.
