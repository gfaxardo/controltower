# Driver Supply Dynamics — Mapa de arquitectura completo

Este documento describe el flujo de información desde base de datos hasta frontend para el módulo Driver Supply Dynamics (antes Supply Real).

---

## 1. DATA FLOW COMPLETO

Para cada parte del módulo se indica: objeto PostgreSQL → servicio/repositorio backend → endpoint FastAPI → llamada API frontend → componente React → elemento de UI.

### Overview

| Capa | Elemento |
|------|----------|
| **PostgreSQL** | `ops.mv_supply_weekly` (o `ops.mv_supply_monthly` según grain); `ops.mv_supply_segments_weekly` (para trips y shares por semana). |
| **Backend service** | `get_supply_overview_enhanced()` en `app.services.supply_service`: lee series de `mv_supply_weekly`/`monthly`, agrega por semana desde `mv_supply_segments_weekly` (SUM trips_sum, FILTER por segment_week FT/PT/CASUAL+OCCASIONAL), calcula en Python trips, avg_trips_per_driver, FT_share, PT_share, weak_supply_share; WoW (drivers_wow_pct, trips_wow_pct, etc.) sobre serie ordenada DESC. |
| **Endpoint** | `GET /ops/supply/overview-enhanced` (park_id, from, to, grain). |
| **Frontend API** | `getSupplyOverviewEnhanced({ park_id, from, to, grain })` en `api.js`. |
| **Component** | `SupplyView.jsx`: `loadOverview()` (useCallback) que llama a `getSupplyOverviewEnhanced` y guarda en `overviewData` (summary, series, series_with_wow). |
| **UI** | Tab **Overview**: cards (activations_sum, churned_sum, reactivated_sum, net_growth_sum, active_drivers_last_period, churn_rate_weighted, trips, avg_trips_per_driver, FT_share, PT_share, weak_supply_share); tabla serie por periodo con columnas WoW cuando grain=weekly; enlace Download CSV. |

### Segments / Composition

| Capa | Elemento |
|------|----------|
| **PostgreSQL** | `ops.mv_supply_segments_weekly` (week_start, park_id, segment_week, drivers_count, trips_sum, share_of_active, park_name, city, country). |
| **Backend service** | `get_supply_composition()`: llama a `get_supply_segments_series()` (query directa a `mv_supply_segments_weekly`), luego en Python añade avg_trips_per_driver por fila y WoW por (week, segment) con LAG implícito (serie ordenada por week DESC). Alternativa legacy: `get_supply_segments_series()` solo (sin WoW) usada por endpoint `/segments/series`. |
| **Endpoint** | `GET /ops/supply/composition` (park_id, from, to; format=csv opcional). |
| **Frontend API** | `getSupplyComposition({ park_id, from, to })` en `api.js`. |
| **Component** | `SupplyView.jsx`: tab **Composition**; `loadComposition()` al activar la tab; estado `composition`. |
| **UI** | Info box “Criterio de segmentación (semanal por viajes)”; tabla week_start × segment_week con drivers_count, trips_sum, share_of_active, avg_trips_per_driver, drivers_wow_pct, trips_wow_pct, share_wow_pp; Download CSV. |

### Alerts

| Capa | Elemento |
|------|----------|
| **PostgreSQL** | `ops.mv_supply_alerts_weekly` (week_start, park_id, park_name, city, country, segment_week, alert_type, severity, baseline_avg, current_value, delta_pct, message_short, recommended_action). |
| **Backend service** | `get_supply_alerts()`: SELECT sobre `mv_supply_alerts_weekly` con filtros (week_start_from/to, park_id, country, city, alert_type, severity, limit); añade `priority_label` (P0/P1→High, P2→Medium, P3→Low) en Python. |
| **Endpoint** | `GET /ops/supply/alerts` (park_id, from, to, week_start_from, week_start_to, country, city, alert_type, severity, limit, format=csv). |
| **Frontend API** | `getSupplyAlerts({ park_id, from, to, limit })` en `api.js`. |
| **Component** | `SupplyView.jsx`: tab **Alerts**; `loadAlerts()` al activar la tab; estado `alerts`. |
| **UI** | Tabla alertas con Semana, Prioridad, Severidad, Tipo, Segmento, Baseline (8w), Actual, Δ%, Mensaje; botón “Ver drivers” y enlace CSV. |

### Drilldown (alertas)

| Capa | Elemento |
|------|----------|
| **PostgreSQL** | `ops.v_supply_alert_drilldown` (vista sobre `ops.mv_driver_segments_weekly`: week_start, park_id, segment_week, driver_key, prev_segment_week, segment_week_current, trips_completed_week, baseline_trips_4w_avg, segment_change_type; filtro segment_change_type IN ('downshift','drop')). |
| **Backend service** | `get_supply_alert_drilldown(week_start, park_id, segment_week?, alert_type?)`: SELECT sobre `v_supply_alert_drilldown` con WHERE week_start, park_id y opcional segment_week; orden baseline_trips_4w_avg DESC. |
| **Endpoint** | `GET /ops/supply/alerts/drilldown` (park_id, week_start, segment_week, alert_type, format=csv). |
| **Frontend API** | `getSupplyAlertDrilldown({ park_id, week_start, segment_week, alert_type })` en `api.js`. |
| **Component** | `SupplyView.jsx`: al hacer clic en “Ver drivers” de una alerta se llama `openDrilldown(alert)` → `loadDrilldown(alert)` → estado `drilldownAlert`, `drilldownRows`. |
| **UI** | Modal: título con segment_week, week_start, park_name, city, country; tabla driver_key, prev_segment_week, segment_week_current, trips_completed_week, baseline_trips_4w_avg, segment_change_type; Export CSV. |

### Drilldown (migración)

| Capa | Elemento |
|------|----------|
| **PostgreSQL** | `ops.mv_driver_segments_weekly` (driver_key, week_start, park_id, prev_segment_week, segment_week, segment_change_type, trips_completed_week, baseline_trips_4w_avg). |
| **Backend service** | `get_supply_migration_drilldown(park_id, week_start, from_segment?, to_segment?)`: SELECT sobre `mv_driver_segments_weekly` con filtros; añade `migration_type` (upshift→upgrade, downshift→downgrade, drop, new→revival, stable→lateral) en Python. |
| **Endpoint** | `GET /ops/supply/migration/drilldown` (park_id, week_start, from_segment, to_segment, format=csv). |
| **Frontend API** | `getSupplyMigrationDrilldown({ park_id, week_start, from_segment, to_segment })` en `api.js`. |
| **Component** | `SupplyView.jsx`: en tab Migration, “Ver drivers” por fila → `openMigrationDrilldown(row)` → estado `migrationDrilldown`, `migrationDrilldownRows`. |
| **UI** | Modal: from_segment → to_segment, week_start, park_id; tabla driver_key, from_segment, to_segment, migration_type, trips_completed_week, baseline_trips_4w_avg. |

### Geo (filtros)

| Capa | Elemento |
|------|----------|
| **PostgreSQL** | `dim.v_geo_park` (park_id, park_name, city, country); fallback `ops.v_dim_park_resolved`. |
| **Backend service** | `get_supply_geo(country?, city?)`: SELECT en dim.v_geo_park; en Python deriva countries, cities, parks filtrados. |
| **Endpoint** | `GET /ops/supply/geo` (country, city). |
| **Frontend API** | `getSupplyGeo({ country, city })` en `api.js`. |
| **Component** | `SupplyView.jsx`: `loadGeo()` en useEffect; estado `geo` (countries, cities, parks). |
| **UI** | Dropdowns País → Ciudad → Park (obligatorio para cargar datos). |

---

## 2. OBJETOS DE BASE DE DATOS

Todos los objetos usados por el módulo, con tipo, columnas principales, keys, lógica y consumidor.

| Objeto | Tipo | Columnas principales | Keys / unicidad | Lógica de cálculo | Consumidor |
|--------|------|----------------------|-----------------|-------------------|------------|
| **ops.mv_driver_segments_weekly** | materialized view | driver_key, week_start, park_id, trips_completed_week, segment_week, prev_segment_week, segment_change_type, weeks_active_rolling_4w, baseline_trips_4w_avg | UNIQUE (driver_key, week_start) | Segmento por trips_completed_week (FT≥60, PT 20–59, CASUAL 5–19, OCC 1–4, DORMANT 0); LAG para prev_segment_week y baseline 4w; segment_change_type: drop, downshift, upshift, stable, new. Fuente: ops.mv_driver_weekly_stats. | supply_service (composition vía segments; migration; migration_drilldown; alert drilldown vía vista), refresh_supply_alerting_mvs |
| **ops.mv_supply_segments_weekly** | materialized view | week_start, park_id, park_name, city, country, segment_week, drivers_count, trips_sum, share_of_active | UNIQUE (week_start, park_id, segment_week) | Agregado desde mv_driver_segments_weekly: GROUP BY week_start, park_id, segment_week; share_of_active = 100*drivers_count/active_drivers (activos = no DORMANT). Geo desde dim.v_geo_park. | supply_service (get_supply_segments_series, get_supply_composition, get_supply_overview_enhanced), mv_supply_segment_anomalies_weekly |
| **ops.mv_supply_segment_anomalies_weekly** | materialized view | week_start, park_id, park_name, city, country, segment_week, current_value, baseline_avg, baseline_std, delta_abs, delta_pct, z_score, is_drop, is_spike, severity | UNIQUE (week_start, park_id, segment_week) | Desde mv_supply_segments_weekly: ventana 8 semanas previas (ROWS 8 PRECEDING 1 PRECEDING) por (park_id, segment_week); baseline_avg, baseline_std; delta_pct, z_score; is_drop = delta_pct ≤ -0.15, is_spike = delta_pct ≥ 0.20; severity P0–P3 por delta_pct/z_score. Solo filas con is_drop OR is_spike y baseline_avg ≥ 30. | supply_service no la lee directamente; la consume mv_supply_alerts_weekly |
| **ops.mv_supply_alerts_weekly** | materialized view | week_start, park_id, park_name, city, country, segment_week, alert_type, severity, baseline_avg, current_value, delta_pct, message_short, recommended_action | UNIQUE (week_start, park_id, segment_week, alert_type) | UNION de segment_drop y segment_spike desde mv_supply_segment_anomalies_weekly; message_short y recommended_action por segmento/tipo. | get_supply_alerts (supply_service) |
| **ops.v_supply_alert_drilldown** | view | week_start, park_id, segment_week, driver_key, prev_segment_week, segment_week_current, trips_completed_week, baseline_trips_4w_avg, segment_change_type | — | SELECT sobre mv_driver_segments_weekly WHERE segment_change_type IN ('downshift','drop'). | get_supply_alert_drilldown (supply_service) |
| **ops.refresh_supply_alerting_mvs()** | function | — | — | REFRESH MATERIALIZED VIEW CONCURRENTLY en orden: mv_driver_segments_weekly, mv_supply_segments_weekly, mv_supply_segment_anomalies_weekly, mv_supply_alerts_weekly; statement_timeout 60min, lock_timeout 60s. | supply_service.refresh_supply_alerting_mvs(); POST /ops/supply/refresh y /supply/refresh-alerting; scripts regenerate_views_and_verify (--refresh-supply) |
| **ops.mv_supply_weekly** | materialized view | week_start, park_id, park_name, city, country, activations, active_drivers, churned, reactivated, churn_rate, reactivation_rate, net_growth | UNIQUE (week_start, park_id) | Calendar desde mv_driver_weekly_stats; activations (first_week), active_drivers, churn/reactivated desde v_driver_weekly_churn_reactivation + mv_driver_weekly_stats; geo dim.v_geo_park. No contiene trips. | get_supply_series, get_supply_summary, get_supply_global_series, get_supply_overview_enhanced (serie base) |
| **ops.mv_supply_monthly** | materialized view | month_start, park_id, park_name, city, country, activations, active_drivers, churned=0, reactivated=0, churn_rate, reactivation_rate, net_growth | UNIQUE (month_start, park_id) | Análogo a weekly desde mv_driver_monthly_stats; sin churn mensual (simplificado). | get_supply_series, get_supply_summary, get_supply_global_series, get_supply_overview_enhanced (grain=monthly) |
| **dim.v_geo_park** | view | park_id, park_name, city, country | — | SELECT FROM dim.dim_geo_park WHERE is_active. | get_supply_geo, get_supply_parks; usado en definición de mv_supply_weekly, mv_supply_monthly, mv_supply_segments_weekly |
| **ops.v_dim_park_resolved** | view | park_id, park_name, city, country | — | Resolución desde dim.dim_park. | get_supply_geo / get_supply_parks (fallback cuando v_geo_park vacío) |

---

## 3. LÓGICA DE SEGMENTACIÓN

- **Dónde se calcula**: En la definición de la materialized view **ops.mv_driver_segments_weekly**, dentro de la migración Alembic **063_supply_segments_alerts_weekly.py**.
- **Archivo**: `backend/alembic/versions/063_supply_segments_alerts_weekly.py` (variable `_SEGMENT_CASE`, inyectada en el CREATE MATERIALIZED VIEW).
- **Query exacta (fragmento)**:
  ```sql
  CASE
      WHEN trips_completed_week >= 60 THEN 'FT'
      WHEN trips_completed_week >= 20 THEN 'PT'
      WHEN trips_completed_week >= 5 THEN 'CASUAL'
      WHEN trips_completed_week >= 1 THEN 'OCCASIONAL'
      ELSE 'DORMANT'
  END AS segment_week
  ```
  Fuente de `trips_completed_week`: **ops.mv_driver_weekly_stats** (columna ya existente en esa MV).
- **¿Está hardcodeado?** Sí. Los umbrales 60, 20, 5, 1 están fijos en el SQL de la migración.
- **¿Depende de trips_sum?** No directamente. Depende de **trips_completed_week** por driver y semana (en mv_driver_weekly_stats). trips_sum en mv_supply_segments_weekly es la suma de viajes por segmento (derivada de los mismos drivers ya clasificados).
- **¿Otra métrica?** Solo **trips_completed_week** (conteo de viajes del conductor en esa semana en mv_driver_weekly_stats).

---

## 4. REFRESH PIPELINE

- **Función SQL**: `ops.refresh_supply_alerting_mvs()` ejecuta REFRESH CONCURRENTLY en este orden:  
  `mv_driver_segments_weekly` → `mv_supply_segments_weekly` → `mv_supply_segment_anomalies_weekly` → `mv_supply_alerts_weekly`.
- **Quién la llama**:
  - **Backend**: `app.services.supply_service.refresh_supply_alerting_mvs()` (ejecuta `SELECT ops.refresh_supply_alerting_mvs()`).
  - **Endpoints**:  
    - `POST /ops/supply/refresh` (sin guard; siempre ejecuta).  
    - `POST /ops/supply/refresh-alerting` (solo si `SUPPLY_REFRESH_ALLOWED=true`).
  - **Frontend**: Botón “Refrescar MVs” en SupplyView llama a `refreshSupplyAlerting()` → POST `/ops/supply/refresh`.
  - **Scripts**:  
    - `backend/scripts/regenerate_views_and_verify.py` con opción `--refresh-supply` (llama a `refresh_supply_alerting_mvs()`).  
    - No se encontró invocación desde `run_regenerate_all.py` sin flag (existe `--no-supply` para omitir).
- **Cron / job scheduler**: No hay cron ni job scheduler referenciado en el repo para este refresh; es **manual** (usuario en UI o ejecución de script).
- **Frecuencia estimada**: Manual / bajo demanda; típicamente tras refresco de driver lifecycle (mv_driver_weekly_stats) para que las MVs de supply tengan datos actualizados.

Nota: **ops.mv_supply_weekly** y **ops.mv_supply_monthly** se refrescan con otra función, **ops.refresh_supply_mvs()** (definida en 060), no con `refresh_supply_alerting_mvs()`. Ese refresh no está enlazado en los endpoints actuales del módulo (solo están /supply/refresh y /supply/refresh-alerting que llaman a refresh_supply_alerting_mvs).

---

## 5. ENDPOINTS DEL MÓDULO

Todos los endpoints bajo el router montado en `/ops` (prefijo efectivo `/ops/supply/...`).

| Método y ruta | Servicio backend | Query / origen de datos | Contrato de respuesta |
|---------------|------------------|--------------------------|------------------------|
| GET /ops/supply/geo | get_supply_geo | dim.v_geo_park (fallback v_dim_park_resolved); filtrado en Python | `{ "countries": [], "cities": [], "parks": [{ park_id, park_name, city, country }] }` |
| GET /ops/supply/parks | get_supply_parks | dim.v_geo_park con WHERE opcionales | `{ "data": [ { park_id, park_name, city, country }, ... ] }` |
| GET /ops/supply/series | get_supply_series | ops.mv_supply_weekly o mv_supply_monthly por park_id, from, to | `{ "data": [ { period_start, park_id, park_name, city, country, activations, active_drivers, churned, reactivated, churn_rate, reactivation_rate, net_growth }, ... ] }` o CSV |
| GET /ops/supply/summary | get_supply_summary | get_supply_series + agregación en Python | `{ activations_sum, churned_sum, reactivated_sum, net_growth_sum, active_drivers_last_period, churn_rate_weighted, reactivation_rate_weighted, periods_count }` |
| GET /ops/supply/segments/series | get_supply_segments_series | ops.mv_supply_segments_weekly por park_id, from, to | `{ "data": [ { week_start, segment_week, drivers_count, trips_sum, share_of_active, park_name, city, country }, ... ] }` o CSV |
| GET /ops/supply/global/series | get_supply_global_series | ops.mv_supply_weekly o mv_supply_monthly agregado (opcional country/city) | `{ "data": [ { period_start, ... agregados }, ... ] }` o CSV |
| GET /ops/supply/alerts | get_supply_alerts | ops.mv_supply_alerts_weekly + priority_label en servicio | `{ "data": [ { week_start, park_id, ..., severity, priority_label, ... }, ... ], "total": N }` o CSV |
| GET /ops/supply/alerts/drilldown | get_supply_alert_drilldown | ops.v_supply_alert_drilldown por week_start, park_id, segment_week | `{ "data": [ { driver_key, prev_segment_week, segment_week_current, trips_completed_week, baseline_trips_4w_avg, segment_change_type }, ... ], "total": N }` o CSV |
| GET /ops/supply/overview-enhanced | get_supply_overview_enhanced | mv_supply_weekly/monthly + mv_supply_segments_weekly; WoW en Python | `{ "summary": { ... + trips, avg_trips_per_driver, FT_share, PT_share, weak_supply_share }, "series": [...], "series_with_wow": [...] }` |
| GET /ops/supply/composition | get_supply_composition | get_supply_segments_series + WoW en Python | `{ "data": [ { week_start, segment_week, drivers_count, trips_sum, share_of_active, avg_trips_per_driver, drivers_wow_pct, trips_wow_pct, share_wow_pp }, ... ], "total": N }` o CSV |
| GET /ops/supply/migration | get_supply_migration | ops.mv_driver_segments_weekly GROUP BY week_start, park_id, prev_segment_week, segment_week, segment_change_type | `{ "data": [ { week_start, park_id, from_segment, to_segment, migration_type, drivers_migrated }, ... ], "total": N }` o CSV |
| GET /ops/supply/migration/drilldown | get_supply_migration_drilldown | ops.mv_driver_segments_weekly filtrado por park_id, week_start, from_segment, to_segment | `{ "data": [ { driver_key, from_segment, to_segment, migration_type, trips_completed_week, baseline_trips_4w_avg }, ... ], "total": N }` o CSV |
| POST /ops/supply/refresh | — | refresh_supply_alerting_mvs() | `{ "ok": true, "message": "..." }` |
| POST /ops/supply/refresh-alerting | — | refresh_supply_alerting_mvs() (si SUPPLY_REFRESH_ALLOWED) | `{ "ok": true, "message": "..." }` o 403 |

---

## 6. COMPONENTES FRONTEND

- **SupplyView.jsx**  
  - Único componente de pantalla del módulo (sin subcomponentes extraídos).  
  - **Estado**: country, city, parkId, geo, from, to, grain, activeTab; overviewData, composition, migration, alerts; loadings y error; drilldownAlert, drilldownRows; migrationDrilldown, migrationDrilldownRows.  
  - **Hooks**: useState, useEffect, useCallback. No hay hooks personalizados adicionales.  
  - **Servicios API** (todos en `api.js`):  
    - getSupplyGeo → GET /ops/supply/geo  
    - getSupplyOverviewEnhanced → GET /ops/supply/overview-enhanced  
    - getSupplyComposition → GET /ops/supply/composition  
    - getSupplyMigration → GET /ops/supply/migration  
    - getSupplyMigrationDrilldown → GET /ops/supply/migration/drilldown  
    - getSupplyAlerts → GET /ops/supply/alerts  
    - getSupplyAlertDrilldown → GET /ops/supply/alerts/drilldown  
    - refreshSupplyAlerting → POST /ops/supply/refresh  

- **App.jsx**  
  - Renderiza el tab “Driver Supply Dynamics” y, al seleccionarlo, `<SupplyView key={supply-${refreshKey}} />`. No llama a ningún endpoint de supply directamente.

- **Subcomponentes**  
  - No hay componentes hijos propios del módulo; todo está en SupplyView (filtros, tabs, tablas, modales). Se usan elementos nativos (tablas, botones, selects, modales).

---

## 7. DEPENDENCIAS CON OTROS MÓDULOS

- **Driver Lifecycle**  
  - **ops.mv_driver_weekly_stats**: fuente de `trips_completed_week` y de la lista driver_key×week_start×park_id usada para construir mv_driver_segments_weekly y mv_supply_weekly (activations, active_drivers, churn, reactivation).  
  - **ops.mv_driver_monthly_stats**: fuente de mv_supply_monthly.  
  - **ops.v_driver_weekly_churn_reactivation**: usada en la definición de mv_supply_weekly (churn_flow_week, reactivated_week).  
  Supply **depende** del build de Driver Lifecycle (MVs y vista de churn); no mezcla semánticas (segmentación Supply es 60/20/5/1/0; Lifecycle tiene work_mode_week distinto).

- **Parks / dimensión geo**  
  - **dim.v_geo_park** (dim.dim_geo_park): lista de parks para filtros y para rellenar park_name, city, country en MVs de supply.  
  - **ops.v_dim_park_resolved** (dim.dim_park): fallback cuando v_geo_park no devuelve datos.

- **trips_all / datos de viajes**  
  - No se accede directamente desde el módulo Supply. Los viajes llegan vía **mv_driver_weekly_stats** (y de ahí a mv_driver_segments_weekly), que a su vez se alimenta del pipeline de Driver Lifecycle (p. ej. vistas sobre trips / conductor).

- **Otros módulos de Control Tower**  
  - Plan vs Real, Real LOB, Phase2B, etc. no son dependencias directas de Supply. Supply es solo consumo de MVs ops y dimensión dim.

---

## 8. EVALUACIÓN FINAL

- **Bien diseñadas**  
  - Separación clara por capas: MVs/vistas SQL → servicio único (supply_service) → endpoints bajo /ops/supply → un componente principal que concentra estado y llamadas API.  
  - Reutilización de dim.v_geo_park y de mv_driver_weekly_stats sin duplicar lógica de viajes.  
  - Pipeline de alertas bien encadenado (segmentos → anomalías 8w → alertas con mensaje y acción).  
  - Drilldown de alertas y de migración bien acotados (vista + query por filtros).  
  - Endpoints nuevos (overview-enhanced, composition, migration, migration/drilldown) mantienen compatibilidad con los existentes.

- **Frágiles**  
  - Segmentación y umbrales de anomalías (8w, -15%, +20%, P0–P3) hardcodeados en SQL; cualquier cambio exige migración y no hay configuración auditable.  
  - Refresh: solo se refrescan las 4 MVs de “alerting”; mv_supply_weekly y mv_supply_monthly tienen su propia función (refresh_supply_mvs) pero no están expuestas en la UI del módulo, por lo que pueden quedar desactualizadas respecto a driver lifecycle.  
  - Un solo componente muy grande (SupplyView) con toda la lógica y UI; cambios y pruebas son más costosos.

- **Reutilizables**  
  - Patrón filtros geo (country → city → park) y uso de get_supply_geo.  
  - Patrón “tab + carga bajo demanda + CSV” para Composition, Migration, Alerts.  
  - Servicio de supply como única entrada a datos de supply (fácil de extender o testear).  
  - Lógica de WoW y de priority_label en servicio, reutilizable desde otros endpoints o reportes.

- **A rediseñar / mejorar**  
  - Extraer subcomponentes (OverviewCards, CompositionTable, MigrationTable, AlertsTable, modales de drilldown) para reducir complejidad de SupplyView.  
  - Introducir configuración de segmentos (p. ej. ops.driver_segment_config) y, si aplica, de umbrales de alertas.  
  - Unificar o documentar estrategia de refresh: qué refresca la UI (solo alerting vs también supply_weekly/monthly) y con qué frecuencia/cron.  
  - Considerar un contrato formal (Pydantic) para respuestas de los endpoints principales para documentación y evolución controlada.
