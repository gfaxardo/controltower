# YEGO Control Tower — Auditoría real del sistema en ejecución

**Fecha de auditoría:** 2025-03-12  
**Objetivo:** Verificar qué está funcionando realmente (frontend, backend, BD, endpoints, UI) y si las implementaciones recientes (Behavioral Alerts, Sudden Stop, Last Trip) están conectadas de punta a punta.  
**No se ha implementado ningún cambio; solo auditoría.**

---

## FASE 1 — Escaneo de frontend real

### Tabla: vista → componente → ruta → endpoints → visible en nav → observaciones

| vista | componente | ruta | endpoints que consume | visible_en_nav | observaciones |
|-------|------------|------|------------------------|----------------|---------------|
| Real LOB | RealLOBDrillView | frontend/src/components/RealLOBDrillView.jsx | GET /ops/real-lob/drill, /ops/real-lob/drill/children, /ops/real-lob/drill/parks, /ops/period-semantics, /ops/real-lob/comparatives/weekly, /ops/real-lob/comparatives/monthly, /ops/real-drill/summary, /ops/real-drill/by-lob, /ops/real-drill/by-park | Sí | Incluye subvista Daily (RealLOBDailyView) que usa /ops/real-lob/daily/* |
| Driver Lifecycle | DriverLifecycleView | frontend/src/components/DriverLifecycleView.jsx | GET /ops/driver-lifecycle/parks, /summary, /series, /parks-summary, /cohorts, /base-metrics-drilldown, /cohort-drilldown, /drilldown | Sí | Park obligatorio |
| Driver Supply Dynamics | SupplyView | frontend/src/components/SupplyView.jsx | GET /ops/supply/geo, /overview-enhanced, /composition, /migration, /migration/drilldown, /alerts, /alerts/drilldown, /freshness, /definitions, /segments/config | Sí | 4 tabs: Overview, Composition, Migration, Alerts |
| Behavioral Alerts | BehavioralAlertsView | frontend/src/components/BehavioralAlertsView.jsx | GET /ops/supply/geo, /ops/behavior-alerts/summary, /insight, /drivers, /driver-detail; GET /ops/behavior-alerts/export (URL descarga) | Sí | Tabla con columna "Último viaje" (last_trip_date) |
| Fleet Leakage | FleetLeakageView | frontend/src/components/FleetLeakageView.jsx | GET /ops/supply/geo, /ops/leakage/summary, /ops/leakage/drivers; GET /ops/leakage/export (URL) | Sí | — |
| Driver Behavior | DriverBehaviorView | frontend/src/components/DriverBehaviorView.jsx | GET /ops/supply/geo, /ops/driver-behavior/summary, /drivers, /driver-detail; GET /ops/driver-behavior/export (URL) | Sí | — |
| Action Engine | ActionEngineView | frontend/src/components/ActionEngineView.jsx | GET /ops/supply/geo, /ops/action-engine/summary, /cohorts, /cohort-detail, /recommendations, /export; GET /ops/top-driver-behavior/summary, /benchmarks, /patterns, /playbook-insights, /export | Sí | — |
| Snapshot | ExecutiveSnapshotView | frontend/src/components/ExecutiveSnapshotView.jsx | Usa KPICards: GET /ops/plan/monthly, /ops/real/monthly (vía getPlanMonthlySplit, getRealMonthlySplit) | Sí | Solo envuelve KPICards; filtros de App |
| System Health | SystemHealthView | frontend/src/components/SystemHealthView.jsx | GET /ops/system-health, /ops/data-pipeline-health; POST /ops/integrity-audit/run | Sí | — |
| Legacy (contenedor) | — | App.jsx | Según subpestaña (ver abajo) | Sí | 6 subvistas internas |
| Plan Válido (Legacy) | MonthlySplitView + WeeklyPlanVsRealView | MonthlySplitView.jsx, WeeklyPlanVsRealView.jsx | /ops/real/monthly, /ops/plan/monthly, /ops/compare/overlap-monthly; /phase2b/weekly/plan-vs-real, /phase2b/weekly/alerts | Dentro Legacy | — |
| Expansión (Legacy) | PlanTabs | PlanTabs.jsx | /plan/out_of_universe, /ingestion/status | Dentro Legacy | activeTab=out_of_universe |
| Huecos (Legacy) | PlanTabs | PlanTabs.jsx | /plan/missing, /ingestion/status | Dentro Legacy | activeTab=missing |
| Fase 2B (Legacy) | Phase2BActionsTrackingView | Phase2BActionsTrackingView.jsx | GET/PATCH /phase2b/actions, createPhase2BAction (POST) | Dentro Legacy | — |
| Fase 2C (Legacy) | Phase2CAccountabilityView | Phase2CAccountabilityView.jsx | GET /phase2c/scoreboard, /backlog, /breaches; POST /phase2c/run-snapshot; GET /phase2c/lob-universe, /lob-universe/unmatched | Dentro Legacy | — |
| Universo & LOB (Legacy) | LobUniverseView | LobUniverseView.jsx | GET /phase2c/lob-universe, /phase2c/lob-universe/unmatched | Dentro Legacy | — |
| GlobalFreshnessBanner | GlobalFreshnessBanner | GlobalFreshnessBanner.jsx | GET /ops/data-freshness/global, /ops/data-pipeline-health | Siempre visible | — |
| UploadPlan (modal ADMIN) | UploadPlan | UploadPlan.jsx | POST /plan/upload_simple, uploadPlanRuta27 | Oculto (modal) | — |

---

## FASE 2 — Verificación Behavioral Alerts (implementación)

### Backend: vistas y MV

| Objeto | Estado en código | Estado en BD (según migración aplicada) |
|--------|-------------------|------------------------------------------|
| ops.v_driver_behavior_alerts_weekly | Definido en migración **090** (y en 089/anteriores con otra definición) | **090 NO aplicada** → la BD tiene la versión anterior (pre–Sudden Stop). Ver Fase 3. |
| ops.mv_driver_behavior_alerts_weekly | Creado en migración 090 (y en anteriores) | Misma observación: esquema actual en BD es el de 089. |
| ops.v_driver_last_trip | Usado por behavior_alerts_service (JOIN para last_trip_date) | Depende de migración 089 u otra que la cree; no verificada en BD en esta auditoría. |

### Endpoints

| Endpoint | Definido en backend | Llamado desde frontend |
|----------|---------------------|-------------------------|
| GET /ops/behavior-alerts/summary | Sí (ops.py) | Sí (getBehaviorAlertsSummary → BehavioralAlertsView) |
| GET /ops/behavior-alerts/drivers | Sí (ops.py) | Sí (getBehaviorAlertsDrivers) |
| GET /ops/behavior-alerts/export | Sí (ops.py) | Sí (getBehaviorAlertsExportUrl — link de descarga) |
| GET /ops/behavior-alerts/insight | Sí (ops.py) | Sí (getBehaviorAlertsInsight) |
| GET /ops/behavior-alerts/driver-detail | Sí (ops.py) | Sí (getBehaviorAlertsDriverDetail) |

### Servicio

- **behavior_alerts_service.py:** Existe y está conectado a los endpoints. Usa `_ALERTS_VIEW` y `_ALERTS_MV` (ops.v_driver_behavior_alerts_weekly / mv). Para lista de conductores y export hace `LEFT JOIN ops.v_driver_last_trip lt` y devuelve `lt.last_trip_date`.

### Campos requeridos

| Campo | En vista 090 (definición en código) | En servicio (drivers/detail/export) | En UI (BehavioralAlertsView) |
|-------|-------------------------------------|-------------------------------------|------------------------------|
| alert_type | Sí (CASE: Sudden Stop, Critical Drop, …) | Sí | Sí (columna Alerta) |
| severity | Sí | Sí | Sí (columna Severidad) |
| risk_band | Sí | Sí | Sí (columna Risk Band) |
| weeks_declining_consecutively | Sí (viene de base) | Sí | Sí (Persistencia / getPersistenceLabel) |
| weeks_rising_consecutively | Sí (viene de base) | Sí | Sí (Persistencia) |
| last_trip_date | **No** en la vista 090 (la vista no la incluye) | **Sí** (vía JOIN con ops.v_driver_last_trip en drivers y export) | **Sí** (columna "Último viaje", formatLastTrip(r.last_trip_date)) |

Conclusión: **last_trip_date** no está en la vista de alertas; el servicio la añade en **drivers** y **export** mediante JOIN con `ops.v_driver_last_trip`. En **driver-detail** el servicio no incluye last_trip_date (solo lee de _ALERTS_SOURCE).

---

## FASE 3 — Validación migración 090

### Existencia y aplicación

- **Archivo de migración:** `backend/alembic/versions/090_behavioral_alerts_sudden_stop_mutually_exclusive.py` — **existe**.
- **Aplicada en BD:** **NO**. `alembic current` en el backend devuelve **089_driver_behavior_deviation_last_trip**. La migración 090 no se ha ejecutado.

Implicación: en la base de datos sigue la definición **anterior** de `ops.v_driver_behavior_alerts_weekly` (y de la MV). Es decir:

- **Sudden Stop** como primer nivel de precedencia y clasificación **mutuamente excluyente** (Sudden Stop → Critical Drop → Moderate Drop → Silent Erosion → High Volatility → Strong Recovery → Stable Performer) **no está activa en BD**.
- El código del servicio y del front asumen la lógica de 090 (p. ej. summary con `sudden_stop`); si la vista en BD no tiene esa definición, los conteos "Sudden Stop" y el resto pueden no coincidir con la lógica documentada.

### Definición en 090 (solo en código, no en BD)

La migración 090 define:

1. **Sudden Stop:** `trips_current_week = 0` y `avg_trips_baseline > 0`.
2. **Critical Drop:** baseline ≥ 40, delta_pct ≤ -30%, active_weeks_in_window ≥ 4.
3. **Moderate Drop:** -30% < delta_pct ≤ -15%.
4. **Silent Erosion:** weeks_declining_consecutively ≥ 3 (y no ya clasificado como Critical/Moderate).
5. **High Volatility:** (stddev/avg) > 0.5 en baseline (y no ya clasificado como Critical/Moderate/Silent).
6. **Strong Recovery:** delta_pct ≥ 30% y active_weeks_in_window ≥ 3.
7. **Stable Performer:** resto.

Precedencia: **mutuamente excluyente** en el orden 1→7 (CASE WHEN en ese orden).

---

## FASE 4 — Last Trip hasta la UI

### Flujo comprobado

| Paso | Componente | Estado |
|------|------------|--------|
| 1. SQL / vista | ops.v_driver_last_trip (driver_key, last_trip_date) | Asumido existente (usado por servicio y por driver_behavior). No se verificó en BD. |
| 2. Servicio | behavior_alerts_service.get_behavior_alerts_drivers: `LEFT JOIN ops.v_driver_last_trip lt ... SELECT ... lt.last_trip_date` | **Conectado**: la respuesta de `/ops/behavior-alerts/drivers` incluye `last_trip_date`. |
| 3. Endpoint | GET /ops/behavior-alerts/drivers devuelve filas con last_trip_date | **Sí** (el router devuelve el dict del servicio). |
| 4. api.js | getBehaviorAlertsDrivers → GET /ops/behavior-alerts/drivers; respuesta sin transformación | **Sí**. |
| 5. BehavioralAlertsView | Recibe `r.last_trip_date` en cada fila de la tabla; columna "Último viaje" con `formatLastTrip(r.last_trip_date)` | **Sí** (línea ~596: `<td ...>{formatLastTrip(r.last_trip_date)}</td>`). |

Conclusión: **Last Trip llega a la UI** en la tabla principal de Behavioral Alerts. La cadena no se rompe. En el **detalle del conductor** (driver-detail) el servicio no devuelve last_trip_date; si se quisiera mostrar ahí, habría que añadirlo al endpoint driver-detail.

---

## FASE 5 — Endpoints realmente usados por vista

Resumen: cada vista visible en la navegación llama a un conjunto concreto de endpoints (ver tabla Fase 1). A continuación se listan endpoints del backend que **no** son llamados por ningún componente que esté montado en App.jsx (vistas principales o Legacy).

### Endpoints que SÍ usa el front (desde vistas conectadas)

- /ops/supply/geo, /behavior-alerts/*, /leakage/*, /driver-behavior/*, /action-engine/*, /top-driver-behavior/*, /real-lob/drill*, /real-lob/drill/parks, /period-semantics, /real-lob/comparatives/*, /real-drill/summary, /real-drill/by-lob, /real-drill/by-park
- /ops/driver-lifecycle/parks, /summary, /series, /parks-summary, /cohorts, /base-metrics-drilldown, /cohort-drilldown, /drilldown
- /ops/supply/overview-enhanced, /composition, /migration*, /alerts*, /freshness, /definitions, /segments/config
- /ops/real/monthly, /ops/plan/monthly, /ops/compare/overlap-monthly, /ops/real-lob/daily/*
- /phase2b/weekly/*, /phase2b/actions, /phase2c/*, /plan/out_of_universe, /plan/missing, /ingestion/status
- /ops/system-health, /data-pipeline-health, /ops/integrity-audit/run, /ops/data-freshness/global
- /plan/upload_simple (y upload_ruta27)

### Endpoints huérfanos o no usados por vistas visibles

(No hay llamada desde ningún componente que se renderice en App.)

| Endpoint | Usado por (código) | Observación |
|----------|---------------------|-------------|
| GET /core/summary/monthly | MonthlyView (getCoreMonthlySummary) | MonthlyView **no está en App** → endpoint usado solo por componente huérfano. |
| GET /ops/universe | getOpsUniverse en api.js | Ningún componente en App importa getOpsUniverse. |
| GET /ops/territory-quality/kpis | — | No hay función en api.js que lo llame. |
| GET /ops/territory-quality/unmapped-parks | — | Idem. |
| GET /ops/plan-vs-real/monthly | PlanVsRealView (getPlanVsRealMonthly) | PlanVsRealView **no está en App**. |
| GET /ops/plan-vs-real/alerts | PlanVsRealView (getPlanVsRealAlerts) | Idem. |
| GET /ops/real-lob/monthly, /weekly, /monthly-v2, /weekly-v2, /filters, /v2/data | RealLOBView | RealLOBView **no está en App**. |
| GET /ops/real-strategy/country, /lob, /cities | RealLOBView | Idem. |
| GET /ops/real-drill/coverage, /totals | RealLOBDrillView podría usar totals; coverage no referenciado en RealLOBDrillView leído | Parcialmente usados o legacy. |
| GET /ops/supply/parks, /series, /summary, /global/series, /segments/series | SupplyView no usa getSupplyParks, getSupplySeries, getSupplySummary, getSupplyGlobalSeries, getSupplySegmentsSeries (usa overview-enhanced, composition, migration, alerts) | No usados por la Supply actual. |
| GET /ops/driver-lifecycle/weekly, /monthly, /base-metrics | api.js los exporta; DriverLifecycleView usa /parks, /summary, /series, /parks-summary, /cohorts, drilldowns | weekly/monthly/base-metrics no usados por DriverLifecycleView. |
| GET /controltower/behavior-alerts/* | Alias del mismo ops; front usa /ops/behavior-alerts | Duplicado de /ops (otro prefijo). |
| GET /ingestion/status | PlanTabs, con dataset por defecto | Usado (PlanTabs bajo Legacy). |

---

## FASE 6 — Mapeo de fuentes de datos por vista

| Vista | Tabla / Vista SQL | Materialized View |
|-------|-------------------|--------------------|
| Real LOB (Drill) | ops.v_real_data_coverage | ops.mv_real_drill_dim_agg; ops.mv_real_drill_service_by_park |
| Real LOB Daily | (consultar real_lob_daily_service) | — |
| Driver Lifecycle | ops.v_driver_weekly_churn_reactivation, ops.v_dim_park_resolved, dim.dim_park | ops.mv_driver_lifecycle_base, ops.mv_driver_weekly_stats, ops.mv_driver_monthly_stats, ops.mv_driver_lifecycle_weekly_kpis |
| Driver Supply Dynamics | dim.v_geo_park, ops.v_dim_park_resolved, ops.v_supply_alert_drilldown | ops.mv_supply_weekly, ops.mv_supply_monthly, ops.mv_supply_segments_weekly, ops.mv_supply_alerts_weekly |
| Behavioral Alerts | ops.v_driver_behavior_alerts_weekly, ops.v_driver_last_trip | ops.mv_driver_behavior_alerts_weekly |
| Fleet Leakage | — | — (solo vista) ops.v_fleet_leakage_snapshot |
| Driver Behavior | ops.v_driver_last_trip, dim.v_geo_park, ops.v_dim_driver_resolved | ops.mv_driver_segments_weekly |
| Action Engine | — | — (vistas) ops.v_action_engine_driver_base, ops.v_action_engine_cohorts_weekly, ops.v_action_engine_recommendations_weekly |
| Snapshot (KPICards) | ops.v_plan_trips_monthly_latest | ops.mv_real_trips_monthly |
| Legacy Plan Válido | Idem + phase2b weekly | Idem |
| System Health | ops.v_control_tower_integrity_report, ops.data_integrity_audit, ops.v_mv_freshness, ops.v_ingestion_audit | — |

---

## FASE 7 — Componentes rotos o no usados

| Componente | Ruta | Usado en App | Estado |
|------------|------|--------------|--------|
| RealLOBView | frontend/src/components/RealLOBView.jsx | No (no referenciado en App.jsx) | **Huérfano**. Usa getRealLobMonthly, getRealLobWeekly, getRealLobV2Data, getRealStrategyCountry, getRealStrategyLob, getRealLobFilters. |
| PlanVsRealView | frontend/src/components/PlanVsRealView.jsx | No | **Huérfano**. Usa getPlanVsRealMonthly, getPlanVsRealAlerts. |
| MonthlyView | frontend/src/components/MonthlyView.jsx | No | **Huérfano**. Usa getCoreMonthlySummary, getIngestionStatus. |
| CoreTable | frontend/src/components/CoreTable.jsx | No | **Roto**. Importa `getCore` desde api.js; **getCore no existe** en api.js (solo existe getCoreMonthlySummary). Si se abriera la vista fallaría en runtime. |
| RealLOBDailyView | frontend/src/components/RealLOBDailyView.jsx | Sí (como hijo de RealLOBDrillView, tab "Diario") | Conectado. |
| DriverSupplyGlossary | frontend/src/components/DriverSupplyGlossary.jsx | Sí (usado dentro SupplyView) | Conectado. |
| RegisterActionModal | frontend/src/components/RegisterActionModal.jsx | Usado desde Phase2BActionsTrackingView | Conectado. |

Resumen: **4 componentes** no usados o rotos: RealLOBView, PlanVsRealView, MonthlyView, **CoreTable (roto)**.

---

## FASE 8 — Validación de renderizado y columnas

Para cada vista principal se verificó en código:

- Que el componente llame al endpoint correspondiente.
- Que renderice datos (estado loading/error y tabla o cards).

No se ejecutó el front en navegador en esta auditoría; la verificación es estática.

### Columnas backend vs UI (Behavioral Alerts)

- **summary:** drivers_monitored, sudden_stop, critical_drops, moderate_drops, silent_erosion, strong_recoveries, high_volatility, stable_performer, high_risk_drivers, medium_risk_drivers. La UI muestra KPIs; sudden_stop se usa en insight. Si 090 no está aplicada, el valor `sudden_stop` puede venir de una vista que no define Sudden Stop (conteo podría ser 0 o incorrecto).
- **drivers (tabla):** driver_key, driver_name, week_start, week_label, country, city, park_id, park_name, segment_current, movement_type, trips_current_week, avg_trips_baseline, delta_abs, delta_pct, alert_type, severity, risk_score, risk_band, risk_score_*, weeks_declining_consecutively, weeks_rising_consecutively, **last_trip_date**. La UI pinta todas estas; "Último viaje" = last_trip_date. **Conectado.**
- **driver-detail:** No incluye last_trip_date en la respuesta del servicio; el modal de detalle no muestra "Último viaje" como dato del backend (sí usa semanas, delta, persistencia, etc.).

---

## FASE 9 — Reporte de estado real

### 1. Estado de Behavioral Alerts

- **Backend (servicio + endpoints):** Conectado. Summary, drivers, driver-detail, insight, export definidos y usados.
- **BD:** Migración **090 no aplicada**. La vista/MV actual en BD no tiene la lógica Sudden Stop ni la precedencia mutuamente excluyente de 090. Los conteos (p. ej. sudden_stop) pueden no coincidir con el código 090.
- **Last Trip:** Llega a la tabla principal vía JOIN con v_driver_last_trip; la UI muestra "Último viaje". No llega al detalle del conductor.
- **Frontend:** BehavioralAlertsView visible en nav; consume todos los endpoints; tabla con columnas esperadas.

### 2. Estado de Fleet Leakage

- Backend: leakage_service lee ops.v_fleet_leakage_snapshot; endpoints summary, drivers, export conectados.
- Frontend: FleetLeakageView en nav; usa getSupplyGeo, getLeakageSummary, getLeakageDrivers, getLeakageExportUrl. **Conectado de punta a punta.**

### 3. Estado de Driver Behavior

- Backend: driver_behavior_service usa ops.mv_driver_segments_weekly, ops.v_driver_last_trip, dim.v_geo_park, ops.v_dim_driver_resolved; endpoints summary, drivers, driver-detail, export.
- Frontend: DriverBehaviorView en nav; usa getSupplyGeo, getDriverBehaviorSummary, getDriverBehaviorDrivers, getDriverBehaviorDriverDetail, getDriverBehaviorExportUrl. **Conectado.**

### 4. Estado de Real LOB

- Backend: real_lob_drill_pro_service (mv_real_drill_dim_agg, v_real_data_coverage); real_drill_service (summary, by-lob, by-park); comparatives, period-semantics, daily. Todos los endpoints usados por RealLOBDrillView existen.
- Frontend: RealLOBDrillView en nav; drill + Daily; múltiples GET. **Conectado.** (Rendimiento/timeouts no validados en esta auditoría.)

### 5. Estado de Supply

- Backend: supply_service (v_geo_park, mv_supply_*, v_supply_alert_drilldown, etc.); endpoints geo, overview-enhanced, composition, migration, alerts, freshness, definitions, segments/config.
- Frontend: SupplyView en nav; 4 tabs; usa los endpoints anteriores (no usa supply/parks, supply/series, supply/summary, global/series, segments/series). **Conectado.**

### 6. Componentes rotos

- **CoreTable:** Roto (importa getCore que no existe en api.js).
- **RealLOBView, PlanVsRealView, MonthlyView:** Huérfanos (no montados en App).

### 7. Endpoints no usados por vistas visibles

- /core/summary/monthly (solo MonthlyView, huérfano).
- /ops/universe (ningún componente en App).
- /ops/territory-quality/kpis, /ops/territory-quality/unmapped-parks (sin uso en api.js).
- /ops/plan-vs-real/monthly, /ops/plan-vs-real/alerts (solo PlanVsRealView, huérfano).
- /ops/real-lob/monthly, /weekly, /monthly-v2, /weekly-v2, /filters, /v2/data (solo RealLOBView, huérfano).
- /ops/real-strategy/* (solo RealLOBView).
- /ops/supply/parks, /series, /summary, /global/series, /segments/series (SupplyView usa otros).
- /ops/driver-lifecycle/weekly, /monthly, /base-metrics (DriverLifecycleView usa otros).
- /controltower/behavior-alerts/* (alias; front usa /ops/behavior-alerts).

### 8. Vistas duplicadas o solapadas

- **Plan vs Real:** Snapshot (KPICards) y Legacy → Plan Válido (MonthlySplit + WeeklyPlanVsReal) muestran Plan vs Real con distinto nivel de detalle; no duplicadas de datos pero sí redundancia conceptual.
- **Conductores a atender:** Behavioral Alerts, Driver Behavior, Fleet Leakage, Action Engine son cuatro entradas distintas que responden a “quiénes requieren atención” con fuentes y lenguajes diferentes (ver propuesta Fase 10).

---

## FASE 10 — Propuesta de consolidación

### Consolidación conceptual sugerida: “Driver Risk Center”

Las cuatro vistas **Behavioral Alerts**, **Driver Behavior**, **Fleet Leakage** y **Action Engine** comparten el mismo tipo de pregunta de negocio: **quiénes requieren atención** (recuperación, riesgo, fuga, acciones recomendadas). Hoy están en cuatro tabs separados, con fuentes de datos distintas y nombres que se solapan (“Driver Behavior” vs “Behavioral Alerts”).

**Propuesta (solo conceptual, sin implementar):**

- Crear una única entrada de primer nivel: **“Driver Risk Center”** (o “Conductores en riesgo / Centro de riesgo”).
- Dentro, **cuatro subsecciones o tabs**:
  1. **Alertas de conducta** (actual Behavioral Alerts): desviación vs baseline, alert_type, severity, risk_band, last_trip.
  2. **Desviación por ventanas** (actual Driver Behavior): ventanas reciente/baseline, days_since_last_trip, suggested_action.
  3. **Fuga de flota** (actual Fleet Leakage): leakage_status, top_performer_at_risk.
  4. **Acciones recomendadas** (actual Action Engine): cohorts, recomendaciones, Top Driver Behavior.

Ventajas: un solo lugar para “conductores a atender”; menos tabs en la barra; naming más claro. Los backend y fuentes de datos pueden mantenerse; solo se unificaría la navegación y la presentación en una sola vista contenedora con subsecciones.

---

## Entregable final — Resumen ejecutivo

- **Mapa real del sistema:** 10 vistas de primer nivel en nav (Real LOB, Driver Lifecycle, Supply, Behavioral Alerts, Fleet Leakage, Driver Behavior, Action Engine, Snapshot, System Health, Legacy) + 6 subvistas bajo Legacy; componentes y endpoints trazados en Fase 1 y 5.
- **Estado por vista:** Behavioral Alerts, Fleet Leakage, Driver Behavior, Real LOB, Supply están conectados front–backend; Behavioral Alerts queda condicionado a que la BD tenga la lógica correcta (090 no aplicada).
- **Behavioral Alerts:** Servicio y endpoints OK; Last Trip llega a la tabla principal; **migración 090 no aplicada** → Sudden Stop y clasificación mutuamente excluyente no están activas en BD.
- **Componentes rotos:** CoreTable (getCore inexistente). **Huérfanos:** RealLOBView, PlanVsRealView, MonthlyView.
- **Endpoints huérfanos/no usados:** Listados en Fase 5 y 9.
- **Propuesta de consolidación:** Un único “Driver Risk Center” con cuatro subsecciones (Alertas de conducta, Desviación por ventanas, Fuga de flota, Acciones recomendadas).

**Acción recomendada prioritaria:** Aplicar la migración **090_behavioral_alerts_sudden_stop_mutually_exclusive** en la base de datos para alinear BD con el código y la UI de Behavioral Alerts (Sudden Stop y precedencia). No se han implementado cambios en esta auditoría.
