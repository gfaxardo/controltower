# FASE 0A — SYSTEM DISCOVERY / ARCHITECTURE SCAN
## Proyecto: YEGO CONTROL TOWER

**Fecha:** 2025-03-13  
**Alcance:** Discovery y documentación únicamente. Sin cambios en código, BD ni configuración.

---

## 1. Resumen ejecutivo

YEGO CONTROL TOWER es una aplicación full-stack de control de operaciones que integra datos **Plan** (proyecciones) y **Real** (viajes completados), con módulos de supply de conductores, ciclo de vida, alertas de conducta, fuga de flota y motor de acciones. El **backend** es FastAPI (Python 3.8+), con PostgreSQL (esquemas `ops`, `bi`, `plan`, `dim`), conexión vía **psycopg2** (sin ORM), y migraciones **Alembic**. El **frontend** es **React 18 + Vite** (no Next.js), con TailwindCSS y axios; no hay librería de estado global ni React Query. Los datos se materializan en **Materialized Views (MVs)** y vistas en el esquema `ops`; el refresh de MVs se hace mediante **scripts Python** ejecutados manualmente o por cron/jobs externos (no hay scheduler embebido en el repo). Existen **11 routers** en backend y **6 tabs principales** en UI (Resumen, Real, Supply, Conductores en riesgo, Ciclo de vida, Plan y validación), más Diagnósticos (System Health). Todos los módulos listados por negocio (Real LOB, Driver Lifecycle, Supply Dynamics, Behavioral Alerts, Fleet Leakage, Plan vs Real, Ingestion) están **presentes** en código y UI; algunos tienen rutas duplicadas (controltower vs ops) o vistas legacy que conviene unificar en fases posteriores.

---

## 2. Estructura del repositorio

### 2.1 Árbol resumido de carpetas principales

```
YEGO CONTROL TOWER/
├── backend/                    # API y lógica de negocio
│   ├── alembic/                # Migraciones de BD
│   │   ├── versions/           # ~97 migraciones (002 a 090+)
│   │   └── env.py, script.py.mako, alembic.ini
│   ├── app/
│   │   ├── main.py             # Entrypoint FastAPI, registro de routers
│   │   ├── settings.py        # Pydantic Settings (DB_*, CORS, etc.)
│   │   ├── db/                # Conexión, schema_verify, creación esquemas
│   │   ├── routers/           # 11 routers (plan, real, core, ops, health, ingestion, phase2b, phase2c, driver_lifecycle, controltower)
│   │   ├── services/          # Servicios de datos (driver_lifecycle, supply, behavior_alerts, leakage, action_engine, real_lob, etc.)
│   │   ├── adapters/          # plan_repo, real_repo, lob_universe_repo
│   │   └── contracts/         # data_contract (revenue column detection)
│   ├── scripts/               # Scripts Python (refresh MVs, validaciones, diagnósticos)
│   ├── sql/                   # SQL suelto si existe
│   ├── seeds/                 # Datos semilla
│   ├── tests/
│   ├── exports/               # Salidas de export
│   ├── logs/
│   ├── run_server.py         # Arranque uvicorn
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── main.jsx, App.jsx   # Entrypoint y navegación por tabs
│   │   ├── components/        # 29 componentes (.jsx): RealLOB*, SupplyView, DriverLifecycleView, BehavioralAlertsView, FleetLeakageView, etc.
│   │   └── services/
│   │       └── api.js         # Cliente axios, baseURL /api, todas las llamadas API
│   ├── index.html
│   ├── vite.config.js         # Proxy /api -> backend (puerto 8000)
│   ├── package.json           # React 18, Vite 5, axios, Tailwind
│   └── .env.example
├── docs/                      # ~101 archivos .md (lógica, APIs, runbooks, auditorías)
├── scripts/                   # Scripts raíz: phase2b_closeout.ps1, orchestrate_phase2b_closeout.ps1
├── logs/                      # Logs a nivel raíz
└── .cursor/                   # Configuración Cursor
```

### 2.2 Propósito inferido por carpeta

| Carpeta | Propósito |
|---------|-----------|
| `backend/` | API REST FastAPI, acceso a PostgreSQL, servicios y adapters. |
| `backend/alembic/` | Migraciones: tablas, vistas, MVs, índices en esquemas ops, bi, plan, dim. |
| `backend/app/routers/` | Definición de endpoints por dominio (plan, real, ops, phase2b, phase2c, ingestion, driver_lifecycle, controltower, health, core). |
| `backend/app/services/` | Lógica de negocio y consultas a BD (get_* desde MVs/views). |
| `backend/app/adapters/` | Acceso a tablas plan.* y datos real/universe. |
| `backend/scripts/` | Refresh de MVs (driver_lifecycle, real_lob, supply), validaciones, backfills, diagnósticos. No hay cron definido en repo. |
| `frontend/src/components/` | Vistas por tab/subtab; cada módulo tiene al menos un componente (ej. SupplyView, DriverLifecycleView). |
| `frontend/src/services/api.js` | Capa de llamadas HTTP (axios); baseURL dev: proxy /api → backend. |
| `docs/` | Documentación técnica: arquitectura Supply, behavioral alerts, action engine, real LOB, data freshness, runbooks. |

### 2.3 Dónde vive cada parte

- **Backend:** `backend/app/` (main.py, routers, services, db, adapters). Entrypoint: `backend/run_server.py` o `uvicorn app.main:app`.
- **Frontend:** `frontend/src/` (App.jsx, components, services/api.js). Entrypoint: `npm run dev` (Vite, puerto 5173).
- **SQL / MVs:** Definidos en `backend/alembic/versions/*.py` (CREATE MATERIALIZED VIEW / CREATE VIEW en esquema `ops` principalmente).
- **Scripts:** `backend/scripts/*.py` (refresh, validación, pipeline). Raíz: `scripts/*.ps1` (Phase2B closeout).
- **Docs:** `docs/*.md`.

---

## 3. Módulos funcionales detectados

### 3.1 Tabla de módulos (evidencia: UI, rutas, endpoints, vistas SQL/MV)

| modulo_detectado | nombre_visible_en_ui | ruta_frontend | endpoint_backend_relacionado | vista_sql_o_mv_relacionada | estado | descripcion_funcional | evidencia |
|------------------|----------------------|---------------|------------------------------|-----------------------------|--------|------------------------|-----------|
| **Real LOB** | Real | Tab "Real" | `/ops/real-lob/*`, `/ops/real-lob/v2/data`, `/ops/real-lob/drill`, `/ops/real-drill/*`, `/ops/real-strategy/*` | `ops.mv_real_lob_month_v2`, `ops.mv_real_lob_week_v2`, `ops.mv_real_rollup_day`, `ops.real_drill_dim_fact`, `ops.v_trips_real_canon` | activo | Drill-down Real por país, periodo, LOB, park; comparativos WoW/MoM; vista diaria; strategy por país/LOB/ciudad | App.jsx TAB_REAL → RealLOBDrillView; api.js getRealLobV2Data, getRealLobDrillPro; ops.py real-lob/*, real-drill/*, real-strategy/* |
| **Driver Lifecycle** | Ciclo de vida | Tab "Ciclo de vida" | `/ops/driver-lifecycle/*` (weekly, monthly, drilldown, cohorts, parks, series, base-metrics, pro/*) | `ops.mv_driver_lifecycle_base`, `ops.mv_driver_weekly_stats`, `ops.mv_driver_weekly_behavior`, `ops.mv_driver_churn_segments_weekly`, `ops.mv_driver_behavior_shifts_weekly`, `ops.mv_driver_park_shock_weekly`, `ops.mv_driver_segments_weekly` | activo | Evolución del parque y cohortes por park; métricas base; pro: churn segments, park shock, behavior shifts, drivers at risk | App.jsx TAB_LIFECYCLE → DriverLifecycleView; driver_lifecycle.py prefix /ops/driver-lifecycle; driver_lifecycle_service.py; scripts refresh_driver_lifecycle.py, run_driver_lifecycle_build.py |
| **Supply Dynamics** | Supply | Tab "Supply" | `/ops/supply/*` (geo, parks, series, summary, segments/series, alerts, overview-enhanced, composition, migration, definitions, freshness, refresh) | `ops.mv_supply_weekly`, `ops.mv_supply_monthly`, `ops.mv_supply_segments_weekly`, `ops.mv_supply_segment_anomalies_weekly`, `ops.mv_supply_alerts_weekly`, `ops.v_supply_alert_drilldown`, `dim.v_geo_park`, `ops.v_dim_park_resolved` | activo | Dinámica de supply por park: overview, composición, migración entre segmentos, alertas, drilldown | App.jsx TAB_SUPPLY → SupplyView; ops.py supply/*; supply_service.py; run_supply_refresh_pipeline.py; docs DRIVER_SUPPLY_DYNAMICS_*.md |
| **Behavioral Alerts** | Alertas de conducta | Sub-tab "Conductores en riesgo" → "Alertas de conducta" | `/ops/behavior-alerts/*` (summary, insight, drivers, driver-detail, export); también `/controltower/behavior-alerts/*` (duplicado) | Vistas de behavioral alerts (semanal, risk score, etc.) en alembic 082, 085, 090 | activo | Alertas de desviación vs línea base del conductor | App.jsx DRIVER_RISK_SUBTABS behavioral_alerts → BehavioralAlertsView; ops.py y controltower.py behavior-alerts; behavior_alerts_service.py |
| **Fleet Leakage** | Fuga de flota | Sub-tab "Conductores en riesgo" → "Fuga de flota" | `/ops/leakage/*` (summary, drivers, export) | Servicio leakage sobre vistas/MVs de conductores que dejan de operar | activo | Conductores que dejan la flota o reducen actividad de forma relevante | App.jsx fleet_leakage → FleetLeakageView; ops.py leakage/*; leakage_service.py |
| **Plan vs Real** | Plan y validación (Plan Válido, Fase 2B, Fase 2C, Universo & LOB) | Tab "Plan y validación" + sub-tabs (valid, actions, accountability, lob_universe, out_of_universe, missing) | `/ops/plan-vs-real/*`, `/phase2b/*`, `/phase2c/*`, `/plan/*`, `/core/summary/monthly`, `/real/summary/monthly` | `ops.v_plan_vs_real_weekly`, `ops.v_plan_vs_real_realkey_final`, `ops.v_plan_trips_monthly_latest`, `ops.mv_real_trips_weekly`, `ops.v_alerts_2b_weekly`, phase2b/phase2c tablas y vistas | activo | Plan vs Real mensual/semanal; alertas 2B; acciones; scoreboard/backlog/breaches 2C; universo LOB; subida de plan (upload) | App.jsx TAB_PLAN_VALIDATION, MonthlySplitView, WeeklyPlanVsRealView, Phase2BActionsTrackingView, Phase2CAccountabilityView, LobUniverseView, PlanTabs; routers plan, phase2b, phase2c, ops plan-vs-real |
| **Ingestion** | (no tab dedicado; usado en freshness/banner) | GlobalFreshnessBanner, System Health | `/ingestion/status` | `bi.ingestion_status` | activo | Estado de ingesta por dataset (max_year, max_month, last_loaded_at, is_complete_2025) | ingestion.py GET /ingestion/status; api.js getIngestionStatus; bi.ingestion_status en ingestion.py |
| **Driver Behavior (desviación)** | Desviación por ventanas | Sub-tab "Conductores en riesgo" → "Desviación por ventanas" | `/ops/driver-behavior/*` (summary, drivers, driver-detail, export) | `ops.mv_driver_segments_weekly`, `ops.v_driver_last_trip`, `ops.v_dim_driver_resolved` | activo | Desviación por ventanas de tiempo y days_since_last_trip | App.jsx driver_behavior → DriverBehaviorView; ops.py driver-behavior/*; driver_behavior_service.py |
| **Action Engine** | Acciones recomendadas | Sub-tab "Conductores en riesgo" → "Acciones recomendadas" | `/ops/action-engine/*` (summary, cohorts, cohort-detail, recommendations, export) | `ops.v_action_engine_driver_base`, `ops.v_action_engine_cohorts_weekly`, `ops.v_action_engine_recommendations_weekly` | activo | Cohortes y acciones recomendadas para conductores en riesgo | App.jsx action_engine → ActionEngineView; ops.py action-engine/*; action_engine_service.py |
| **Resumen (Executive Snapshot)** | Resumen | Tab "Resumen" | `/core/summary/monthly`, `/ops/plan-vs-real/monthly`, `/ops/compare/overlap-monthly` (y otros para KPIs) | Vistas plan vs real, overlap | activo | KPIs Plan vs Real (viajes, conductores, revenue) en resumen ejecutivo | App.jsx TAB_RESUMEN → ExecutiveSnapshotView; core.py, ops.py |
| **System Health / Diagnósticos** | System Health (dentro Diagnósticos) | Diagnósticos ▾ → System Health | `/ops/system-health`, `/ops/data-freshness/*`, `/ops/integrity-report`, `/ops/data-pipeline-health`, `/ops/integrity-audit/run`, `/ops/pipeline-refresh`, `/ops/supply/refresh` | Observabilidad: data_freshness, integrity, pipeline health | activo | Integridad de datos, freshness de MVs, ingestión, auditoría | App.jsx TAB_SYSTEM_HEALTH → SystemHealthView; ops.py system-health, data-freshness, integrity-report, pipeline-refresh |
| **Top Driver Behavior** | (no tab propio en UI principal; puede ser usado en vistas o futuras) | — | `/ops/top-driver-behavior/*` (summary, benchmarks, patterns, playbook-insights, export) | Vistas top_driver_behavior (087) | parcial / experimental | Insights y patrones de top conductores; puede ser usado en diagnósticos o reportes | ops.py top-driver-behavior/*; top_driver_behavior_service.py; no componente dedicado en App.jsx como tab principal |

### 3.2 Validación explícita de módulos listados por negocio

| Módulo | ¿Existe? | Dónde |
|--------|----------|--------|
| **Real LOB** | Sí | Tab "Real", RealLOBDrillView, RealLOBView, RealLOBDailyView, RealLOBDrillView; routers ops (real-lob/*, real-drill/*, real-strategy/*); MVs mv_real_lob_*_v2, drill, etc. |
| **Driver Lifecycle** | Sí | Tab "Ciclo de vida", DriverLifecycleView; router driver_lifecycle prefix /ops/driver-lifecycle; servicios y scripts de refresh. |
| **Supply Dynamics** | Sí | Tab "Supply", SupplyView; ops/supply/*; docs DRIVER_SUPPLY_DYNAMICS_*; MVs mv_supply_*. |
| **Behavioral Alerts** | Sí | Sub-tab "Alertas de conducta", BehavioralAlertsView; /ops/behavior-alerts y /controltower/behavior-alerts. |
| **Fleet Leakage** | Sí | Sub-tab "Fuga de flota", FleetLeakageView; /ops/leakage/*. |
| **Plan vs Real** | Sí | Tab "Plan y validación" y sub-tabs (Plan Válido, Fase 2B, Fase 2C, Universo & LOB, Expansión, Huecos); phase2b, phase2c, plan, ops plan-vs-real. |
| **Ingestion** | Sí | GET /ingestion/status; usado por freshness/banner y system health; tabla bi.ingestion_status. |

### 3.3 Clasificación activo / legacy / parcial / experimental

- **Activos (en uso en UI y API):** Real LOB, Driver Lifecycle, Supply Dynamics, Behavioral Alerts, Fleet Leakage, Plan vs Real, Ingestion, Driver Behavior (desviación), Action Engine, Resumen, System Health.
- **Parcial / experimental:** Top Driver Behavior (backend completo, sin tab dedicado en navegación principal).
- **Legacy a considerar:** Rutas duplicadas `/controltower/behavior-alerts/*` vs `/ops/behavior-alerts/*`; endpoints legacy Real LOB v1 (monthly, weekly sin v2) aún presentes; PlanTabs para "Expansión" y "Huecos" (out_of_universe, missing) referidos como Legacy en comentarios App.jsx.

---

## 4. Stack tecnológico validado

### 4.1 Matriz tecnología

| capa | tecnologia | version_si_aplica | evidencia_archivo | comentario |
|------|------------|-------------------|-------------------|------------|
| Backend API | FastAPI | ≥0.104 | backend/requirements.txt, app/main.py | Confirmado. |
| Backend runtime | Python | 3.8+ (recomendado 3.9/3.10) | backend/requirements.txt (comentario) | Sin pyproject.toml/poetry; requirements.txt. |
| Servidor ASGI | Uvicorn | ≥0.24 | backend/requirements.txt, run_server.py | Estándar. |
| Base de datos | PostgreSQL | — | backend/.env.example DB_NAME=yego_integral, connection.py psycopg2 | Confirmado. |
| Acceso a BD | psycopg2 (binary) | ≥2.9 | backend/requirements.txt, app/db/connection.py | Sin ORM; pool ThreadedConnectionPool, RealDictCursor. |
| Migraciones | Alembic | ≥1.12 | backend/requirements.txt, backend/alembic.ini, alembic/versions/*.py | Confirmado; ~97 migraciones. |
| Materialized Views | PostgreSQL (ops.*) | — | alembic/versions (CREATE MATERIALIZED VIEW, REFRESH) | MVs en esquema ops; refresh vía scripts. |
| Frontend framework | React | ^18.2 | frontend/package.json | Confirmado. |
| Build / dev server | Vite | ^5.0 | frontend/package.json, vite.config.js | **No Next.js.** |
| HTTP cliente (frontend) | axios | ^1.6 | frontend/package.json, src/services/api.js | baseURL /api (proxy en dev). |
| Estilos | TailwindCSS | ^3.3 | frontend/package.json | PostCSS, autoprefixer. |
| Config / env | pydantic-settings, python-dotenv | — | backend/app/settings.py, .env.example | DB_*, CORS_ORIGINS, DATABASE_URL. |
| Validación | Pydantic | ≥2.0 | backend/requirements.txt | Modelos y settings. |
| Datos / Excel | pandas, openpyxl | pandas≥2.0, openpyxl≥3.1 | backend/requirements.txt | Carga/transformación plan y datos. |

### 4.2 Confirmación explícita

| Tecnología | ¿Confirmado? | Evidencia |
|------------|-------------|-----------|
| FastAPI | Sí | main.py, routers, requirements.txt |
| Python | Sí | requirements.txt, scripts .py |
| PostgreSQL | Sí | connection.py, .env.example, esquemas ops, bi, plan, dim |
| Alembic | Sí | alembic.ini, versions/*.py |
| Materialized Views | Sí | MVs en ops (mv_real_lob_*, mv_supply_*, mv_driver_*, etc.) |
| React | Sí | package.json, componentes .jsx |
| Next.js | **No** | Frontend es Vite + React, no Next.js |
| Scripts Python | Sí | backend/scripts/*.py (refresh, validación, pipeline) |
| Cron / jobs / refresh | Parcial | Scripts existen (run_supply_refresh_pipeline.py, refresh_driver_lifecycle.py, refresh_real_lob_mvs_v2.py); **no hay cron ni scheduler definido dentro del repo**; pendiente validar si se programan externamente. |

### 4.3 Otros elementos

- **ORM:** No. Acceso directo con psycopg2 y RealDictCursor.
- **Charts / UI:** No hay librería de gráficos en package.json; tablas y cards con Tailwind.
- **Estado global frontend:** Solo React useState/useContext en App.jsx (filters, activeTab, sub-tabs); no Redux, no Zustand, no React Query.
- **Capa de fetch:** axios en `api.js` con interceptors en dev (log duración); timeouts por tipo de endpoint (ej. REAL_DRILL_TIMEOUT_MS 360000).
- **Autenticación:** No detectada en routers ni en frontend (no hay login ni guards).
- **Proxy dev:** Vite proxy `/api` → `http://127.0.0.1:8000` (rewrite quita `/api`), timeout 360000 para drill.

---

## 5. Flujo de datos resumido

### 5.1 Patrón general

```
source (tablas bi.*, dim.*, plan.*)
  → transform (vistas SQL, MVs en ops.*)
  → refresh (scripts Python: refresh_*.py, run_*_pipeline.py)
  → endpoint (FastAPI router → service → get_db() → SELECT)
  → frontend (api.js → axios.get/post)
  → page/tab (componente React)
```

### 5.2 Por módulo (diagrama textual)

- **Real LOB:**  
  `bi.*/trips` + homologación LOB → `ops.v_trips_real_canon`, `ops.mv_real_lob_month_v2`, `ops.mv_real_lob_week_v2`, `ops.real_drill_dim_fact` / `ops.real_rollup_day_fact` → refresh con `refresh_real_lob_mvs_v2.py` / `refresh_real_lob_drill_pro_mv.py` → `/ops/real-lob/*`, `/ops/real-lob/drill`, `/ops/real-drill/*`, `/ops/real-strategy/*` → RealLOBDrillView, RealLOBDailyView.

- **Driver Lifecycle:**  
  Viajes (trips_unified / v_driver_lifecycle_trips_completed) → `ops.mv_driver_lifecycle_base`, `ops.mv_driver_weekly_stats`, `ops.mv_driver_weekly_behavior`, `ops.mv_driver_churn_segments_weekly`, etc. → refresh con `refresh_driver_lifecycle.py`, `run_driver_lifecycle_build.py` → `/ops/driver-lifecycle/*` → DriverLifecycleView.

- **Supply Dynamics:**  
  `ops.mv_driver_weekly_stats` + `ops.driver_segment_config` → `ops.mv_driver_segments_weekly` → `ops.mv_supply_segments_weekly`, `ops.mv_supply_segment_anomalies_weekly`, `ops.mv_supply_alerts_weekly`; `ops.mv_supply_weekly`/`monthly` → refresh con `run_supply_refresh_pipeline.py` (ops.refresh_supply_alerting_mvs) → `/ops/supply/*` → SupplyView.

- **Behavioral Alerts:**  
  Vistas de behavioral alerts (semanal, risk score) → `/ops/behavior-alerts/*` o `/controltower/behavior-alerts/*` → BehavioralAlertsView.

- **Fleet Leakage:**  
  Lógica sobre conductores que dejan/reducen actividad → `/ops/leakage/*` → FleetLeakageView.

- **Ingestion:**  
  `bi.ingestion_status` (dataset_name, max_year, max_month, last_loaded_at, is_complete_2025) → `/ingestion/status` → GlobalFreshnessBanner / System Health.

---

## 6. Database structure discovery

### 6.1 Esquemas relevantes

| Esquema | Uso |
|---------|-----|
| **ops** | Vistas y MVs operativas: plan_vs_real, real_lob, supply, driver lifecycle, behavioral alerts, action engine, integrity, freshness. |
| **bi** | Datos de negocio: real_monthly_agg, real_daily_enriched, ingestion_status. |
| **plan** | Tablas de plan: plan_long_raw, plan_trips_monthly (vía migraciones). |
| **dim** | Dimensiones: dim_park, v_geo_park (parks, ciudad, país). |

### 6.2 Tablas principales (inferidas)

- `bi.real_monthly_agg`, `bi.real_daily_enriched`, `bi.ingestion_status`
- `plan.plan_long_raw` y tablas derivadas del plan
- `dim.dim_park` (o equivalente); `ops.driver_segment_config`, `ops.supply_refresh_log`, `ops.data_integrity_audit` (si existen por migraciones)
- Phase2B: tabla de acciones (015); Phase2C: accountability y LOB universe

### 6.3 Views y Materialized Views principales (ops)

- **Real LOB:** mv_real_lob_month_v2, mv_real_lob_week_v2, mv_real_rollup_day (o vista sobre real_rollup_day_fact), real_drill_dim_fact / mv_real_drill_dim_agg, v_trips_real_canon, v_real_freshness_trips, v_real_trips_with_lob_v2, v_real_drill_* (country/lob/park month/week).
- **Plan vs Real:** v_plan_trips_monthly_latest, mv_real_trips_weekly, v_plan_vs_real_weekly, v_alerts_2b_weekly, v_plan_weekly_baseline_effective, v_plan_vs_real_realkey_final.
- **Supply:** mv_driver_segments_weekly, mv_supply_segments_weekly, mv_supply_segment_anomalies_weekly, mv_supply_alerts_weekly, mv_supply_weekly, mv_supply_monthly, v_supply_alert_drilldown.
- **Driver Lifecycle:** mv_driver_lifecycle_base, mv_driver_weekly_stats, mv_driver_weekly_behavior, mv_driver_churn_segments_weekly, mv_driver_behavior_shifts_weekly, mv_driver_park_shock_weekly.
- **Behavioral / Action Engine:** vistas de behavioral alerts (082, 085, 090), v_action_engine_driver_base, v_action_engine_cohorts_weekly, v_action_engine_recommendations_weekly.
- **Dimensiones:** v_dim_park_resolved, v_dim_driver_resolved, v_geo_park (dim).

### 6.4 Funciones de refresh y scripts batch

- **Refresh MVs:** Scripts en `backend/scripts/`: `refresh_driver_lifecycle.py`, `refresh_real_lob_mvs_v2.py`, `refresh_real_lob_drill_pro_mv.py`, `run_supply_refresh_pipeline.py` (llama ops.refresh_supply_alerting_mvs), `refresh_mv_real_v2.py`, `refresh_plan_weekly_weighted.py`, etc.
- **Pipeline:** `run_supply_refresh_pipeline.py` registra en `ops.supply_refresh_log` y ejecuta refresh encadenado.
- **Naming:** Migraciones con prefijo numérico (002_..., 080_...); MVs con prefijo `mv_`, vistas `v_`.

### 6.5 Inventario resumido y módulo que alimentan

- **Real LOB:** mv_real_lob_*_v2, mv_real_rollup_day (o vista), real_drill_dim_fact, v_trips_real_canon → Real LOB y Real Drill.
- **Plan vs Real:** v_plan_*, mv_real_trips_weekly, v_plan_vs_real_*, v_alerts_2b_weekly → Plan y validación, Phase2B/2C.
- **Supply:** mv_driver_segments_weekly, mv_supply_* → Supply Dynamics.
- **Driver Lifecycle:** mv_driver_lifecycle_base, mv_driver_weekly_*, mv_driver_churn_*, mv_driver_behavior_shifts_*, mv_driver_park_shock_* → Ciclo de vida.
- **Behavioral / Action Engine:** vistas behavioral + action_engine_* → Conductores en riesgo (alertas, acciones).

Artefactos en migraciones recientes (080+) y en scripts de refresh se consideran **activos**; vistas reemplazadas por MVs o por fact tables (p. ej. mv_real_drill_dim_agg como vista sobre real_drill_dim_fact) pueden considerarse compatibilidad y no legacy crudo.

---

## 7. Respuesta final a las tres preguntas

### PREGUNTA 1 — ¿Cuáles son exactamente los módulos funcionales actuales del sistema?

Los módulos funcionales actuales, con nombres exactos en código/UI/API, son:

1. **Real LOB** — UI: tab "Real"; componentes RealLOBDrillView (principal), RealLOBDailyView, RealLOBView; API: `/ops/real-lob/*`, `/ops/real-lob/drill`, `/ops/real-drill/*`, `/ops/real-strategy/*`.
2. **Driver Lifecycle (Ciclo de vida)** — UI: tab "Ciclo de vida"; DriverLifecycleView; API: `/ops/driver-lifecycle/*`.
3. **Supply Dynamics (Supply)** — UI: tab "Supply"; SupplyView; API: `/ops/supply/*`.
4. **Behavioral Alerts (Alertas de conducta)** — UI: sub-tab "Alertas de conducta" bajo "Conductores en riesgo"; BehavioralAlertsView; API: `/ops/behavior-alerts/*` y `/controltower/behavior-alerts/*`.
5. **Fleet Leakage (Fuga de flota)** — UI: sub-tab "Fuga de flota" bajo "Conductores en riesgo"; FleetLeakageView; API: `/ops/leakage/*`.
6. **Plan vs Real (Plan y validación)** — UI: tab "Plan y validación" con sub-tabs Plan Válido, Expansión, Huecos, Fase 2B, Fase 2C, Universo & LOB; componentes MonthlySplitView, WeeklyPlanVsRealView, Phase2BActionsTrackingView, Phase2CAccountabilityView, LobUniverseView, PlanTabs; API: `/plan/*`, `/phase2b/*`, `/phase2c/*`, `/ops/plan-vs-real/*`, `/core/summary/monthly`, `/real/summary/monthly`.
7. **Ingestion** — Sin tab propio; API: `/ingestion/status`; usado en freshness y System Health.
8. **Driver Behavior (Desviación por ventanas)** — UI: sub-tab "Desviación por ventanas"; DriverBehaviorView; API: `/ops/driver-behavior/*`.
9. **Action Engine (Acciones recomendadas)** — UI: sub-tab "Acciones recomendadas"; ActionEngineView; API: `/ops/action-engine/*`.
10. **Resumen (Executive Snapshot)** — UI: tab "Resumen"; ExecutiveSnapshotView; API: `/core/summary/monthly`, `/ops/plan-vs-real/monthly`, etc.
11. **System Health (Diagnósticos)** — UI: Diagnósticos → System Health; SystemHealthView; API: `/ops/system-health`, `/ops/data-freshness/*`, `/ops/integrity-report`, `/ops/pipeline-refresh`, etc.

Adicional: **Top Driver Behavior** existe en backend (`/ops/top-driver-behavior/*`) pero no tiene tab dedicado en la navegación principal (parcial/experimental).

### PREGUNTA 2 — ¿Cuál es la arquitectura tecnológica real del sistema?

- **Backend:** FastAPI (Python 3.8+), Uvicorn, Pydantic. **Base de datos:** PostgreSQL (esquemas ops, bi, plan, dim). **Acceso a BD:** psycopg2 (pool, RealDictCursor), sin ORM. **Migraciones:** Alembic; definición de tablas, vistas y Materialized Views en `ops` (y otros esquemas). **Carga de datos:** pandas, openpyxl (plan, transformaciones).
- **Frontend:** React 18, Vite 5 (no Next.js), TailwindCSS, axios. Sin librería de estado global ni React Query; estado local en App y componentes. Proxy en dev: `/api` → backend en puerto 8000.
- **Infra lógica:** Scripts Python en `backend/scripts/` para refresh de MVs (driver lifecycle, real LOB, supply) y pipelines (run_supply_refresh_pipeline); no hay cron ni scheduler definido dentro del repositorio (pendiente validar si hay cron externo).
- **API:** 11 routers: plan, real, core, ops, health, ingestion, phase2b, phase2c, driver_lifecycle, controltower. La mayoría de endpoints de datos están bajo `/ops/`. No hay caché explícito en código (lectura directa a BD).

### PREGUNTA 3 — ¿Cuál es la estructura real del repositorio?

- **Raíz:** `backend/`, `frontend/`, `docs/`, `scripts/` (2 scripts .ps1), `logs/`, `.cursor/`.
- **backend:** `alembic/` (versions con ~97 migraciones), `app/` (main.py, db, routers, services, adapters, contracts, settings), `scripts/` (Python: refresh, validación, pipeline), `sql/`, `seeds/`, `tests/`, `exports/`, `logs/`, `run_server.py`, `requirements.txt`, `.env.example`.
- **frontend:** `src/` (main.jsx, App.jsx, components/, services/api.js), `index.html`, `vite.config.js`, `package.json`, `.env.example`.
- **docs:** ~101 archivos .md (arquitectura, APIs, runbooks, auditorías).

No existe en raíz `package.json` ni `pyproject.toml` a nivel monorepo; backend y frontend son proyectos separados.

---

## 8. Gaps y riesgos (Gap & Risk Report)

### 8.1 Módulos mencionados por negocio no encontrados técnicamente

- **Ninguno.** Real LOB, Driver Lifecycle, Supply Dynamics, Behavioral Alerts, Fleet Leakage, Plan vs Real e Ingestion están implementados y referenciados en código y/o UI.

### 8.2 Módulos encontrados técnicamente pero poco visibles en UI

- **Top Driver Behavior:** Endpoints completos en `/ops/top-driver-behavior/*` sin tab propio en la navegación principal; podría ser usado en diagnósticos o reportes internos.

### 8.3 Lógica en backend sin uso claro en frontend

- Duplicación de rutas **behavior-alerts** en `/controltower/` y `/ops/`; conviene unificar consumo en un solo prefijo.
- Posibles endpoints legacy de Real LOB (v1 monthly/weekly sin v2) aún en uso por alguna pantalla o no; revisar referencias en api.js (getRealLobMonthly, getRealLobWeekly siguen definidos).

### 8.4 Frontend sin backend claro

- No detectado. Cada tab/subtab principal tiene endpoints asociados en api.js y routers.

### 8.5 Artefactos legacy que pueden confundir

- **PlanTabs** para "Expansión" (out_of_universe) y "Huecos" (missing) marcados como Legacy en comentarios de App.jsx.
- Múltiples migraciones que redefinen las mismas MVs o las convierten de MV a vista sobre fact table (ej. mv_real_drill_dim_agg, mv_real_rollup_day); al leer documentación o hacer cambios, verificar la migración más reciente aplicada.
- Carpeta `backend/alembic/versions/__pycache__/` con .pyc de migraciones (no afecta ejecución pero puede generar ruido).

### 8.6 Dependencias críticas

- PostgreSQL accesible con esquemas ops, bi, plan, dim y tablas/MVs creadas por Alembic.
- Variables de entorno: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD (o DATABASE_URL); CORS_ORIGINS para frontend.
- Refresh de MVs ejecutado de forma periódica (scripts o cron externo) para que Supply, Real LOB y Driver Lifecycle tengan datos recientes.
- En producción, backend detrás de nginx (o similar) con proxy `/api` al puerto del backend; frontend con VITE_API_URL si el API no está en el mismo origen.

---

## 9. Recomendaciones para siguiente fase

1. **Unificar rutas de Behavioral Alerts:** Decidir si el frontend consume solo `/ops/behavior-alerts/*` o solo `/controltower/behavior-alerts/*` y deprecar el otro para evitar duplicación.
2. **Documentar o automatizar refresh de MVs:** Si existe cron/job externo, documentarlo en docs/ o runbook; si no, valorar un único punto de orquestación (script o job) que ejecute en orden: driver lifecycle → real LOB → supply (según dependencias).
3. **Revisar uso de Real LOB v1:** Confirmar si algún componente usa getRealLobMonthly/getRealLobWeekly (sin v2) y, si no, considerar marcar como legacy o eliminar.
4. **Clarificar rol de Top Driver Behavior:** Si es para uso interno/diagnósticos, documentar; si debe ser primera clase en UI, añadir tab o sub-tab y enlazar en App.jsx.
5. **Inventario de migraciones aplicadas:** Para cada entorno, tener claro el revision actual de Alembic y la lista de MVs/views realmente presentes, para alinear documentación y scripts de refresh.
6. **Fase 0B o diseño:** Con este discovery, se puede pasar a diseño de cambios (nuevos módulos, refactors o consolidación de legacy) sin modificar aún el comportamiento del sistema.

---

*Documento generado en FASE 0A — System Discovery. Solo lectura y mapeo; no se realizaron cambios en código, BD ni configuración.*
