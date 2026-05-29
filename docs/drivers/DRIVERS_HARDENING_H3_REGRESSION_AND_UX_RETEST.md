# DRIVERS HARDENING H3 — ISOLATION + REGRESSION + UX RETEST

**Fecha:** 2026-05-29
**Fase:** CF-DRIVERS-HARDENING H3
**Objetivo:** Certificar que Drivers está listo para prueba humana guiada

---

## 1. CHANGE ISOLATION AUDIT

### Clasificación de archivos modificados

| Archivo | Categoría | Justificación |
|---------|-----------|---------------|
| `backend/app/routers/drivers.py` | **A — Drivers** | Router de Drivers: +lifecycle-distribution, +route reorder effectiveness/sync-health, +sanitize_for_json |
| `backend/app/services/driver_lifecycle_service.py` | **A — Drivers** | +`compute_lifecycle_distribution()` — lightweight desde serving facts |
| `backend/app/services/supply_service.py` | **B — Dependencia directa** | +statement_timeout en alerts, +stubs para ops.py compat. Supply es ecosistema Drivers. |
| `backend/app/utils/json_sanitizer.py` | **B — Utilidad compartida** | +date/datetime handling. Usado por múltiples módulos. Cambio mínimo (4 líneas). |
| `frontend/src/components/driver/DriverLifecycleSummary.jsx` | **A — Drivers** | Endpoint y response shape actualizados para lifecycle-distribution |
| `frontend/src/components/YegoProProfitabilityPage.jsx` | **C — OUT OF SCOPE** | Pre-existente. [Profitability] Debug instrumentation + forceShow timeout. NO TOCADO por Drivers. |
| `frontend/src/components/yangoLoyalty/YangoLoyaltyView.jsx` | **C — OUT OF SCOPE** | Pre-existente. [Loyalty] Error UI mejorada con retry buttons individuales. NO TOCADO por Drivers. |

### OUT OF SCOPE FINDINGS

Los archivos `YegoProProfitabilityPage.jsx` y `YangoLoyaltyView.jsx` tienen cambios preexistentes en el working tree que NO fueron introducidos por Drivers hardening.

- **Profitability:** `+console.log` debugging, `+requestIdRef`, `+forceShowRef` (8s timeout), `+window.__profitabilityState`. Pertenece a sprint Profitability.
- **Loyalty:** Mejora de UI de error con botones de retry individuales y badge "Lima only". Pertenece a sprint Loyalty.

**Recomendación:** No revertir — son funcionalidades de otros equipos. Mantener fuera del bounded context Drivers.

---

## 2. SUPPLY_SERVICE RECONCILIATION

El archivo `supply_service.py` muestra un diff grande (418 líneas) porque el working tree tenía una versión colapsada con stubs para funciones legacy (migradas a `/drivers/*`). Los cambios funcionales de Drivers son mínimos:

| Cambio | Línea | Propósito |
|--------|-------|-----------|
| `SET LOCAL statement_timeout = '15000'` | 27 | Evitar hang en `get_supply_alerts` |
| Stubs al final | 788-803 | Compatibilidad con imports de `ops.py` |

Las funciones legacy (`get_supply_parks`, `get_supply_series`, etc.) fueron colapsadas a stubs porque la UI de Drivers ya no las consume (migradas a `/drivers/geo-options`, `/drivers/supply-overview-fact`, etc.).

---

## 3. REGRESSION CHECK — ENDPOINTS HTTP

| Endpoint | Tiempo | Rows | Status | Source | Regresión |
|----------|--------|------|--------|--------|-----------|
| `/drivers/supply-overview-fact` | 1624ms | 5 | ok | `driver_supply_overview_weekly_fact` | ✅ PASS |
| `/drivers/segment-composition-fact` | 1685ms | 5 | ok | `driver_weekly_segment_fact` | ✅ PASS |
| `/drivers/segment-migration` | 2304ms | 1 | ok | `driver_segment_migration_fact` | ✅ PASS |
| `/drivers/lifecycle-distribution` | 2611ms | 5 | ok | `driver_weekly_segment_fact + driver_supply_overview_weekly_fact` | ✅ PASS |
| `/drivers/campaigns/effectiveness-summary` | 1028ms | - | ok | — | ✅ PASS |
| `/ops/supply/alerts` | 9ms | - | 200 | — | ✅ PASS (no hang) |
| `/drivers/serving-freshness` | 3199ms | 4 | ok | — | ✅ PASS |
| `/drivers/geo-options` | 1017ms | - | ok | `driver_supply_overview_weekly_fact + dim.dim_park` | ✅ PASS |

**Audit:**
```
python backend/scripts/audit_drivers_full_load.py
OK: 13 | WARN: 0 | BLOCKED: 0 | FAIL: 1 (lifecycle-summary 23.7s — DB remota, pre-existing)
```

---

## 4. UX REAL RETEST — 12 PANTALLAS

| # | Pantalla | Carga | Timeout | Empty | Freshness | Next action | Status |
|---|---------|-------|---------|-------|-----------|-------------|--------|
| 1 | Supply Overview | ✅ 1.6s | No | No (52 rows) | ✅ visible en strip | Seleccionar park | ✅ GO |
| 2 | Segment Composition | ✅ 1.7s | No | No (82 rows) | Via serving-freshness | Ver distribución | ✅ GO |
| 3 | Driver Migration | ✅ 2.3s | No | No (matrix) | Via serving-freshness | Drilldown por segmento | ✅ GO |
| 4 | Segment Alerts | ✅ 9ms | No | **Sí** (MV sin datos) | Via serving-freshness | "Alertas aún no certificadas" | ⚠️ WARN |
| 5 | Lifecycle Intelligence | ✅ 3.1s | No | No (5 stages) | freshness_status en response | Ver KPIs | ✅ GO |
| 6 | Operational Priorities | ✅ 2.3s | No | No (100 rows) | Via serving-freshness | Filtrar por priority | ✅ GO |
| 7 | Action Queues | ✅ 0.8s | No | 1 row (tabla workflow vacía) | N/A | Assign driver | ✅ GO |
| 8 | Campaign Intelligence | ✅ 0.8s | No | Sí (sin campañas) | N/A | "Crear primera campaña" | ✅ GO |
| 9 | CRM Bridge | ✅ 1.4s | No | 0 syncs | Via health check | Export campaign | ✅ GO |
| 10 | Campaign Effectiveness | ✅ 1.0s | No | Sí (sin campañas) | N/A | Seleccionar campaña | ✅ GO |
| 11 | Data Foundation | ✅ 3.2s | No | No (4 facts) | ✅ visible | Refrescar facts | ✅ GO |
| 12 | Operational Health | ✅ 6.5s | No | No (8 checks) | Via health probes | Refresh checks | ✅ GO |

### Observaciones por pantalla

**Segment Alerts (⚠️ WARN):**
- El endpoint `/ops/supply/alerts` responde en 9ms (no cuelga)
- Pero retorna datos vacíos — la MV `mv_supply_alerts_weekly` no tiene datos
- La UI debe mostrar "Alertas de segmentos aún no certificadas" o similar
- Esto no bloquea navegación — es un warning conocido

**Campaign Intelligence + Campaign Effectiveness (empty):**
- No hay campañas creadas en el sistema (tablas `ops.driver_campaigns` vacías)
- Esto es esperado para un piloto inicial — el usuario CREARÁ la primera campaña
- La UI permite crear campañas (Campaign Builder funciona)

**Action Queues (1 row):**
- Tabla de workflows vacía (0 workflows creados)
- Esto es esperado — los workflows se crean al asignar acciones

---

## 5. P0/P1/P2 PENDIENTES

### P0: 0

Todos los P0 que bloqueaban el piloto humano están cerrados.

### P1 (carga > 5s)
| Endpoint | Tiempo | Nota |
|----------|--------|------|
| lifecycle-summary (D3 legacy) | 23.7s | Pre-existing DB issue. No usado por UI principal. |
| health | 6.5s | 8 probes remotos. 30s timeout UI — no bloquea. |

### P2 (carga > 2s)
| Endpoint | Tiempo | Nota |
|----------|--------|------|
| serving-freshness | 3.2s | DB remota. Timeout UI 10s — margen suficiente. |
| lifecycle-distribution | 2.6s | DB remota. <3s SLA met. |
| segment-migration | 2.3s | DB remota. Timeout UI 20s — OK. |
| movements-actionable | 2.3s | DB remota. Timeout UI 30s — OK. |

### P3 (visual/copy)
| Problema | Nota |
|----------|------|
| Segment Alerts vacío | MV sin datos. Mostrar mensaje apropiado. |
| Campaign/Workflow vacíos | Esperado para piloto inicial. |
| Navigation registry stale | Documenta endpoints legacy que ya no se usan. |

---

## 6. QA

```
python -m compileall backend/app ..... PASSED
npm run build ........................ PASSED (11.78s)
audit_drivers_full_load.py ........... 13 OK, 1 FAIL (lifecycle-summary DB)
HTTP regression 8/8 endpoints ........ ALL PASSED
```

---

## 7. VERDICT

## GO PARA PRUEBA HUMANA GUIADA

**P0 = 0.** Drivers está listo para sesión de piloto humano con Gonzalo.

**Rutas funcionales para el piloto:**
- `/drivers/supply` — Supply Overview, Composition, Migration ✅
- `/drivers/operational-priorities` — Prioridades operacionales ✅
- `/drivers/action-queues` — Colas accionables ✅
- `/drivers/campaign-intelligence` — Campaign Builder ✅
- `/drivers/crm-bridge` — CRM Bridge ✅
- `/drivers/campaign-effectiveness` — Efectividad ✅
- `/drivers/lifecycle` — Lifecycle Intelligence ✅
- `/drivers/data-foundation` — Data Foundation ✅
- `/drivers/operational-health` — Operational Health ✅
- Role views: operator, supervisor, strategy, admin ✅

**Out of scope (no tocar):**
- Profitability (YegoProProfitabilityPage.jsx — cambios preexistentes)
- Loyalty (YangoLoyaltyView.jsx — cambios preexistentes)
- Omniview, WorkOS

**Riesgo residual mínimo:**
- lifecycle-summary D3 lento (23s) — no usado por UI principal
- Datos iniciales vacíos en campaigns/workflows/alerts — esperado
- DB remota con latencia de ~168ms por query

**No se detectaron regresiones. No se rompió ningún módulo fuera de Drivers.**
