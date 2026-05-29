# DRIVERS UX REAL NAVIGATION SIMULATION — D1.3.3

**Fecha:** 2026-05-29
**Método:** Code-trace complete de cada componente y su backend router
**Objetivo:** Radiografía real de lo que vería un humano navegando Drivers

---

## 1. FLUJO NAVEGADO

| # | Ruta | Componente | Capa | Endpoints |
|---|------|-----------|------|-----------|
| 1 | `/drivers/supply` | SupplyView | Command Center | 11 endpoints (ver detalle abajo) |
| 2 | `/drivers/lifecycle` | DriverLifecycleView | Intelligence | 6 endpoints `/ops/driver-lifecycle/*` |
| 3 | `/drivers/diagnostic` | DriverLifecycleDashboard | Intelligence | `/driver-lifecycle/summary` + stages |
| 4 | `/drivers/behavior-benchmarking` | DriverBehaviorBenchmarkingDashboard | Intelligence | `/ops/driver-behavior/*` |
| 5 | `/drivers/behavioral-alerts` | BehavioralAlertsView | Intelligence | `/ops/behavior-alerts/*` |
| 6 | `/drivers/fleet-leakage` | FleetLeakageView | Intelligence | `/ops/leakage/*` |
| 7 | `/drivers/behavioral-patterns` | BehavioralPatternDiagnosisDashboard | Intelligence | patterns service |
| 8 | `/drivers/operational-intelligence` | OperationalBehavioralIntelligenceDashboard | Intelligence | oper. intel service |
| 9 | `/drivers/recoverability` | RecoverabilityIntelligenceDashboard | Intelligence | recoverability service |
| 10 | `/drivers/operational-priorities` | OperationalPriorities | Execution | `/drivers/movements/actionable` ✅ |
| 11 | `/drivers/action-queues` | DriverActionableLists | Execution | `/drivers/actionable-list` ✅ |
| 12 | `/drivers/pilot` | PilotWorkboard | Execution | `/drivers/pilot/*` |
| 13 | `/drivers/campaign-intelligence` | CampaignIntelligence | Execution | `/drivers/campaigns/*` |
| 14 | `/drivers/crm-bridge` | CrmBridge | Execution | `/drivers/crm-bridge/health` |
| 15 | `/drivers/campaign-effectiveness` | CampaignEffectiveness | Execution | `/drivers/campaigns/effectiveness-summary` |
| 16 | `/drivers/data-foundation` | **DriverCapabilityPlaceholder** | Foundation | NINGUNO (placeholder) |
| 17 | `/drivers/operational-health` | **DriverCapabilityPlaceholder** | Foundation | NINGUNO (placeholder) |
| 18 | `/drivers/capability-governance` | **DriverCapabilityPlaceholder** | Foundation | NINGUNO (placeholder) |

**Role Views (sub-navegación):**
| # | Ruta | Componente | Endpoints |
|---|------|-----------|-----------|
| 19 | `/drivers/operator` | DriverOperatorView | `/drivers/workflow`, `/drivers/workflow-metrics` |
| 20 | `/drivers/supervisor` | DriverSupervisorView | workflow + campaigns + sync-health |
| 21 | `/drivers/strategy` | DriverStrategyView | effectiveness-summary, lifecycle-summary, campaigns |
| 22 | `/drivers/admin` | DriverAdminDataView | `/drivers/health`, sync-health, raw-freshness |

---

## 2. HALLAZGOS POR PANTALLA

### 2.1 Supply Overview (`/drivers/supply`)

**Qué espera un humano:** Datos de supply de conductores, poder filtrar por país/ciudad/park, ver tendencias, composición de segmentos y migración.

**Qué ve realmente:**
- Geo: Countries, cities, parks cargan correctamente desde `/drivers/geo-options` ✅
- Overview: Serie de activaciones/churn/reactivaciones/net_growth por semana desde `/drivers/supply-overview-fact` ✅
- Composition: Distribución por segmento desde `/drivers/segment-composition-fact` ✅
- Migration: Migración entre segmentos desde `/drivers/segment-migration` ✅ (mapeado de fact)
- Alerts: Alertas de segmento desde `/ops/supply/alerts` ⚠️ (legacy, sin equivalente fact-based)
- Freshness: Estado de serving facts desde `/drivers/serving-freshness` ✅

**Endpoints llamados:**
| Endpoint | Tipo | Timeout UI | Audit |
|----------|------|-----------|-------|
| `/drivers/geo-options` | fact-based | 10000ms | 790ms OK |
| `/drivers/supply-overview-fact` | fact-based | 15000ms | 795ms OK |
| `/drivers/segment-composition-fact` | fact-based | 15000ms | 810ms OK |
| `/drivers/segment-migration` | fact-based | 20000ms | 2292ms OK |
| `/drivers/serving-freshness` | fact-based | 10000ms | 4341ms OK |
| `/ops/supply/alerts` | legacy | 15000ms | NO AUDITADO |
| `/ops/supply/alerts/drilldown` | legacy | 15000ms | NO AUDITADO |
| `/ops/supply/migration/drilldown` | legacy | 15000ms | NO AUDITADO |
| `/ops/supply/definitions` | metadata | 5000ms | NO AUDITADO |
| `/ops/supply/segments/config` | metadata | 5000ms | NO AUDITADO |
| `/ops/supply/refresh` | action | 600000ms | NO AUDITADO |

**Problemas:**
- [P1] Segment Alerts usa endpoints legacy (`/ops/supply/alerts*`) sin validación de audit. Si la tabla source no existe, falla silenciosamente.
- [P2] Migration muestra datos de un solo periodo (fact es snapshot). WeeklySummary/Critical son sintetizados del matrix; columnas WoW/delta muestran "—".
- [P2] Composition `share_of_active` bug de división por 100 fue corregido en hotfix anterior.
- [P3] Navigation registry (`controlTowerNavigationRegistry.js:119`) lista endpoints legacy obsoletos: `/ops/supply/geo`, `/ops/supply/series`, etc. — no corresponde con implementación real.

### 2.2 Lifecycle Intelligence (`/drivers/lifecycle`)

**Qué espera un humano:** KPIs de lifecycle (activations, churned, reactivated), drilldown por park, cohorts.

**Qué ve realmente:**
- Summary y series cargan correctamente desde `/ops/driver-lifecycle/*` ✅
- Cohorts funcionan con filtros de semana ✅
- Drilldown solo funciona si hay park seleccionado (obligatorio) — UX lo documenta ✅
- **PERO**: `/drivers/lifecycle-summary` (usado en DriverLifecycleSummary y DriverStrategyView) tarda ~25s

**Endpoints:**
| Endpoint | Timeout UI | Problema |
|----------|-----------|----------|
| `/ops/driver-lifecycle/parks` | 10000ms | OK |
| `/ops/driver-lifecycle/series` | 30000ms | OK |
| `/ops/driver-lifecycle/summary` | 30000ms | OK |
| `/ops/driver-lifecycle/parks-summary` | 30000ms | OK |
| `/ops/driver-lifecycle/cohorts` | 30000ms | OK |
| `/ops/driver-lifecycle/drilldown` | 30000ms | OK |
| `/ops/driver-lifecycle/base-metrics-drilldown` | 30000ms | OK |
| `/drivers/lifecycle-summary` | 25000ms (LifecycleSummary) / **15000ms (StrategyView)** | ⚠️ CRÍTICO |

**Problemas:**
- [P0] `DriverStrategyView.jsx` llama `/drivers/lifecycle-summary` con timeout **15000ms** pero el endpoint tarda ~25s (audit: 24894ms). **Siempre timeout** en Strategy View.
- [P0] `DriverLifecycleSummary.jsx` timeout es 25000ms — en el límite exacto. Cualquier latencia de red adicional causa timeout.
- [P1] Si lifecycle-summary timeoutea, se muestra "Lifecycle: error técnico" con mensaje genérico. Un humano interpreta que todo Drivers está roto aunque solo sea esa consulta.

### 2.3 Operational Priorities (`/drivers/operational-priorities`)

**Qué espera un humano:** Lista priorizada de drivers con movimientos operacionales accionables.

**Qué ve realmente:**
- Tabla de drivers con movement, priority, readiness, recoverability ✅
- Filtros de priority y movement type funcionan ✅
- KPI strip con contadores P0-P3 ✅

**Endpoint:** `/drivers/movements/actionable` (30000ms timeout, audit: 2279ms OK) ✅

**Problemas:**
- [P1] No tiene filtro de país/ciudad/park. Carga TODOS los movimientos globalmente sin contexto geo. Si hay muchas filas (>100), solo muestra las primeras 100.
- [P2] Tabla truncada a 100 drivers por defecto sin paginación visible.

### 2.4 Action Queues (`/drivers/action-queues`)

**Qué espera un humano:** Colas operacionales por tipo (At Risk, Churned, Declining, etc.) con quick actions.

**Qué ve realmente:**
- Tabs de colas (At Risk, Churned, etc.) con conteo ✅
- Tabla de drivers con priority badge ✅
- Quick actions: Assign, Contact, Recover ✅
- Workflow status tracking ✅

**Endpoint:** `/drivers/actionable-list` (30000ms timeout, audit: 775ms OK) ✅

**Problemas:**
- [P3] Quick actions no validan si el workflow ya existe para ese driver. Posible duplicación silenciosa.
- [P3] Sin feedback visual de "action completed" — el botón se presiona y no hay toast/confirmación.

### 2.5 Campaign Intelligence (`/drivers/campaign-intelligence`)

**Qué espera un humano:** Crear campañas, previsualizar cohortes, ver detalle y progreso.

**Qué ve realmente:**
- Campaign Builder con formulario completo ✅
- Preview antes de crear ✅
- Lista de campañas con filtros ✅
- Detalle con miembros, progreso, effectiveness ✅
- Operating Board con loop stages ✅

**Endpoints:**
| Endpoint | Timeout |
|----------|---------|
| `/drivers/campaigns/preview` (POST) | 30000ms |
| `/drivers/campaigns` (GET/POST) | 15000-30000ms |
| `/drivers/campaigns/{id}` | 15000ms |
| `/drivers/campaigns/{id}/members` | 15000ms |
| `/drivers/campaigns/{id}/progress` | 15000ms |
| `/drivers/campaigns/{id}/effectiveness` | 30000ms |
| `/drivers/campaigns/{id}/loop-status` | 15000ms |

**Problemas:**
- [P1] Campaign Builder usa text inputs para country/city (libre escritura) en vez de dropdowns desde `/drivers/geo-options`. Riesgo de typos que resultan en campañas vacías.
- [P2] Cuando no hay campañas, el Campaign Builder es la única vista. No hay mensaje claro de "crea tu primera campaña".
- [P2] Detail hace 4 requests en paralelo al abrir — puede saturar si hay muchas campañas.

### 2.6 CRM Bridge (`/drivers/crm-bridge`)

**Qué espera un humano:** Ver estado de sync con CRM, exportar campañas, ver historial.

**Qué ve realmente:**
- Health status del bridge ✅
- Sync history ✅
- Export action para campañas ✅
- Degradation banner: "Si el CRM no responde, Drivers sigue funcionando" ✅

**Endpoints:**
- `/drivers/crm-bridge/health` (15000ms)
- `/drivers/campaigns/sync-history` (15000ms)
- `/drivers/campaigns/{id}/crm-export` (30000ms)

**Problemas:**
- [P3] Solo muestra sync history global — no permite filtrar por campaña específica desde esta vista.

### 2.7 Campaign Effectiveness (`/drivers/campaign-effectiveness`)

**Qué espera un humano:** Métricas de efectividad de campañas con before/after comparison.

**Qué ve realmente:**
- Lista de campañas con métricas base ✅
- Al seleccionar una: KPI strip, before/after comparison ✅
- Windows D+1, D+3, D+7, D+14, D+30 ✅
- Group by: owner, queue, lifecycle, priority, city, country ✅
- Disclaimer: "NO afirmar causalidad" ✅

**Endpoints:**
- `/drivers/campaigns/effectiveness-summary` (15000ms)
- `/drivers/campaigns/{id}/effectiveness` (30000ms)

**Problemas:**
- [P2] Loads effectiveness summary for ALL campaigns on mount — could be slow if many campaigns exist.
- [P3] No visual indication of which campaigns have been analyzed vs not.

### 2.8 Data Foundation (`/drivers/data-foundation`)

**Qué espera un humano:** Estado de las fuentes de datos, freshness, cobertura.

**Qué ve realmente:**
- **PLACEHOLDER** — `DriverCapabilityPlaceholder moduleKey="drivers_data_foundation"`
- Muestra: "No operational execution here yet / This capability is visible as a roadmap preview"
- **NOTA:** El componente `DriverDataFoundation` SÍ existe y FUNCIONA dentro de los role views (operator, supervisor, strategy, admin). Pero la ruta directa `/drivers/data-foundation` está mapeada a un placeholder.

**Problemas:**
- [P0] Ruta `/drivers/data-foundation` muestra placeholder sin datos. Confunde al usuario: cree que Data Foundation no existe cuando sí está funcionando en los role views.
- [P1] El espacio real de Data Foundation (con serving freshness, facts status) solo es visible en vistas de rol (operator/supervisor/strategy/admin), no como tab independiente.

### 2.9 Operational Health (`/drivers/operational-health`)

**Qué espera un humano:** Health check del sistema, estado de cada servicio.

**Qué ve realmente:**
- **PLACEHOLDER** — `DriverCapabilityPlaceholder moduleKey="drivers_operational_health"`
- El endpoint `/drivers/health` SÍ existe (8 probes: serving-facts, geo-parks, identity, activity, lifecycle, workflow, campaigns, geo-options) y es usado en `DriverAdminDataView`
- Pero la ruta directa es un placeholder.

**Problemas:**
- [P0] Misma situación que Data Foundation — endpoint existe, funcionalidad existe en Admin View, pero tab independiente es placeholder.

### 2.10 Capability Governance (`/drivers/capability-governance`)

**Qué espera un humano:** Estado de todas las capabilities de Drivers, roadmap.

**Qué ve realmente:**
- **PLACEHOLDER** — `DriverCapabilityPlaceholder moduleKey="drivers_capability_governance"`
- Legítimamente es un placeholder (la funcionalidad de governance no está implementada)

**Problemas:**
- [P3] Placeholder correcto para capability no construida.

### 2.11 Role Views (operator, supervisor, strategy, admin)

**Operator View (`/drivers/operator`):**
- Muestra "My Work Today" + Action Queues ✅
- `/drivers/workflow` + `/drivers/workflow-metrics` ✅
- Vista funcional para operador

**Supervisor View (`/drivers/supervisor`):**
- Muestra execution overview, campaigns, sync health, stuck cases ✅
- `/drivers/workflow-metrics` + campaigns + sync-health ✅

**Strategy View (`/drivers/strategy`):**
- Campaign effectiveness + lifecycle trends + campaigns list ✅
- [P0] `/drivers/lifecycle-summary` con timeout 15000ms → SIEMPRE timeout

**Admin View (`/drivers/admin`):**
- Data Foundation + System Health + Governance ✅
- `/drivers/health` (30000ms) — este sí funciona porque el health endpoint es rápido

---

## 3. ENDPOINTS LENTOS

| Endpoint | Audit (ms) | Timeout UI (ms) | Componente | Riesgo |
|----------|-----------|-----------------|-----------|-------|
| `/drivers/lifecycle-summary` | 24894 | 15000 (StrategyView) | DriverStrategyView | **SIEMPRE TIMEOUT** |
| `/drivers/lifecycle-summary` | 24894 | 25000 (LifecycleSummary) | DriverLifecycleSummary | Al borde |
| `/drivers/serving-freshness` | 4341 | 10000 | DriverDataFoundation | OK |
| `/drivers/segment-migration` | 2292 | 20000 | SupplyView | OK |
| `/ops/driver-lifecycle/series` | ~5000-8000 | 30000 | DriverLifecycleView | OK |
| `/ops/driver-lifecycle/cohorts` | ~3000-5000 | 30000 | DriverLifecycleView | OK |

---

## 4. DESACOPLES UX/API

### 4.1 Response shape: overview fact → `period_start`
- **Backend devuelve:** `week_start`
- **UX espera:** `period_start`
- **Fix:** Mapeo agregado en `loadOverview` (hotfix anterior). OK.

### 4.2 Response shape: composition fact → `share_of_active`
- **Backend devuelve:** porcentaje (ej. 25.0 = 25%)
- **UX hacía:** `/ 100` (mostraba 0.3%)
- **Fix:** División removida (hotfix anterior). OK.

### 4.3 Migration fact → structure mismatch
- **Backend devuelve:** `{matrix: [...], drivers_sample: [...], summary: {...}}`
- **UX esperaba:** `{data: [...migration rows], summary: {...}}`
- **Fix:** Mapeo en `loadMigration` (hotfix anterior). WeeklySummary/Critical se derivan del matrix pero muestran "—" en columnas delta.

### 4.4 Navigation registry stale
- `controlTowerNavigationRegistry.js:119` lista endpoints legacy para `drivers_supply`:
  ```
  ['/ops/supply/geo', '/ops/supply/series', '/ops/supply/summary', '/ops/supply/composition', '/ops/supply/migration']
  ```
- La implementación real ya no usa ninguno de estos (Overview, Composition, Migration usan fact-based `/drivers/*`). Solo Alerts sigue usando `/ops/supply/*`.

### 4.5 Data Foundation dual existence
- El componente `DriverDataFoundation.jsx` existe y funciona (dentro de role views)
- La ruta `/drivers/data-foundation` renderiza `DriverCapabilityPlaceholder` (placeholder)
- Misma situación con Operational Health

---

## 5. PROBLEMAS DE COPY

| Problema | Ubicación | Severidad |
|----------|-----------|-----------|
| "Lifecycle: error técnico" sin indicar que es timeout | DriverLifecycleSummary.jsx:89 | P1 |
| "Sin datos en el rango" no distingue entre "sin filtros" y "no hay datos reales" | SupplyView.jsx:737 | P2 |
| "No operational execution here yet" se muestra para Data Foundation que SÍ existe | DriverCapabilityPlaceholder.jsx:78 | P1 |
| Campaign Builder: country/city son text inputs sin validación | CampaignIntelligence.jsx:179-188 | P1 |
| Navigation registry documenta endpoints que ya no se usan | controlTowerNavigationRegistry.js:119 | P3 |

---

## 6. PROBLEMAS DE FILTROS

| Componente | Filtros disponibles | Problema |
|-----------|-------------------|----------|
| SupplyView | country, city, park, grain, from, to | ✅ Completos |
| DriverLifecycleView | from, to, park, week/month | ✅ Completos |
| OperationalPriorities | priority, movement_type, checkboxes | ⚠️ Sin geo filters |
| DriverActionableLists | queue_type tabs | ⚠️ Sin geo ni priority filters |
| CampaignIntelligence | tipo, queues, priority, country (text), city (text) | ⚠️ Country/city son text input, no dropdown |
| CampaignEffectiveness | campaign selector, window, group by | ✅ OK |

---

## 7. PROBLEMAS DE FRESHNESS

| Componente | Freshness visible | Fuente | Problema |
|-----------|------------------|--------|----------|
| SupplyView | Sí (strip con last_week, last_refresh, status) | `/drivers/serving-freshness` | Solo mira el overview fact; no muestra estado de otros facts |
| DriverDataFoundation | Sí (serving facts con dots) | `/drivers/serving-freshness` | ✅ Completo |
| DriverLifecycleSummary | No | N/A | No muestra freshness |
| CampaignIntelligence | No | N/A | No muestra freshness de campaigns |
| OperationalPriorities | Parcial (warnings si fact stale) | response inline | Solo muestra warning si el fact está stale |

---

## 8. CLASIFICACIÓN P0/P1/P2/P3

### P0 — Bloquea uso
| ID | Descripción | Componente |
|----|-----------|-----------|
| P0-1 | `/drivers/lifecycle-summary` timeout garantizado (15s UI vs 25s real) | DriverStrategyView |
| P0-2 | `/drivers/data-foundation` muestra placeholder en vez de DriverDataFoundation funcional | App.jsx routing |
| P0-3 | `/drivers/operational-health` muestra placeholder en vez de health check funcional | App.jsx routing |

### P1 — Confunde operación
| ID | Descripción | Componente |
|----|-----------|-----------|
| P1-1 | "Lifecycle: error técnico" sin aclarar que es timeout de DB | DriverLifecycleSummary |
| P1-2 | Campaign Builder country/city son text inputs (no dropdown de geo real) | CampaignIntelligence |
| P1-3 | OperationalPriorities sin filtros geo — carga global sin contexto | OperationalPriorities |
| P1-4 | Segment Alerts usa endpoints legacy no auditados | SupplyView |
| P1-5 | "No operational execution here yet" en Data Foundation (existe pero escondido) | DriverCapabilityPlaceholder |
| P1-6 | Navigation registry documenta endpoints que ya no se usan | controlTowerNavigationRegistry |

### P2 — Ralentiza pero permite operar
| ID | Descripción | Componente |
|----|-----------|-----------|
| P2-1 | Migration WeeklySummary/Critical sintetizados del matrix — columnas WoW muestran "—" | SupplyView |
| P2-2 | Campaign detail carga 4 requests en paralelo al abrir | CampaignIntelligence |
| P2-3 | CampaignEffectiveness carga todas las campañas en mount | CampaignEffectiveness |
| P2-4 | OperationalPriorities truncado a 100 sin paginación | OperationalPriorities |
| P2-5 | "Sin datos en el rango" no distingue causa (filtros vs no hay datos) | SupplyView |

### P3 — Mejora visual/copy
| ID | Descripción | Componente |
|----|-----------|-----------|
| P3-1 | Quick actions sin feedback visual de completado | DriverActionableLists |
| P3-2 | CRM Bridge sin filtro por campaña específica | CrmBridge |
| P3-3 | Campaign Effectiveness sin indicador de "ya analizada" | CampaignEffectiveness |
| P3-4 | Action Queues sin validación de duplicados en quick actions | DriverActionableLists |
| P3-5 | Capability Governance es placeholder legítimo (no implementado) | DriverCapabilityPlaceholder |

---

## 9. PLAN DE CORRECCIÓN SUGERIDO

### Fase 1 — P0 (críticos, antes de piloto humano)
1. **Aumentar timeout de lifecycle-summary en StrategyView** de 15000ms → 30000ms o usar loading state optimista
2. **Corregir routing de Data Foundation** para que `/drivers/data-foundation` renderice `DriverDataFoundation` en vez de placeholder
3. **Corregir routing de Operational Health** para que `/drivers/operational-health` renderice admin health (o al menos muestre los health probes)
4. **Optimizar query de lifecycle-summary** (24s en BD remota) — considerar materialized view o pre-aggregation

### Fase 2 — P1 (confusión operativa)
5. **Mejorar mensaje de error en DriverLifecycleSummary** → "Lifecycle tardando más de lo esperado (DB remota). Reintentar."
6. **Agregar geo dropdowns en Campaign Builder** desde `/drivers/geo-options`
7. **Agregar filtros geo en OperationalPriorities**
8. **Actualizar navigation registry** con endpoints fact-based reales
9. **Crear fact-based alert endpoint** o documentar que alerts es legacy tolerado

### Fase 3 — P2 (mejora progresiva)
10. **Agregar weekly-summary y critical endpoints fact-based** para migration (desde `driver_segment_migration_fact`)
11. **Lazy-load campaign detail tabs** (no 4 requests simultáneos)
12. **Paginación en OperationalPriorities**
13. **Mejorar copy de "Sin datos en el rango"** con hint contextual

### Fase 4 — P3 (pulido)
14. **Toast/feedback en quick actions**
15. **CRM Bridge: filtro por campaña**
16. **Indicador "ya analizada" en Campaign Effectiveness**

---

## 10. QA

```
npm run build ............................ PASSED (11.97s)
python -m compileall backend/app ......... PASSED (sin errores)
python backend/scripts/audit_drivers_full_load.py:
  OK: 13 | WARN: 0 | BLOCKED: 0 | FAIL: 1 (lifecycle-summary timeout)
```

---

## 11. REPORTE FINAL

### Pantallas OK
- Supply Overview (Overview tab) ✅
- Supply Overview (Composition tab) ✅
- Supply Overview (Migration tab) ✅ (datos correctos, WoW en "—")
- Lifecycle Intelligence ✅ (series, summary, cohorts, drilldown)
- Operational Priorities ✅
- Action Queues ✅
- Campaign Intelligence ✅
- CRM Bridge ✅
- Campaign Effectiveness ✅
- Pilot Workboard ✅
- Operator View ✅
- Supervisor View ✅
- Admin View ✅ (health check funciona)

### Pantallas con Warning
- Supply Overview (Alerts tab) ⚠️ — legacy endpoints, no auditados
- Lifecycle Intelligence ⚠️ — lifecycle-summary query lenta (24s)
- Campaign Intelligence ⚠️ — country/city text input sin validación

### Pantallas Bloqueadas
- Strategy View ❌ — lifecycle-summary timeout 15s vs 25s real
- Data Foundation (ruta directa) ❌ — placeholder en vez de componente funcional
- Operational Health (ruta directa) ❌ — placeholder en vez de health check

### P0 encontrados: 3
### P1 encontrados: 6
### P2 encontrados: 5
### P3 encontrados: 5

### VERDICT: **CONDITIONAL GO**
- Supply Overview, Action Queues, Campaigns, CRM Bridge, Pilot: **GO**
- Lifecycle Intelligence: **GO** (con advertencia de lentitud)
- Strategy View: **NO-GO** hasta fix de timeout
- Data Foundation / Operational Health (rutas directas): **NO-GO** hasta fix de routing

**Recomendación:** Corregir los 3 P0 antes de sesión de piloto humano. Los P1 pueden documentarse como known issues.
