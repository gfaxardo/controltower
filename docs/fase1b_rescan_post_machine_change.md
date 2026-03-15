# FASE 1B — Re-scan post cambio de máquina

**Proyecto:** YEGO Control Tower  
**Fecha:** 2025-03-14  
**Objetivo:** Determinar con evidencia real el estado del sistema tras traer la rama remota.

---

## 1. Matriz de estado (artifact × expected × found × status)

| Artifact | Expected from previous phases | Found now | Status | Comments |
|----------|-------------------------------|-----------|--------|---------|
| **Backend** |
| `app/routers/observability.py` | Router Fase 1 | Sí, prefix `/ops/observability` | ok | Montado en main con prefix `/ops` |
| `app/services/observability_service.py` | Servicio observability | Sí, lee registry + refresh_log + vistas | ok | get_overview, modules, artifacts, lineage, freshness, log_refresh |
| `app/routers/ops.py` | Plan vs Real, Real LOB, Supply, etc. | Sí, muchas rutas bajo `/ops/` | ok | plan-vs-real, real-lob, supply, system-health, etc. |
| `app/routers/plan.py`, `real.py`, `core.py` | Plan, Real, Core | Sí | ok | |
| `app/routers/driver_lifecycle.py` | Driver lifecycle | Sí, bajo `/ops/driver-lifecycle/` | ok | |
| `app/main.py` | Inclusión de todos los routers | Sí, incluye observability con prefix `/ops` | ok | |
| Imports `from app.*` | Sin rotos | Verificado: todos los módulos referenciados existen | ok | |
| **Migraciones** |
| `092_observability_artifact_registry_and_refresh_log.py` | Registry + refresh log + vistas observability | Sí | ok | Crea observability_artifact_registry, observability_refresh_log, v_observability_* |
| `093_merge_real_lob_governance_and_observability.py` | Merge de heads | Sí, sin cambios de schema | ok | |
| `075_control_tower_data_observability.py` | Observabilidad datos | Sí (en repo) | ok | |
| Última migración en código | Head lineal | 096_real_lob_mvs_partial_120d | ok | Cadena: 093→094→095→096 |
| Migraciones real_lob / plan_vs_real / supply / driver_lifecycle | Varias 041, 043, 044, 046, 047, 053, 060, 056, etc. | Presentes en versions/ | ok | |
| **Frontend** |
| `SystemHealthView.jsx` | Vista System Health | Sí | ok | Importa getSystemHealth, getObservabilityOverview, getObservabilityArtifacts |
| `api.js` observability | getObservabilityOverview, Artifacts, Lineage, Freshness | Sí | ok | Rutas `/ops/observability/*` |
| Tabs principales | Resumen, Real, Supply, Conductores en riesgo, Ciclo de vida, Plan y validación | Sí en App.jsx | ok | mainNavTabs + Diagnósticos dropdown |
| Tab System Health | Dentro de Diagnósticos ▾ | Sí, abre SystemHealthView | ok | |
| Plan vs Real / MonthlySplitView / WeeklyPlanVsRealView | Existen | Sí | ok | Bajo Plan y validación |
| **Scripts** |
| `refresh_real_lob_mvs_v2.py` | Refresco MVs Real LOB v2 + log_refresh | Sí, usa log_refresh de observability_service | ok | Escribe en observability_refresh_log |
| `close_real_lob_governance.py` | Cierre E2E Real LOB, opcional log_refresh | Sí, log_refresh opcional | ok | |
| `run_supply_refresh_pipeline.py` | Pipeline supply | Sí (en scripts) | ok | Supply usa supply_refresh_log |
| `run_driver_lifecycle_build*.py` | Driver lifecycle | Sí | ok | |
| Scripts de auditoría / backfill / plan | Varios | Presentes | ok | |
| **SQL / Modelos** |
| `ops.observability_artifact_registry` | Tabla | Creada en 092 | ok | |
| `ops.observability_refresh_log` | Tabla | Creada en 092, columnas rows_before/after, duration en 095 | ok | |
| `ops.v_observability_module_status` | Vista | En 092 | ok | |
| `ops.mv_real_lob_month_v2`, `ops.mv_real_lob_week_v2` | MVs Real LOB v2 | Definidas en 096 (120d), 094, 047, etc. | ok | trips, revenue, margin_total, etc. |
| `ops.mv_real_trips_monthly` | MV Real mensual (plan vs real) | Referenciada en real_repo, plan_real_split, 013, 010 | ok | trips_real_completed, active_drivers_real, revenue_real_yego, avg_ticket_real |
| `ops.v_plan_vs_real_realkey_final` | Vista Plan vs Real | Referenciada en plan_vs_real_service | ok | |
| **Tests** | Tests observability / integración | No buscado en detalle | unknown | Tests existen en backend/tests |

---

## 2. Resumen ejecutivo del re-scan

- **Backend:** Completo. Routers, services y adapters coherentes; sin imports rotos.
- **Migraciones:** Cadena lineal hasta 096. Observability (092), merge (093) y Real LOB (094–096) presentes.
- **Frontend:** System Health existe y consume `/ops/system-health` y `/ops/observability/*`. Navegación y tabs alineados con lo esperado.
- **Scripts:** `refresh_real_lob_mvs_v2.py` y `close_real_lob_governance.py` integrados con `log_refresh` (observability). Supply y driver lifecycle con scripts propios.
- **Estado:** El sistema en código está **coherente** con lo esperado tras traer la rama remota. La incertidumbre restante es **runtime**: si las migraciones están aplicadas en la BD local y si las MVs están refrescadas (depende del entorno).

---

## 3. Veredicto Fase 1 (Observability) — STEP 2

**Fase 1: parcialmente cerrada / cerrada en código.**

- **En código:** Completa. Existen `observability_service.py`, router `observability` bajo `/ops/observability/*`, migración 092 (registry + refresh_log + vistas), 093 (merge). El frontend `SystemHealthView` consume `getObservabilityOverview` y `getObservabilityArtifacts`; las rutas están en `api.js`. El script `refresh_real_lob_mvs_v2.py` llama a `log_refresh` y deja trazabilidad en `observability_refresh_log`.
- **En runtime:** Depende de que en esta máquina se hayan ejecutado `alembic upgrade head` y al menos un refresh de MVs. Si las tablas/vistas de observability no existen, el servicio devuelve listas vacías o mensaje de error (no rompe la app).
- **Conclusión:** Fase 1 está **implementada e integrada**. Si tras cambiar de máquina no se han aplicado las migraciones, la observabilidad aparecerá "sin módulos" hasta ejecutar `alembic upgrade head` y poblar el registry (la migración 092 ya inserta filas de ejemplo para Real LOB). No se ha rediseñado ni roto nada; no hay correcciones mínimas obligatorias salvo aplicar migraciones si faltan.

---

## 4. Qué verificar en runtime (esta máquina)

1. `alembic current` en backend: que coincida con head (096; tras aplicar 097 será 097).
2. Existencia de `ops.observability_artifact_registry` y `ops.observability_refresh_log` (y vistas).
3. Que el endpoint `GET /ops/observability/overview` responda sin error y, si hay datos, que devuelva módulos/artifacts.
4. Que System Health en la UI cargue sin error y muestre mensaje o módulos según el estado de la BD.
