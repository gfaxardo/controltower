# YEGO Control Tower — Scan global de performance, duplicidad y robustez

**Fecha:** 2025-03  
**Objetivo:** Mapeo integral antes de optimización sistémica incremental.

---

## A. FRONTEND — SCAN GLOBAL

### A.1 Estructura de páginas/tabs

| Tab (activeTab) | Componente | key |
|-----------------|------------|-----|
| real_lob | RealLOBDrillView | real-lob-drill-{refreshKey} |
| driver_lifecycle | DriverLifecycleView | driver-lifecycle-{refreshKey} |
| supply | SupplyView | supply-{refreshKey} |
| behavioral_alerts | BehavioralAlertsView | behavioral-alerts-{refreshKey} |
| driver_behavior | DriverBehaviorView | driver-behavior-{refreshKey} |
| action_engine | ActionEngineView | action-engine-{refreshKey} |
| snapshot | ExecutiveSnapshotView | snapshot-{refreshKey} |
| system_health | SystemHealthView | system-health-{refreshKey} |
| legacy | Varios (MonthlySplitView, PlanTabs, etc.) | — |

**Siempre montados (independientes del tab):**
- GlobalFreshnessBanner → llama `getDataFreshnessGlobal()` en mount
- CollapsibleFilters

**Consecuencia:** Al cambiar de tab se desmonta el componente anterior y se monta el nuevo. Cada vista que se abre ejecuta sus `useEffect` y hace sus requests. No hay persistencia de datos entre tabs; al volver a un tab se vuelve a montar y se repiten todos los fetches.

### A.2 React StrictMode

- **main.jsx:** `<React.StrictMode>` está activo.
- En desarrollo React monta, desmonta y vuelve a montar componentes para detectar efectos secundarios, por lo que los `useEffect` con `[]` se ejecutan **dos veces** en dev → duplicación de requests (data-freshness, period-semantics, supply/geo, summary, drivers, etc.) en la misma carga de vista.

### A.3 Componentes compartidos y hooks de fetch

- **No hay React Query / SWR / capa central de cache.** Todo el fetch es manual vía `api.js` (axios).
- **Catálogos compartidos:** `getSupplyGeo`, `getPeriodSemantics`, `getDataFreshnessGlobal` son usados por varias vistas pero cada una los llama por su cuenta al montar; no hay deduplicación ni cache compartido.

### A.4 Endpoint → quién lo llama → cuántas veces al montar

| Endpoint | Llamado por | Veces al montar (estimado) |
|----------|-------------|----------------------------|
| GET /ops/data-freshness/global | GlobalFreshnessBanner (siempre montado) | 1 (o 2 en dev por StrictMode) |
| GET /ops/period-semantics | RealLOBDrillView, RealLOBDailyView | 1–2 por vista (2 en dev) |
| GET /ops/supply/geo | DriverBehaviorView, BehavioralAlertsView, ActionEngineView, SupplyView | 1 por vista que use geo (2 en dev) |
| GET /ops/real-lob/drill/parks | RealLOBDrillView | 1 (2 en dev) |
| GET /ops/real-lob/drill?… | RealLOBDrillView | 1 (2 en dev) |
| GET /ops/real-lob/comparatives/monthly o weekly | RealLOBDrillView | 1 (2 en dev) |
| GET /ops/driver-behavior/summary | DriverBehaviorView | 1 (2 en dev) |
| GET /ops/driver-behavior/drivers | DriverBehaviorView | 1 (2 en dev) |
| GET /ops/behavior-alerts/summary | BehavioralAlertsView | 1 (2 en dev) |
| GET /ops/behavior-alerts/insight | BehavioralAlertsView | 1 (2 en dev) |
| GET /ops/behavior-alerts/drivers | BehavioralAlertsView | 1 (2 en dev) |
| GET /ops/action-engine/summary | ActionEngineView | 1 (2 en dev) |
| GET /ops/action-engine/recommendations | ActionEngineView | 1 (2 en dev) |
| GET /ops/action-engine/cohorts | ActionEngineView | 1 (2 en dev) |

### A.5 Flujo de carga por vista (resumen)

- **Real LOB (por defecto):** GlobalFreshnessBanner (data-freshness) + RealLOBDrillView (drill/parks, period-semantics, drill, comparatives) → **mín. 5 requests** (en dev con StrictMode puede duplicarse).
- **Driver Behavior:** GlobalFreshnessBanner ya cargó + DriverBehaviorView: loadGeo (supply/geo), loadSummary, loadDrivers → **3 requests** (más 1x data-freshness si se considera el primer load de la app).
- **Behavioral Alerts:** supply/geo + summary + insight + drivers → **4 requests**.
- **Action Engine:** supply/geo + summary + recommendations + cohorts → **4 requests**.
- **Supply:** supply/geo + otros endpoints de supply según la vista.

### A.6 Top duplicidades frontend

1. **data-freshness/global:** Una vez por carga de app (Banner); en dev puede ser 2 por StrictMode.
2. **period-semantics:** Llamado por Real LOB (drill y daily); cada vez que se monta esa pestaña; en dev x2.
3. **supply/geo:** Llamado por Driver Behavior, Behavioral Alerts, Action Engine, Supply. Cada vez que el usuario abre una de esas pestañas se vuelve a pedir; sin cache, 4 vistas = 4 (u 8 en dev) llamadas independientes.
4. **summary + drivers (o insight + drivers):** En Driver Behavior y Behavioral Alerts se hace summary y drivers por separado; ambos podrían compartir base en backend (ver Backend).
5. **Remount al cambiar tab:** Al volver a “Real LOB” o “Driver Behavior” el componente se monta de nuevo y se repiten todos los requests de esa vista.

### A.7 Dependencias inestables y doble fetch

- **DriverBehaviorView:** `filters` es un objeto recalculado en cada render; `loadSummary` y `loadDrivers` dependen de primitivos (recentWeeks, country, etc.), no del objeto `filters`, por lo que está estable. Pero `loadGeo` depende de `[country, city]`; si el padre no pasa estable esas props, puede haber refetches.
- **BehavioralAlertsView:** loadSummary y loadInsight en el mismo `useEffect([loadSummary, loadInsight])`; loadDrivers en otro `useEffect([loadDrivers])` → al montar se disparan 3 requests (summary, insight, drivers). Correcto pero sin dedup.
- No se observa fetch en parent + child del mismo recurso en paralelo; el problema es repetición por remount y por falta de cache compartido.

---

## B. BACKEND — SCAN GLOBAL

### B.1 Router principal (ops) y servicios

- **ops.router** montado en la app; prefijo según configuración (p. ej. `/ops`).
- **Endpoints de infraestructura compartida:**
  - GET /ops/data-freshness/global → data_freshness_service (o equivalente en ops).
  - GET /ops/period-semantics → period_semantics_service / ops.
  - GET /ops/supply/geo → supply_service.get_supply_geo (o get_definitions + geo).
- **Driver Behavior:** GET /ops/driver-behavior/summary, /drivers, /driver-detail, /export → driver_behavior_service (get_driver_behavior_summary, get_driver_behavior_drivers, etc.). Usa **get_db_audit(timeout)** (conexión dedicada 5 min), no pool.
- **Behavioral Alerts:** GET /ops/behavior-alerts/summary, /insight, /drivers, /driver-detail, /export → behavior_alerts_service. Timeout largo en queries.
- **Action Engine:** GET /ops/action-engine/* → action_engine_service.
- **Real LOB drill:** getRealLobDrillPro, getRealLobDrillParks, getRealLobComparativesMonthly/Weekly → real_lob_drill_pro_service, comparative_metrics_service, etc. **get_db_drill()** (conexión dedicada statement_timeout=0) para el drill principal.

### B.2 Bug alias "ra" (GET /ops/driver-behavior/drivers con park_id)

- **Error:** `missing FROM-clause entry for table "ra"` en el SELECT final que usa `FROM with_action` con `WHERE ... AND ra.park_id...`.
- **Causa:** Los filtros dinámicos (having_parts) usaban `ra.park_id` y `ra.current_segment`; la query principal hace `SELECT * FROM with_action`, donde solo existen columnas sin alias (park_id, current_segment, etc.); el alias `ra` no existe en ese scope.
- **Corrección aplicada:** (1) Todos los having_parts usan **cls.** (cls.park_id, cls.current_segment, cls.alert_type, etc.). (2) Para la query principal se construye `where_sql_main = where_sql.replace("cls.", "").replace("LOWER(TRIM(geo.country))", "LOWER(TRIM(country))").replace("LOWER(TRIM(geo.city))", "LOWER(TRIM(city))")` y se usa en `SELECT * FROM with_action WHERE 1=1 ... + where_sql_main`. (3) La query de count hace `FROM cls` y usa `where_sql` sin reemplazo (cls. correcto).
- **Estado:** Corregido en driver_behavior_service. Si el 500 persiste, verificar que el proceso backend esté usando la versión actual del archivo (reinicio o despliegue).

### B.3 Conexiones dedicadas (drill) y statement_timeout

- **get_db_drill():** Conexión dedicada con `statement_timeout=0`. Usado en **real_lob_drill_pro_service** para el drill PRO (timeline pesado). Cada request de drill abre una conexión nueva, ejecuta y cierra.
- **get_db_audit(timeout_ms):** Usado en **driver_behavior_service** (300_000 ms). Conexión dedicada por request, no pool.
- **Pool estándar (get_db):** statement_timeout=180000 ms en opciones de conexión. Usado por el resto de endpoints (supply, behavior_alerts, action_engine, data_freshness, period_semantics, etc.).
- **Duplicidad de “Drill connection opened”:** Si el frontend hace 2 requests al drill (p. ej. por StrictMode o doble llamada), se abren 2 conexiones drill. No hay pooling para drill; es intencional para no bloquear el pool con queries largas.

### B.4 Recomputación summary vs drivers

- **Driver Behavior:** summary y drivers son **dos queries distintas**; ambas calculan ventanas reciente/baseline y clasificación desde mv_driver_segments_weekly y v_driver_last_trip. No comparten resultado intermedio; hay recomputación completa en cada uno.
- **Behavioral Alerts:** summary, insight y drivers también son consultas separadas; comparten lógica de ventanas pero no resultado cacheado en el mismo request.

### B.5 Top 10 endpoints candidatos a optimización

1. GET /ops/driver-behavior/summary y /drivers — queries pesadas; podrían compartir CTE o cache de sesión.
2. GET /ops/behavior-alerts/summary, /insight, /drivers — mismo criterio.
3. GET /ops/real-lob/drill — ya usa conexión dedicada; candidato a cache de resultado por params (period, desglose, segmento, park_id) con TTL corto.
4. GET /ops/data-freshness/global — llamado en cada carga; muy cacheable (ej. 60 s).
5. GET /ops/period-semantics — poco cambiante; muy cacheable.
6. GET /ops/supply/geo — catálogo; muy cacheable (ej. 5–15 min o invalidación por evento).
7. GET /ops/real-lob/comparatives/monthly y /weekly — candidatos a cache por periodo.
8. GET /ops/action-engine/summary, /cohorts, /recommendations — comparten base; posibilidad de respuesta combinada o cache.
9. GET /ops/driver-behavior/driver-detail — por driver_key + ventanas; cacheable por request idempotente.
10. GET /ops/behavior-alerts/driver-detail — igual.

### B.6 Filtros dinámicos y ORDER BY

- **Driver Behavior:** order_by aceptado (risk_score, delta_pct, days_since_last_trip, recent_avg_weekly_trips); se mapea a columnas del SELECT desde with_action (sin alias). Filtros: park_id, country, city, segment_current, alert_type, severity, risk_band, inactivity_status. Composición WHERE vía where_sql_main (sin cls/ra/geo en el SELECT final). Corregido.
- **Recomendación:** Mantener whitelist de columnas ordenables y de filtros; evitar interpolar input de usuario en SQL sin validación.

---

## C. SQL / DATA LAYER — SCAN GLOBAL

### C.1 Fuentes por módulo

- **Driver Behavior:** ops.mv_driver_segments_weekly, ops.v_driver_last_trip, dim.v_geo_park (o dim.dim_park), ops.v_dim_driver_resolved. Agregación por driver_key + park_id; ventanas reciente/baseline en el mismo query (CTEs).
- **Behavioral Alerts:** ops.v_driver_behavior_alerts_weekly (o MV); grain driver-week.
- **Real LOB drill:** real_lob_drill_pro_service lee de vistas/MVs de drill (real_drill_dim_fact, etc.); period month/week, desglose LOB/PARK/SERVICE_TYPE.
- **Supply / geo:** supply_service; catálogos y series desde MVs de supply (mv_supply_segments_weekly, definiciones, etc.).

### C.2 Consultas pesadas y recomputación

- **driver_behavior_service:** Una query con múltiples CTEs (ref, recent_agg, baseline_agg, week_series, strk, base, cls, with_action); sin MV precalculada para “driver behavior deviation”; cada request recalcula desde mv_driver_segments_weekly.
- **behavior_alerts_service:** Lee de vistas de alertas por semana; posible recomputación similar si no hay MV.
- **real_lob_drill_pro_service:** Drill con muchas filas; usa get_db_drill() para no bloquear el pool.

### C.3 Oportunidades

- **Cache HTTP o aplicación:** data-freshness/global, period-semantics, supply/geo con TTL.
- **Base compartida en backend:** Un solo “driver behavior base” por request (mismos filtros/ventanas) y derivar summary (COUNT/aggregates) y lista (filas) del mismo resultado en memoria o con una sola query que devuelva ambos (ej. WITH base AS (...) SELECT (SELECT json_object_agg(...) FROM (SELECT COUNT(*) FROM base)...), (SELECT json_agg(...) FROM base ...) — o dos lecturas del mismo cursor/CTE).
- **Índices:** Revisar con EXPLAIN ANALYZE en entorno real sobre week_start, park_id, driver_key, (country, city) donde apliquen filtros.

---

## D. RESUMEN TOP CAUSAS RAÍZ

| Causa | Capa | Impacto |
|-------|------|--------|
| StrictMode en dev duplica mount y useEffects | Frontend | 2x requests en desarrollo |
| Remount al cambiar tab sin cache | Frontend | Repetición de todos los requests al volver a un tab |
| No hay cache compartido (geo, freshness, period-semantics) | Frontend + Backend | supply/geo, data-freshness, period-semantics llamados N veces por N vistas |
| Summary y drivers (e insight) como requests separados | Backend + Frontend | Más round-trips y recomputación en backend |
| Bug alias "ra" en WHERE sobre with_action | Backend | 500 con park_id (corregido en código) |
| Múltiples conexiones drill por múltiples requests drill | Backend | Esperado si el cliente hace 2 requests; se puede reducir duplicando menos desde el cliente |

---

## E. PRÓXIMOS PASOS (FASES 1–8)

- **Fase 1:** Instrumentación (logs por request: endpoint, params, tiempo, correlation id).
- **Fase 2:** Validar fix park_id en driver-behavior; tests de regresión para filtros dinámicos.
- **Fase 3:** Frontend: capa de datos con cache/deduplicación (React Query o módulo central) para geo, freshness, period-semantics; estabilizar dependencias de useCallback/useEffect.
- **Fase 4:** Backend: cache corto para data-freshness/global, period-semantics, supply/geo; opcionalmente unificar summary+drivers donde sea posible.
- **Fase 5:** SQL: EXPLAIN ANALYZE de queries clave; índices según planes; opcional MV o base compartida para driver behavior.
- **Fase 6–7:** Matriz vista/endpoints, normalización de hooks y keys, validación E2E.
- **Fase 8:** Documento entregables con cambios archivo por archivo y métricas before/after.

Este documento se actualizará con los resultados de instrumentación (Fase 1) y con los cambios aplicados en fases posteriores.

---

## F. ESTADO DE FASES (ACTUALIZADO)

| Fase | Estado | Notas |
|------|--------|--------|
| Fase 0 | Hecho | Scan frontend, backend y SQL documentado arriba. |
| Fase 1 | Hecho | Middleware en `main.py` (request_id, duration_ms, params para GET /ops/). Interceptor en `api.js` (dev: log método, URL, duración). |
| Fase 2 | Hecho | Fix alias "ra" en `driver_behavior_service.py`; tests en `tests/test_driver_behavior_drivers_park_id.py`. Validar en entorno real que 500 con park_id desapareció. |
| Fase 3–8 | Pendiente | Capa datos frontend, cache backend, SQL/índices, normalización, validación, entregables. |
