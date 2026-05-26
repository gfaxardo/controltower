# DRIVERS FEATURE — DEEP AUDIT & REORGANIZATION PLAN

**Fecha:** 2026-05-25
**Fase activa:** 1H.4 — Operational Maturity Governance Layer
**Propósito:** Auditoría completa para decidir viabilidad de reorganización hacia listas accionables por driver.

---

## 1. GOVERNANCE CHECK

### Fase ACTIVE
- **Motor:** Control Foundation
- **Fase:** 1H.4 — Operational Maturity Governance Layer
- **Foco actual:** clasificación de madurez de módulos, governance de visibilidad, navegación confiable, feature flag hardening, eliminación de features zombie, reducción de falsas expectativas.

### Fase READY NEXT
- **Motor:** Diagnostic Engine
- **Fase:** 2A.3 — Behavioral Pattern Diagnosis (bloqueado hasta estabilizar Serving Governance Foundation).

### Motores BLOQUEADOS
- Reachability Engine
- Forecast Engine
- Suggestion Engine
- Decision Engine
- Action Engine
- AI Copilot
- Learning Engine

### Verdicto de alcance
Esta auditoría es **COMPATIBLE** con la fase activa porque:
- Clasifica módulos de Drivers por madurez (objetivo explícito de 1H.4)
- Identifica tabs legacy/zombie/prematuras
- Propone ocultar/bannear tabs prematuras para reducir falsas expectativas
- No implementa nuevos endpoints, features ni motores bloqueados
- No activa Diagnostic, Reachability, ni AI
- Se limita a documentar, clasificar y proponer reorganización

**GO para auditoría. NO-GO para implementación de nuevos motores.**

---

## 2. ESTADO ACTUAL

### Resumen numérico
| Métrica | Cantidad |
|---------|----------|
| Tabs visibles en Drivers | 9 |
| Componentes frontend dedicados | 14 |
| Archivos de servicio backend | 14 |
| Routers backend | 10 |
| Endpoints driver-related | ~50+ |
| MVs/Vistas de datos driver | ~40+ |
| Líneas de código frontend driver | ~8,200 |
| Líneas de código backend driver | ~8,400+ |
| Archivos de migración SQL driver | 17+ |
| Archivos SQL de validación | 12+ |

### Clasificación por motor
| Motor | Tabs | Estado permitido |
|-------|------|-----------------|
| Control Foundation | 2 (Supply, Lifecycle) | ACTIVE — permitido |
| Diagnostic Engine | 7 (Diagnóstico, Behavior, Alertas, Fuga, Patrones, Operational Intel, Recoverability) | READY NEXT — NO ACTIVO |

**Problema detectado:** 7 de 9 tabs visibles pertenecen a un motor que NO está activo (Diagnostic Engine). Todos tienen `productionReady: true` y `visibility: KEEP_VISIBLE` en el registry.

---

## 3. MAPA FRONTEND

### 3.1 Rutas y componentes

| Ruta | Tab Key | Componente | Motor | Madurez | ¿Renderiza? |
|------|---------|-----------|-------|---------|-------------|
| `/drivers/supply` | `drivers_supply` | `SupplyView.jsx` (1430 líneas) | Control Foundation | STABLE | SI — data real |
| `/drivers/lifecycle` | `drivers_lifecycle` | `DriverLifecycleView.jsx` (670 líneas) | Control Foundation | HARDENING | SI — data real |
| `/drivers/diagnostic` | `drivers_diagnostic` | `DriverLifecycleDashboard.jsx` (365 líneas) | Diagnostic 2A.1 | IN_CONSTRUCTION | SI — data parcial |
| `/drivers/behavior-benchmarking` | `drivers_behavior_benchmarking` | `DriverBehaviorBenchmarkingDashboard.jsx` (415 líneas) | Diagnostic 2A.2 | IN_CONSTRUCTION | SI — data parcial |
| `/drivers/behavioral-alerts` | `drivers_behavioral_alerts` | `BehavioralAlertsView.jsx` (694 líneas) | Diagnostic 2A | IN_CONSTRUCTION | SI — data parcial |
| `/drivers/fleet-leakage` | `drivers_fleet_leakage` | `FleetLeakageView.jsx` (283 líneas) | Diagnostic 2A | IN_CONSTRUCTION | SI — bajo revisión |
| `/drivers/behavioral-patterns` | `drivers_behavioral_patterns` | `BehavioralPatternDiagnosisDashboard.jsx` (348 líneas) | Diagnostic 2A.3 | IN_CONSTRUCTION | SI — data parcial |
| `/drivers/operational-intelligence` | `drivers_operational_intelligence` | `OperationalBehavioralIntelligenceDashboard.jsx` (557 líneas) | Diagnostic 2B | IN_CONSTRUCTION | SI — data parcial |
| `/drivers/recoverability` | `drivers_recoverability` | `RecoverabilityIntelligenceDashboard.jsx` (547 líneas) | Diagnostic 2C.1 | IN_CONSTRUCTION | SI — shadow mode |
| `/riesgo/driver-behavior` | `riesgo_driver_behavior` | `DriverBehaviorView.jsx` (486 líneas) | Diagnostic | IN_CONSTRUCTION | SI — data parcial |

### 3.2 Hallazgos frontend críticos

1. **Sin lazy loading:** Los 10 componentes se importan estáticamente en `App.jsx`. Bundle size innecesario.
2. **DriverTripsLineChart duplicado:** Definido inline en `BehavioralAlertsView.jsx:115-145` y `DriverBehaviorView.jsx:50-78`. No extraído a shared component.
3. **Inconsistencia de API:** `OperationalBehavioralIntelligenceDashboard` usa `api.get()` raw en vez del patrón de funciones nombradas del resto.
4. **Inconsistencia de estilos:** `RecoverabilityIntelligenceDashboard` usa inline styles (sin Tailwind), todos los demás usan Tailwind.
5. **Sin custom hooks:** Cada componente implementa su propio loading/error/pagination. Sin cache compartido.
6. **getSupplyGeo llamado 4 veces independientemente** (SupplyView, BehavioralAlertsView, FleetLeakageView, DriverBehaviorView). Sin cache compartido.
7. **FleetLeakageView marcado "under_review"** con banner amber explícito de validación pendiente.
8. **RecoverabilityDashboard en SHADOW MODE** con banner naranja de "no operational actions executed".
9. **Sin tests:** No se encontraron archivos de test para ningún componente de drivers.

### 3.3 API calls por componente (frontend → backend)

| Componente | Endpoints consumidos | Timeouts |
|------------|---------------------|----------|
| SupplyView | 13 endpoints (`/ops/supply/*`) | 5s–600s |
| DriverLifecycleView | 8 endpoints (`/ops/driver-lifecycle/*`) + data_trust | 10s–30s |
| DriverLifecycleDashboard | 4 endpoints (`/driver-lifecycle/*`) | 60s |
| DriverBehaviorBenchmarkingDashboard | 4 endpoints (`/driver-behavior/*`) | 60s |
| BehavioralAlertsView | 5 endpoints (`/ops/behavior-alerts/*`) + supply/geo | 10s–30s |
| FleetLeakageView | 3 endpoints (`/ops/leakage/*`) + supply/geo | 10s–30s |
| BehavioralPatternDiagnosisDashboard | 4 endpoints (`/behavioral-patterns/*`) | 60s |
| OperationalBehavioralIntelligenceDashboard | 8 endpoints (`/operational-intelligence/*`) | 120s |
| RecoverabilityIntelligenceDashboard | 8 endpoints (`/recoverability/*`) | 60s |
| DriverBehaviorView (Riesgo) | 4 endpoints (`/ops/driver-behavior/*`) | default |

**Total: ~54 API calls distintas desde frontend hacia backend para drivers.**

### 3.4 Shared components

| Componente | Usado por |
|-----------|----------|
| `DataTrustBadge.jsx` | SupplyView, DriverLifecycleView |
| `DataStateBadge.jsx` | BehavioralAlertsView, FleetLeakageView |
| `DriverSupplyGlossary.jsx` | SupplyView |
| `segmentSemantics.js` | SupplyView, DriverSupplyGlossary |
| `explainabilitySemantics.js` | BehavioralAlertsView, DriverBehaviorView |
| `decisionColors.js` | BehavioralAlertsView, DriverBehaviorView |
| `DriverTripsLineChart` (inline, DUPLICADO) | BehavioralAlertsView, DriverBehaviorView |

### 3.5 Feature flags y registry

- **controlTowerNavigationRegistry.js:** 9 entries de drivers. TODAS con `visibility: KEEP_VISIBLE`, `productionReady: true`. 2 legacy entries ocultas.
- **operationalMaturityRegistry.js:** 2 STABLE/HARDENING, 7 IN_CONSTRUCTION.
- **Sin feature flags de drivers:** Solo existe `VITE_SHOW_FORECAST_EXPERIMENTAL`. Ningún toggle para ocultar tabs de Diagnostic Engine.

---

## 4. MAPA BACKEND

### 4.1 Routers y endpoints principales

#### Router A: `/ops/driver-lifecycle` (Control Foundation)
**File:** `backend/app/routers/driver_lifecycle.py`
**Service:** `driver_lifecycle_service.py` (1525 líneas)

| # | Ruta | Método | Grain | Retorna driver_id? | Retorna nombre? | Retorna phone? |
|---|------|--------|-------|-------------------|-----------------|----------------|
| 1 | `/weekly` | GET | Week | NO (agregado) | NO | NO |
| 2 | `/monthly` | GET | Month | NO (agregado) | NO | NO |
| 3 | `/drilldown` | GET | Driver-week | SI (driver_key) | NO | NO |
| 4 | `/base-metrics` | GET | Aggregate | NO | NO | NO |
| 5 | `/base-metrics-drilldown` | GET | Driver | SI | NO | NO |
| 6 | `/series` | GET | Week/Month | NO | NO | NO |
| 7 | `/summary` | GET | Aggregate | NO | NO | NO |
| 8 | `/parks-summary` | GET | Park | NO | NO | NO |
| 9 | `/parks` | GET | Park | NO | NO | NO |
| 10 | `/cohorts` | GET | Cohort week | NO | NO | NO |
| 11 | `/pro/churn-segments` | GET | Driver-week | SI | NO | NO |
| 12 | `/pro/park-shock` | GET | Driver-week | SI | NO | NO |
| 13 | `/pro/behavior-shifts` | GET | Driver-week | SI | NO | NO |
| 14 | `/pro/drivers-at-risk` | GET | Driver-week | SI | NO | NO |
| 15 | `/cohort-drilldown` | GET | Driver | SI | NO | NO |

**Gaps severos:** Drilldown endpoints retornan solo `driver_key`. Sin nombre, sin teléfono, sin ciudad/país a nivel driver. No sirven para listas accionables operacionales.

#### Router B: `/driver-lifecycle` (Diagnostic Engine — 2A.1)
**File:** `backend/app/routers/driver_lifecycle_diagnostic.py`
**Service:** `driver_lifecycle_diagnostic_service.py` (631 líneas)

| # | Ruta | Retorna driver_id? | Retorna nombre? | Retorna phone? | Retorna lifecycle? | Retorna city? |
|---|------|-------------------|-----------------|----------------|-------------------|---------------|
| 16 | `/summary` | NO | NO | NO | SI (agregado) | SI (filtro) |
| 17 | `/funnel` | NO | NO | NO | SI (agregado) | SI (filtro) |
| 18 | `/risk-list` | SI | SI (display_name) | NO | SI (lifecycle_state) | SI |
| 19 | `/cohorts-basic` | NO | NO | NO | SI (agregado) | SI (filtro) |

**El endpoint `/risk-list` es el MÁS CERCANO a una lista accionable.** Retorna: `driver_id, display_name, country, city, lifecycle_state, risk_level, rule_reason, first_trip_date, last_trip_date, days_since_last_trip, rolling_7d_trips, baseline_trips_28d, decline_pct, tags`. Pero le falta phone, park_id, park_name, trips_14d, trips_30d.

#### Router C: `/driver-behavior` (Diagnostic Engine — 2A.2)
**File:** `backend/app/routers/driver_behavior_benchmarking.py`
**Service:** `driver_behavior_benchmarking_service.py` (881 líneas)
- 4 endpoints de benchmarking agregado. Sin listas driver-level accionables directas.

#### Router D: `/ops/driver-behavior/*` (Diagnostic Engine)
**File:** `backend/app/routers/ops.py` (líneas 1813+)
**Service:** `driver_behavior_service.py` (839 líneas)

El endpoint `/ops/driver-behavior/drivers` retorna la lista más rica del sistema:
`driver_key, park_id, driver_name, country, city, park_name, recent_window_trips, baseline_window_trips, delta_pct, z_score_simple, days_since_last_trip, inactivity_status, alert_type, severity, risk_score, risk_band, suggested_action, rationale_short`.

**Le falta:** phone, lifecycle_stage unificado, trips_7d/14d/30d, last_trip_date explícito, workflow_status.

#### Router E: `/ops/behavior-alerts/*` (Diagnostic Engine)
**Service:** `behavior_alerts_service.py` (415 líneas)
- 5 endpoints sobre alertas semanales de comportamiento. Driver-level con driver_key.

#### Router F: `/ops/leakage/*` (Diagnostic Engine)
**Service:** `leakage_service.py`
- 2 endpoints sobre fuga de flota. Usa `ops.v_fleet_leakage_snapshot`.

#### Router G: `/ops/supply/*` (Control Foundation)
**Service:** `supply_service.py` (1180 líneas)
- 13+ endpoints de supply agregado con segmentos, migraciones, alertas. Sin listas driver-level accionables directas (solo drilldowns).

#### Routers adicionales
- `/behavioral-patterns/*` — 4 endpoints (Diagnostic 2A.3)
- `/operational-intelligence/*` — 8 endpoints (Diagnostic 2B)
- `/recoverability/*` — 8 endpoints (Diagnostic 2C.1, shadow mode)
- `/ops/diagnostics/behavioral/mvp` — 1 endpoint

### 4.2 Servicios compartidos clave

| Servicio | Función |
|----------|---------|
| `driver_identity_resolver_service.py` | Resuelve driver_id → display_name, park_name. **phone siempre = None.** |
| `driver_segment_registry.py` | Registry de segmentos (FT/PT/CASUAL/OCC/DORMANT/ELITE/LEGEND). |
| `supply_definitions.py` | Definiciones de métricas (sin DB). |

### 4.3 Hallazgos backend críticos

1. **Fragmentación de routers:** 10 routers distintos tocan drivers. Sin router unificado `/drivers`.
2. **Sin endpoint de perfil unificado:** No existe `GET /drivers/{driver_id}` con todos los campos.
3. **Phone = None siempre:** `driver_identity_resolver_service.py` hardcodea `"phone": None`. Bloquea workflows de contacto.
4. **Sin Pydantic schemas:** Las respuestas son `dict` sin tipado. `DriverDisplay` y `ParkDisplay` son stubs sin usar.
5. **Endpoint duplicado:** `/ops/behavior-alerts/driver-detail` existe en `ops.py` Y en `controltower.py`.
6. **Drilldowns sin enrichment:** Los endpoints de lifecycle drilldown retornan `{driver_key}` sin nombre, park, ciudad.
7. **Dos prefijos `/driver-lifecycle` y `/ops/driver-lifecycle`:** Pueden coexistir pero generan confusión.

---

## 5. MAPA DE DATOS

### 5.1 Fuentes canónicas

| Campo | Fuente canónica | Schema | Notas |
|-------|----------------|--------|-------|
| `driver_id` | `public.drivers.driver_id` | public | PK, matchea con `conductor_id` en trips |
| `driver_name` | `ops.v_dim_driver_resolved` | ops | Resuelto de `trips_unified.MAX(conductor_nombre)` |
| `phone` | `public.drivers_data.driver_phone` | public | **Existe pero NO integrado en ops.** Identity resolver hardcodea None. |
| `email` | NO ENCONTRADO | — | Gap total |
| `park_id` | `public.drivers.park_id` | public | También en `mv_driver_lifecycle_base.driver_park_id` |
| `park_name` | `ops.v_dim_park_resolved` / `dim.dim_park` | ops/dim | Resuelto de dim_park |
| `city` | `dim.dim_park.city` → `ops.v_dim_park_resolved` | ops/dim | Resuelto vía park |
| `country` | `dim.dim_park.country` → `ops.v_dim_park_resolved` | ops/dim | Resuelto vía park |
| `created_at` | `public.drivers.created_at` | public | Registration timestamp |
| `hire_date` | `public.drivers.hire_date` | public | Fecha de contratación |
| `first_trip` | `ops.mv_driver_lifecycle_base.activation_ts` | ops | Primer viaje completado |
| `last_trip` | `ops.mv_driver_lifecycle_base.last_completed_ts` | ops | Último viaje completado |
| `trips_completed` | `ops.mv_driver_weekly_stats.trips_completed_week` | ops | Por semana |
| `lifecycle_stage` | `driver_lifecycle_diagnostic_service.py` (computado) | — | CHURNED/DORMANT/REACTIVATED/NEW/AT_RISK/DECLINING/GROWING/STABLE/ACTIVATING |
| `segment` | `ops.mv_driver_segments_weekly.segment_week` | ops | FT/PT/CASUAL/OCC/DORMANT/ELITE/LEGEND |
| `churn_segment` | `ops.mv_driver_churn_segments_weekly` | ops | power/mid/light/newbie |
| `license` | `driver_identity_resolver_service.py` (stub) | — | Siempre None |

### 5.2 Serving facts existentes

| Fact | Schema | Grain | Estado |
|------|--------|-------|--------|
| `driver_daily_activity_fact` | ops | driver × date | CENTRAL — usado por diagnostic, benchmarking, behavioral MVP |
| `driver_trip_behavior_daily_fact` | ops | driver × date × park | Usado por operational intelligence, recoverability |
| `driver_session_fact` | ops | driver × session | Usado por operational intelligence |
| `driver_zone_behavior_daily_fact` | ops | driver × date × zone | Usado por operational intelligence |
| `driver_time_behavior_hourly_fact` | ops | driver × date × hour | Usado por operational intelligence |

**No existe un serving fact unificado de identidad de driver** (`driver_identity_fact`). Tampoco existe un serving fact de listas accionables.

### 5.3 Materialized Views principales

| MV | Grain | Refresco |
|----|-------|----------|
| `mv_driver_lifecycle_base` | driver | `ops.refresh_driver_lifecycle_mvs()` |
| `mv_driver_weekly_stats` | driver × week | mismo |
| `mv_driver_monthly_stats` | driver × month | mismo |
| `mv_driver_lifecycle_weekly_kpis` | week | mismo |
| `mv_driver_lifecycle_monthly_kpis` | month | mismo |
| `mv_driver_cohorts_weekly` | driver × cohort_week | mismo |
| `mv_driver_cohort_kpis` | cohort_week × park | mismo |
| `mv_driver_churn_segments_weekly` | driver × week | mismo |
| `mv_driver_behavior_shifts_weekly` | driver × week | mismo |
| `mv_driver_park_shock_weekly` | driver × week | mismo |
| `mv_driver_segments_weekly` | driver × week | `ops.refresh_supply_alerting_mvs()` |
| `mv_supply_segments_weekly` | week × park × segment | mismo |
| `mv_supply_alerts_weekly` | week × park × segment × alert | mismo |
| `mv_driver_behavior_alerts_weekly` | driver × week | — |

### 5.4 Tablas NO integradas (gaps de datos)

| Tabla | Schema | Campos útiles | Estado |
|-------|--------|--------------|--------|
| `public.drivers_data` | public | `driver_phone`, `hire_date`, etc. | **NO integrada en ops** — bloquea contacto |
| `module_ct_cabinet_drivers` | — | — | **NO existe en el proyecto** |
| `summary_daily` | — | — | **NO existe en el proyecto** |

---

## 6. TABS ACTUALES — MAPA Y RECOMENDACIÓN

| Tab / Vista | Propósito actual | Endpoint principal | Fuente de datos | Grain | Estado | Valor operacional | Riesgo técnico | Acción recomendada |
|------------|-----------------|-------------------|----------------|-------|--------|-------------------|---------------|-------------------|
| **Supply** | KPIs agregados de oferta por park, migración de segmentos, alertas | `/ops/supply/*` (13 endpoints) | `mv_supply_weekly`, `mv_driver_segments_weekly`, `mv_supply_alerts_weekly` | week × park × segment | **ACTIVO — STABLE** | ALTO — visión operacional de supply | BAJO — MVs consolidadas | **MANTENER como vista dominante** |
| **Ciclo de vida** | KPIs de activación, churn, retención, cohortes | `/ops/driver-lifecycle/*` (8 endpoints) | `mv_driver_lifecycle_base`, `mv_driver_weekly_stats`, `mv_driver_cohort_kpis` | driver × week | **ACTIVO — HARDENING** | ALTO — entendimiento de retención | BAJO — MVs maduras | **MANTENER, enriquecer con drilldown mejorado** |
| **Diagnóstico** | KPIs con funnel input→retained→risk→leakage + risk list | `/driver-lifecycle/*` (4 endpoints) | `driver_daily_activity_fact` | driver × day | **IN_CONSTRUCTION — Diagnostic 2A.1** | MEDIO — risk list es útil pero sin phone/contacto | MEDIO — depende de serving fact con fallback a trips_2026 | **FUSIONAR con Lifecycle como drilldown avanzado** |
| **Behavior** | Group benchmarks TOP vs DECLINING vs AT_RISK | `/driver-behavior/*` (4 endpoints) | `driver_daily_activity_fact` | driver × day | **IN_CONSTRUCTION — Diagnostic 2A.2** | BAJO — diagnósticos agregados sin acciones | ALTO — sin serving fact dedicado, fallback a raw trips | **OCULTAR (marcar "en construcción")** |
| **Alertas de conducta** | Driver alerts table con severity/risk | `/ops/behavior-alerts/*` (5 endpoints) | `v_driver_behavior_alerts_weekly` | driver × week | **IN_CONSTRUCTION — Diagnostic 2A** | MEDIO — alertas individuales útiles | MEDIO — depende de vista semanal | **OCULTAR (marcar "en construcción")** |
| **Fuga de flota** | Driver leakage table con watchlist/lost | `/ops/leakage/*` (3 endpoints) | `v_fleet_leakage_snapshot` | driver × week | **IN_CONSTRUCTION — BAJO REVISIÓN** | BAJO — marcado "under_review" por el propio sistema | ALTO — el propio componente advierte inestabilidad | **OCULTAR (marcar "legacy/bajo revisión")** |
| **Patrones** | Pattern detection + group profiles + decline signals | `/behavioral-patterns/*` (4 endpoints) | `driver_daily_activity_fact` | driver × day | **IN_CONSTRUCTION — Diagnostic 2A.3** | BAJO — patrones sin acciones | ALTO — READY NEXT, aún no activo | **OCULTAR (marcar "en construcción")** |
| **Operational Intel** | 7 sub-tabs de eficiencia, sesiones, arquetipos, zonas, horarios, pre-churn, top vs churned | `/operational-intelligence/*` (8 endpoints) | `driver_trip_behavior_daily_fact`, `driver_session_fact`, etc. | driver × day | **IN_CONSTRUCTION — Diagnostic 2B** | BAJO — demasiados sub-tabs, análisis sin output accionable | ALTO — 120s timeouts, raw api.get(), motor no activo | **OCULTAR (marcar "en construcción")** |
| **Recoverability** | Shadow mode scoring + ranking + explainability | `/recoverability/*` (8 endpoints) | `driver_trip_behavior_daily_fact` | driver × day | **IN_CONSTRUCTION — Diagnostic 2C.1, SHADOW MODE** | BAJO — shadow mode, no ejecuta acciones | ALTO — inline styles, sin serving fact, Reachability no activo | **OCULTAR (marcar "shadow/experimental")** |

### Riesgo de exposición actual

**7 de 9 tabs** son del Diagnostic Engine (READY NEXT, no activo). Todas marcadas `productionReady: true` en el registry. Esto viola el principio de governance: los usuarios ven features que no están estabilizadas y cuyos motores subyacentes no están activos.

Esto es exactamente el tipo de problema que la fase 1H.4 debe resolver: **features zombie expuestas al usuario.**

---

## 7. GAP CONTRA OBJETIVO OPERACIONAL — LISTAS ACCIONABLES

### Evaluación de las 10 listas accionables requeridas

| # | Lista accionable | ¿Posible hoy? | Datos faltantes | Serving fact necesario | Endpoint faltante | Prioridad | Motor |
|---|-----------------|--------------|-----------------|----------------------|-------------------|-----------|-------|
| 1 | **Nuevos sin primer viaje** | PARCIAL | Sin phone, sin assigned_owner, sin workflow_status | `driver_lifecycle_fact` | `GET /drivers/actionable-list?list_type=new_no_trips` | P0 | Control Foundation |
| 2 | **Registrados/conectados sin actividad** | PARCIAL | Sin phone, sin fecha de registro en serving fact unificado | `driver_lifecycle_fact` | Mismo endpoint, otro list_type | P0 | Control Foundation |
| 3 | **Activos en caída WoW** | PARCIAL | Sin trips_7d/14d/30d unificados, sin phone | `driver_activity_weekly_fact` | Mismo endpoint | P1 | Control Foundation |
| 4 | **Drivers buenos subutilizados** | PARCIAL | Sin definición de "subutilizado", sin phone | `driver_activity_weekly_fact` | Mismo endpoint | P1 | Control Foundation |
| 5 | **Churn reciente recuperable** | PARCIAL | Sin recoverability score persistido, sin phone, sin contacto | `driver_recoverability_fact` | Mismo endpoint | P1 | Diagnostic → Reachability |
| 6 | **Churn antiguo no prioritario** | PARCIAL | Sin phone, clasificación manual | `driver_lifecycle_fact` | Mismo endpoint | P2 | Control Foundation |
| 7 | **Drivers sin teléfono/contacto** | SI — detectable | La tabla `public.drivers_data` tiene phone. Solo hay que integrarla. | `driver_contactability_fact` | `GET /drivers/actionable-list?list_type=no_contact` | P0 | Control Foundation |
| 8 | **Drivers por park con déficit de supply** | PARCIAL | Sin serving fact de supply vs plan por park | `driver_supply_actionable_fact` | Mismo endpoint, filtro por park | P1 | Control Foundation |
| 9 | **Drivers con potencial de reactivación** | PARCIAL | Sin scoring de reactivación, sin phone | `driver_recoverability_fact` | Mismo endpoint | P1 | Diagnostic → Reachability |
| 10 | **Drivers que requieren gestión humana** | PARCIAL | Sin workflow_status, sin assigned_owner | `driver_supply_actionable_fact` | Mismo endpoint + workflow | P2 | Control Foundation |

### Conclusión del gap

**Ninguna de las 10 listas es posible hoy de forma completa.** El bloqueante principal es la ausencia de:
1. **Phone** — no integrado en ops (existe en `public.drivers_data` pero no se consulta)
2. **Serving fact unificado** — los datos están fragmentados en 15+ MVs/views
3. **Endpoint unificado de listas accionables** — no existe `GET /drivers/actionable-list`
4. **Workflow/owner** — no existe modelo de asignación de drivers a owners ni tracking de workflow

4 de las 10 listas (nuevos sin viaje, sin contacto, activos en caída, sin actividad) pueden resolverse dentro de **Control Foundation** sin tocar Diagnostic Engine. Las otras 6 requieren serving facts de Diagnostic o Reachability.

---

## 8. PROPUESTA DE ARQUITECTURA — REORGANIZACIÓN DE DRIVERS

### 8.1 Vista dominante: `/drivers/supply` como Driver Operating Overview

La vista `/drivers/supply` (SupplyView) debe convertirse en el **single entry point operacional** para gestionar drivers:

```
/drivers/supply → Driver Operating Overview
  ├── Filtros globales: país, ciudad, park, rango fecha, lifecycle_stage, supply_status
  ├── KPIs superiores (4-6 cards)
  ├── Lista accionable principal (tabla driver-level)
  ├── Drill por conductor (modal/side panel)
  ├── Workflow básico de gestión (asignar owner, cambiar status)
  └── Export CSV/Excel
```

### 8.2 Reorganización de tabs propuesta

| # | Nuevo orden | Tabs actuales | Acción |
|---|------------|--------------|--------|
| 1 | **Supply Overview** | Supply | **MANTENER** — Vista dominante. Ampliar con actionable list. |
| 2 | **Actionable Lists** | (NUEVO) | **CREAR** — Listas accionables P0/P1. Nuevo endpoint. |
| 3 | **Lifecycle** | Ciclo de vida + Diagnóstico | **FUSIONAR** — Lifecycle absorbe el funnel y risk list de Diagnóstico. |
| 4 | **Behavior Benchmarking** | Behavior + Patrones | **FUSIONAR y OCULTAR** — Marcar "en construcción (Diagnostic Engine)" hasta que 2A esté activo. |
| 5 | **Recoverability** | Recoverability | **OCULTAR** — Marcar "experimental/shadow" hasta que Reachability esté activo. |
| 6 | **Workflows** | (NUEVO) | **CREAR** — Tracking de asignaciones, estados, follow-ups. Control Foundation. |
| 7 | **Definitions / Data Quality** | Supply Glossary | **MANTENER** — Glosario + freshness + coverage metadata. |

### 8.3 Tabs actuales — disposición

| Tab actual | Acción | Justificación |
|-----------|--------|---------------|
| Supply | **MANTENER** | Única vista con data real, STABLE, Control Foundation |
| Ciclo de vida | **MANTENER + AMPLIAR** | HARDENING, Control Foundation. Absorber risk list de Diagnóstico |
| Diagnóstico | **FUSIONAR en Lifecycle** | Su risk list es valiosa pero el resto duplica Lifecycle |
| Behavior | **OCULTAR — "en construcción"** | Diagnostic 2A.2 — motor no activo |
| Alertas de conducta | **OCULTAR — "en construcción"** | Diagnostic 2A — motor no activo |
| Fuga de flota | **OCULTAR — "legacy/bajo revisión"** | El propio componente se declara under_review |
| Patrones | **OCULTAR — "en construcción"** | Diagnostic 2A.3 — READY NEXT, no activo |
| Operational Intel | **OCULTAR — "en construcción"** | Diagnostic 2B — 7 sub-tabs sin output accionable, timeouts 120s |
| Recoverability | **OCULTAR — "shadow/experimental"** | Diagnostic 2C.1 — shadow mode, inline styles, Reachability bloqueado |

### 8.4 Navegación resultante (propuesta)

```
Drivers (sidebar)
  ├── Supply Overview       ← Default landing (única visible para todos)
  ├── Actionable Lists      ← P0: visible para ops managers
  ├── Lifecycle             ← Retención + cohortes + risk drilldown
  ├── Workflows             ← Tracking de gestión (asignaciones, estados)
  └── Definitions           ← Glosario + data quality

  ── En construcción (visible solo con VITE_SHOW_DEV_MODULES) ──
  ├── Behavior Benchmarking
  ├── Alertas de conducta
  ├── Patrones
  ├── Operational Intel
  └── Recoverability (shadow)

  ── Legacy / Ocultos ──
  └── Fuga de flota (bajo revisión)
```

---

## 9. SERVING FACTS REQUERIDAS (DISEÑO MÍNIMO)

### 9.1 `driver_identity_fact`

| Propiedad | Valor |
|-----------|-------|
| **Grain** | 1 row per driver_id |
| **Columnas** | `driver_id`, `driver_name`, `phone`, `email`, `country`, `city`, `park_id`, `park_name`, `registered_at`, `hire_date`, `license`, `status` (active/suspended/banned) |
| **Fuente RAW** | `public.drivers` + `public.drivers_data` + `trips_unified` (name) + `dim.dim_park` |
| **Refresh** | Diario, delta sobre nuevos drivers |
| **Consumidores UI** | Supply Overview, Actionable Lists, Lifecycle, Workflows |
| **Criterio calidad** | phone NOT NULL para >80% de drivers activos |
| **Fallback** | Si `drivers_data` no disponible, phone=NULL con badge "sin contacto" |

### 9.2 `driver_activity_daily_fact`

| Propiedad | Valor |
|-----------|-------|
| **Grain** | driver × activity_date |
| **Columnas** | `driver_id`, `activity_date`, `completed_trips`, `cancelled_trips`, `revenue`, `distance_km`, `duration_min`, `park_id`, `country`, `city` |
| **Fuente RAW** | `trips_unified` → agregación diaria |
| **Refresh** | Diario, últimos 90 días |
| **Consumidores UI** | Supply Overview, Actionable Lists |
| **Criterio calidad** | Sin gaps de fechas para drivers activos |
| **Nota** | Ya existe como `ops.driver_daily_activity_fact`. Solo requiere integración con el nuevo endpoint. |

### 9.3 `driver_activity_weekly_fact`

| Propiedad | Valor |
|-----------|-------|
| **Grain** | driver × week_start |
| **Columnas** | `driver_id`, `week_start`, `trips_7d`, `trips_14d` (rolling), `trips_30d` (rolling), `active_days_7d`, `segment_week`, `work_mode_week`, `churn_risk_flag` |
| **Fuente RAW** | `driver_activity_daily_fact` → rolling aggregation |
| **Refresh** | Semanal |
| **Consumidores UI** | Actionable Lists |
| **Criterio calidad** | Rolling windows consistentes, sin semanas huérfanas |

### 9.4 `driver_lifecycle_fact`

| Propiedad | Valor |
|-----------|-------|
| **Grain** | 1 row per driver_id |
| **Columnas** | `driver_id`, `first_trip_at`, `last_trip_at`, `days_since_last_trip`, `lifetime_days`, `total_trips_completed`, `lifecycle_stage` (ACTIVATING/STABLE/GROWING/DECLINING/AT_RISK/DORMANT/CHURNED), `churn_date`, `reactivation_date` |
| **Fuente RAW** | `mv_driver_lifecycle_base` + `driver_activity_daily_fact` |
| **Refresh** | Diario |
| **Consumidores UI** | Lifecycle, Actionable Lists |
| **Criterio calidad** | lifecycle_stage determinístico, sin IA |

### 9.5 `driver_supply_actionable_fact`

| Propiedad | Valor |
|-----------|-------|
| **Grain** | 1 row per driver_id |
| **Columnas** | `driver_id`, `driver_name`, `phone`, `country`, `city`, `park_id`, `park_name`, `lifecycle_stage`, `supply_status`, `action_reason`, `recommended_action`, `priority` (P0/P1/P2), `evidence` (JSONB), `last_trip_at`, `trips_7d`, `trips_14d`, `trips_30d`, `first_trip_at`, `days_since_registration`, `assigned_owner`, `workflow_status`, `list_type`, `generated_at` |
| **Fuente RAW** | `driver_identity_fact` + `driver_activity_weekly_fact` + `driver_lifecycle_fact` |
| **Refresh** | Diario |
| **Consumidores UI** | Actionable Lists (único consumidor) |
| **Criterio calidad** | action_reason determinístico, recommended_action trazable a regla, priority ordinal |

### 9.6 `driver_contactability_fact`

| Propiedad | Valor |
|-----------|-------|
| **Grain** | 1 row per driver_id |
| **Columnas** | `driver_id`, `has_phone`, `has_email`, `phone_type`, `contactability_score`, `last_contact_at`, `contact_channel` |
| **Fuente RAW** | `driver_identity_fact` → derivado |
| **Refresh** | Diario |
| **Consumidores UI** | Actionable Lists (lista #7), Workflows |
| **Criterio calidad** | `has_phone = false` → badge "sin contacto" |

### 9.7 `driver_recoverability_fact`

| Propiedad | Valor |
|-----------|-------|
| **Grain** | 1 row per driver_id |
| **Columnas** | `driver_id`, `recoverability_score` (0-100), `recoverability_tier` (high/medium/low), `churn_segment`, `days_since_churn`, `pre_churn_trips_avg`, `pre_churn_revenue_avg`, `reactivation_probability`, `recommended_channel`, `recommended_incentive` |
| **Fuente RAW** | `driver_activity_daily_fact` + `driver_lifecycle_fact` |
| **Refresh** | Semanal |
| **Consumidores UI** | Recoverability (cuando Reachability esté activo) |
| **Criterio calidad** | Score basado en reglas determinísticas, NO en ML/AI |
| **Nota** | POSTERGADO hasta que Reachability Engine esté activo. Hoy es premature. |

---

## 10. ENDPOINT CONTRACT — `GET /drivers/actionable-list`

### 10.1 Request

```
GET /api/drivers/actionable-list
```

**Query params:**

| Param | Tipo | Requerido | Default | Descripción |
|-------|------|-----------|---------|-------------|
| `country` | string | No | — | Filtrar por país |
| `city` | string | No | — | Filtrar por ciudad |
| `park_id` | string | No | — | Filtrar por park |
| `list_type` | enum | **Si** | — | `new_no_trips`, `no_activity`, `declining_wow`, `underutilized`, `recent_churn_recoverable`, `old_churn`, `no_contact`, `park_supply_deficit`, `reactivation_potential`, `needs_human_mgmt` |
| `date_from` | date | No | 30 días atrás | Inicio del período de análisis |
| `date_to` | date | No | today | Fin del período de análisis |
| `min_priority` | enum | No | P2 | `P0`, `P1`, `P2` |
| `owner` | string | No | — | Filtrar por assigned_owner |
| `lifecycle_stage` | string | No | — | Filtrar por lifecycle_stage |
| `limit` | int | No | 100 | Máximo de resultados |
| `offset` | int | No | 0 | Paginación |

### 10.2 Response

```json
{
  "list_type": "new_no_trips",
  "generated_at": "2026-05-25T10:00:00Z",
  "total": 245,
  "limit": 100,
  "offset": 0,
  "drivers": [
    {
      "driver_id": "uuid",
      "driver_name": "Carlos Pérez",
      "phone": "+57 300 123 4567",
      "country": "Colombia",
      "city": "Bogotá",
      "park_id": "uuid",
      "park_name": "Park Centro",
      "lifecycle_stage": "NEW",
      "supply_status": "INACTIVE",
      "action_reason": "Driver registrado hace 15 días sin primer viaje completado",
      "recommended_action": "Contactar para verificar onboarding y activación",
      "priority": "P0",
      "evidence": {
        "registered_at": "2026-05-10",
        "days_since_registration": 15,
        "has_phone": true,
        "first_trip_at": null
      },
      "last_trip_at": null,
      "trips_7d": 0,
      "trips_14d": 0,
      "trips_30d": 0,
      "assigned_owner": null,
      "workflow_status": "unassigned"
    }
  ],
  "meta": {
    "data_source": "driver_supply_actionable_fact",
    "data_freshness": "2026-05-25T06:00:00Z",
    "coverage_pct": 94.5,
    "fallback_active": false
  }
}
```

### 10.3 Campos requeridos en cada driver record

| Campo | Tipo | Origen | Obligatorio |
|-------|------|--------|-------------|
| `driver_id` | UUID | `driver_identity_fact` | SI |
| `driver_name` | string | `driver_identity_fact` | SI |
| `phone` | string | `driver_identity_fact` | NO (nullable, badge si falta) |
| `country` | string | `driver_identity_fact` | SI |
| `city` | string | `driver_identity_fact` | SI |
| `park_id` | UUID | `driver_identity_fact` | SI |
| `park_name` | string | `driver_identity_fact` | SI |
| `lifecycle_stage` | enum | `driver_lifecycle_fact` | SI |
| `supply_status` | enum | `driver_supply_actionable_fact` | SI |
| `action_reason` | string | `driver_supply_actionable_fact` | SI (determinístico) |
| `recommended_action` | string | `driver_supply_actionable_fact` | SI (trazable a regla) |
| `priority` | enum | `driver_supply_actionable_fact` | SI (P0/P1/P2) |
| `evidence` | JSONB | `driver_supply_actionable_fact` | SI |
| `last_trip_at` | timestamp | `driver_lifecycle_fact` | NO |
| `trips_7d` | int | `driver_activity_weekly_fact` | SI |
| `trips_14d` | int | `driver_activity_weekly_fact` | SI |
| `trips_30d` | int | `driver_activity_weekly_fact` | SI |
| `assigned_owner` | string | `driver_supply_actionable_fact` | NO |
| `workflow_status` | enum | `driver_supply_actionable_fact` | SI |

### 10.4 Factibilidad

**VIABLE en Control Foundation para list_types P0:**
- `new_no_trips` — requiere `driver_lifecycle_fact` + `driver_identity_fact` (ambos Control Foundation)
- `no_activity` — mismas dependencias
- `no_contact` — requiere integrar `public.drivers_data.phone` en `driver_identity_fact`

**REQUIERE Diagnostic Engine (postergar):**
- `declining_wow` — requiere classification de tendencia (Diagnostic)
- `underutilized` — requiere benchmark (Diagnostic)
- `recent_churn_recoverable` — requiere recoverability scoring (Reachability)
- `reactivation_potential` — requiere recoverability scoring (Reachability)

**REQUIERE Workflow Engine (postergar):**
- `needs_human_mgmt` — requiere modelo de asignación + workflow

---

## 11. ROADMAP POR FASES

### Fase 1 — Control Foundation Hardening (AHORA — compatible con 1H.4)

| # | Acción | Motor | Prioridad |
|---|--------|-------|-----------|
| 1.1 | Ocultar tabs Diagnostic (Behavior, Alertas, Patrones, Operational Intel, Recoverability, Fuga) del menú público | Control Foundation | P0 |
| 1.2 | Agregar `VITE_SHOW_DEV_MODULES` toggle para mostrar tabs en construcción solo en dev | Control Foundation | P0 |
| 1.3 | Actualizar `operationalMaturityRegistry.js` — cambiar visibility de tabs IN_CONSTRUCTION a `HIDE_FROM_NAV` | Control Foundation | P0 |
| 1.4 | Actualizar `controlTowerNavigationRegistry.js` — `productionReady: false` para tabs no activos | Control Foundation | P0 |
| 1.5 | Integrar `public.drivers_data.phone` en `ops.v_dim_driver_resolved` | Control Foundation | P0 |
| 1.6 | Actualizar `driver_identity_resolver_service.py` — devolver phone real en vez de None | Control Foundation | P0 |
| 1.7 | Crear `driver_identity_fact` (MVIEW en schema `serving`) | Control Foundation | P1 |
| 1.8 | Crear `driver_lifecycle_fact` (MVIEW) unificando lifecycle + actividad | Control Foundation | P1 |
| 1.9 | Crear `driver_activity_weekly_fact` (MVIEW) con rolling windows 7/14/30d | Control Foundation | P1 |
| 1.10 | Crear endpoint `GET /drivers/actionable-list` para list_types P0 | Control Foundation | P1 |
| 1.11 | Enriquecer SupplyView con lista accionable embebida (primeros 3 list_types P0) | Control Foundation | P1 |
| 1.12 | Fusionar DriverLifecycleDashboard (risk list) dentro de DriverLifecycleView | Control Foundation | P2 |
| 1.13 | Extraer `DriverTripsLineChart` a shared component | Control Foundation | P2 |
| 1.14 | Extraer `formatNum`/`formatPct` a shared utils | Control Foundation | P2 |

### Fase 2 — Diagnostic Engine Activation (CUANDO 2A esté ACTIVO)

| # | Acción | Motor | Prioridad |
|---|--------|-------|-----------|
| 2.1 | Reactivar tabs Behavior Benchmarking y Patrones (ya con serving facts estables) | Diagnostic | — |
| 2.2 | Completar `driver_supply_actionable_fact` con list_types Diagnostic (declining_wow, underutilized) | Diagnostic | — |
| 2.3 | Migrar OperationalBehavioralIntelligenceDashboard a Tailwind y named API exports | Diagnostic | — |

### Fase 3 — Reachability Engine (CUANDO Reachability esté ACTIVO)

| # | Acción | Motor | Prioridad |
|---|--------|-------|-----------|
| 3.1 | Crear `driver_recoverability_fact` con scoring determinístico | Reachability | — |
| 3.2 | Reactivar tab Recoverability | Reachability | — |
| 3.3 | Completar list_types de recoverability en actionable-list | Reachability | — |
| 3.4 | Implementar `driver_contactability_fact` | Reachability | — |

---

## 12. GO / NO-GO — VEREDICTO FINAL

### ¿Drivers está listo para reorganización?

**GO condicional — solo para Control Foundation.**

| Decisión | Veredicto | Razón |
|----------|-----------|-------|
| ¿Reorganizar tabs? | **GO** | Alineado con fase 1H.4. Ocultar tabs prematuras es urgente. |
| ¿Crear listas accionables P0? | **GO** | 3 de 10 listas son viables con Control Foundation. Son las de mayor valor operacional. |
| ¿Activar Diagnostic Engine tabs? | **NO-GO** | Motor READY NEXT, no activo. Violaría governance. |
| ¿Implementar recoverability? | **NO-GO** | Reachability Engine está en BACKLOG. Prematuro. |
| ¿Implementar AI recommendations? | **NO-GO** | Suggestion/Decision Engines en PROTOTYPE ONLY. Violaría principio determinístico. |

### Qué bloquea

1. **Phone no integrado** — Bloquea cualquier lista accionable que requiera contacto. Remediation: Fase 1.5-1.6.
2. **Tabs Diagnostic visibles** — Exponen features no estabilizadas. Remediation: Fase 1.1-1.4.
3. **Sin serving facts unificados** — Datos fragmentados en 15+ MVs. Remediation: Fase 1.7-1.9.
4. **Sin endpoint de listas accionables** — No hay contrato único. Remediation: Fase 1.10.

### Qué puede hacerse en Control Foundation (AHORA)

- Ocultar tabs prematuras (1.1-1.4)
- Integrar phone de `drivers_data` (1.5-1.6)
- Crear serving facts de identidad, lifecycle y actividad semanal (1.7-1.9)
- Endpoint de listas accionables para list_types P0 (1.10)
- Enriquecer SupplyView con lista accionable (1.11)

### Qué pertenece a Diagnostic Engine (POSTERGAR)

- Behavior benchmarking, patrones, operational intelligence
- Listas accionables de decline/underutilization
- Alertas de conducta (requieren clasificación de desviación)

### Qué es prematuro (NO TOCAR)

- Recoverability (requiere Reachability Engine)
- AI recommendations o scoring automático
- Forecast de churn
- Automatización de contacto

### Qué debe ocultarse para no confundir (URGENTE)

1. Fuga de flota — marcado "under_review", legacy
2. Operational Intel — 7 sub-tabs sin output accionable, timeouts 120s
3. Recoverability — shadow mode, sin engine activo
4. Behavior — sin serving fact estable
5. Patrones — READY NEXT
6. Alertas de conducta — READY NEXT

### Qué debe hacerse primero para lograr listas accionables reales

1. **Integrar phone** (unblock P0)
2. **Crear `driver_identity_fact`** (foundation para todo lo demás)
3. **Crear `driver_lifecycle_fact`** (clasificación determinística)
4. **Crear `driver_activity_weekly_fact`** (rolling windows)
5. **Endpoint `GET /drivers/actionable-list`** (contrato único)
6. **Actualizar SupplyView** con lista accionable embebida

---

## APÉNDICE A — ARCHIVOS REVISADOS

### Frontend (14 archivos)
- `frontend/src/App.jsx` — rutas y renderizado
- `frontend/src/components/SupplyView.jsx` — 1430 líneas
- `frontend/src/components/DriverLifecycleView.jsx` — 670 líneas
- `frontend/src/components/DriverBehaviorView.jsx` — 486 líneas
- `frontend/src/components/BehavioralAlertsView.jsx` — 694 líneas
- `frontend/src/components/FleetLeakageView.jsx` — 283 líneas
- `frontend/src/components/DriverSupplyGlossary.jsx` — 83 líneas
- `frontend/src/components/driverLifecycle/DriverLifecycleDashboard.jsx` — 365 líneas
- `frontend/src/components/driverBehavior/DriverBehaviorBenchmarkingDashboard.jsx` — 415 líneas
- `frontend/src/components/behavioralPatterns/BehavioralPatternDiagnosisDashboard.jsx` — 348 líneas
- `frontend/src/components/operationalIntelligence/OperationalBehavioralIntelligenceDashboard.jsx` — 557 líneas
- `frontend/src/components/recoverability/RecoverabilityIntelligenceDashboard.jsx` — 547 líneas
- `frontend/src/components/DataTrustBadge.jsx` — 57 líneas
- `frontend/src/components/DataStateBadge.jsx` — 79 líneas
- `frontend/src/services/api.js` — ~80 funciones driver-related
- `frontend/src/config/controlTowerNavigationRegistry.js` — 9 entries drivers
- `frontend/src/config/operationalMaturityRegistry.js` — 9 entries drivers
- `frontend/src/constants/segmentSemantics.js`
- `frontend/src/constants/explainabilitySemantics.js`
- `frontend/src/theme/decisionColors.js`

### Backend (14+ archivos)
- `backend/app/main.py` — montaje de routers
- `backend/app/routers/driver_lifecycle.py` — 391 líneas
- `backend/app/routers/driver_lifecycle_diagnostic.py` — 82 líneas
- `backend/app/routers/driver_behavior_benchmarking.py` — 129 líneas
- `backend/app/routers/ops.py` — secciones driver-behavior, behavioral-alerts, supply, leakage
- `backend/app/routers/behavioral_mvp.py` — 52 líneas
- `backend/app/routers/behavioral_pattern_diagnosis.py`
- `backend/app/routers/operational_behavioral_intelligence.py`
- `backend/app/routers/recoverability_intelligence.py`
- `backend/app/routers/controltower.py` — endpoint duplicado
- `backend/app/services/driver_lifecycle_service.py` — 1525 líneas
- `backend/app/services/driver_lifecycle_diagnostic_service.py` — 631 líneas
- `backend/app/services/driver_behavior_benchmarking_service.py` — 881 líneas
- `backend/app/services/driver_behavior_service.py` — 839 líneas
- `backend/app/services/top_driver_behavior_service.py` — 255 líneas
- `backend/app/services/behavior_alerts_service.py` — 415 líneas
- `backend/app/services/driver_identity_resolver_service.py` — 258 líneas
- `backend/app/services/driver_segment_registry.py` — 96 líneas
- `backend/app/services/supply_service.py` — 1180 líneas
- `backend/app/services/supply_definitions.py` — 61 líneas
- `backend/app/services/leakage_service.py`
- `backend/app/services/behavioral_diagnostic_mvp_service.py`
- `backend/app/services/behavioral_pattern_diagnosis_service.py`
- `backend/app/services/operational_behavioral_intelligence_service.py`
- `backend/app/services/recoverability_intelligence_service.py`
- `backend/app/models/schemas.py` — DriverDisplay, ParkDisplay (stubs)

### Migraciones SQL (17+ archivos)
- `backend/alembic/versions/054_trips_unified_view_and_indexes.py`
- `backend/alembic/versions/055_driver_lifecycle_use_trips_unified.py`
- `backend/alembic/versions/056_driver_lifecycle_pro_mvs.py`
- `backend/alembic/versions/057_merge_plan_financials_and_driver_lifecycle_pro.py`
- `backend/alembic/versions/058_fix_driver_lifecycle_trips_completed_source.py`
- `backend/alembic/versions/061_ops_dim_park_and_driver_resolved_views.py`
- `backend/alembic/versions/062_v_dim_driver_resolved_conductor_nombre.py`
- `backend/alembic/versions/065_driver_segment_config_and_mv_rebuild.py`
- `backend/alembic/versions/067_mv_driver_segments_weekly_join_config.py`
- `backend/alembic/versions/078_segment_taxonomy_elite_legend.py`
- `backend/alembic/versions/079_driver_segment_migrations_weekly_views.py`
- `backend/alembic/versions/080_mv_driver_segment_migrations_weekly_optional.py`
- `backend/alembic/versions/081_driver_behavior_baseline_weekly_view.py`
- `backend/alembic/versions/082_driver_behavior_alerts_weekly_view.py`
- `backend/alembic/versions/083_mv_driver_behavior_alerts_weekly_optional.py`
- `backend/alembic/versions/087_top_driver_behavior_views.py`
- `backend/alembic/versions/088_action_engine_driver_base_weeks_rising.py`
- `backend/alembic/versions/089_driver_behavior_deviation_last_trip.py`
- `backend/alembic/versions/106_real_driver_segmentation_canonical.py`

### Governance files
- `ai_operating_system.md`
- `ai_current_phase.md`

---

## APÉNDICE B — HALLAZGOS NO CRÍTICOS (CODE SMELLS)

1. `DriverTripsLineChart` duplicado en BehavioralAlertsView y DriverBehaviorView
2. `formatNum`/`formatPct` duplicados en todos los componentes
3. `OperationalBehavioralIntelligenceDashboard` usa `api.get()` raw — inconsistente con el resto
4. `RecoverabilityIntelligenceDashboard` usa inline styles — inconsistente con Tailwind
5. Endpoint `/ops/behavior-alerts/driver-detail` duplicado en `ops.py` y `controltower.py`
6. Dos prefijos `/driver-lifecycle` y `/ops/driver-lifecycle` coexisten confusamente
7. `getSupplyGeo` llamado 4 veces sin cache compartido
8. Sin lazy loading para componentes de drivers — bundle size innecesario
9. Sin tests de frontend ni backend para drivers
10. `DriverDisplay` y `ParkDisplay` en `schemas.py` son stubs sin usar
11. Sin Pydantic schemas tipados para respuestas de endpoints driver
12. FleetLeakageView se auto-declara "under_review" — debe ocultarse o resolverse

---

**FIN DEL DOCUMENTO DE AUDITORÍA**
