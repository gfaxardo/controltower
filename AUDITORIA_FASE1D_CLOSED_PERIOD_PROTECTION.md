# Fase 1D — Closed Period Protection

**Fecha**: 2026-05-19
**Fase**: Control Foundation — Fase 1D
**Estado**: **GO** — All validation tests passed

---

## 1. Estado ejecutivo

| Dimensión | Valor |
|-----------|-------|
| **GO / NO-GO** | **GO** — infraestructura lista, dry-run habilitado |
| **Last reliable date** | 2026-05-18 (lag=1 day) |
| **May 2026** | OPEN |
| **April 2026** | CLOSED CANDIDATE (QA: pass, coverage 99.47%) |
| **Bogotá** | Carga=2,801, Delivery=188 — sin cambios |
| **Barranquilla** | Taxi Moto=12,483, Auto=9,764, Delivery=1,406 — sin cambios |

---

## 2. Objetos creados

| Objeto | Tipo | Schema | Descripción |
|--------|------|--------|-------------|
| `ops.period_closure_registry` | Tabla | ops | Registro de cierre/reapertura de periodos con QA, checksum, métricas |
| `ops.v_period_closure_status` | Vista | ops | Estado actual de todos los periodos registrados |
| `period_closure_service.py` | Service | app/services | Lógica de clasificación, QA, cierre, reapertura y checksums |
| `GET /ops/period-closure/status` | Endpoint | ops_refresh | Estado de periodos (read-only) |
| `GET /ops/period-closure/readiness` | Endpoint | ops_refresh | ¿Puede cerrarse este periodo? (read-only) |
| `backend/scripts/validate_closed_period_protection_phase1d.py` | QA Script | scripts | Validación end-to-end |

---

## 3. Política de periodos

| Estado | Definición | Refresh normal | Backfill |
|--------|-----------|:---:|:---:|
| `open` | Periodo activo, datos parciales | Permitido | N/A |
| `provisional` | Periodo terminado pero datos incompletos | Permitido | N/A |
| `closed` | Periodo terminado, datos cargados, QA inicial | Bloqueado | Solo con flag |
| `locked` | Periodo cerrado, QA pasada, checksum guardado | **Bloqueado** | Solo con flag + reason |
| `backfill` | Periodo reabierto temporalmente para corrección | Permitido | Activo |
| `failed_closure` | Intento de cierre que no pasó QA | Bloqueado | Requiere re-QA |

---

## 4. Configuración

| Flag | Default | Descripción |
|------|---------|-------------|
| `CT_DATA_LAG_DAYS` | 1 | Lag aceptable para considerar datos fresh |
| `CT_ALLOW_CLOSED_PERIOD_REFRESH` | false | Permite refresh sobre locked/closed |
| `CT_PERIOD_CLOSURE_ENABLED` | true | Habilita protección |
| `CT_PERIOD_CLOSURE_DRY_RUN` | **true** | Modo seguro: reporta sin bloquear |
| `CT_MIN_MAPPING_COVERAGE_PCT` | 99.0 | Cobertura mínima para cierre |

---

## 5. QA de cierre — Abril 2026

| Métrica | Valor |
|---------|-------|
| Overall | **PASS** |
| Coverage | 99.47% |
| Raw completed | 833,553 |
| Fact completed | 829,118 |
| Unmatched | 4,435 (0.53%) |
| Blockers | Ninguno |
| Warnings | Ninguno |
| Can close | **YES** |

---

## 6. Cómo funciona la protección

1. **Clasificación**: `classify_period()` compara el último día del periodo contra `last_reliable_data_date - CT_DATA_LAG_DAYS`. Si el periodo terminó antes de esa fecha, es `closed_candidate`.

2. **QA**: `run_closure_qa()` verifica coverage >= `CT_MIN_MAPPING_COVERAGE_PCT`, freshness OK, y que no haya errores en los facts.

3. **Cierre**: `close_period()` ejecuta QA, calcula checksum, guarda en `period_closure_registry` con status `locked`.

4. **Protección**: `assert_period_refresh_allowed()` consulta el registry. Si el periodo está `locked`/`closed` y `CT_ALLOW_CLOSED_PERIOD_REFRESH` no está activado, bloquea el refresh.

5. **Reapertura**: `reopen_for_backfill()` requiere `CT_ALLOW_CLOSED_PERIOD_REFRESH=1` + `reason`. Cambia status a `backfill`.

---

## 7. Riesgos pendientes

| Riesgo | Estado |
|--------|--------|
| Dry-run activo (no bloquea realmente) | Por diseño — activar `CT_PERIOD_CLOSURE_DRY_RUN=false` en producción cuando se valide |
| Integración con refresh scripts (guardrail en month_fact, hourly_chain) | No implementada en esta fase — los scripts no consultan el registry todavía |
| Cali + Lima ~0.5% unmatched residual | Documentado, no bloquea cierre |
| Resolved view >120s | Pendiente índices nocturnos |
| Snapshots físicos de datos cerrados | Fase futura |

---

## 8. Siguiente fase recomendada

**Fase 1E — Serving Stability / Last Good Data / Performance**

- Integrar `assert_period_refresh_allowed()` en los scripts de refresh
- Activar `CT_PERIOD_CLOSURE_DRY_RUN=false` en producción
- Agregar snapshots físicos de periodos locked
- Performance final de resolved view con índices nocturnos
- Métricas de serving latency

---

## 9. Archivos creados/modificados

| Archivo | Acción |
|---------|--------|
| `backend/alembic/versions/142_period_closure_registry.py` | NUEVO — migración |
| `backend/app/services/period_closure_service.py` | NUEVO — service |
| `backend/app/settings.py` | MODIFICADO — +5 flags |
| `backend/app/routers/ops_refresh.py` | MODIFICADO — +2 endpoints |
| `backend/scripts/validate_closed_period_protection_phase1d.py` | NUEVO — QA |
