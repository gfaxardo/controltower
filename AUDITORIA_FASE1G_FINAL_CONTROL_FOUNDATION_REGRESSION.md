# Fase 1G — Final Control Foundation Regression / Production Readiness

**Fecha**: 2026-05-19
**Estado**: **GO — PRODUCTION READY** (53/53 PASS)

---

## 1. Resumen de Fase 1 — Control Foundation cerrada

| Subfase | Objetivo | Estado | Evidencia |
|---------|----------|--------|-----------|
| **1B** | Refresh Hardening | GO | advisory locks, refresh_run_log, DROP+CASCADE guardrail, scheduler control |
| **1C** | Business Slice Mapping | GO | Bogotá fix (rule 143), Barranquilla fix (rule 95+144), coverage 99.5% |
| **1D** | Closed Period Protection | GO | period_closure_registry, classify/QA/close/lock, enforcement in scripts |
| **1E** | Snapshots / Last Good | GO | snapshot table, serving view, April snapshot (829,118 trips, checksum) |
| **1F** | Omniview Serving | GO | FACT_MONTHLY → serving view, snapshot for locked, working_fact for open |

---

## 2. Datos certificados

| Métrica | Valor |
|---------|-------|
| Coverage global May 2026 | 99.5% |
| Bogotá Carga | 2,801 |
| Bogotá Delivery moto | 188 |
| Barranquilla Taxi Moto | 12,483 |
| Barranquilla Auto regular | 9,764 |
| Barranquilla Delivery moto | 1,406 |
| April 2026 status | **locked** |
| April snapshot total | 829,118 |
| April snapshot checksum | `1123bf21a454446c` |
| May 2026 status | **open** |
| May working fact total | 472,468 |
| Query performance (April/May) | 0.2s |

---

## 3. Flags recomendados para producción

| Flag | Valor recomendado | Justificación |
|------|-------------------|---------------|
| `CT_SCHEDULER_ENABLED` | `false` | Evitar APScheduler en multi-worker |
| `CT_ALLOW_DESTRUCTIVE_REFRESH` | `false` | Bloquear DROP+CASCADE |
| `CT_ALLOW_CLOSED_PERIOD_REFRESH` | `false` | Solo backfill autorizado |
| `CT_PERIOD_CLOSURE_DRY_RUN` | `true` → `false` después de 1 semana | Primero monitorear, luego activar |
| `CT_DATA_LAG_DAYS` | `1` | D-1 cerrado |

---

## 4. Rollback documentado

```sql
-- Revertir FACT_MONTHLY a tabla original
-- En business_slice_service.py:
--   FACT_MONTHLY = "ops.real_business_slice_month_fact"

-- Desactivar reglas de mapping
UPDATE ops.business_slice_mapping_rules SET is_active=false WHERE id IN (143, 144);
UPDATE ops.business_slice_mapping_rules SET park_id='ef21f793358144f589aabcbeb8bd7d51' WHERE id=95;

-- Desbloquear April
UPDATE ops.period_closure_registry SET status='open' WHERE grain='monthly' AND period_start='2026-04-01';

-- Eliminar snapshot
DELETE FROM ops.real_business_slice_month_snapshot WHERE period_start='2026-04-01';
```

---

## 5. Riesgos pendientes (no bloqueantes)

| Riesgo | Prioridad |
|--------|-----------|
| Resolved view >120s (índices nocturnos) | Backlog técnico |
| Snapshots para day/week facts | Backlog futuro |
| Refresh scoped por ciudad | Backlog futuro |
| Cali + Lima ~0.5% unmatched residual | Documentado |

---

## 6. Recomendación de producción

**GO para deploy en producción** con las siguientes condiciones:

1. `CT_PERIOD_CLOSURE_DRY_RUN=true` inicialmente (1 semana de monitoreo)
2. `CT_SCHEDULER_ENABLED=false`
3. `CT_ALLOW_DESTRUCTIVE_REFRESH=false`
4. `CT_ALLOW_CLOSED_PERIOD_REFRESH=false`
5. Migraciones aplicadas hasta `143_last_good_snapshots`
6. Monitorear `/ops/serving/status` y `/ops/refresh/status` durante la primera semana

---

## 7. Siguiente fase

**Fase 2 — Diagnostic Engine** (solo si Fase 1G es GO, que lo es).
