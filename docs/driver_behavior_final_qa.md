# Driver Behavioral Deviation Engine — QA y entregables (Phase 21)

**Proyecto:** YEGO Control Tower  
**Módulo:** Driver Behavior (additive, no destructivo)

---

## 1. Implementación entregada

- Capa de datos: ventanas reciente/baseline sobre `ops.mv_driver_segments_weekly` + `ops.v_driver_last_trip`; agregados y clasificación en `driver_behavior_service.py`.  
- API: GET /ops/driver-behavior/summary, /drivers, /driver-detail, /export.  
- Frontend: tab “Driver Behavior”, DriverBehaviorView (filtros, KPIs, tabla, drilldown, ayuda, export).  
- Documentación: scan, propuesta, lógica, wiring, render validation, este QA.

---

## 2. Documentos creados

| Documento | Contenido |
|-----------|-----------|
| docs/driver_behavior_deviation_scan.md | Scan arquitectónico (fuentes driver-week, identificador, campos, qué no tocar). |
| docs/driver_behavior_deviation_proposal.md | Propuesta técnica/UX (modelo, datos, alertas, risk, API, UX). |
| docs/driver_behavior_logic.md | Reglas: ventanas, días sin viaje, alertas, estado conductual, risk score, acción. |
| docs/driver_behavior_ui_wiring_report.md | Cadena DB → servicio → ruta → api → componente → tab; confirmación de no uso de paths legacy. |
| docs/driver_behavior_render_validation.md | Pasos de validación manual y preguntas que el usuario debe poder responder. |
| docs/driver_behavior_final_qa.md | Este archivo: checklist, archivos tocados, riesgos. |

---

## 3. Archivos tocados

- **Backend:**  
  - backend/app/services/driver_behavior_service.py (nuevo)  
  - backend/app/routers/ops.py (import + 4 endpoints driver-behavior)  
- **Migración:**  
  - backend/alembic/versions/089_driver_behavior_deviation_last_trip.py (crea ops.v_driver_last_trip)  
- **Frontend:**  
  - frontend/src/services/api.js (getDriverBehaviorSummary, getDriverBehaviorDrivers, getDriverBehaviorDriverDetail, getDriverBehaviorExportUrl)  
  - frontend/src/App.jsx (import DriverBehaviorView, tab “Driver Behavior”, render condicional)  
  - frontend/src/components/DriverBehaviorView.jsx (nuevo)  
- **Docs:**  
  - docs/driver_behavior_deviation_scan.md  
  - docs/driver_behavior_deviation_proposal.md  
  - docs/driver_behavior_logic.md  
  - docs/driver_behavior_ui_wiring_report.md  
  - docs/driver_behavior_render_validation.md  
  - docs/driver_behavior_final_qa.md  

---

## 4. Objetos SQL creados

- **ops.v_driver_last_trip:** driver_key, last_trip_date (desde ops.v_driver_lifecycle_trips_completed).  
- No se han creado vistas adicionales públicas; la lógica de desviación (ventanas, alertas, risk) está en el servicio (SQL dinámico contra mv_driver_segments_weekly y v_driver_last_trip).

---

## 5. Rutas API creadas

- GET /ops/driver-behavior/summary  
- GET /ops/driver-behavior/drivers  
- GET /ops/driver-behavior/driver-detail  
- GET /ops/driver-behavior/export  

---

## 6. Componentes frontend creados

- DriverBehaviorView.jsx: filtros (ventanas, geo, segmento, alert_type, severity, risk_band, inactivity_status, min_baseline_trips), KPIs, tabla, modal de detalle con timeline opcional, panel de ayuda, enlace de export CSV.

---

## 7. Comportamiento de export

- El export usa los mismos filtros que la pantalla (recent_weeks, baseline_weeks, as_of_week, country, city, park_id, segment_current, alert_type, severity, risk_band, inactivity_status).  
- Formato CSV; columnas: driver_key, driver_name, country, city, park_name, recent_window_weeks, baseline_window_weeks, recent_avg_weekly_trips, baseline_avg_weekly_trips, delta_pct, behavior_direction, days_since_last_trip, alert_type, risk_score, risk_band, suggested_action.

---

## 8. Notas de QA y pruebas

- Ejecutar `alembic upgrade head` en el backend para crear `ops.v_driver_last_trip` antes de probar.  
- Comprobar que las pestañas Behavioral Alerts y Action Engine siguen funcionando sin cambios (módulo additive).  
- Seguir los pasos de docs/driver_behavior_render_validation.md para validación manual.  
- Si no hay datos en mv_driver_segments_weekly o v_driver_last_trip, los KPIs pueden ser 0 y la tabla vacía; no indica fallo del módulo.

---

## 9. Riesgos y refinamientos futuros

- **Rendimiento:** Con muchos conductores y ventanas grandes, los queries pueden ser pesados; valorar MV materializada (p. ej. ops.mv_driver_behavior_deviation_base) si hace falta.  
- **Sustained Degradation en summary:** El summary actual no incluye declining_weeks en su CTE, por lo que el conteo de “Sustained Degradation” en KPIs puede ser 0; la tabla sí muestra alert_type “Sustained Degradation” cuando aplica. Refinamiento: añadir lógica de rachas al summary si se requiere el KPI.  
- **Umbrales:** Los umbrales de inactividad (0–3, 4–7, 8–14, 15+) y de alertas (delta_pct -30%, -15%, +25%) son configurables en código; en el futuro podrían venir de configuración o backend.  
- **driver_name:** Depende de ops.v_dim_driver_resolved (o equivalente); si no existe, se muestra driver_key.
