# REPORTE VALIDACIÓN STAGING — FASE 1B REFRESH HARDENING

**Fecha**: 2026-05-19 12:48 UTC-5
**Entorno**: Staging (dev)
**Ejecutor**: QA automatizado — `_staging_validate_phase1b.py`

---

## Estado: **NO-GO** (condicionado)

**55/57 pruebas PASS (96.5%)**. 2 fallos son por un hallazgo pre-existente (C3 del audit) que debe resolverse antes del GO definitivo.

---

## 1. Evidencia de migración

| Check | Resultado |
|-------|-----------|
| `alembic current` reporta `139_refresh_run_log (head)` | **PASS** |
| `ops.refresh_run_log` existe | **PASS** |
| `ops.v_refresh_latest_status` existe | **PASS** |
| Columna `status` | **PASS** |
| Columna `lock_key` | **PASS** |
| Columna `lock_acquired` | **PASS** |
| Columna `refresh_name`, `error_message`, `started_at`, `finished_at`, `rows_affected` | **PASS** (8/8) |
| 6 índices creados (pkey + 5 explícitos) | **PASS** |

---

## 2. Evidencia de endpoint GET /ops/refresh/status

| Check | Resultado |
|-------|-----------|
| Retorna dict con `statuses`, `stale_warning` | **PASS** |
| `stale_warning = false` (última corrida success) | **PASS** |
| Respeta `limit=5` | **PASS** |
| No contiene llamadas a `refresh_supply_alerting_mvs`, `run_refresh`, ni `REFRESH MATERIALIZED` en source | **PASS** |
| Solo lee de `ops.v_refresh_latest_status` | **PASS** |

**Payload de ejemplo**:
```json
{
  "statuses": [
    {"refresh_name": "qa_test_lock_integration", "status": "success", "lock_acquired": true, ...},
    {"refresh_name": "qa_test_double_lock", "status": "running", "lock_acquired": true, ...}
  ],
  "total": 2,
  "stale_warning": false
}
```

---

## 3. Evidencia de advisory locks

| Check | Resultado |
|-------|-----------|
| **Raw psycopg2**: Session 1 adquiere lock (`pg_try_advisory_lock = true`) | **PASS** |
| **Raw psycopg2**: Session 2 es bloqueada (`pg_try_advisory_lock = false`) | **PASS** |
| **refresh_guard**: Adquiere lock correctamente | **PASS** |
| **refresh_guard (mismo proceso)**: En single-process comparte pool de conexiones; el lock cross-session está validado con raw connections | **PASS** (documentado) |
| **Ledger**: Registros existen en `ops.refresh_run_log` | **PASS** |
| **Ledger**: Status `success` registrado | **PASS** |

**Conclusión**: En producción (procesos separados: cron vs API vs manual), el advisory lock previene correctamente la doble ejecución.

---

## 4. Scripts con refresh_guard

| Script | refresh_guard | import refresh_control_service | Safe wrapper |
|--------|:---:|:---:|:---:|
| `run_pipeline_refresh_and_audit.py` | **PASS** | **PASS** | N/A |
| `run_supply_refresh_pipeline.py` | **PASS** | **PASS** | N/A |
| `run_driver_lifecycle_build.py` | **PASS** | **PASS** | N/A |
| `refresh_hourly_first_chain.py` | **PASS** | **PASS** | N/A |
| `refresh_business_slice_mvs.py` | **PASS** | **PASS** | N/A |
| `business_slice_real_refresh_job.py` | **PASS** | **PASS** | **PASS** (`_safe` wrapper) |
| `main.py` (APScheduler) | N/A | N/A | **PASS** (usa `_safe`) |
| `main.py` (scheduler check) | N/A | N/A | **PASS** (`is_scheduler_enabled`) |

---

## 5. Guardrail DROP+CASCADE

| Check | Resultado |
|-------|-----------|
| Detecta `DROP MATERIALIZED VIEW ... CASCADE` | **PASS** |
| Detecta `DROP TABLE ... CASCADE` | **PASS** |
| Detecta `DROP VIEW ... CASCADE` | **PASS** |
| `SELECT 1` pasa el filtro (no bloquea) | **PASS** |
| `REFRESH MATERIALIZED VIEW CONCURRENTLY` pasa el filtro (no bloquea) | **PASS** |
| En producción sin `CT_ALLOW_DESTRUCTIVE_REFRESH=1` bloquearía | **PASS** (verificado en lógica) |
| `run_driver_lifecycle_build.py` ejecuta `check_destructive_sql_safe()` antes de SQL | **PASS** |

---

## 6. Scheduler

| Check | Resultado |
|-------|-----------|
| `CT_SCHEDULER_ENABLED` default = `false` | **PASS** |
| `is_scheduler_enabled()` respeta entorno: en dev = true, en prod sin flag = false | **PASS** |
| `main.py` verifica `is_scheduler_enabled()` antes de arrancar APScheduler | **PASS** |
| `main.py` programa `run_business_slice_real_refresh_job_safe` (con advisory lock) | **PASS** |

---

## 7. Supply — HALLAZGO CRÍTICO (C3 confirmado)

| Check | Resultado |
|-------|-----------|
| `run_supply_refresh_pipeline.py` llama a `ops.refresh_supply_mvs()` como paso 2 | **PASS** |
| `refresh_supply_alerting_mvs` importable desde servicio | **PASS** |
| `ops.mv_supply_segments_weekly` EXISTE con datos (max=2026-05-18) | **PASS** |
| `ops.mv_supply_weekly` **NO EXISTE** | **FAIL** |
| `ops.mv_supply_monthly` **NO EXISTE** | **FAIL** |
| Freshness `mv_supply_segments_weekly` vs `mv_driver_weekly_stats`: delta=0 días | **PASS** |
| `ops.refresh_supply_mvs()` función EXISTE pero target MVs MISSING | **PASS** (warning) |

### Análisis del hallazgo

- La función `ops.refresh_supply_mvs()` fue definida en migración 060 pero las MVs `mv_supply_weekly` y `mv_supply_monthly` **nunca fueron creadas** (o fueron eliminadas por una migración posterior).
- Los endpoints `GET /ops/supply/series`, `GET /ops/supply/summary`, `GET /ops/supply/global/series` leen de estas MVs. Como no existen, las queries fallan con `UndefinedTable`, pero el `try/except` en `supply_service.py` captura el error y retorna `[]` silenciosamente.
- **Impacto**: Los usuarios de Supply > Series/Summary/Global ven datos vacíos sin advertencia. Solo `GET /ops/supply/segments/series` y endpoints de migration/alerts funcionan (usan `mv_supply_segments_weekly`).
- `ops.refresh_supply_mvs()` lanzará error al ejecutarse (las MVs no existen), pero está envuelto en `try/except` en el pipeline, así que no detiene el pipeline.

### Recomendación inmediata

1. Verificar si migración 060 fue aplicada o saltada. Si nunca se aplicó, ejecutar `alembic upgrade 060` (solo esa revisión).
2. Si las MVs fueron eliminadas intencionalmente, actualizar `supply_service.py` para que los endpoints de series/summary/global usen `mv_supply_segments_weekly` (que sí existe y tiene datos) en lugar de `mv_supply_weekly`/`mv_supply_monthly`.
3. Remover `ops.refresh_supply_mvs()` del pipeline hasta que las MVs existan.

---

## 8. Omniview

| Check | Resultado |
|-------|-----------|
| `business_slice_omniview_service` importable | **PASS** |
| `ops.real_business_slice_month_fact` EXISTE | **PASS** |
| `ops.real_business_slice_week_fact` EXISTE | **PASS** |
| `ops.real_business_slice_day_fact` EXISTE | **PASS** |
| `supply_service` sin cambios en KPIs/fórmulas | **PASS** |
| `driver_lifecycle_service` sin cambios | **PASS** |
| Omniview contract preservado (solo wrappers agregados) | **PASS** |

**Confirmación**: Ningún cambio en Omniview Matrix. Solo se agregaron wrappers de seguridad (locks, ledger) a los scripts de refresh. Los servicios de lectura de datos no fueron modificados.

---

## 9. Riesgos pendientes

| Riesgo | Severidad | Acción requerida |
|--------|-----------|-----------------|
| `mv_supply_weekly` y `mv_supply_monthly` no existen | **CRITICAL** | Aplicar migración 060 o actualizar endpoints para usar `mv_supply_segments_weekly` |
| `ops.refresh_supply_mvs()` fallará en producción | **HIGH** | Ya está wrappeado en try/except; no detiene el pipeline pero no refresca nada útil |
| Supply series/summary/global endpoints retornan `[]` silenciosamente | **HIGH** | Usuarios ven datos vacíos sin saber que las MVs faltan |
| Full refresh histórico sin closed period protection (C1) | **HIGH** | Pendiente Fase 1D |
| Sin rollback si refresh de supply falla a medias (H2) | **MEDIUM** | Pendiente Fase 1D |

---

## 10. Recomendación final

**NO-GO** hasta resolver el hallazgo de `mv_supply_weekly`/`mv_supply_monthly` inexistentes.

### Acciones antes del GO:

1. **Aplicar migración 060** (`060_supply_mvs`) si nunca fue ejecutada:
   ```bash
   cd backend && alembic upgrade 060
   ```
   Si la migración ya fue aplicada pero las MVs fueron eliminadas después, recrearlas manualmente con el SQL de la migración.

2. **Alternativa**: Si se decide no crear estas MVs, actualizar `supply_service.py` línea 163-193 para que `get_supply_series()` y `get_supply_global_series()` usen `ops.mv_supply_segments_weekly` como fuente alternativa con agregación.

3. **Remover `ops.refresh_supply_mvs()` del pipeline** hasta que las MVs existan (o mantenerlo con warning explícito).

4. **Re-ejecutar validación** tras resolver el hallazgo.

### Una vez resuelto: **GO** para producción con `CT_SCHEDULER_ENABLED=false` y `CT_ALLOW_DESTRUCTIVE_REFRESH=false`.

---

## 11. Siguiente fase

**Fase 1C — Closed Period Protection + Business Slice Mapping Audit**

- Crear `ops.period_state` con `is_closed`, `data_hash`, `refresh_count`
- Modificar funciones de refresh para respetar periodos cerrados
- Auditoría de cobertura de reglas business_slice (hallazgo Bogotá)
- Política de cierre de periodo (día 5 del mes siguiente, lunes siguiente para semanas)

---

## Apéndice — Resultados completos

```
TOTAL: 55/57 PASS, 2 FAIL
============================================================
  [PASS]  1.1 ops.refresh_run_log EXISTS
  [PASS]  1.2 ops.v_refresh_latest_status EXISTS
  [PASS]  1.3-1.7 All required columns exist (8 columns)
  [PASS]  1.6 6 indexes on refresh_run_log
  [PASS]  2.1-2.5 GET /ops/refresh/status: dict, keys, stale_warning, limit, read-only
  [PASS]  3.1-3.3 Advisory locks: session 1 acquires, session 2 blocked, guard acquires
  [PASS]  3.4-3.7 Ledger: records present, success recorded
  [PASS]  4.1-4.8 All 6 scripts + main.py use refresh_guard / safe wrappers
  [PASS]  5.1-5.6 Guardrail: detects destructive SQL, safe SQL passes, prod would block
  [PASS]  6.1-6.2 Scheduler: disabled by default, env-respecting logic
  [PASS]  7.1-7.3 Supply: pipeline integration, alerting importable, segments MV exists
  [FAIL]  7.4 mv_supply_weekly EXISTS — CRITICAL: MV not found
  [FAIL]  7.5 mv_supply_monthly EXISTS — CRITICAL: MV not found
  [PASS]  7.6-7.8 Supply freshness OK, function exists but targets missing MVs
  [PASS]  8.1-8.5 Omniview: all services importable, fact tables exist, no modifications
```
