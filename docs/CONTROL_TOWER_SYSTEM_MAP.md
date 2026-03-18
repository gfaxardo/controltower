# CONTROL TOWER — SYSTEM MAP

Documento de mapeo completo: flujo de datos, vistas/MVs, API y UI. Base para FASE 1 (detección de problemas) y rediseño sin romper data ni lógica core.

---

## 1. DATA FLOW (RAW → TRANSFORM → AGG → API → UI)

### 1.1 RAW (fuente de viajes)

| Origen | Schema | Descripción |
|--------|--------|-------------|
| **public.trips_all** | public | Viajes históricos (< 2026). Campos clave: `id`, `park_id`, `tipo_servicio`, `fecha_inicio_viaje`, `fecha_finalizacion`, `comision_empresa_asociada`, `pago_corporativo`, `distancia_km`, `condicion`, `conductor_id`, `efectivo`, `tarjeta`, `propina`, etc. |
| **public.trips_2026** | public | Viajes desde 2026 (comercial). Misma estructura que trips_all. |
| **public.trips_unified** | public | Vista UNION de trips_all + trips_2026. Usada por Driver Lifecycle (v_driver_lifecycle_trips_completed). |
| **public.drivers** | public | Conductores: `driver_id`, `created_at`, `hire_date`, `park_id`. |
| **public.parks** | public | Parques: `id`, `name`, `city`. |
| **plan.*** | plan | Tablas de plan (ingestión CSV): plan_trips_monthly, etc. |

### 1.2 Transform (vistas intermedias)

| Vista | Fuente | Grano | Uso |
|-------|--------|-------|-----|
| **ops.v_trips_real_canon** | trips_all ∪ trips_2026 (DISTINCT ON id, prioridad 2026) | viaje | Canon real sin duplicados. |
| **ops.v_trips_real_canon_120d** | Igual con filtro fecha_inicio_viaje ≥ CURRENT_DATE - 120d | viaje | Cadena Real LOB (hourly-first) y MVs 120d. |
| **ops.v_real_trips_service_lob_resolved** / **_120d** | v_trips_real_canon + parks + LOB/canon | viaje | LOB resuelto (lob_group_resolved, segment_tag B2B/B2C). |
| **ops.v_real_trips_with_lob_v2** / **_120d** | v_real_trips_service_lob_resolved | viaje | Contrato LOB para MVs month_v2 / week_v2. |
| **ops.v_real_trip_fact_v2** | v_trips_real_canon_120d | viaje | Fact horario: trip_hour, trip_outcome_norm, cancel_reason_norm. |
| **ops.v_driver_lifecycle_trips_completed** | public.trips_unified | viaje | Solo condicion='Completado', conductor_id NOT NULL. |
| **public.trips_unified** | trips_all UNION trips_2026 | viaje | Driver Lifecycle base. |

### 1.3 Agregaciones (Materialized Views y vistas finales)

| Objeto | Grano | Dimensiones | Métricas principales |
|--------|--------|-------------|----------------------|
| **ops.mv_real_trips_monthly** (o v2) | month | park, tipo_servicio, segment (b2b/b2c) → city_norm, country, lob_base | trips_real_completed, revenue_real_yego, active_drivers_real, avg_ticket_real |
| **ops.mv_real_trips_by_lob_month** | month | country, city, lob (resuelto) | Viajes/revenue por LOB (Real LOB legacy). |
| **ops.mv_real_trips_by_lob_week** | week | idem | idem |
| **ops.mv_real_lob_month_v2** / **week_v2** | month / week | country, city, lob_group, segment | Desde v_real_trips_with_lob_v2 (120d). |
| **ops.mv_real_lob_hour_v2**, **mv_real_lob_day_v2** | hour / day | trip_hour, day, country, city, lob, segment | Operativo (hourly-first). |
| **ops.mv_real_lob_week_v3**, **mv_real_lob_month_v3** | week / month | idem | Agregación desde day. |
| **ops.real_rollup_day_fact** / **mv_real_rollup_day** | day | country, city, park, lob, segment (trip_day) | Drill: trips, margin, distance, b2b. |
| **ops.mv_real_drill_dim_agg** (o real_drill_dim_fact) | period | country, period_start, breakdown (lob \| park \| service_type), dimension_* | viajes, margen, km, b2b, segmentación driver (activo/solo_cancela). |
| **ops.mv_driver_lifecycle_base** | driver | driver_key, park, activation_ts, last_completed_ts | total_trips_completed, lifetime_days, registered_ts. |
| **ops.mv_driver_weekly_stats** | driver-week | week_start, park_id, work_mode_week (FT/PT) | trips_completed_week, segment_mode. |
| **ops.mv_driver_monthly_stats** | driver-month | month_start, park_id | idem mensual. |
| **ops.mv_driver_lifecycle_weekly_kpis** | week | park_id (opcional) | activations, churned, reactivated, active, fulltime, parttime. |
| **ops.mv_driver_lifecycle_monthly_kpis** | month | park_id (opcional) | idem mensual. |
| **ops.v_driver_weekly_churn_reactivation** | driver-week | churn_week / reactivated_week | Churn y reactivación. |
| **ops.mv_supply_weekly** / **mv_supply_monthly** | week / month | park_id, country, city | Activos, churn, reactivación, fulltime, parttime (desde driver lifecycle). |
| **ops.mv_driver_segments_weekly** | driver-week | week_start, park_id, segment_week | trips_completed_week, baseline_trips_4w_avg, segment_week. |
| **ops.mv_driver_behavior_alerts_weekly** | driver-week | week_start, park_id, alert_type, etc. | Alertas de conducta (caída, spike, sudden_stop). |
| **ops.v_driver_behavior_alerts_weekly** | vista sobre lógica de alertas | idem | Usada por Behavioral Alerts API. |
| **ops.v_fleet_leakage_snapshot** | driver (última semana) | park, segment_week, clasificación | stable_retained, watchlist, progressive_leakage, lost_driver. |
| **ops.mv_real_tipo_servicio_universe_fast** | — | tipo_servicio | Universo tipo servicio (drill). |

### 1.4 Resumen del flujo por dominio

- **Resumen (Plan vs Real)**  
  Plan: plan.* → summary_service → `/core/summary/monthly` (vía core_service).  
  Real: **public.trips_all** → **ops.mv_real_trips_monthly** (v2) → real_repo → real_normalizer → `/real/summary/monthly` y `/ops/real/monthly`.  
  UI: Resumen → KPICards (getPlanMonthlySplit, getRealMonthlySplit → `/ops/real/monthly`).

- **Real LOB (mensual/semanal legacy)**  
  trips_all/trips_2026 → v_trips_real_canon → v_real_trips_with_lob_v2 → **mv_real_trips_by_lob_month** / **mv_real_trips_by_lob_week** → real_lob_service → `/ops/real-lob/monthly`, `/ops/real-lob/weekly`.

- **Real LOB v2 (strategy)**  
  v_real_trips_with_lob_v2_120d → **mv_real_lob_month_v2** / **mv_real_lob_week_v2** → real_lob_service_v2 → `/ops/real-lob/monthly-v2`, `/ops/real-lob/weekly-v2`.

- **Real Drill (drill PRO)**  
  v_trips_real_canon_120d → cadena hourly (v_real_trip_fact_v2 → mv_real_lob_day_v2 → …) → **mv_real_rollup_day** + **real_drill_dim_fact** / **mv_real_drill_dim_agg** → real_drill_service + real_lob_drill_pro_service → `/ops/real-drill/*`, `/ops/real-lob/drill`, `/ops/real-lob/drill/children`, `/ops/real-lob/drill/parks`.

- **Real Operativo**  
  mv_real_lob_hour_v2, mv_real_lob_day_v2, etc. → real_operational_service → `/ops/real-operational/snapshot`, `day-view`, `hourly-view`, `cancellations`, comparativos.

- **Supply**  
  mv_driver_weekly_stats, mv_driver_monthly_stats, v_driver_weekly_churn_reactivation → **mv_supply_weekly** / **mv_supply_monthly** + dim.v_geo_park → supply_service → `/ops/supply/*`.

- **Driver Lifecycle**  
  trips_unified → v_driver_lifecycle_trips_completed → mv_driver_lifecycle_base → mv_driver_weekly_stats, mv_driver_monthly_stats, mv_driver_lifecycle_weekly_kpis, mv_driver_lifecycle_monthly_kpis, v_driver_weekly_churn_reactivation (+ cohortes mv_driver_cohorts_weekly, mv_driver_cohort_kpis) → driver_lifecycle_service → `/ops/driver-lifecycle/*`.

- **Behavioral Alerts**  
  ops.v_driver_behavior_alerts_weekly (o mv_driver_behavior_alerts_weekly) + v_driver_last_trip → behavior_alerts_service → `/ops/behavior-alerts/*`, `/controltower/behavior-alerts/*`.

- **Fleet Leakage**  
  ops.v_fleet_leakage_snapshot (fuente: mv_driver_segments_weekly, v_driver_last_trip, dim.v_geo_park, v_dim_driver_resolved) → leakage_service → `/ops/leakage/*`.

- **Action Engine**  
  v_action_engine_* → action_engine_service → `/ops/action-engine/*`.

---

## 2. MATERIALIZED VIEWS / VISTAS POR TAB DE UI

### Real (Operativo + Drill)

| Vista/MV | Grano | Dimensiones | Métricas |
|----------|-------|-------------|----------|
| ops.mv_real_lob_hour_v2, mv_real_lob_day_v2, week_v3, month_v3 | hour / day / week / month | trip_hour, day, country, city, lob, segment | Viajes, revenue, cancelaciones. |
| ops.mv_real_rollup_day | day | country, city, park, lob, segment | trips, margin, distance, b2b. |
| ops.mv_real_drill_dim_agg (real_drill_dim_fact) | period | country, period_start, breakdown, dimension_* | viajes, margen, km, b2b, segmentación. |
| ops.v_real_data_coverage | país | country | last_trip_date, last_month_with_data, last_week_with_data. |
| ops.v_real_drill_country_month/week, v_real_drill_lob_*, v_real_drill_park_* | period | country, period_start, lob, park | estado, trips, margin, b2b (drill legacy). |

### Real LOB (legacy LOB mensual/semanal)

| Vista/MV | Grano | Dimensiones | Métricas |
|----------|-------|-------------|----------|
| ops.mv_real_trips_by_lob_month, mv_real_trips_by_lob_week | month / week | country, city, lob | Viajes, revenue (real_lob_service). |
| ops.mv_real_lob_month_v2, mv_real_lob_week_v2 | month / week | country, city, lob_group, segment | Idem v2 (120d). |

### Supply

| Vista/MV | Grano | Dimensiones | Métricas |
|----------|-------|-------------|----------|
| ops.mv_supply_weekly, ops.mv_supply_monthly | week / month | park_id, country, city | Activos, churn, reactivación, FT/PT. |
| dim.v_geo_park, ops.v_dim_park_resolved | — | park_id, park_name, city, country | Geo para filtros. |
| ops.mv_supply_segments_weekly, mv_supply_alerts_weekly, v_supply_alert_drilldown | week | park, segment | Alertas supply. |

### Driver Lifecycle

| Vista/MV | Grano | Dimensiones | Métricas |
|----------|-------|-------------|----------|
| ops.mv_driver_lifecycle_base | driver | driver_key, park | activation_ts, last_completed_ts, total_trips_completed. |
| ops.mv_driver_weekly_stats, mv_driver_monthly_stats | driver-week / driver-month | week_start/month_start, park_id | trips_completed_week, work_mode_week. |
| ops.mv_driver_lifecycle_weekly_kpis, mv_driver_lifecycle_monthly_kpis | week / month | park_id | activations, churned, reactivated, active, fulltime, parttime. |
| ops.v_driver_weekly_churn_reactivation | driver-week | week_start, park_id | churn_week, reactivated_week. |
| ops.mv_driver_cohorts_weekly, mv_driver_cohort_kpis | week / cohort | park_id | Cohortes. |

### Behavioral Alerts

| Vista/MV | Grano | Dimensiones | Métricas |
|----------|-------|-------------|----------|
| ops.v_driver_behavior_alerts_weekly, ops.mv_driver_behavior_alerts_weekly | driver-week | week_start, park_id, alert_type, severity, risk_band | risk_score, delta_pct, trips_current_week, avg_trips_baseline. |
| ops.v_driver_last_trip | driver | driver_key | last_trip_date. |

### Fleet Leakage

| Vista/MV | Grano | Dimensiones | Métricas |
|----------|-------|-------------|----------|
| ops.v_fleet_leakage_snapshot | driver (ref_week) | park_id, segment_week, clasificación | stable_retained, watchlist, progressive_leakage, lost_driver, days_since_last_trip. |
| ops.mv_driver_segments_weekly | driver-week | week_start, park_id | trips_completed_week, baseline_trips_4w_avg, segment_week. |

### Plan y validación

| Vista/MV | Grano | Dimensiones | Métricas |
|----------|-------|-------------|----------|
| ops.v_plan_trips_monthly_latest, plan.* | month | country, city, lob | projected_trips, projected_revenue, projected_drivers. |
| Varias vistas plan-vs-real, alerts 2b, accountability | week / month | territorio, LOB | Plan vs Real, alertas, accountability. |

---

## 3. API — ENDPOINTS POR TAB

### Resumen

| Endpoint | Método | Servicio | Tab UI |
|----------|--------|----------|--------|
| /core/summary/monthly | GET | core_service.get_core_monthly_summary | Resumen (Plan+Real combinado) |
| /real/summary/monthly | GET | real_normalizer.get_real_monthly_summary | Resumen (Real solo) |
| /plan/summary/monthly | GET | summary_service.get_plan_monthly_summary | Resumen (Plan solo) |
| /ops/real/monthly | GET | plan_real_split_service.get_real_monthly | Resumen KPICards (split por país) |
| /ops/plan/monthly | GET | plan_real_split_service.get_plan_monthly | Resumen KPICards |
| /ops/compare/overlap-monthly | GET | plan_real_split_service.get_overlap_monthly | Resumen |
| /ops/plan-vs-real/monthly | GET | plan_vs_real_service | Plan y validación |
| /ops/plan-vs-real/alerts | GET | plan_vs_real_service | Plan y validación |

### Real (Operativo + Drill)

| Endpoint | Método | Servicio | Tab UI |
|----------|--------|----------|--------|
| /ops/real-operational/snapshot | GET | real_operational_service | Real → Operativo |
| /ops/real-operational/day-view | GET | real_operational_service | Real → Operativo |
| /ops/real-operational/hourly-view | GET | real_operational_service | Real → Operativo |
| /ops/real-operational/cancellations | GET | real_operational_service | Real → Operativo |
| /ops/real-operational/comparatives/* | GET | real_operational_comparatives_service | Real → Operativo |
| /ops/real-lob/drill | GET | real_lob_drill_pro_service.get_drill | Real → Drill |
| /ops/real-lob/drill/children | GET | real_lob_drill_pro_service.get_drill_children | Real → Drill |
| /ops/real-lob/drill/parks | GET | real_lob_drill_pro_service.get_drill_parks | Real → Drill |
| /ops/real-drill/summary | GET | real_drill_service | Real → Drill (legacy) |
| /ops/real-drill/by-lob | GET | real_drill_service | Real → Drill |
| /ops/real-drill/by-park | GET | real_drill_service | Real → Drill |
| /ops/real-drill/coverage | GET | real_drill_service | Real → Drill |
| /ops/real-drill/totals | GET | real_drill_service | Real → Drill |
| POST /ops/real-drill/refresh | POST | real_drill_service.refresh_real_drill_mv | Admin |
| /ops/real-lob/monthly, /weekly | GET | real_lob_service | Real LOB legacy |
| /ops/real-lob/monthly-v2, /weekly-v2 | GET | real_lob_service_v2 | Real LOB v2 |
| /ops/real-lob/filters | GET | real_lob_filters_service | Real |
| /ops/real-lob/v2/data | GET | real_lob_v2_data_service | Real |
| /ops/real-lob/daily/* | GET | real_lob_daily_service | Real (diario) |
| /ops/real-strategy/country, /lob, /cities | GET | real_strategy_service | Real strategy |
| /ops/real-lob/comparatives/weekly | GET | comparative_metrics_service | Real |
| /ops/real-lob/comparatives/monthly | GET | comparative_metrics_service | Real |

### Supply

| Endpoint | Método | Servicio | Tab UI |
|----------|--------|----------|--------|
| /ops/supply/geo | GET | supply_service.get_supply_geo | Supply |
| /ops/supply/parks | GET | supply_service.get_supply_parks | Supply |
| /ops/supply/series | GET | supply_service.get_supply_series | Supply |
| /ops/supply/segments/series | GET | supply_service.get_supply_segments_series | Supply |
| /ops/supply/summary | GET | supply_service.get_supply_summary | Supply |
| /ops/supply/global/series | GET | supply_service.get_supply_global_series | Supply |
| /ops/supply/alerts | GET | supply_service.get_supply_alerts | Supply |
| /ops/supply/alerts/drilldown | GET | supply_service.get_supply_alert_drilldown | Supply |
| /ops/supply/overview-enhanced | GET | supply_service.get_supply_overview_enhanced | Supply |
| /ops/supply/composition | GET | supply_service.get_supply_composition | Supply |
| /ops/supply/migration | GET | supply_service.get_supply_migration | Supply |
| /ops/supply/migration/drilldown | GET | supply_service.get_supply_migration_drilldown | Supply |
| /ops/supply/migration/weekly-summary | GET | supply_service.get_supply_migration_weekly_summary | Supply |
| /ops/supply/migration/critical | GET | supply_service.get_supply_migration_critical | Supply |
| /ops/supply/definitions | GET | supply_definitions.get_definitions | Supply |
| /ops/supply/freshness | GET | supply_service.get_supply_freshness | Supply |
| POST /ops/supply/refresh | POST | supply_service.refresh_supply_alerting_mvs | Admin |

### Conductores en riesgo (Driver Risk)

| Endpoint | Método | Servicio | Tab UI |
|----------|--------|----------|--------|
| /ops/behavior-alerts/summary | GET | behavior_alerts_service | Conductores en riesgo → Alertas de conducta |
| /ops/behavior-alerts/insight | GET | behavior_alerts_service | Idem |
| /ops/behavior-alerts/drivers | GET | behavior_alerts_service | Idem |
| /ops/behavior-alerts/driver-detail | GET | behavior_alerts_service | Idem |
| /ops/behavior-alerts/export | GET | behavior_alerts_service | Idem |
| /controltower/behavior-alerts/* | GET | (delega a behavior_alerts_service) | Idem (alias) |
| /ops/leakage/summary | GET | leakage_service | Conductores en riesgo → Fuga de flota |
| /ops/leakage/drivers | GET | leakage_service | Idem |
| /ops/leakage/export | GET | leakage_service | Idem |
| /ops/driver-behavior/summary | GET | driver_behavior_service | Conductores en riesgo → Desviación por ventanas |
| /ops/driver-behavior/drivers | GET | driver_behavior_service | Idem |
| /ops/driver-behavior/driver-detail | GET | driver_behavior_service | Idem |
| /ops/driver-behavior/export | GET | driver_behavior_service | Idem |
| /ops/action-engine/summary | GET | action_engine_service | Conductores en riesgo → Acciones recomendadas |
| /ops/action-engine/cohorts | GET | action_engine_service | Idem |
| /ops/action-engine/cohort-detail | GET | action_engine_service | Idem |
| /ops/action-engine/recommendations | GET | action_engine_service | Idem |
| /ops/action-engine/export | GET | action_engine_service | Idem |
| /ops/top-driver-behavior/* | GET | top_driver_behavior_service | Idem (benchmarks, patterns, playbook) |

### Ciclo de vida

| Endpoint | Método | Servicio | Tab UI |
|----------|--------|----------|--------|
| /ops/driver-lifecycle/weekly, /weekly-kpis | GET | driver_lifecycle_service | Ciclo de vida |
| /ops/driver-lifecycle/monthly, /monthly-kpis | GET | driver_lifecycle_service | Ciclo de vida |
| /ops/driver-lifecycle/drilldown, /kpi-drilldown | GET | driver_lifecycle_service | Ciclo de vida |
| /ops/driver-lifecycle/parks-summary | GET | driver_lifecycle_service | Ciclo de vida |
| /ops/driver-lifecycle/series | GET | driver_lifecycle_service | Ciclo de vida |
| /ops/driver-lifecycle/summary | GET | driver_lifecycle_service | Ciclo de vida |
| /ops/driver-lifecycle/cohorts | GET | driver_lifecycle_service | Ciclo de vida |
| /ops/driver-lifecycle/cohort-drilldown | GET | driver_lifecycle_service | Ciclo de vida |
| /ops/driver-lifecycle/base-metrics | GET | driver_lifecycle_service | Ciclo de vida |
| /ops/driver-lifecycle/parks-for-selector | GET | driver_lifecycle_service | Ciclo de vida |
| /ops/driver-lifecycle/pro-churn-segments | GET | driver_lifecycle_service | Ciclo de vida |
| /ops/driver-lifecycle/pro-park-shock-list | GET | driver_lifecycle_service | Ciclo de vida |
| /ops/driver-lifecycle/pro-behavior-shifts | GET | driver_lifecycle_service | Ciclo de vida |
| /ops/driver-lifecycle/pro-drivers-at-risk | GET | driver_lifecycle_service | Ciclo de vida |

### Plan y validación

| Endpoint | Método | Servicio | Tab UI |
|----------|--------|----------|--------|
| /ops/universe | GET | ops_universe_service | Plan, filtros |
| /ops/territory-quality/kpis | GET | territory_quality_service | Plan y validación |
| /ops/territory-quality/unmapped-parks | GET | territory_quality_service | Plan y validación |
| /ops/parks | GET | ops (parks list) | Filtros |
| Plan upload, valid, out_of_universe, missing | GET/POST | plan router, phase2b, phase2c | Plan y validación (PlanTabs, Phase2B, Phase2C, LobUniverse, Real vs Proyección) |
| /ops/real-vs-projection/* | GET | real_vs_projection (router) | Real vs Proyección |

### Diagnósticos / System Health

| Endpoint | Método | Servicio | Tab UI |
|----------|--------|----------|--------|
| /ops/data-freshness | GET | data_freshness_service | System Health |
| /ops/data-freshness/alerts | GET | data_freshness_service | System Health |
| /ops/data-freshness/expectations | GET | data_freshness_service | System Health |
| /ops/data-freshness/global | GET | data_freshness_service | System Health |
| /ops/real-margin-quality, /ops/real/margin-quality | GET | real_margin_quality_service | System Health / Real |
| POST /ops/real/margin-quality/run | POST | real_margin_quality_service | Admin |
| /ops/data-pipeline-health | GET | — | System Health |
| /ops/integrity-report | GET | data_integrity_service | System Health |
| /ops/system-health | GET | data_integrity_service.get_system_health | System Health |
| POST /ops/integrity-audit/run | POST | data_integrity_service | System Health |
| POST /ops/data-freshness/run | POST | data_freshness_service | System Health |
| POST /ops/pipeline-refresh | POST | — | Admin |

---

## 4. UI — TABS, SUB-VISTAS, KPIs Y FILTROS

### 4.1 Navegación principal

| Tab ID | Label | Contenido |
|--------|-------|-----------|
| resumen | Resumen | Plan vs Real en KPIs (viajes, conductores, revenue). ExecutiveSnapshotView → KPICards. |
| real | Real | Sub-tabs: Operativo (RealOperationalView) \| Drill y diario (RealLOBDrillView). RealMarginQualityCard cuando tab Real activo. |
| supply | Supply | SupplyView: overview, composición, migración, alertas. |
| driver_risk | Conductores en riesgo | Sub-tabs: Alertas de conducta, Desviación por ventanas, Fuga de flota, Acciones recomendadas. |
| driver_lifecycle | Ciclo de vida | DriverLifecycleView: evolución parque y cohortes por park. |
| plan_validation | Plan y validación | Sub-tabs: Plan Válido, Expansión, Huecos, Fase 2B, Fase 2C, Universo & LOB, Real vs Proyección. |
| system_health | System Health (Diagnósticos ▾) | SystemHealthView: integridad, freshness, ingestión. |

### 4.2 Sub-tabs y componentes

- **Real**  
  - Operativo: RealOperationalView (hoy, ayer, esta semana; por día; por hora; cancelaciones; comparativos).  
  - Drill y diario: RealLOBDrillView (drill por país, periodo, LOB, park).

- **Conductores en riesgo**  
  - behavioral_alerts → BehavioralAlertsView.  
  - driver_behavior → DriverBehaviorView.  
  - fleet_leakage → FleetLeakageView.  
  - action_engine → ActionEngineView.

- **Plan y validación**  
  - valid → MonthlySplitView + WeeklyPlanVsRealView.  
  - actions → Phase2BActionsTrackingView.  
  - accountability → Phase2CAccountabilityView.  
  - lob_universe → LobUniverseView.  
  - real_vs_projection → RealVsProjectionView.  
  - out_of_universe, missing → PlanTabs.

### 4.3 Filtros globales (CollapsibleFilters)

- country, city, line_of_business, year_real (ej. 2025), year_plan (ej. 2026).  
- Usados por Resumen, Plan y validación y por APIs que aceptan country/city/lob/year.

### 4.4 KPIs por vista (resumen)

- **Resumen**: trips Real/Plan YTD, drivers Real/Plan YTD, revenue Real/Plan YTD (global y por país PE/CO).  
- **Real Operativo**: snapshot (hoy), día, hora, cancelaciones, comparativos (hoy vs ayer, misma semana, hora actual vs histórico, semana vs comparable).  
- **Real Drill**: países con cobertura, KPIs por periodo (viajes, margen, km, b2b), desglose LOB/park/service_type, estado (CERRADO/ABIERTO/FALTA_DATA/VACIO).  
- **Supply**: overview (activos, churn, reactivación), composición, migración, alertas, definiciones.  
- **Conductores en riesgo**: resúmenes por alerta/leakage/behavior/action-engine; listas de conductores; detalle por conductor; export.  
- **Ciclo de vida**: KPIs semanales/mensuales (activations, churned, reactivated, active, fulltime, parttime), drilldown por park, series, cohortes.  
- **Plan y validación**: tablas Plan vs Real, alertas, acciones 2B, accountability 2C, universo LOB, Real vs Proyección.

### 4.5 Elementos transversales

- **GlobalFreshnessBanner**: según activeTab (muestra estado de freshness cuando aplica).  
- **RealMarginQualityCard**: solo cuando tab Real activo.  
- **ADMIN**: modal UploadPlan (subir plan).  
- **Diagnósticos**: dropdown con enlace a System Health.

---

## 5. NOTAS PARA FASE 1 (DETECCIÓN DE PROBLEMAS)

- **Duplicidad de métricas**: Real aparece en Resumen (mv_real_trips_monthly), Real LOB (mv_real_trips_by_lob_* / mv_real_lob_*_v2), Real Drill (mv_real_rollup_day, mv_real_drill_dim_agg) y Real Operativo (hour_v2, day_v2, …). Múltiples fuentes de “viajes” y “revenue” según ventana y grano.  
- **Dos cadenas Real**: (1) mv_real_trips_monthly desde trips_all (sin 2026 en misma MV); (2) cadena 120d (v_trips_real_canon_120d → mv_real_rollup_day, mv_real_drill_dim_agg, hourly-first). Coherencia y semántica de “último dato” a unificar en presentación.  
- **Segmentación driver (activo vs solo cancelan)**: en mv_real_drill_dim_agg/real_drill_dim_fact; batch en ejecución — no tocar; en UI conviene dejar claro “en proceso” vs “poblado”.  
- **Tabs redundantes o confusos**: “Drill y diario (avanzado)” vs “Operativo”; “Conductores en riesgo” con 4 sub-tabs (alerts, behavior, leakage, action engine) sin un hilo único claro.  
- **Semanas**: distintas definiciones (lunes como week_start en lifecycle/supply vs calendario en drill). Tooltips y etiquetas deben aclarar “semana operativa (lunes-domingo)”.  
- **Features desconectadas**: Behavioral Alerts, Fleet Leakage y segmentación Real viven en tabs/sub-tabs separados; se pueden integrar en flujos PERFORMANCE / DRIVERS / RISK sin cambiar datos.  
- **Cobertura y estados de data**: v_real_data_coverage y estados (CERRADO/ABIERTO/FALTA_DATA/VACIO) ya existen; en UI falta diferenciar claramente “poblado” vs “en proceso” vs “faltante” (FASE 5).

---

## 6. CRITERIOS DE ÉXITO (recordatorio)

- Sistema más simple y legible.  
- Menos pestañas o agrupación más clara (4 bloques: PERFORMANCE, DRIVERS, RISK, OPERACIÓN).  
- Mejor lectura ejecutiva (KPIs arriba, colores verde/amarillo/rojo, tooltips).  
- Sin romper nada existente ni batch de segmentación en curso.  
- Compatible con batch en curso: diferenciación visual de estados de data (poblado / en proceso / faltante).

Este documento es la base para FASE 1 (detección de problemas), FASE 2 (rediseño conceptual) y mejoras de UI/UX (FASE 3–5) sin tocar RAW, lógica core ni crear MVs nuevas sin justificación.
