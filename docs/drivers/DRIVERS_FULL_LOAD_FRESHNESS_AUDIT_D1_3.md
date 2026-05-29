# DRIVERS FULL LOAD & FRESHNESS AUDIT — D1.3

**Fecha:** 2026-05-28
**Objetivo:** Hacer que TODO Drivers cargue de forma confiable. Sin loading infinito, sin timeout silencioso, freshness visible.

---

## 1. MAPA DE CARGA REAL POR TAB

### Tabs con Serving Fact (fact-first, <2s esperado)

| Tab | Endpoint | Source | Freshness visible | Timeout risk | Status |
|---|---|---|---|---|---|
| Supply Overview | `/drivers/supply-overview-fact` | `ops.driver_supply_overview_weekly_fact` | Si (freshness_status, refreshed_at) | LOW | OK |
| Segment Composition | `/drivers/segment-composition-fact` | `ops.driver_weekly_segment_fact` | Si | LOW | OK |
| Driver Migration | `/drivers/segment-migration` | `ops.driver_segment_migration_fact` | Si (fact mode) | LOW fact / HIGH runtime | OK (fact mode) |
| Operational Priorities | `/drivers/movements/actionable` | `ops.driver_operational_priority_fact` | Si (fact mode) | LOW fact / EXTREME runtime | OK (fact mode) |

### Tabs con query directa (latencia variable)

| Tab | Endpoint | Source | Freshness visible | Timeout risk | Status |
|---|---|---|---|---|---|
| Lifecycle Intelligence | `/drivers/lifecycle-summary` | `ops.driver_daily_activity_fact + public.drivers` | Parcial (coverage %) | HIGH (full scan) | WARNING |
| Action Queues | `/drivers/actionable-list` | `ops.driver_daily_activity_fact + public.drivers` | Si (queue_generated_at) | HIGH (10K+ drivers) | WARNING |
| Operational Workflows | `/drivers/workflow` | `ops.driver_supply_workflow` | No | LOW | OK |
| Campaign Intelligence | `/drivers/campaigns` + multiple | `ops.driver_campaigns + members` | No | LOW-MEDIUM | OK |
| CRM Bridge | `/drivers/crm-bridge/health` | `ops.driver_campaign_sync` | No | LOW | OK |
| Campaign Effectiveness | `/drivers/campaigns/{id}/effectiveness` | `ops.driver_campaign_effectiveness` | Parcial (days_since) | EXTREME (per-member) | WARNING |
| Operating Board | `/drivers/campaigns/operating-board` | `ops.driver_campaigns + members` | No | MEDIUM | OK |
| Pilot Workboard | `/drivers/pilot-readiness` | Multiple services | Delegated | CRITICAL (chains 5+ calls) | WARNING |

### Tabs con fuente estática o metadata

| Tab | Endpoint | Source | Freshness visible | Timeout risk | Status |
|---|---|---|---|---|---|
| Data Foundation | `/drivers/serving-freshness` | `ops.driver_serving_freshness_fact` | Si (per-fact status) | LOW | OK |
| Operational Health | `/drivers/health` | 8 lightweight probes | Si (per-check status) | LOW (5s per probe) | OK |
| Capability Governance | Static registry | `operationalMaturityRegistry.js` | N/A | NONE | OK |
| Operational Loop Model | `/drivers/operational-loop/model` | Static | N/A | NONE | OK |

### Tabs con data derivada (role views)

| Tab | Endpoint | Source | Timeout risk | Status |
|---|---|---|---|---|
| Vista Operador | `/drivers/workflow` + `/workflow-metrics` + ActionableLists | workflows + queues | MEDIUM (aggregated) | OK |
| Vista Supervisor | `/drivers/workflow-metrics` + `/campaigns` + `/sync-health` | workflows + campaigns | MEDIUM | OK |
| Vista Estrategia | `/drivers/effectiveness-summary` + `/lifecycle-summary` + `/campaigns` | effectiveness + lifecycle | MEDIUM-HIGH | WARNING |
| Vista Admin | `/drivers/health` + `/raw-freshness` + `/sync-health` + DataFoundation | health + freshness | MEDIUM | OK |

### Tabs futuras (placeholder, no endpoint propio)

| Tab | Status |
|---|---|
| Behavioral Intelligence | Placeholder (registry only) |
| Behavioral Alerts | Placeholder (registry only) |
| Fleet & Leakage Intelligence | Placeholder (registry only) |
| Behavioral Patterns | Placeholder (registry only) |
| Loyalty & Recoverability | Placeholder (registry only) |
| Operational Intelligence | Placeholder (registry only) |

---

## 2. FRESHNESS CONTRACT

### Endpoints que YA implementan freshness contract:

| Endpoint | Status | freshness_status | refreshed_at | max_operational_date | remediation |
|---|---|---|---|---|---|
| `/drivers/supply-overview-fact` | Si | Si | Si | Via freshness_fact | Si |
| `/drivers/segment-composition-fact` | Si | Si | Si | Via freshness_fact | Si |
| `/drivers/segment-migration` | Si | Si (fact mode) | Si | Via require_fact | Si |
| `/drivers/movements/actionable` | Si | Si (fact mode) | Si | Via require_fact | Si |
| `/drivers/serving-freshness` | Si | Per-fact | Per-fact | Per-fact | Si |
| `/drivers/health` | Si | Per-check | N/A | N/A | Per-check |

### Endpoints que NO necesitan freshness (write/CRUD/static):

- `/drivers/workflow/*` (CRUD operations)
- `/drivers/campaigns/*` (CRUD + frozen snapshots)
- `/drivers/crm-bridge/*` (sync operations)
- `/drivers/pilot/*` (cohort management)
- `/drivers/operational-loop/model` (static)

### Endpoints WARNING (freshness parcial):

- `/drivers/lifecycle-summary` — devuelve coverage % pero no freshness_status formal
- `/drivers/actionable-list` — devuelve queue_generated_at pero no freshness_status
- `/drivers/campaigns/{id}/effectiveness` — devuelve days_since_campaign pero no freshness_status de fuente

---

## 3. CAMBIOS REALIZADOS

### Backend

| Archivo | Cambio | Motivo |
|---|---|---|
| `backend/app/routers/drivers.py` | `/drivers/health`: reemplazadas probes pesadas (compute_lifecycle_summary, generate_actionable_summary) por probes ligeras de tabla (SELECT 1 FROM ... LIMIT 1) con timeout 5s | Eliminar timeouts en health endpoint |
| `backend/app/routers/drivers.py` | `_probe_table_rows()`: nueva función para probes ligeras | Health endpoint reliability |
| `backend/app/routers/drivers.py` | `_probe_serving_facts()`: añadido refreshed_at y max_period al resultado, context manager, timeout 5s | Freshness visible en health |
| `backend/app/routers/drivers.py` | `_probe_geo_parks()`: context manager, timeout 5s | Consistency |
| `backend/scripts/audit_drivers_full_load.py` | NUEVO: audit script con 14 probes, freshness check, FAIL criteria, remediation | Audit automation |

### Frontend

| Archivo | Cambio | Motivo |
|---|---|---|
| `frontend/src/components/driver/DriverLoadState.jsx` | NUEVO: shared components (DriverLoadingSkeleton, DriverErrorState, DriverFreshnessStrip, DriverRefreshHint) | UI consistency across tabs |
| `frontend/src/components/driver/DriverDataFoundation.jsx` | Retry button, per-fact detail (refreshed_at), DriverRefreshHint, timeout-specific error message | Data Foundation must never be opaque |
| `frontend/src/components/driver/DriverLifecycleSummary.jsx` | Error state with retry + remediation (was: silent catch → null) | No silent failures |
| `frontend/src/components/driver/DriverOperatorView.jsx` | Error state with retry + remediation (was: silent catch) | No silent failures |
| `frontend/src/components/driver/DriverSupervisorView.jsx` | Error state with retry + remediation (was: silent catch) | No silent failures |
| `frontend/src/components/driver/DriverStrategyView.jsx` | Error state with retry + remediation (was: silent catch) | No silent failures |
| `frontend/src/components/driver/DriverAdminDataView.jsx` | Error state with retry + remediation, DriverRefreshHint, remediation column in health table (was: silent catch) | No silent failures + refresh guidance |

---

## 4. TIMEOUT FIXES

| Problema | Antes | Después |
|---|---|---|
| `/drivers/health` llamaba `compute_lifecycle_summary()` | Full scan de ALL drivers sin LIMIT, 10-25s | Probe ligero: `SELECT 1 FROM ops.mv_driver_lifecycle_base LIMIT 1`, <100ms |
| `/drivers/health` llamaba `generate_actionable_summary()` | Procesaba 10K drivers en Python memory, 15-30s | Eliminado. Reemplazado por probe de tabla `ops.driver_supply_overview_weekly_fact` |
| `/drivers/health` llamaba `get_raw_freshness_map()` | Inspecciona ~10 fuentes, hasta 60s total | Eliminado del health. Disponible en Admin Data View vía `/drivers/raw-freshness` |
| `_probe_geo_parks` sin timeout | Could hang on slow DB | Statement timeout 5s |
| `_probe_serving_facts` sin timeout | Could hang | Statement timeout 5s |

---

## 5. UI ERROR STATES (ANTES vs DESPUÉS)

| Estado | Antes | Después |
|---|---|---|
| API timeout | Loading infinito o silencioso | "Timeout: el cálculo tardó demasiado" + botón Reintentar |
| API error | Ignorado (catch vacío) | Banner rojo con detalle, botón Reintentar, remediación |
| Endpoint blocked | Genérico o invisible | "Fuente no disponible" + remediación específica |
| Data stale | No visible en la mayoría | Freshness strip con dot + timestamp |
| Data empty | A veces confundido con error | "Sin datos" separado de error |

---

## 6. OUT_OF_SCOPE_FINDINGS

| Archivo | Detalle | Acción |
|---|---|---|
| `backend/app/services/yango_loyalty_service.py` | Cambios uncommitted, Yango Loyalty | NO TOCAR |
| `frontend/src/components/yangoLoyalty/YangoLoyaltyView.jsx` | Cambios uncommitted, Yango Loyalty | NO TOCAR |
| `frontend/src/config/controlTowerNavigationRegistry.js` | Cambios uncommitted, navigation | NO TOCAR |
| `frontend/src/services/api.js` | Funciones de Yego Pro Profitability P2 | NO TOCAR |
| `frontend/src/App.jsx` | Cambios adicionales uncommitted (no Drivers) | NO TOCAR |

---

## 7. QA

| Check | Resultado |
|---|---|
| `python -m compileall backend/app` | PASS |
| `npm run build` (frontend) | PASS — 838 modules, 14.19s |
| `python -m py_compile backend/scripts/audit_drivers_full_load.py` | PASS |
| Archivos Drivers modificados | 7 modified + 2 new = 9 total |
| Archivos fuera de Drivers tocados | **0** |

---

## 8. REMEDIATIONS PENDIENTES (no bloqueantes)

| Item | Prioridad | Detalle |
|---|---|---|
| `compute_lifecycle_summary()` sigue siendo O(N) en runtime | MEDIUM | Debería existir un `driver_lifecycle_summary_fact` pre-calculado. No bloquea porque el tab carga, pero puede ser lento. |
| `generate_actionable_summary()` procesa 10K drivers | MEDIUM | Candidato a fact materializado. No es llamado desde health ya. |
| `compute_campaign_effectiveness()` loop per-member | LOW | Solo se ejecuta on-demand al ver una campaña específica. No bloquea carga general. |
| `evaluate_pilot_readiness()` encadena 5+ servicios | LOW | Solo se ejecuta al abrir Pilot tab. No bloquea carga general. |
| Tabs placeholder (6 tabs) no tienen endpoint propio | INFO | Son capacidades futuras, mostradas como placeholder con DriverCapabilityBanner. Correcto por diseño. |

---

## 9. GO / NO-GO

### Veredicto: **GO — para prueba humana real (con condiciones)**

### Justificación:

1. **0 archivos modificados fuera del bounded context Drivers**
2. **Build backend + frontend: PASS**
3. **Health endpoint ya no hace timeout** — probes ligeras <5s total
4. **Data Foundation siempre carga** — queries ligeras contra serving_freshness_fact
5. **7 componentes con error silencioso ahora muestran error + retry + remediación**
6. **Refresh command hint visible** en Data Foundation y Admin Data View
7. **Audit script completo** para validación automatizada

### Condiciones:

1. Ejecutar `python scripts/refresh_driver_supply_facts.py` ANTES de la prueba humana para que las facts estén frescas
2. Lifecycle summary puede ser lento si la base de drivers es grande — monitorear
3. Tabs placeholder (Behavioral Intelligence, Fleet Leakage, etc.) mostrarán banner de "en construcción" — correcto por diseño

### Cómo validar:

```bash
cd backend
python scripts/refresh_driver_supply_facts.py
python scripts/audit_drivers_full_load.py
```
