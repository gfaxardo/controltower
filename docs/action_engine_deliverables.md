# Action Engine + Top Driver Behavior — Deliverables

**Project:** YEGO Control Tower  
**Feature:** Action Engine + Top Driver Behavior (additive)  
**Date:** 2026-03-11

---

## 1. Implementation summary

- **Action Engine:** cohortes accionables derivados de Behavioral Alerts y Risk Score; priorización; recomendaciones; API y pestaña nueva.
- **Top Driver Behavior:** benchmarks y patrones Elite/Legend/FT; insights tipo playbook; API y sub-pestaña dentro de Action Engine.
- **Enfoque:** solo aditivo; no se han eliminado ni reemplazado módulos existentes (Migration, Behavioral Alerts, Supply, Driver Lifecycle).

---

## 2. Documentación creada

| Documento | Contenido |
|-----------|-----------|
| docs/action_engine_architecture_scan.md | Phase 0: fuentes de señal, frontend, APIs, proxies de valor, arquitectura recomendada, rutas legacy a no usar, plan de wiring. |
| docs/action_engine_logic.md | Definición de cohortes, prioridad, canal, capa de recomendaciones. |
| docs/top_driver_behavior_logic.md | Métricas, benchmarks, patrones, insights playbook, disponibilidad de datos. |
| docs/action_engine_ui_wiring_report.md | Verificación Phase 19: objeto SQL → servicio → ruta API → api.js → componente → tab; sin path legacy. |
| docs/action_engine_deliverables.md | Este archivo: archivos tocados, objetos SQL, API, pruebas, riesgos. |

---

## 3. Archivos tocados

### Backend (additive)

| Archivo | Cambio |
|---------|--------|
| backend/alembic/versions/086_action_engine_views.py | **Nuevo.** Vistas ops.v_action_engine_driver_base, v_action_engine_cohorts_weekly, v_action_engine_recommendations_weekly. |
| backend/alembic/versions/087_top_driver_behavior_views.py | **Nuevo.** Vistas ops.v_top_driver_behavior_weekly, v_top_driver_behavior_benchmarks, v_top_driver_behavior_patterns. |
| backend/app/services/action_engine_service.py | **Nuevo.** get_action_engine_summary, get_action_engine_cohorts, get_action_engine_cohort_detail, get_action_engine_recommendations, get_action_engine_export. |
| backend/app/services/top_driver_behavior_service.py | **Nuevo.** get_top_driver_behavior_summary, get_top_driver_behavior_benchmarks, get_top_driver_behavior_patterns, get_top_driver_behavior_playbook_insights, get_top_driver_behavior_export. |
| backend/app/routers/ops.py | **Añadido.** Rutas /ops/action-engine/* (summary, cohorts, cohort-detail, recommendations, export) y /ops/top-driver-behavior/* (summary, benchmarks, patterns, playbook-insights, export). Imports de los nuevos servicios. |

### Frontend (additive)

| Archivo | Cambio |
|---------|--------|
| frontend/src/App.jsx | **Añadido.** Botón de tab "Action Engine", import de ActionEngineView, render `activeTab === 'action_engine'`. |
| frontend/src/components/ActionEngineView.jsx | **Nuevo.** Sub-tabs Cohortes y Top Driver Behavior; filtros; KPIs; panel de acciones recomendadas; tabla de cohortes; drilldown; benchmarks/patrones/playbook; export; ayuda. |
| frontend/src/services/api.js | **Añadido.** getActionEngineSummary, getActionEngineCohorts, getActionEngineCohortDetail, getActionEngineRecommendations, getActionEngineExportUrl; getTopDriverBehaviorSummary, getTopDriverBehaviorBenchmarks, getTopDriverBehaviorPatterns, getTopDriverBehaviorPlaybookInsights, getTopDriverBehaviorExportUrl. |

---

## 4. Objetos SQL creados

| Objeto | Tipo | Descripción |
|--------|------|-------------|
| ops.v_action_engine_driver_base | VIEW | Driver-week con cohort_type (primera coincidencia); fuente: mv_driver_behavior_alerts_weekly. |
| ops.v_action_engine_cohorts_weekly | VIEW | Agregado por week_start, cohort_type: cohort_size, avg_risk_score, avg_delta_pct, avg_baseline_value, dominant_segment, suggested_priority, suggested_channel, action_name, action_objective. |
| ops.v_action_engine_recommendations_weekly | VIEW | Igual que cohorts + priority_score para ordenar el panel. |
| ops.v_top_driver_behavior_weekly | VIEW | Filtrar alerts por segment_current IN ('ELITE','LEGEND','FT'); consistency_score. |
| ops.v_top_driver_behavior_benchmarks | VIEW | Agregado por segment_current: driver_count, avg_weekly_trips, consistency_score_avg, active_weeks_avg. |
| ops.v_top_driver_behavior_patterns | VIEW | Agregado por segment_current, country, city, park_id: driver_count, avg_trips, pct_of_segment. |

---

## 5. API — Parámetros

### Action Engine

| Endpoint | Parámetros principales |
|----------|-------------------------|
| GET /ops/action-engine/summary | week_start, from, to, country, city, park_id, segment_current, cohort_type, priority |
| GET /ops/action-engine/cohorts | week_start, from, to, country, city, park_id, segment_current, cohort_type, priority, limit, offset |
| GET /ops/action-engine/cohort-detail | cohort_type (required), week_start (required), country, city, park_id, limit, offset |
| GET /ops/action-engine/recommendations | week_start, from, to, country, city, park_id, segment_current, top_n |
| GET /ops/action-engine/export | week_start, from, to, country, city, park_id, segment_current, cohort_type, priority, format (csv|excel), max_rows |

### Top Driver Behavior

| Endpoint | Parámetros principales |
|----------|-------------------------|
| GET /ops/top-driver-behavior/summary | week_start, from, to, country, city, park_id |
| GET /ops/top-driver-behavior/benchmarks | country, city, park_id (opcional; actualmente benchmarks globales) |
| GET /ops/top-driver-behavior/patterns | segment_current, country, city, limit |
| GET /ops/top-driver-behavior/playbook-insights | country, city |
| GET /ops/top-driver-behavior/export | segment_current, week_start, from, to, country, city, park_id, format, max_rows |

---

## 6. Componentes frontend y rutas usadas

- **Tab:** "Action Engine" en App.jsx → `activeTab === 'action_engine'` → `<ActionEngineView />`.
- **api.js:** Todas las llamadas usan baseURL (proxy /api en dev) y rutas `/ops/action-engine/*` y `/ops/top-driver-behavior/*`; no se usa /controltower ni /ops/behavior-alerts para estos datos.
- **ActionEngineView.jsx:** Monta sub-tabs "Cohortes y acciones" y "Top Driver Behavior"; carga datos con getActionEngine* y getTopDriverBehavior*; export con getActionEngineExportUrl y getTopDriverBehaviorExportUrl.

---

## 7. Instrucciones de prueba

1. **Backend:** `uvicorn app.main:app --host 127.0.0.1 --port 8000` (o el puerto configurado). Asegurar que la MV `ops.mv_driver_behavior_alerts_weekly` esté poblada (refresh si se usa MV).
2. **Frontend:** Arrancar el front (p. ej. `npm run dev`). Navegar a la pestaña "Action Engine".
3. **Action Engine – Cohortes:** Comprobar que se muestran KPIs (conductores accionables, cohortes detectados, etc.), panel de acciones recomendadas, tabla de cohortes. Aplicar filtros (fecha, país, ciudad). Clic en "Ver" en una cohorte → drilldown con lista de conductores. "Exportar CSV" debe descargar con filtros aplicados.
4. **Top Driver Behavior:** Cambiar al sub-tab "Top Driver Behavior". Comprobar resumen Elite/Legend/FT, tabla de benchmarks, lista de insights playbook, tabla de patrones. "Exportar Top Driver Behavior" debe respetar filtros.
5. **No regresiones:** Verificar que las pestañas Behavioral Alerts, Supply, Migration y Driver Lifecycle siguen funcionando igual.

---

## 8. Riesgos y refinamientos futuros

- **Rendimiento:** Las vistas se apoyan en `ops.mv_driver_behavior_alerts_weekly`. Si las consultas se vuelven lentas, valorar MVs para cohortes y recomendaciones (ops.mv_action_engine_cohorts_weekly, etc.) y refresco tras el de behavioral alerts.
- **Cohort_size con filtros:** Al filtrar por país/ciudad, la tabla de cohortes sigue mostrando el tamaño global del cohorte (week + tipo). El drilldown sí está filtrado. Opción futura: agregar tamaño filtrado en API.
- **Day-of-week / time-slot:** No implementado en Top Driver Behavior por no estar en la fuente actual; documentado en docs/top_driver_behavior_logic.md.
- **Playbook insights:** Actualmente reglas fijas (Elite vs FT consistencia, etc.). Futuro: más reglas o texto generado según benchmarks.

---

## 9. Criterios de éxito (comprobados)

- [x] Action Engine existe como capa accionable (cohortes + recomendaciones).
- [x] Top Driver Behavior existe y muestra patrones replicables (benchmarks, insights).
- [x] Ambos están conectados a la UI (tab Action Engine, sub-tab Top Driver Behavior).
- [x] No se usa path legacy para estos datos.
- [x] Export respeta filtros.
- [x] Módulos existentes (Behavioral Alerts, Migration, Supply, Driver Lifecycle) no han sido modificados en rutas ni tabs.
