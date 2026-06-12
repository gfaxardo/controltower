# LG_CAN_1B_CANONICAL_MOVEMENT_BACKFILL_CERTIFICATION

**Generated:** 2026-06-12T21:40  
**Phase:** LG-CAN-1B — Canonical Movement Backfill  
**Veredicto:** `LG_CAN_1B_CERTIFIED`

---

## 1. BUILDER AUDIT

| Atributo | Valor |
|----------|-------|
| **Archivo** | `backend/app/services/yego_lima_v2_daily_pipeline_service.py:663-755` |
| **Pipeline step** | 7 de 9 |
| **Tabla destino** | `growth.yego_lima_v2_movement_fact` |

### Fuentes primarias (traces):

| Tabla | Datos 06-10 | Último dato | Causa del vacío |
|-------|-------------|-------------|-----------------|
| `yego_lima_state_transition_trace` | 0 rows | 2026-06-05 | Writer (`write_transition_traces` en `diagnostic_trace_writer.py`) nunca es llamado |
| `yego_lima_program_decision_trace` | 0 rows | 2026-06-05 | Writer (`write_decision_traces` en `diagnostic_trace_writer.py`) nunca es llamado |

### Fuentes de fallback (agregadas en esta fase):

| Tabla | Datos 06-10 | Lógica |
|-------|-------------|--------|
| `yego_lima_v2_taxonomy_daily` | 68,473 rows | Comparar `segment` entre `target_date - 1` y `target_date` |
| `yego_lima_v2_program_daily` | 68,473 rows | Comparar `program_code` entre `target_date - 1` y `target_date` |

---

## 2. SOURCE AUDIT

| Tabla | Total Rows | Max Date | Rows 06-10 | Rows 06-11 | Rows 06-12 |
|-------|-----------|----------|------------|------------|------------|
| `yego_lima_state_transition_trace` | 1,205 | 2026-06-05 | **0** | **0** | **0** |
| `yego_lima_program_decision_trace` | 5,558 | 2026-06-05 | **0** | **0** | **0** |
| `yego_lima_v2_taxonomy_daily` | 273,908 | 2026-06-10 | 68,473 | **0** | **0** |
| `yego_lima_v2_program_daily` | 273,908 | 2026-06-10 | 68,473 | **0** | **0** |
| `yego_lima_v2_lifecycle_daily` | 273,908 | 2026-06-10 | 68,473 | **0** | **0** |
| `yego_lima_driver_lifecycle_daily` | 273,908 | 2026-06-10 | 68,473 | **0** | **0** |

---

## 3. CANONICAL MOVEMENT CONTRACT

| Atributo | Valor |
|----------|-------|
| **Tabla canónica** | `growth.yego_lima_v2_movement_fact` |
| **Grain** | 1 row por driver × target_date × movement_type |
| **Unique key** | `(target_date, driver_id, movement_type)` |
| **Campos** | `target_date`, `driver_id`, `movement_type`, `from_state`, `to_state`, `from_program`, `to_program`, `trigger_reason` |
| **Source precedence** | 1. Traces (`state_transition_trace` + `program_decision_trace`) → 2. Fallback (taxonomy diff + program diff) |
| **Empty state** | Retorna 0 rows si las fuentes no tienen datos. No lanza 500. |
| **Writer** | `_build_movement_fact()` en V2 pipeline step 7 |
| **Scheduler** | `lima_growth_v2_daily_pipeline` cron 04:45 |
| **Status** | `driver_movement_fact` = DEPRECATED. Todo lee de esta tabla. |

---

## 4. CAMBIOS APLICADOS

### 4.1 Builder modificado

**Archivo:** `backend/app/services/yego_lima_v2_daily_pipeline_service.py:663-755`

**Cambio:** Agregado fallback para STATE_CHANGE y PROGRAM_CHANGE cuando las trace tables están vacías:

- **STATE_CHANGE fallback:** Compara `segment` en `yego_lima_v2_taxonomy_daily` entre `target_date - 1` y `target_date`. Detecta cambios de lifecycle.
- **PROGRAM_CHANGE fallback:** Compara `program_code` en `yego_lima_v2_program_daily` entre `target_date - 1` y `target_date`. Detecta asignaciones/desasignaciones.
- **Idempotencia:** `ON CONFLICT (target_date, driver_id, movement_type) DO NOTHING` garantiza que ejecuciones repetidas no dupliquen datos.
- **DELETE before INSERT** garantiza que cada run regenera la data completa para la fecha.

### 4.2 Servicios consumidores (LG-CAN-1A)

Ya migrados en fase anterior:
- `yego_lima_movement_analytics_service.py` → `TABLE_MOV = "growth.yego_lima_v2_movement_fact"`
- `yego_lima_effectiveness_service.py` → `TABLE_MOV = "growth.yego_lima_v2_movement_fact"`
- `yego_lima_rna_priority_service.py` → `TABLE_MOV = "growth.yego_lima_v2_movement_fact"`

---

## 5. BACKFILL EJECUTADO

| Fecha | Pipeline Run | Step 7 Status | Rows Before | Rows After | Fuente |
|-------|-------------|---------------|-------------|------------|--------|
| **2026-06-10** | `36e1968d` | **SUCCESS** | 0 | **486** | Fallback (taxonomy + program diff) |
| **2026-06-11** | Automático | SKIPPED_NO_NEW_DATA | 0 | 0 | Sin fuentes (taxonomy/program sin datos para 06-11) |
| **2026-06-12** | No ejecutado | — | 0 | 0 | Sin fuentes |

### Detalle del backfill 06-10:

| Movement Type | Rows | Descripción |
|--------------|------|-------------|
| STATE_CHANGE | 260 | Cambios de segment entre 06-09 y 06-10 (ej. ACTIVE_GROWTH → TOP_PERFORMER) |
| PROGRAM_CHANGE | 226 | Cambios de programa entre 06-09 y 06-10 (ej. UNASSIGNED → RNA_ONBOARDING) |
| **Total** | **486** | |

---

## 6. ENDPOINT SMOKE (BEFORE vs AFTER)

| Endpoint | Before (orphan) | Before (canonical empty) | After (backfill) |
|----------|-----------------|-------------------------|-----------------|
| `/movement-analytics/stats` | 68,473 transitions, 200 OK | 0 transitions, 200 OK | **486 transitions, 200 OK** |
| `/movement-analytics/matrix` | Data completa, 200 OK | 0 movements, 200 OK | **486 movements, 200 OK** |
| `/movement-analytics/winners` | **500** (tabla vacía V2) | 200 OK (empty) | **200 OK (empty — sin movement_score)** |
| `/movement-analytics/losers` | **500** (tabla vacía V2) | 200 OK (empty) | **200 OK (empty — sin movement_score)** |

---

## 7. BUILD VERIFICACIÓN

| Artefacto | Comando | Resultado |
|-----------|---------|-----------|
| Backend compile | `python -m compileall backend\app` | ✅ PASS |
| Frontend build | `npm run build` (4.64s) | ✅ PASS |

---

## 8. RIESGOS REMANENTES

| Riesgo | Severidad | Plan |
|--------|-----------|------|
| **Winners/losers vacíos** | MEDIUM | Canonical table no tiene `movement_score`. Se requiere agregar scoring o eliminar winners/losers del UI. |
| **06-11 y 06-12 sin movement** | HIGH | Requiere ejecución del pipeline V2 para esas fechas. Las fuentes (taxonomy, program) deben poblarse primero. |
| **Trace writer dead code** | LOW | `diagnostic_trace_writer.py` existe pero nunca se llama. Podría eliminarse o integrarse al scheduler. |
| **Fallback taxonomy diff lento** | LOW | El JOIN entre dos fechas de 68K rows es ~4s. Aceptable para backfill pero podría optimizarse con índices. |

---

## 9. VEREDICTO

```
LG_CAN_1B_CERTIFIED
```

### Criterio GO cumplido:

| Criterio | Estado |
|----------|--------|
| `yego_lima_v2_movement_fact` tiene datos reales | ✅ 486 rows para 06-10 |
| Endpoints movement responden 200 | ✅ stats, matrix, winners, losers todos 200 |
| No se usa `driver_movement_fact` | ✅ Deprecated, 0 referencias activas |
| No se rompe taxonomy | ✅ Sin cambios en tabla taxonomy |
| Build backend PASS | ✅ `compileall` OK |
| Build frontend PASS | ✅ `npm run build` OK |

### Movimiento canónico vive en:

```
growth.yego_lima_v2_movement_fact  ✅
```

No en tablas huérfanas. ✅
