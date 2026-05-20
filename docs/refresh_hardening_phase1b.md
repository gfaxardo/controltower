# Fase 1B — Refresh Hardening: Reporte de Implementación

**Fecha**: 2026-05-19
**Estado**: GO / NO-GO (pendiente de validación en staging)
**Fase**: Control Foundation — Subfase 1B

---

## 1. Resumen de cambios implementados

### 1.1 Migración nueva (139_refresh_run_log)

| Objeto | Tipo | Schema | Descripción |
|--------|------|--------|-------------|
| `ops.refresh_run_log` | Tabla | ops | Registro de trazabilidad de ejecuciones de refresh. Cada corrida de pipeline, script o job deja una fila con metadata de lock, scope, periodo, resultado y duración. |
| `ops.v_refresh_latest_status` | Vista | ops | Última corrida por (refresh_name, pipeline_name, step_name). Usado por GET /ops/refresh/status. |

**Índices**: 5 índices para consultas por fecha, nombre, status, pipeline/step y GIN sobre scope JSONB.

**Archivo**: `backend/alembic/versions/139_refresh_run_log.py`

### 1.2 Service central (refresh_control_service.py)

| Componente | Descripción |
|------------|-------------|
| `_compute_lock_key()` | Hash determinista SHA256 → int64 para `pg_try_advisory_lock`. Estable entre procesos y reinicios. |
| `start_refresh_run()` | Adquiere lock vía `pg_try_advisory_lock`, inserta fila `running` en `ops.refresh_run_log`, retorna `RefreshGuardState`. |
| `finish_refresh_run()` | Actualiza `status='success'`, `finished_at`, `duration_seconds`, libera lock. |
| `fail_refresh_run()` | Actualiza `status='failed'`, `error_message`, libera lock. |
| `skip_refresh_run()` / `block_refresh_run()` | Casos controlados de skip/block. |
| `refresh_guard()` | Context manager que automatiza lock + ledger + finally release. |
| `check_destructive_sql()` | Detecta `DROP MATERIALIZED VIEW`, `DROP VIEW`, `DROP TABLE`, `CASCADE` en texto SQL. |
| `check_destructive_sql_safe()` | Versión booleana sin raise. |
| `_production_destructive_allowed()` | Verifica flag `CT_ALLOW_DESTRUCTIVE_REFRESH` en producción. |
| `is_scheduler_enabled()` | Verifica `CT_SCHEDULER_ENABLED` (false por defecto en prod). |
| `get_refresh_status()` | Consulta `ops.v_refresh_latest_status` con filtros opcionales. |

**Archivo**: `backend/app/services/refresh_control_service.py`

### 1.3 Settings flags (settings.py)

| Flag | Default | Descripción |
|------|---------|-------------|
| `CT_ALLOW_DESTRUCTIVE_REFRESH` | `false` | Solo true en ventana de backfill autorizada. |
| `CT_SCHEDULER_ENABLED` | `false` | En producción debe ser false salvo configuración explícita. |
| `CT_REFRESH_LOCKS_ENABLED` | `true` | Habilita advisory locks anti-concurrencia. |
| `CT_REFRESH_LEDGER_ENABLED` | `true` | Habilita registro en ops.refresh_run_log. |

### 1.4 Scripts protegidos

| Script | Protección aplicada |
|--------|-------------------|
| `run_pipeline_refresh_and_audit.py` | `refresh_guard` con `refresh_name='pipeline_refresh_and_audit'`, `--trigger-source` arg. |
| `run_supply_refresh_pipeline.py` | `refresh_guard` con `refresh_name='supply_refresh_pipeline'`. **Además**: integra `ops.refresh_supply_mvs()` como paso 2. |
| `run_driver_lifecycle_build.py` | `refresh_guard` en `__main__`. **Guardrail**: bloquea ejecución si detecta DROP+CASCADE en `driver_lifecycle_build.sql` en producción sin `CT_ALLOW_DESTRUCTIVE_REFRESH`. |
| `refresh_hourly_first_chain.py` | `refresh_guard` con `refresh_name='refresh_hourly_first_chain'`. |
| `refresh_business_slice_mvs.py` | `refresh_guard` con `refresh_name='refresh_business_slice_mvs'`, `--trigger-source` arg. |
| `business_slice_real_refresh_job.py` | `run_business_slice_real_refresh_job_safe()` wrapper para APScheduler con su propio advisory lock. |

### 1.5 APScheduler fix (main.py)

- **Antes**: `BackgroundScheduler` corría siempre que `OMNIVIEW_REAL_REFRESH_ENABLED` o `OMNIVIEW_REAL_WATCHDOG_ENABLED` fueran true, sin verificar entorno ni evitar multi-worker.
- **Ahora**: Verifica `CT_SCHEDULER_ENABLED` vía `is_scheduler_enabled()`. En producción solo arranca si explícitamente habilitado. El job programado usa `run_business_slice_real_refresh_job_safe()` que adquiere advisory lock antes de ejecutar.

### 1.6 Endpoint de status

| Endpoint | Descripción |
|----------|-------------|
| `GET /ops/refresh/status` | Últimas N corridas de refresh_run_log. Filtrable por `refresh_name`, `pipeline_name`. Incluye `stale_warning` boolean. |

**Archivo**: `backend/app/routers/ops_refresh.py:18-50`

### 1.7 Integración de ops.refresh_supply_mvs()

- **Antes (C3)**: `ops.refresh_supply_mvs()` existía (migración 060) pero NO era llamada por nadie. `mv_supply_weekly` y `mv_supply_monthly` estaban permanentemente stale.
- **Ahora**: `run_supply_refresh_pipeline.py` ejecuta `ops.refresh_supply_mvs()` como paso 2 (después de `ops.refresh_supply_alerting_mvs()`), con try/except no bloqueante.

---

## 2. Cómo se evita doble refresh

1. **Advisory lock por pipeline**: Cada script adquiere `pg_try_advisory_lock(lock_key)` con key derivada del `refresh_name`. Si otro proceso ya tiene el lock, el segundo proceso registra `status='skipped'` en `refresh_run_log` y termina con `sys.exit(0)`.
2. **Multi-worker APScheduler**: El scheduler está desactivado por defecto en producción (`CT_SCHEDULER_ENABLED=false`). Si se activa, cada job pasa por `refresh_guard` que garantiza exclusión mutua vía advisory lock (no depende de memoria del proceso).

---

## 3. Cómo se bloquea DROP+CASCADE en producción

1. Antes de ejecutar SQL de `driver_lifecycle_build.sql`, se analiza el texto completo.
2. Si se detectan patrones `DROP MATERIALIZED VIEW`, `DROP VIEW`, `DROP TABLE`, o `CASCADE`:
   - Si `ENVIRONMENT=production` (o `prod`) **Y** `CT_ALLOW_DESTRUCTIVE_REFRESH` no es `1/true/yes` → **BLOQUEADO**.
   - Se imprime mensaje claro: _"Blocked destructive SQL in production. Set CT_ALLOW_DESTRUCTIVE_REFRESH=1 only for an authorized backfill window."_
   - El script termina con código controlado.

---

## 4. Qué pasó con ops.refresh_supply_mvs()

**Integrado en `run_supply_refresh_pipeline.py`** como paso 2 (después de `ops.refresh_supply_alerting_mvs()`). Es no bloqueante: si falla, se registra warning en log pero el pipeline continúa.

La función `ops.refresh_supply_mvs()` definida en migración 060 refresca `mv_supply_weekly` y `mv_supply_monthly` con `REFRESH MATERIALIZED VIEW CONCURRENTLY`. No usa DROP+CASCADE, por lo que es segura para integrar.

**Riesgo remanente**: Si `ops.refresh_supply_mvs()` falla consistentemente (ej: la MV no tiene unique index), `mv_supply_weekly` y `mv_supply_monthly` seguirán stale. El sistema lo reporta como warning en logs y en `refresh_run_log.warning_message`.

---

## 5. QA — Tests ejecutados

| Test | Resultado esperado |
|------|-------------------|
| `lock_key_deterministic_same_name` | Mismo refresh_name → misma key |
| `lock_key_different_pipelines` | Distintos nombres → distintas keys |
| `lock_key_in_int64_range` | Key dentro de rango válido PG |
| `detects_DROP_MATERIALIZED_VIEW` | Detecta patrón destructivo |
| `detects_DROP_VIEW` | Detecta patrón destructivo |
| `detects_DROP_TABLE` | Detecta patrón destructivo |
| `detects_CASCADE` | Detecta patrón destructivo |
| `ignores_safe_select` | No detecta SELECT como destructivo |
| `env_name_not_empty` | ENVIRONMENT definido |
| `locks_enabled_default_true` | CT_REFRESH_LOCKS_ENABLED default true |
| `ledger_enabled_default_true` | CT_REFRESH_LEDGER_ENABLED default true |
| `CT_ALLOW_DESTRUCTIVE_REFRESH_exists` | Flag en settings |
| `CT_SCHEDULER_ENABLED_exists` | Flag en settings |
| `CT_REFRESH_LOCKS_ENABLED_exists` | Flag en settings |
| `CT_REFRESH_LEDGER_ENABLED_exists` | Flag en settings |
| `refresh_run_log_table_exists` | Tabla existe (requiere migración aplicada) |
| `v_refresh_latest_status_exists` | Vista existe (requiere migración aplicada) |
| `lock_acquired_in_test` | Lock se adquiere |
| `ledger_status_success` | Log registra success |
| `first_lock_acquired` | Primer proceso obtiene lock |
| `second_lock_skipped` | Segundo proceso es skipped |

**Script**: `backend/scripts/validate_refresh_hardening_phase1b.py`

---

## 6. Riesgos pendientes (NO resueltos en esta fase)

| Riesgo | Fase pendiente |
|--------|---------------|
| Full refresh histórico (C1) — MVs se refrescan completas sin WHERE | Fase 1D Closed Period Protection |
| Sin rollback si refresh de supply falla a medias (H2) | Fase 1D |
| GET /ops/driver-lifecycle/series sin park_id hace joins pesados (H4) | Fase 1F Performance |
| Business slice month_fact se recalcula cada scheduler run (H6) | Fase 1D |
| Sin métricas de duración persistidas por MV individual | Fase 1F |
| Hallazgo Bogotá — parks con envíos/moto sin reglas Delivery en business_slice | Fase 1C Business Slice Mapping Audit |

---

## 7. Comandos de deploy

```bash
# 1. Aplicar migración
cd backend
alembic upgrade head

# 2. Verificar tablas
python -c "
from app.db.connection import get_db
with get_db() as conn:
    cur = conn.cursor()
    cur.execute('SELECT count(*) FROM ops.refresh_run_log')
    print('refresh_run_log:', cur.fetchone()[0], 'rows')
    cur.execute('SELECT count(*) FROM ops.v_refresh_latest_status')
    print('v_refresh_latest_status:', cur.fetchone()[0], 'rows')
    cur.close()
"

# 3. Ejecutar validación (NO ejecuta refrescos reales)
python -m scripts.validate_refresh_hardening_phase1b

# 4. Verificar endpoint
curl http://localhost:8000/ops/refresh/status
```

## 8. Rollback

```bash
# La migración es backward-compatible. Para eliminar:
cd backend
alembic downgrade 138

# Los scripts siguen funcionando sin refresh_guard (los imports fallan silenciosamente
# porque refresh_control_service.py usa try/except y defaults seguros).
```

---

## 9. Siguiente fase recomendada

**Fase 1C — Closed Period Protection + Refresh Ledger operativo**

Objetivos:
- Crear `ops.period_state` (period_start, grain, is_closed, data_hash)
- Modificar funciones de refresh para respetar `is_closed`
- Agregar `POST /ops/admin/period/close` y `/reopen`
- Política: cerrar mes anterior el día 5, cerrar semana anterior el lunes
- Auditoría de cobertura de business_slice mapping (hallazgo Bogotá)

---

## 10. Archivos modificados/creados

| Archivo | Acción |
|---------|--------|
| `backend/alembic/versions/139_refresh_run_log.py` | **NUEVO** — migración |
| `backend/app/services/refresh_control_service.py` | **NUEVO** — service central |
| `backend/app/settings.py` | **MODIFICADO** — +4 flags |
| `backend/app/main.py` | **MODIFICADO** — APScheduler fix |
| `backend/app/routers/ops_refresh.py` | **MODIFICADO** — + GET /ops/refresh/status |
| `backend/app/services/business_slice_real_refresh_job.py` | **MODIFICADO** — +safe wrapper |
| `backend/scripts/run_pipeline_refresh_and_audit.py` | **MODIFICADO** — refresh_guard |
| `backend/scripts/run_supply_refresh_pipeline.py` | **MODIFICADO** — refresh_guard + supply_mvs |
| `backend/scripts/run_driver_lifecycle_build.py` | **MODIFICADO** — guardrail + refresh_guard |
| `backend/scripts/refresh_hourly_first_chain.py` | **MODIFICADO** — refresh_guard |
| `backend/scripts/refresh_business_slice_mvs.py` | **MODIFICADO** — refresh_guard |
| `backend/scripts/validate_refresh_hardening_phase1b.py` | **NUEVO** — QA tests |
