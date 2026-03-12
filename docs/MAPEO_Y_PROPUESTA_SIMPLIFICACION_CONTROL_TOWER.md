# YEGO Control Tower — Mapeo integral y propuesta de simplificación cognitiva

**Objetivo:** Radiografía real del sistema (frontend + backend + datos) y propuesta estratégica de navegación, naming y simplificación. Sin implementación en esta etapa.

---

## 1. Resumen ejecutivo del estado actual

- **Navegación:** Una barra de tabs horizontal con **10 tabs de primer nivel** siempre visibles (Real LOB, Driver Lifecycle, Driver Supply Dynamics, Behavioral Alerts, Fleet Leakage, Driver Behavior, Action Engine, Snapshot, System Health, Legacy). Con `VITE_CT_LEGACY_ENABLED=true` se añaden **6 tabs más** (Plan Válido, Expansión, Huecos, Fase 2B, Fase 2C, Universo & LOB), lo que puede llegar a **16 ítems** en la barra.
- **Vistas realmente usadas desde App:** 10 componentes como vistas principales; bajo "Legacy" hay **6 subvistas** (Plan Válido = MonthlySplit + WeeklyPlanVsReal; Expansión/Huecos = PlanTabs; Fase 2B, Fase 2C, Universo & LOB = componentes propios). Una vista (Real LOB) incluye **subvista Daily** (RealLOBDailyView) como pestaña interna.
- **Componentes no conectados a la navegación actual:** RealLOBView, PlanVsRealView, MonthlyView, CoreTable (este último importa `getCore` que **no existe** en api.js → componente roto).
- **Filtros globales:** Un panel colapsable (CollapsibleFilters → Filters) con: País, Ciudad, Línea de negocio, Año Real, Año Plan. Solo **Snapshot (KPICards)** y las vistas bajo Legacy consumen explícitamente estos filtros; el resto de vistas usan filtros **locales** (country/city/park/from/to, etc.) no sincronizados con el panel global.
- **Backend:** Múltiples routers (plan, real, core, ops, phase2b, phase2c, health, ingestion, driver_lifecycle, controltower). La mayoría de la lógica operativa está en **ops** (real-lob, supply, behavior-alerts, leakage, action-engine, driver-behavior, top-driver-behavior, data-freshness, system-health, real-drill, real-strategy, etc.) con timeouts largos en varios endpoints (drill 6 min, behavior 5 min).
- **Fuentes de datos:** Múltiples MVs y vistas en schema `ops` (y algunos en `dim`, `plan`). Hay solapamiento conceptual entre Behavioral Alerts, Driver Behavior, Action Engine y Fleet Leakage (todos conducen a “conductores a atender” con lenguajes y fuentes distintas).

---

## 2. Mapa completo de vistas y componentes (FASE 1)

### 2.1 Tabla: vista → componente → navegación → propósito → relevancia → observaciones

| Nombre visible en UI | Componente real | ¿En nav. principal? | Propósito aparente | Uso/relevancia estimado | Redundancia/solape |
|----------------------|----------------|----------------------|--------------------|-------------------------|---------------------|
| Real LOB | RealLOBDrillView | Sí | Drill-down real por país/periodo, LOB/Park/tipo servicio; comparativos WoW/MoM; subvista Daily | Alta – vista principal de negocio real | Incluye RealLOBDailyView como tab "Diario". No usa filtros globales App. |
| Driver Lifecycle | DriverLifecycleView | Sí | Ciclo de vida por park: KPIs, series, cohortes, drilldown por conductor | Alta | Obligatorio elegir park. Muchas llamadas (summary, series, parks-summary, cohorts, drilldowns). |
| Driver Supply Dynamics | SupplyView | Sí | Supply por park: Overview, Composition, Migration, Alerts; drilldowns | Alta | 4 tabs internas. Park obligatorio. Comparte getSupplyGeo con varias vistas. |
| Behavioral Alerts | BehavioralAlertsView | Sí | Alertas de desviación vs baseline; insight; lista conductores; detalle; export | Alta | Muchos filtros (from/to, segment, movement_type, alert_type, severity, risk_band). Solapa con Driver Behavior y Action Engine. |
| Fleet Leakage | FleetLeakageView | Sí | Fuga de flota: KPIs, filtros (status, top performers), tabla conductores, export | Alta | Fuente propia (v_fleet_leakage_snapshot). Solapa en “quiénes requieren atención”. |
| Driver Behavior | DriverBehaviorView | Sí | Desviación por ventanas reciente/baseline; días sin viaje; tabla y detalle conductor | Alta | Fuente: mv_driver_segments_weekly + v_driver_last_trip. Solapa con Behavioral Alerts. |
| Action Engine | ActionEngineView | Sí | Cohorts + recomendaciones; Top Driver Behavior (benchmarks, patterns, playbook); export | Media-Alta | Usa action_engine + top_driver_behavior. Varias subsecciones. Solapa con Behavioral Alerts / Driver Behavior. |
| Snapshot | ExecutiveSnapshotView | Sí | Plan vs Real: KPIs (viajes, conductores, revenue) por año; compact | Media | Solo envuelve KPICards. Sí usa filtros globales (country, year_real, year_plan). |
| System Health | SystemHealthView | Sí | Integridad, freshness MVs, ingestión; botón ejecutar auditoría | Técnica | Para diagnóstico/confianza, no operación diaria. |
| Legacy | (contenedor) | Sí | Agrupa 6 subvistas en tabs internas (si Legacy cerrado) o como tabs extra (si LEGACY_ENABLED) | Mixta | Ver filas siguientes. |
| Plan Válido | MonthlySplitView + WeeklyPlanVsRealView | Dentro Legacy / o tab directa | Plan y Real mensual; Plan vs Real semanal; overlap | Media (planificación) | Solo con filtros globales. |
| Expansión | PlanTabs (activeTab=out_of_universe) | Dentro Legacy / o tab directa | Filas del plan fuera de universo operativo | Media (validación plan) | PlanTabs muestra una tabla u otra según tab. |
| Huecos | PlanTabs (activeTab=missing) | Dentro Legacy / o tab directa | Combinaciones esperadas en plan que faltan | Media (validación plan) | Mismo componente, otra tab. |
| Fase 2B | Phase2BActionsTrackingView | Dentro Legacy / o tab directa | Acciones semanales; crear/actualizar acciones | Media (operativo) | Lista acciones, no comparte UI con otras. |
| Fase 2C | Phase2CAccountabilityView | Dentro Legacy / o tab directa | Scoreboard, backlog, breaches, run snapshot | Media (accountability) | Scoreboard/backlog/breaches. |
| Universo & LOB | LobUniverseView | Dentro Legacy / o tab directa | Universo LOB; viajes sin match plan | Media (técnico/validación) | Tabla coverage + unmatched. |
| — | RealLOBView | No | Observabilidad Real LOB (tabla/KPIs) y modo ejecutivo (strategy) | No usado en navegación | Componente completo no referenciado en App.jsx. |
| — | PlanVsRealView | No | Plan vs Real mensual + alertas | No usado | Sustituido por Snapshot + Legacy Plan Válido. |
| — | MonthlyView | No | Resumen mensual core + ingestion status | No usado | Core monthly + ingestion. |
| — | CoreTable | No | Tabla "core" con getCore(filters) | Roto | api.js no exporta getCore → fallo si se abriera. |

### 2.2 Layout y patrones de UI

- **Layout:** Container único, header con título "YEGO Control Tower" y botón ADMIN (modal UploadPlan), GlobalFreshnessBanner, CollapsibleFilters, barra de tabs, contenido según `activeTab`.
- **Patrones repetidos:**  
  - KPIs/cards: Snapshot (KPICards), Driver Lifecycle, Supply (Overview), Behavioral Alerts, Fleet Leakage, Driver Behavior, Action Engine, System Health.  
  - Filtros: casi todas las vistas tienen country/city/park (muchas vía getSupplyGeo) + from/to o period.  
  - Tablas con paginación/ordenación: Behavioral Alerts, Fleet Leakage, Driver Behavior, Action Engine, PlanTabs, LobUniverse, Phase2B, Phase2C.  
  - Export CSV/Excel: Behavioral Alerts, Fleet Leakage, Driver Behavior, Action Engine (y Top Driver Behavior).  
  - Drilldown / detalle conductor: Behavioral Alerts, Driver Behavior, Action Engine (cohort detail).  
  - Tabs internas: Real LOB (Drill | Diario), Supply (Overview | Composition | Migration | Alerts), Legacy (6 subvistas), Action Engine (cohorts + Top Driver Behavior).  
  - Modales: ADMIN (UploadPlan), detalle conductor, crear/editar acción Fase 2B.  
  - Tooltips: Behavioral Alerts (COLUMN_TOOLTIPS), Supply (glosario), otros puntuales.

---

## 3. Mapa de endpoints y fuentes de datos por vista (FASE 3)

Resumen trazable: vista → endpoints → servicios → fuentes SQL/MV/vistas.

| Vista (componente) | Endpoints principales | Servicios backend | Fuentes de datos (tablas/MVs/vistas) |
|--------------------|------------------------|-------------------|--------------------------------------|
| Real LOB (RealLOBDrillView) | GET /ops/real-lob/drill, /drill/children, /drill/parks, /period-semantics, /real-lob/comparatives/weekly|monthly, /real-drill/summary, /by-lob, /by-park | real_lob_drill_pro_service, real_drill_service, period_semantics_service, comparative_metrics_service | ops.mv_real_drill_dim_agg, ops.v_real_data_coverage, ops.mv_real_drill_service_by_park; real_drill: múltiples |
| Real LOB Daily (dentro Drill) | /ops/real-lob/daily/summary, /daily/comparative, /daily/table, /period-semantics | real_lob_daily_service | (consultar MVs/datos diarios ops) |
| Driver Lifecycle | /ops/driver-lifecycle/parks, /summary, /series, /parks-summary, /cohorts, /base-metrics-drilldown, /cohort-drilldown, /drilldown | driver_lifecycle_service | ops.mv_driver_lifecycle_base, ops.mv_driver_weekly_stats, ops.mv_driver_monthly_stats, ops.mv_driver_lifecycle_weekly_kpis, ops.v_driver_weekly_churn_reactivation, ops.v_dim_park_resolved, dim.dim_park |
| Driver Supply Dynamics | /ops/supply/geo, /overview-enhanced, /composition, /migration, /migration/drilldown, /alerts, /alerts/drilldown, /freshness, /definitions, /segments/config | supply_service | dim.v_geo_park, ops.v_dim_park_resolved, ops.mv_supply_weekly, ops.mv_supply_monthly, ops.mv_supply_segments_weekly, ops.mv_supply_alerts_weekly, ops.v_supply_alert_drilldown, ops.driver_segment_config |
| Behavioral Alerts | /ops/behavior-alerts/summary, /insight, /drivers, /driver-detail, /export | behavior_alerts_service | ops.v_driver_behavior_alerts_weekly (o mv), ops.v_driver_last_trip |
| Fleet Leakage | /ops/leakage/summary, /drivers, /export; /ops/supply/geo | leakage_service, supply (geo) | ops.v_fleet_leakage_snapshot |
| Driver Behavior | /ops/driver-behavior/summary, /drivers, /driver-detail, /export; /ops/supply/geo | driver_behavior_service | ops.mv_driver_segments_weekly, ops.v_driver_last_trip, dim.v_geo_park, ops.v_dim_driver_resolved |
| Action Engine | /ops/action-engine/summary, /cohorts, /cohort-detail, /recommendations, /export; /ops/top-driver-behavior/*; /ops/supply/geo | action_engine_service, top_driver_behavior_service | ops.v_action_engine_driver_base, ops.v_action_engine_cohorts_weekly, ops.v_action_engine_recommendations_weekly; top_driver_behavior (propias) |
| Snapshot | /ops/real/monthly, /ops/plan/monthly (vía getRealMonthlySplit, getPlanMonthlySplit) | plan_real_split_service | ops.mv_real_trips_monthly, ops.v_plan_trips_monthly_latest |
| System Health | /ops/system-health, /data-pipeline-health, POST /ops/integrity-audit/run | data_integrity_service, data_freshness_service | ops.v_control_tower_integrity_report, ops.data_integrity_audit, ops.v_mv_freshness, ops.v_ingestion_audit |
| Legacy – Plan Válido | /ops/real/monthly, /ops/plan/monthly, /ops/compare/overlap-monthly; /phase2b/weekly/plan-vs-real, /phase2b/weekly/alerts | plan_real_split_service, phase2b_weekly_service | ops.mv_real_trips_monthly, ops.v_plan_trips_monthly_latest |
| Legacy – Expansión / Huecos | /plan/out_of_universe, /plan/missing | plan (router) + adapters | plan.* (valid/out_of_universe/missing), universo ops |
| Legacy – Fase 2B | /phase2b/actions (GET/PATCH/POST), /phase2b/weekly/* | phase2b_actions_service, phase2b_weekly_service | (tablas phase2b / ops) |
| Legacy – Fase 2C | /phase2c/scoreboard, /backlog, /breaches, /run-snapshot, /lob-universe, /lob-universe/unmatched | phase2c_accountability_service, lob_universe_service | ops.v_phase2c_weekly_scoreboard, ops.v_phase2c_backlog_by_owner, ops.v_phase2c_sla_breaches; ops.v_plan_vs_real_lob_check / v_lob_universe_check, v_real_without_plan_lob |
| GlobalFreshnessBanner | /ops/data-freshness/global, /data-pipeline-health | data_freshness_service | ops.data_freshness_audit, expectations |

**Observaciones de fragilidad/complejidad:**

- **Real LOB drill:** Timeout 6 min; consultas pesadas sobre mv_real_drill_dim_agg; riesgo 500 si MV desactualizada o volumen alto.
- **Behavioral Alerts / Driver Behavior:** Timeouts 5 min; vistas/MVs sobre datos conductor; muchos filtros combinables pueden disparar consultas lentas.
- **Supply:** Múltiples MVs (weekly, monthly, segments, alerts); refresh_supply_alerting_mvs puede ser costoso.
- **Snapshot/KPICards:** Con filtro "All" hace **6** llamadas en paralelo (plan/real global + PE + CO); duplicación de lógica con Legacy Plan Válido.
- **CoreTable:** Roto (getCore no existe en api.js).

---

## 4. Matriz funcional por vista (FASE 2)

| Vista | Pregunta que responde | Capa funcional | Unidad de análisis | Decisión que habilita | Principal / Secundaria / Técnica |
|-------|------------------------|----------------|--------------------|------------------------|----------------------------------|
| Real LOB | ¿Cómo va el real por país/periodo/LOB/park? | Descriptiva / diagnóstica | país, periodo, LOB, park, tipo servicio | Ajustar foco por canal/territorio | Principal |
| Driver Lifecycle | ¿Cómo evoluciona el parque y los cohortes por park? | Descriptiva / diagnóstica | park, semana/mes, conductor | Priorizar parques y retención | Principal |
| Driver Supply Dynamics | ¿Cómo está la supply por park (overview, composición, migración, alertas)? | Descriptiva / diagnóstica | park, semana | Actuar sobre migraciones y alertas supply | Principal |
| Behavioral Alerts | ¿Qué conductores se desvían de su baseline y con qué severidad? | Conductual / operativa | conductor, semana, park, segmento | Lista de recuperación y priorización | Principal |
| Fleet Leakage | ¿Quiénes están en fuga o en riesgo de fuga (estable/watchlist/progresiva/perdido)? | Conductual / operativa | conductor, park, status | Recuperación y retención de flota | Principal |
| Driver Behavior | ¿Qué conductores tienen desviación reciente vs baseline y días sin viaje? | Conductual / diagnóstica | conductor, ventanas tiempo, park | Atención por inactividad/desviación | Principal |
| Action Engine | ¿Qué cohortes y recomendaciones hay? ¿Qué patrones/playbook para top drivers? | Operativa / analítica | cohorte, semana, conductor | Acciones recomendadas y prioridad | Principal (operativa) |
| Snapshot | ¿Cómo va Plan vs Real en agregado (viajes, conductores, revenue)? | Descriptiva | país, año | Visión ejecutiva rápida | Principal (entrada) |
| System Health | ¿El sistema y los datos están sanos? | Técnica / auditoría | dataset, MV, check | Confianza y debugging | Técnica |
| Legacy – Plan Válido | ¿Desglose Plan y Real mensual/semanal y overlap? | Descriptiva / validación | mes, semana, país, LOB | Validar plan y real | Secundaria / análisis |
| Legacy – Expansión | ¿Qué filas del plan están fuera de universo? | Validación plan | combinación país/ciudad/LOB | Ajustar universo o plan | Secundaria |
| Legacy – Huecos | ¿Qué combinaciones esperadas faltan en el plan? | Validación plan | combinación | Completar plan | Secundaria |
| Legacy – Fase 2B | ¿Qué acciones semanales hay y su estado? | Operativa | acción, semana | Seguimiento de acciones | Secundaria / operativa |
| Legacy – Fase 2C | ¿Scoreboard, backlog y breaches de accountability? | Operativa / auditoría | owner, semana | Accountability y SLA | Secundaria |
| Universo & LOB | ¿Cobertura LOB y viajes sin match? | Técnica / validación | LOB, ubicación | Calidad de mapeo plan-real | Técnica / análisis |

---

## 5. Redundancias y solapes detectados (FASE 4)

### 5.1 Solapos funcionales

- **“Conductores a atender” en cuatro sitios:**  
  - **Behavioral Alerts:** alertas por desviación vs baseline (v_driver_behavior_alerts_weekly).  
  - **Driver Behavior:** desviación por ventanas + days_since_last_trip (mv_driver_segments_weekly).  
  - **Fleet Leakage:** status de fuga (v_fleet_leakage_snapshot).  
  - **Action Engine:** cohorts y recomendaciones (v_action_engine_*).  
  El usuario puede no saber **cuál usar primero** ni si son complementarios o redundantes.

- **Plan vs Real en dos entradas:**  
  - **Snapshot (KPICards):** Plan vs Real agregado (viajes, conductores, revenue) con filtros globales.  
  - **Legacy → Plan Válido:** MonthlySplitView + WeeklyPlanVsRealView (mensual/semanal detallado).  
  Misma familia de datos (ops.mv_real_trips_monthly, v_plan_trips_monthly_latest), presentación distinta; KPICards con "All" hace 6 llamadas.

- **Supply vs Driver Lifecycle:** Ambos por park; Supply se centra en segmentos/migración/alertas supply; Lifecycle en activaciones/churn/cohortes. Pueden confundir si el usuario busca “cómo está mi parque”.

### 5.2 Redundancias de datos y API

- **getSupplyGeo** se usa en: SupplyView, BehavioralAlertsView, FleetLeakageView, DriverBehaviorView, ActionEngineView. Único punto de verdad para país/ciudad/park en UI, correcto; pero refuerza que muchas vistas repiten el mismo patrón de filtros.
- **Real LOB:** Hay endpoints legacy (real-drill/summary, by-lob, by-park) y drill PRO (real-lob/drill, drill/children). La vista usa ambos (summary + drill PRO + by-lob/by-park para expand). Posible simplificación a solo drill PRO cuando esté estable.

### 5.3 Conflictos de naming

- **“Driver Behavior” vs “Behavioral Alerts”:** Suenan muy parecidos; uno es “motor de desviación por ventanas”, otro “alertas de desviación vs baseline”. Se recomienda naming que distinga claramente (p. ej. “Alertas de conducta” vs “Desviación por ventanas” o unificar bajo un paraguas “Conductores en riesgo” con subsecciones).
- **“Snapshot”** suena a “foto general”, pero en la práctica es “Plan vs Real (KPIs)”. Puede renombrarse a “Plan vs Real” o “Resumen ejecutivo”.
- **“Legacy”** agrupa tanto validación de plan (Expansión, Huecos) como operativo (Fase 2B, Fase 2C) y Universo LOB; el nombre no ayuda a decidir cuándo entrar.

### 5.4 Oportunidades de consolidación

- Unificar bajo **una entrada “Conductores que requieren atención”** (o “Riesgo y recuperación”) con subsecciones: Alertas de conducta, Desviación por ventanas, Fuga de flota, Acciones recomendadas (Action Engine), reduciendo tabs de primer nivel y dejando claros los roles de cada bloque.
- Agrupar **Plan vs Real** en una sola entrada: “Plan vs Real” con subvistas Resumen (actual Snapshot) y Desglose (actual Plan Válido), y mover Expansión/Huecos a “Validación de plan” o dentro del mismo grupo.
- Mover **System Health**, **Universo & LOB** y opcionalmente **Fase 2C** (si es más de auditoría) a un grupo “Diagnósticos” o “Técnico” en segundo nivel.

---

## 6. Diagnóstico de carga cognitiva y fricción UX (FASE 5)

- **Demasiadas tabs de primer nivel:** 10 (o 16 con legacy expandido). El operador no tiene una jerarquía clara (“primero esto, luego esto”).
- **Filtros globales vs locales:** Solo Snapshot y Legacy usan los filtros del panel; el resto usa filtros propios. Sensación de “los filtros de arriba no aplican aquí”.
- **Vistas muy parecidas:** Behavioral Alerts, Driver Behavior, Fleet Leakage, Action Engine comparten “lista de conductores + métricas + export”; diferenciar cuándo usar cada una requiere conocimiento interno.
- **Exceso de filtros en Behavioral Alerts:** from/to, segment, movement_type, alert_type, severity, risk_band; muchos usuarios pueden quedarse en defaults o perderse.
- **Driver Lifecycle y Supply exigen park:** Hasta no elegir park no hay datos; correcto para precisión pero añade un paso que no todas las vistas exigen.
- **Nombres técnicos en UI:** “Fase 2B”, “Fase 2C”, “Legacy”, “Real LOB” (LOB no explicado en la misma barra).
- **Estados vacíos/error:** No revisado en detalle en este mapeo; recomendable estandarizar loading/empty/error en todas las vistas.
- **Riesgo 500:** Drill Real LOB, Behavioral Alerts, Driver Behavior con timeouts altos; si fallan, el usuario no tiene un “modo degradado” claro.
- **CoreTable roto:** getCore no existe; si alguien enlazara el componente, fallaría en runtime.

---

## 7. Clasificación en capas (FASE 6)

### Capa A — Vistas principales de negocio (entrada diaria)

- **Real LOB** — Cómo va el real (por país, periodo, LOB, park).  
- **Snapshot (renombrar a “Plan vs Real” o “Resumen ejecutivo”)** — Foto Plan vs Real en KPIs.  
- **Driver Supply Dynamics** — Estado de la supply por park (overview, migración, alertas).  
- **Una única entrada “Conductores / Riesgo y recuperación”** que agrupe: Behavioral Alerts, Driver Behavior, Fleet Leakage, Action Engine (como subsecciones o tabs internas), para reducir 4 tabs a 1 y clarificar el flujo “quiénes requieren atención”.

### Capa B — Análisis / investigación (no necesariamente primera pantalla)

- **Driver Lifecycle** — Análisis por park y cohortes (obligatorio park).  
- **Legacy – Plan Válido** — Desglose mensual/semanal Plan y Real.  
- **Legacy – Expansión / Huecos** — Validación de plan (fuera de universo, huecos).  
- **Legacy – Fase 2B** — Seguimiento de acciones semanales.  
- **Legacy – Fase 2C** — Scoreboard, backlog, breaches (accountability).

### Capa C — Técnico / diagnóstico / legacy

- **System Health** — Integridad, freshness, auditoría.  
- **Legacy – Universo & LOB** — Cobertura y viajes sin match (validación técnica).  
- **Componentes no usados:** RealLOBView, PlanVsRealView, MonthlyView, CoreTable (revisar si eliminar o reconectar; CoreTable arreglar o deprecar).

---

## 8. Propuesta de nueva arquitectura de navegación (FASE 7)

- **Primer nivel (reducido a 5–6 ítems):**  
  1. **Resumen** (antes Snapshot): Plan vs Real en KPIs; puede incluir enlace a “Desglose” (actual Plan Válido).  
  2. **Real** (antes Real LOB): Drill y Daily como subvistas.  
  3. **Supply** (Driver Supply Dynamics): Overview, Composition, Migration, Alerts (mantener tabs internas).  
  4. **Conductores en riesgo** (nueva agrupación): Dentro, subsecciones o tabs: Alertas de conducta (Behavioral Alerts), Desviación por ventanas (Driver Behavior), Fuga de flota (Fleet Leakage), Acciones recomendadas (Action Engine).  
  5. **Ciclo de vida** (Driver Lifecycle): Por park, cohortes y métricas.  
  6. **Plan y validación** (agrupa Legacy útil): Subvistas: Desglose Plan vs Real (mensual/semanal), Expansión/Huecos, Fase 2B, Fase 2C.  

- **Segundo nivel (menú “Diagnósticos” o “Técnico”):**  
  - System Health.  
  - Universo & LOB.  
  (Opcional: Fase 2C si se considera más de auditoría que operativo.)

- **Renombrados sugeridos:**  
  - Snapshot → **Resumen** o **Plan vs Real (resumen)**.  
  - Real LOB → **Real** (y en subtítulo “por país, LOB, park”).  
  - Driver Supply Dynamics → **Supply** o **Dinámica de supply**.  
  - Behavioral Alerts → Dentro de “Conductores en riesgo”: **Alertas de conducta**.  
  - Driver Behavior → **Desviación por ventanas** (o similar).  
  - Fleet Leakage → **Fuga de flota**.  
  - Action Engine → **Acciones recomendadas**.  
  - Legacy → Sustituido por **Plan y validación** con subsecciones claras.

- **Fusiones conceptuales:**  
  - Las cuatro vistas “conductores a atender” en una sola entrada con subsecciones.  
  - Plan vs Real: una entrada con Resumen + Desglose (y opcionalmente Expansión/Huecos en el mismo grupo).

---

## 9. Propuesta de simplificación por vista (FASE 8)

- **Conductores en riesgo (agrupación):**  
  - **Por defecto:** Mostrar primero un resumen unificado (ej. total en alerta, en fuga, en recomendación) y un CTA “Ver listas”.  
  - Filtros visibles: país, ciudad, park, rango de fechas.  
  - Filtros en “Más filtros”: segment, alert_type, severity, risk_band, leakage_status (según subvista).  
  - Columnas por defecto: conductor, park, métrica principal (delta %, status, cohort), última actividad; resto en “Mostrar más columnas”.  
  - Un solo bloque de export “Lista de recuperación” que permita elegir fuente (alertas, desviación, fuga, acciones) o combinar.

- **Real LOB:**  
  - Mantener drill como vista principal; Daily como tab.  
  - Filtros visibles: país, tipo periodo (mensual/semanal), segment (B2B/B2C), park (opcional).  
  - Reducir columnas por defecto a: periodo, viajes, margen (abs), km prom, % B2B; el resto en expandible o “más columnas”.

- **Driver Supply Dynamics:**  
  - Mantener 4 tabs; en Overview mostrar primero KPIs y un solo gráfico clave; Composition/Migration con tablas colapsables por defecto.  
  - Filtros visibles: país, ciudad, park (obligatorio), from/to.  
  - Glosario y definiciones en “?” o panel lateral, no bloqueando.

- **Snapshot / Resumen:**  
  - Un solo bloque de KPIs (Plan vs Real); evitar 6 llamadas cuando country=All (un endpoint agregado o cache).  
  - Filtros visibles: país, año real, año plan; ciudad y LOB en “Más filtros”.

- **Driver Lifecycle:**  
  - Dejar claro que es “por park”; selector de park prominente.  
  - Resumen (cards) + tabla por periodo; cohortes y drilldown en segunda línea (tabs o acordeón).

- **System Health:**  
  - Sin cambio de lógica; asegurar estados loading/error claros y mensaje “Para uso técnico / diagnóstico”.

---

## 10. Propuesta de naming (FASE 9)

- **Nivel principal:** Resumen, Real, Supply, Conductores en riesgo, Ciclo de vida, Plan y validación.  
- **Diagnósticos:** System Health, Universo & LOB.  
- **Dentro “Conductores en riesgo”:** Alertas de conducta (antes Behavioral Alerts), Desviación por ventanas (antes Driver Behavior), Fuga de flota (Fleet Leakage), Acciones recomendadas (Action Engine).  
- **Dentro “Plan y validación”:** Desglose Plan vs Real, Expansión, Huecos, Acciones semanales (Fase 2B), Accountability (Fase 2C).  
- Evitar en primer nivel: “Legacy”, “Fase 2B/2C” sin contexto, “LOB” sin explicación. Opción: tooltip o glosario corto “LOB = Línea de negocio”.

---

## 10 bis. Propuesta de validación visual y operativa (FASE 10)

Para que cada mejora futura sea trazable y comprobable en UI, se recomienda que el proyecto adopte una **metodología estándar** por cambio:

1. **Vista objetivo:** Identificador de la vista (ej. `RealLOBDrillView`, `BehavioralAlertsView`).
2. **Componente real:** Ruta del componente (ej. `frontend/src/components/RealLOBDrillView.jsx`).
3. **Endpoint real:** Método y path (ej. `GET /ops/real-lob/drill`).
4. **Elemento visible esperado:** Descripción breve de qué debe verse (ej. “Tabla con columnas periodo, viajes, margen; filtro país y periodo”).
5. **Cómo validarlo visualmente:** Pasos (ej. “Seleccionar país CO, periodo mensual, comprobar que aparece al menos una fila y que el total de viajes es numérico”).
6. **Evidencia a entregar:** Captura de pantalla o descripción de resultado (OK / fallo) para que no se den por “implementados” cambios que no se ven en UI.

Esto debe quedar como **recomendación operativa** del proyecto (por ejemplo en un README de QA o en criterios de Definition of Done) para evitar reportes de “hecho” sin validación en la interfaz.

---

## 11. Recomendación de plan por fases (FASE 12) — Sin implementar aún

- **Fase 1 – Simplificación de navegación y naming**  
  - Reducir tabs de primer nivel a 5–6; agrupar “Conductores en riesgo”; renombrar Snapshot, Real LOB, Legacy según propuesta.  
  - No cambiar URLs/backend; solo estructura de menú y etiquetas en front.

- **Fase 2 – Consolidación de vistas solapadas**  
  - Implementar contenedor “Conductores en riesgo” con subsecciones (Behavioral Alerts, Driver Behavior, Fleet Leakage, Action Engine) manteniendo componentes actuales.  
  - Unificar entrada “Plan vs Real” (Resumen + Desglose + Expansión/Huecos).

- **Fase 3 – Mejora de estados visuales**  
  - Loading, empty, error estándar en todas las vistas; mensajes claros y acciones (reintentar, filtrar).

- **Fase 4 – Optimización operativa de vistas principales**  
  - Simplificar filtros por defecto y columnas por defecto en Behavioral Alerts, Driver Behavior, Fleet Leakage, Action Engine, Real LOB, Supply.  
  - Revisar KPICards (evitar 6 llamadas cuando All; endpoint agregado o cache).

- **Fase 5 – Diagnóstico técnico y limpieza legacy**  
  - Mover System Health y Universo & LOB a “Diagnósticos”.  
  - Decidir sobre RealLOBView, PlanVsRealView, MonthlyView: eliminar o reconectar.  
  - Corregir o deprecar CoreTable (getCore en api.js o eliminar componente).

---

## 12. Riesgos y decisiones abiertas

- **Riesgos:**  
  - Cambiar navegación puede desorientar a usuarios que ya tienen rutina. Conviene comunicación y, si es posible, un modo “vista clásica” temporal.  
  - Agrupar cuatro vistas de conductores en una sola entrada implica más desarrollo front (tabs o subrutas) y posiblemente un “resumen unificado” que hoy no existe en backend.  
  - Timeouts y 500 en drill y behavior siguen siendo riesgo operativo; la simplificación UX no los elimina sin mejoras en backend (índices, MVs, cache).

- **Decisiones abiertas:**  
  - ¿Se mantiene la variable LEGACY_ENABLED y las 6 tabs extra o se unifica todo bajo “Plan y validación” con subvistas?  
  - ¿Action Engine y Top Driver Behavior siguen como una sola vista o se separan en “Acciones recomendadas” vs “Patrones top drivers”?  
  - ¿Fase 2C (scoreboard, backlog, breaches) se considera operativo (Capa B) o técnico (Capa C)?  
  - ¿Se crea un endpoint “resumen conductores en riesgo” que agregue conteos de alertas + fuga + action engine para la futura vista unificada?

---

**Criterio de éxito (recordatorio):** Este documento permite decidir con claridad qué vistas quedan como principales, cuáles pasan a segundo plano, cuáles se fusionan conceptualmente, cómo reducir carga cognitiva y cómo seguir evolucionando Control Tower por fases sin desordenar más el producto. La siguiente etapa es validar esta propuesta con negocio y luego ejecutar el plan por fases sin implementación apresurada.
