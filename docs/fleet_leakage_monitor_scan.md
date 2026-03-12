# Fleet Leakage Monitor — Fase 0: Escaneo y mapeo obligatorio

**Proyecto:** YEGO Control Tower  
**Módulo:** Fleet Leakage Monitor (Supply Leakage)  
**Fecha:** 2026-03  
**Regla:** No implementar sin este mapeo. No mezclar con Behavioral Alerts.

---

## 0.1 Mapeo de fuentes disponibles

### Viajes por conductor por semana

| Objeto | Schema | Granularidad | Columnas clave | Uso en leakage |
|--------|--------|--------------|----------------|-----------------|
| **mv_driver_weekly_stats** | ops | driver_key, week_start | driver_key, week_start, park_id, trips_completed_week, work_mode_week, tipo_servicio, segment | **Base** para viajes/semana por conductor |
| **mv_driver_segments_weekly** | ops | driver_key, week_start | + segment_week, prev_segment_week, segment_change_type, weeks_active_rolling_4w, **baseline_trips_4w_avg** | **Preferida**: ya tiene baseline 4w; útil para caída vs baseline y segmento |
| **v_driver_behavior_baseline_weekly** | ops | driver_key, week_start | avg_trips_baseline (6 sem), delta_pct, weeks_declining_consecutively, active_weeks_in_window, stddev_trips_baseline | Usada por **Behavioral Alerts**. Leakage **no** debe leerla para no acoplar; podemos **reutilizar la misma fuente** (mv_driver_segments_weekly) en una vista/servicio **nuevo** |

- Origen último: **ops.v_driver_lifecycle_trips_completed** (conductor_id, completion_ts, park_id) → agregado en mv_driver_weekly_stats / mv_driver_segments_weekly.

### Baseline histórico y última actividad

| Objeto | Descripción | Uso en leakage |
|--------|-------------|----------------|
| **mv_driver_segments_weekly** | baseline_trips_4w_avg = media 4 semanas previas | Baseline corto; para leakage conviene ventana configurable (ej. 8–12 sem) |
| **v_driver_behavior_baseline_weekly** | Baseline 6 sem (excl. semana actual); avg, median, stddev | **No usar** en leakage (es de Behavioral Alerts) |
| **ops.v_driver_last_trip** | driver_key, last_trip_date (MAX completion_ts por conductor) | **Sí**: días desde último viaje, crítico para “posible robo” / abandono |
| **mv_driver_lifecycle_base** | driver_key, activation_ts, **last_completed_ts**, total_trips_completed, lifetime_days | Alternativa last_completed_ts; v_driver_last_trip ya expone last_trip_date y es vista ligera |

### Cohortes y ventana de referencia

| Objeto | Descripción | Uso en leakage |
|--------|-------------|----------------|
| **ops.mv_driver_cohorts_weekly** | cohort_week, park_id, driver_key (cohortes de activación) | Driver Lifecycle; definir **cohorte ancla** leakage: “activos en fecha X” o “top N en fecha X” |
| **ops.v_action_engine_cohorts_weekly** | week_start, cohort_type, cohort_size, suggested_priority | Action Engine; **no** reutilizar lógica de cohort_type (recoverable_mid, high_value_deteriorating, etc.) para no mezclar; sí **patrón**: filtrar drivers por ventana temporal de referencia |

- **Cohorte ancla para leakage:** No existe vista específica. Habrá que definir (ej. “drivers con al menos 1 viaje en [fecha_ref − 7d, fecha_ref]” o “top 25% por viajes en semana ref”) y materializarla en servicio o vista SQL nueva.

### Percentiles / rankings de drivers

- **En el sistema:** PERCENTILE_CONT en v_driver_behavior_baseline_weekly (median_trips_baseline), driver_behavior_service (baseline_median_weekly_trips), driver_lifecycle (time_to_first_trip_median, lifetime_days_median). **No hay** vista “driver_tier” (Top 10%, Top 25%, Mid, Low) lista para reutilizar.
- **Para leakage:** Habrá que **derivar** driver_tier (o equivalente) a partir de baseline de viajes / consistencia histórica / actividad reciente, en **nueva** capa (vista o servicio) para no tocar Behavioral Alerts.

### Estabilidad histórica

- **No existe** campo `historical_stability` (High/Medium/Low). En mv_driver_segments_weekly hay: weeks_active_rolling_4w, baseline_trips_4w_avg, segment_week, segment_change_type. En v_driver_behavior_baseline_weekly: stddev_trips_baseline, active_weeks_in_window, weeks_declining_consecutively.
- **Para leakage:** Calcular en nueva capa a partir de: variabilidad (stddev/avg en ventana larga), semanas activas consecutivas, frecuencia de caídas (segment_change_type downshift/drop).

### Geo y conductor

| Objeto | Uso |
|--------|-----|
| **dim.v_geo_park** | park_id, park_name, city, country — ya usada en Supply, Behavioral Alerts, Driver Behavior |
| **ops.v_dim_driver_resolved** | driver_id (= conductor_id), driver_name (MAX conductor_nombre) — para listados y export |

### Resumen de fuentes que SÍ usar (leakage)

- **ops.mv_driver_segments_weekly** — viajes/semana, segmento, baseline 4w, prev_segment, segment_change_type, weeks_active_rolling_4w.
- **ops.v_driver_last_trip** — last_trip_date → days_since_last_trip.
- **dim.v_geo_park** — geo.
- **ops.v_dim_driver_resolved** — nombre conductor.
- **ops.mv_driver_weekly_stats** — por si se necesita más detalle sin segmento (opcional).

### Fuentes que NO usar para lógica de leakage

- **ops.v_driver_behavior_baseline_weekly** — exclusiva Behavioral Alerts.
- **ops.v_driver_behavior_alerts_weekly** / **ops.mv_driver_behavior_alerts_weekly** — alertas conductuales (Critical Drop, Sudden Stop, etc.); no reutilizar como “leakage status”.
- **ops.v_action_engine_*** — cohortes y prioridad de Action Engine; no mezclar con clasificación de leakage.

---

## 0.2 Componentes reutilizables

| Componente / patrón | Ubicación | Uso en Fleet Leakage Monitor |
|---------------------|-----------|------------------------------|
| **Filtros geo (país, ciudad, park)** | getSupplyGeo(), getSupplyParks(); SupplyView, BehavioralAlertsView, DriverBehaviorView | Reutilizar **getSupplyGeo** y mismo patrón de selects (country, city, park_id) |
| **KPI cards** | BehavioralAlertsView: grid de cards con métricas (drivers_monitored, critical_drops, etc.) | Patrón: franja superior con métricas; **no** reutilizar KPICards.jsx (está acoplado a plan/real); sí **estructura** tipo BehavioralAlertsView (divs + números) |
| **Tabla principal** | BehavioralAlertsView, DriverBehaviorView: `<table>`, headers, orderBy/orderDir vía API, paginación | Misma estructura: tabla con th/td, sort por backend, chips/badges por estado |
| **Export CSV/Excel** | getBehaviorAlertsExportUrl(params) → GET /ops/behavior-alerts/export?…; enlace o botón “Export” | Nuevo endpoint **GET /ops/leakage/export** con mismo patrón (query params → CSV/Excel); frontend: getLeakageExportUrl(params) |
| **Tooltips / popovers** | BehavioralAlertsView: COLUMN_TOOLTIPS, título en headers; explainabilitySemantics | Tooltips en headers de tabla; leyenda “Por qué está aquí” (explainability) reutilizando patrón de texto corto |
| **Sort server-side** | behavior_alerts_service: order_by, order_dir en get_behavior_alerts_drivers | Incluir order_by, order_dir en get_leakage_drivers |
| **Chips/badges severidad** | explainabilitySemantics.js: RISK_BAND_COLORS, ALERT_COLORS; decisionColors.js | **Nuevos** colores para leakage status (stable_retained, watchlist, early_leakage, …); mismo patrón de clases CSS |
| **Leyenda / glossary** | DriverSupplyGlossary.jsx, BehavioralAlertsView SEGMENT_LEGEND | Panel o popover con definición de leakage, score, tiers, stability — **nuevo** contenido, mismo patrón |
| **Vista overview + tabla** | BehavioralAlertsView: KPIs → insight → filters → table → modal drilldown | Misma jerarquía: KPIs → (opcional insight) → filtros → tabla → detalle/acción |
| **formatNum / formatPct** | Definidos en BehavioralAlertsView, SupplyView, etc. | Reutilizar o extraer a util compartido (ej. `utils/format.js`) |
| **Segment semantics** | segmentSemantics.js (SEGMENT_LEGEND_MINIMAL) | Para columna segmento / driver_tier si se muestra segmento; reutilizar labels |

---

## 0.3 Punto ideal de implementación

### Endpoint

- **Crear nuevo prefijo:** `/ops/leakage/` (o `/ops/fleet-leakage/`).
- **Endpoints sugeridos:**  
  - `GET /ops/leakage/summary` — KPIs (drivers under watch, early leakage, progressive, high suspicion, lost, top performers at risk, cohort retention, recoverable high-value).  
  - `GET /ops/leakage/drivers` — Lista paginada con filtros (country, city, park_id, driver_tier, historical_stability, leakage_status, recovery_priority, cohort_anchor, days_since_last_trip range, etc.) y order_by/order_dir.  
  - `GET /ops/leakage/driver-detail` — Detalle por driver_key (opcional: timeline, explicación).  
  - `GET /ops/leakage/export` — CSV/Excel “Recovery Queue” (conductor, país, ciudad, park, tier, status, score, priority, last_trip, baseline, delta, semanas cayendo).  
  - `GET /ops/leakage/cohort-metrics` — Métricas de cohorte ancla (tamaño inicial, retenidos, watchlist, early, progressive, high_suspicion, lost) para una ventana de referencia configurable.

### Vista SQL / MV

- **Recomendación:** Nueva **vista** (o MV si el volumen lo exige) que lea **solo** de:
  - ops.mv_driver_segments_weekly  
  - ops.v_driver_last_trip  
  - dim.v_geo_park  
  - ops.v_dim_driver_resolved  
  y que **no** dependa de v_driver_behavior_baseline_weekly ni v_driver_behavior_alerts_weekly.
- **Contenido sugerido (granularidad driver-week o driver snapshot):**  
  driver_key, driver_name, week_start (o “reference_week”), park_id, country, city, park_name,  
  trips_current_week, baseline_trips (ventana configurable), delta_pct, weeks_declining_consecutive,  
  last_trip_date, days_since_last_trip,  
  driver_tier (Top 10% / Top 25% / Mid / Low), historical_stability (High/Medium/Low),  
  leakage_status (stable_retained | watchlist | early_leakage | progressive_leakage | high_suspicion_leakage | lost_driver),  
  leakage_score (0–100), suspicion_band, recovery_priority (P1–P4),  
  explainability_short (texto una línea).
- La **clasificación** (leakage_status, score, priority) debe implementarse en esta capa SQL (o en servicio Python que consulte una vista más “raw”) para mantener trazabilidad y no duplicar lógica con Behavioral Alerts.

### Servicio backend

- **Nuevo:** `backend/app/services/leakage_service.py` (o `fleet_leakage_service.py`).  
  - Funciones: get_leakage_summary, get_leakage_drivers, get_leakage_driver_detail, get_leakage_export, get_leakage_cohort_metrics.  
  - Leer de la nueva vista/MV de leakage (y eventualmente parámetros de cohorte ancla).  
  - **No** importar ni llamar a behavior_alerts_service ni reutilizar sus funciones de clasificación.

### Frontend

- **Nuevo componente:** `frontend/src/components/FleetLeakageView.jsx` (o `LeakageMonitorView.jsx`).  
- **Nueva pestaña:** En `App.jsx`, botón “Fleet Leakage Monitor” (o “Supply Leakage”) y `activeTab === 'fleet_leakage' && <FleetLeakageView />`.  
- **API:** En `api.js`, añadir getLeakageSummary, getLeakageDrivers, getLeakageDriverDetail, getLeakageExportUrl, getLeakageCohortMetrics.

### Reutilización de Behavioral Alerts

- **Solo** reutilizar:  
  - Patrón de layout (KPIs, filtros, tabla, export).  
  - getSupplyGeo para filtros.  
  - Constantes de formato (segmentSemantics si se muestra segmento).  
  - Patrón de tooltips y badges (con semántica **nueva** para leakage).  
- **No** reutilizar:  
  - Lógica de alert_type (Critical Drop, Sudden Stop, etc.).  
  - risk_score / risk_band de Behavioral Alerts.  
  - Vistas/v_driver_behavior_* para clasificación.

---

## 0.4 Salida del escaneo

### Archivos detectados (existentes, no modificar para lógica de leakage)

| Área | Archivos |
|------|----------|
| **Behavioral Alerts** | backend/app/services/behavior_alerts_service.py, backend/app/routers/ops.py (rutas behavior-alerts), backend/alembic/versions/081_*, 082_*, 084_*, 085_*, 090_*, frontend/src/components/BehavioralAlertsView.jsx |
| **Driver Behavior** | backend/app/services/driver_behavior_service.py, ops.py (driver-behavior), frontend/src/components/DriverBehaviorView.jsx |
| **Supply / Geo** | backend/app/services/supply_service.py, getSupplyGeo en api.js |
| **Fuentes de datos** | ops.mv_driver_segments_weekly, ops.v_driver_last_trip, dim.v_geo_park, ops.v_dim_driver_resolved (definidos en alembic 067, 078, 089, etc.) |
| **Action Engine** | action_engine_service.py, v_action_engine_* (solo referencia de patrón cohort; no reutilizar lógica) |

### Assets reutilizables

- getSupplyGeo(), getSupplyParks() (api.js).  
- Patrón de filtros país/ciudad/park (estado + selects).  
- Estructura de vista: KPIs arriba, filtros, tabla con sort, export URL, modal o detalle.  
- formatNum, formatPct (definir en componente o util).  
- segmentSemantics.js para etiquetas de segmento si aplica.  
- explainabilitySemantics.js / decisionColors.js como **referencia** de patrón (badges, colores); crear **nuevos** mapeos para leakage_status y recovery_priority.

### Propuesta de arquitectura

1. **Nueva migración Alembic:** Crear vista (o MV) `ops.v_fleet_leakage_snapshot` (o `ops.v_leakage_drivers_weekly`) que calcule, por driver y semana de referencia:  
   - baseline (ej. 8 o 12 semanas previas), viajes recientes (ej. 4 sem), delta_pct, semanas consecutivas en caída.  
   - days_since_last_trip (JOIN v_driver_last_trip).  
   - driver_tier (percentil de baseline o de actividad reciente; ej. Top 10%, Top 25%, Mid, Low).  
   - historical_stability (High/Medium/Low según stddev/avg y/o semanas estables).  
   - leakage_status (estados definidos en Fase 1).  
   - leakage_score (0–100), suspicion_band, recovery_priority (P1–P4).  
   - explainability_short (texto).  
   Fuente única: mv_driver_segments_weekly + v_driver_last_trip + geo + driver name.  

2. **Servicio:** `leakage_service.py` con get_leakage_summary, get_leakage_drivers, get_leakage_export, get_leakage_cohort_metrics. Parámetros: reference_week, cohort_anchor (fecha o ventana), country, city, park_id, driver_tier, historical_stability, leakage_status, recovery_priority, days_since_min/max, etc.  

3. **Router:** En `ops.py` registrar GET /ops/leakage/summary, /ops/leakage/drivers, /ops/leakage/export, /ops/leakage/cohort-metrics (y opcional driver-detail).  

4. **Frontend:** FleetLeakageView.jsx con KPIs, filtros (incl. ventana de análisis y cohorte ancla), tabla principal, columna “Por qué está aquí”, export “Recovery Queue”, columna Acción (preparada para CTA futura).  

5. **Cohorte ancla:** En backend, cohorte = conjunto de driver_key que cumplen criterio (ej. “activos en semana X” o “con al menos 1 viaje entre fecha A y B”). Métricas de cohorte: tamaño inicial, y por leakage_status retenidos / watchlist / early / progressive / high_suspicion / lost. Implementar en leakage_service + opcional vista auxiliar si hace falta.

### Riesgos

- **Rendimiento:** Si la vista de leakage hace muchos JOINs y agregaciones por driver/semana, puede ser pesada. Mitigación: vista bien indexada (driver_key, week_start, park_id); si hace falta, materializar como MV y refrescar tras mv_driver_segments_weekly.  
- **Duplicación de concepto “caída”:** Behavioral Alerts ya tiene Critical Drop, Moderate Drop, Silent Erosion. Leakage debe usar **nombres y reglas distintas** (early_leakage, progressive_leakage, etc.) y no reutilizar esos tipos para no confundir.  
- **Umbrales del score:** Evitar umbrales arbitrarios; calibrar con percentiles o distribución real (Fase 2).

### Plan de implementación no destructiva

1. **Solo añadir:** Nueva migración (vista/MV leakage), nuevo servicio, nuevas rutas bajo /ops/leakage/, nuevo componente y tab en App.  
2. **No modificar:** behavior_alerts_service, vistas v_driver_behavior_*, BehavioralAlertsView (salvo si se añade un enlace cruzado “Ver en Leakage” por producto).  
3. **No tocar:** mv_driver_segments_weekly, v_driver_last_trip, supply_service, migration, driver lifecycle.  
4. **Documentar:** En este doc o en `docs/fleet_leakage_logic.md`: definición de leakage (Fase 1), clasificación (Fase 2), driver_tier (Fase 3), historical_stability (Fase 4), fórmula del score (Fase 5), cohorte ancla (Fase 6).

---

## FASE 1 — Definición funcional de leakage (resumen para implementación)

**Leakage NO es:**  
- Solo inactividad.  
- Solo sudden stop (eso es Behavioral Alerts).  
- Solo churn genérico.  
- Solo last_trip_days > X.

**Leakage SÍ debe captar:**  
- Caída **progresiva** frente a baseline (varias semanas cayendo).  
- Pérdida de **top performers** (alto valor histórico que cae).  
- Deterioro de conductores **históricamente estables** (patrón anómalo).  
- Salidas o caídas **agrupadas en ventana temporal** (posible evento de jalado).  
- Casos de **alto valor** que no deberían caerse “naturalmente”.

**Estados sugeridos (clasificación propia, no alert_type de BA):**  
stable_retained | watchlist | early_leakage | progressive_leakage | high_suspicion_leakage | lost_driver  
(Definiciones detalladas en Fase 2; umbrales a calibrar con datos.)

---

## Siguiente paso

Tras validar este escaneo, implementar en este orden:  
1) Definición y documento de score/tiers/stability (Fase 1–5).  
2) Migración SQL (vista o MV leakage).  
3) leakage_service.py + rutas.  
4) FleetLeakageView.jsx + api.js + tab.  
5) Cohort metrics y filtro cohorte ancla.  
6) Export Recovery Queue y documentación final.
