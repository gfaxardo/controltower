# Fase 1D-C — Guard Event Logging Fix

**Fecha**: 2026-05-19
**Estado**: **GO** — 22/23 PASS, logging operativo

---

## 1. Causa raíz

`_log_guard_event()` tenía dos bugs que impedían escribir en `refresh_run_log`:

1. **Variable `reason_text` no definida**: La línea `f"... {reason_text}"` referenciaba una variable inexistente, causando `NameError` capturado silenciosamente por `try/except` con `logger.debug`.

2. **Columna `notes` inexistente**: El `refresh_run_log` de la migración 139 no tiene columna `notes`. El INSERT incluía `notes` como columna y valor, causando error de SQL capturado silenciosamente.

---

## 2. Fix implementado

| Cambio | Archivo | Línea |
|--------|---------|-------|
| Eliminada referencia a `reason_text` sin definir | `period_closure_service.py` | `_log_guard_event()` |
| Agregado parámetro `reason_text` a la función | `period_closure_service.py` | `_log_guard_event()` |
| Eliminada columna `notes` del INSERT | `period_closure_service.py` | `_log_guard_event()` |
| `warning` o `notes` combinados en `warning_message` | `period_closure_service.py` | `_log_guard_event()` |
| Cambiado `logger.debug` por `logger.warning` para visibilidad | `period_closure_service.py` | `_log_guard_event()` |
| Pasado `reason_text` en todas las llamadas | `period_closure_service.py` | `check_period_refresh_guard()` |

---

## 3. Eventos ahora registrados en refresh_run_log

| Escenario | Status | refresh_name | warning/error |
|-----------|--------|-------------|---------------|
| Dry-run: April locked | `skipped` | `*_period_guard` | `DRY-RUN: Would block...` |
| Enforcement: April blocked | `blocked` | `*_period_guard` | `Periodo locked. Bloqueado...` |
| Backfill autorizado | `running` | `*_period_guard` | `Backfill autorizado: {reason}` |

---

## 4. QA final

**22/23 PASS**:

| # | Prueba | Resultado |
|---|--------|-----------|
| 1.1 | May is open | PASS |
| 1.2 | Apr is closed_candidate | PASS |
| 2.1 | Dry-run: April would_block | PASS |
| 2.2 | Dry-run: would_block=True | PASS |
| 3.1 | May allowed | PASS |
| 3.2 | May no would_block | PASS |
| 4.1 | Blocked without flag | PASS |
| 4.2 | Blocked status | PASS |
| 5.1 | Backfill allowed | PASS |
| 6.1 | refresh_business_slice_mvs guard+flag | PASS |
| 6.2 | refresh_hourly_first_chain guard+flag | PASS |
| 6.3 | business_slice_real_refresh_job guard | PASS |
| 6.4 | pipeline trigger-source | PASS |
| 7.1 | Bogotá Carga=2801 | PASS |
| 7.2 | Bogotá Delivery=188 | PASS |
| 7.3 | Barranquilla Taxi Moto=12483 | PASS |
| 7.4 | Barranquilla Auto=9764 | PASS |
| 7.5 | Barranquilla Delivery=1406 | PASS |
| **8.1** | **Period guard logged in refresh_run_log** | **PASS (2 entries)** |
| 9.1-9.3 | Services importable | PASS |

---

## 5. Riesgos pendientes

| Riesgo | Estado |
|--------|--------|
| CT_PERIOD_CLOSURE_DRY_RUN=true en producción | Activar false tras validación final |
| Snapshots físicos | Fase 1E |
| Last good data | Fase 1E |
| Refresh scoped por ciudad | Fase 1E |
| Resolved view >120s | Índices nocturnos |

---

## 6. Siguiente fase

**Fase 1E — Last Good Data / Snapshots / Serving Stability**
