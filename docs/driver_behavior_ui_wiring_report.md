# Driver Behavioral Deviation Engine — UI Wiring Report (Phase 18)

**Proyecto:** YEGO Control Tower  
**Objetivo:** Confirmar que la UI visible usa la cadena activa prevista y que ningún path legacy alimenta la pantalla Driver Behavior.

---

## Cadena activa verificada

| Capa | Origen | Detalle |
|------|--------|--------|
| **DB/Views** | ops.mv_driver_segments_weekly, ops.v_driver_last_trip, dim.v_geo_park, ops.v_dim_driver_resolved | Servicio construye SQL parametrizado con ventanas reciente/baseline; baseline excluye ventana reciente. |
| **Backend service** | backend/app/services/driver_behavior_service.py | get_driver_behavior_summary, get_driver_behavior_drivers, get_driver_behavior_driver_detail, get_driver_behavior_export. |
| **API routes** | backend/app/routers/ops.py | GET /ops/driver-behavior/summary, /ops/driver-behavior/drivers, /ops/driver-behavior/driver-detail, /ops/driver-behavior/export. Router montado bajo prefijo /ops (app principal). |
| **Frontend API** | frontend/src/services/api.js | getDriverBehaviorSummary, getDriverBehaviorDrivers, getDriverBehaviorDriverDetail, getDriverBehaviorExportUrl — todos apuntan a /ops/driver-behavior/*. |
| **Componente** | frontend/src/components/DriverBehaviorView.jsx | Usa únicamente las cuatro funciones anteriores para KPIs, tabla, drilldown y export. |
| **Tab visible** | frontend/src/App.jsx | Tab “Driver Behavior” (activeTab === 'driver_behavior') renderiza <DriverBehaviorView />. |

---

## Confirmaciones

1. **Ningún legacy alimenta la pantalla Driver Behavior:**  
   - No se llama a getBehaviorAlertsSummary, getBehaviorAlertsDrivers, getBehaviorAlertsDriverDetail ni getBehaviorAlertsExportUrl en DriverBehaviorView.  
   - No se llama a getActionEngineSummary, getActionEngineCohorts, getActionEngineExportUrl ni ningún endpoint de action-engine en DriverBehaviorView.  
   - La tabla, KPIs, drilldown y export usan exclusivamente getDriverBehaviorSummary, getDriverBehaviorDrivers, getDriverBehaviorDriverDetail y getDriverBehaviorExportUrl.

2. **Filtros y export:**  
   Los mismos filtros (recent_weeks, baseline_weeks, as_of_week, country, city, park_id, segment_current, alert_type, severity, risk_band, inactivity_status, min_baseline_trips) se envían a summary, drivers y export. La URL de export se construye con getDriverBehaviorExportUrl(filters), por lo que el CSV respeta los filtros activos.

3. **Drilldown:**  
   Al abrir detalle de un conductor se llama getDriverBehaviorDriverDetail({ driver_key, recent_weeks, baseline_weeks, as_of_week }). El modal muestra data + weekly serie desde el mismo backend/driver_behavior_service.

---

## Rutas y archivos tocados (resumen)

- **Backend:** app/services/driver_behavior_service.py, app/routers/ops.py  
- **Frontend:** src/services/api.js (nuevas funciones), src/App.jsx (tab + DriverBehaviorView), src/components/DriverBehaviorView.jsx (nuevo)  
- **SQL:** ops.v_driver_last_trip (migración 089); lógica de ventanas y agregados en el servicio (sin nuevas vistas públicas además de v_driver_last_trip).

---

## Conclusión

La UI visible del módulo Driver Behavior está alimentada únicamente por la cadena DB → driver_behavior_service → /ops/driver-behavior/* → api.js (driver-behavior) → DriverBehaviorView → tab “Driver Behavior”. No se utiliza la cadena de Behavioral Alerts ni de Action Engine para esta pantalla.
