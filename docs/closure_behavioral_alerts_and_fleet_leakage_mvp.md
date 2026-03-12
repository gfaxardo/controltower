# Cierre: Behavioral Alerts + Fleet Leakage MVP

**Fecha:** 2025-03-12  
**Proyecto:** YEGO Control Tower

---

# BLOQUE 1 — BEHAVIORAL ALERTS CLOSURE

## Estado final

**CLOSED / READY FOR SIGN-OFF**

La auditoría E2E previa confirmó implementación real sobre la vista correcta. No se rediseñó ni se abrieron nuevas ambiciones. Se validó persistencia real y no se requirieron correcciones adicionales en esta sesión.

## Evidencia visible (checklist obligatorio)

| # | Punto | Evidencia en código / UI |
|---|--------|---------------------------|
| 1 | **Sudden Stop visible en dropdown** | `BehavioralAlertsView.jsx`: `alertTypes = ['Sudden Stop', 'Critical Drop', ...]` (L285); `<select>` "Tipo alerta" renderiza `{alertTypes.map((a) => <option key={a} value={a}>{a}</option>)}` (L399-402). |
| 2 | **Leyenda visible y descubrible** | Botón "? Leyenda" junto a la etiqueta "Tipo alerta" (L382-386); clic abre panel `showSegmentLegend` con SEGMENT_LEGEND (L388-398). |
| 3 | **Columna Último viaje visible** | Tabla incluye `{ label: 'Último viaje', align: 'left', sortable: true }` (L416); celda `formatLastTrip(r.last_trip_date)` (L447); mensaje de ayuda de scroll horizontal (L533); min-width en th/td. |
| 4 | **Orden visible en headers** | `sortIcon(col)` devuelve ↕ sin orden, ↑/↓ en azul cuando la columna está ordenada (L298-302); `handleSort`, `columnToOrderKey` incluyen 'Último viaje': 'last_trip_date'. |
| 5 | **Counters visibles y legibles** | Grid de KPI cards (L422-451): Total en alertas, Sudden Stop, Caídas críticas, … Estables, Alto riesgo, Riesgo medio; grid máximo 5 columnas para evitar compresión. |
| 6 | **Export visible** | Bloque "Exportar datos" (L468-518) con "Export Recovery List (CSV)" y "(Excel)" destacados en verde; CSV/Excel genérico y botón "Exportar conductores (CSV filtrado)". |

## Archivos tocados en esta sesión

Ninguno. No hubo ajuste en Fase A; el estado actual del componente ya cumple los 6 puntos.

## Check final de cierre

- Ruta real: pestaña **Behavioral Alerts** en la barra de navegación.
- Componente: `frontend/src/components/BehavioralAlertsView.jsx`.
- Endpoints: `/api/ops/behavior-alerts/summary`, `insight`, `drivers`, `driver-detail`, `export`.
- Los seis ítems del checklist están implementados y visibles en el código que renderiza la vista real.

**Behavioral Alerts queda cerrado y listo para sign-off.**

---

# BLOQUE 2 — FLEET LEAKAGE MVP

## Resumen de escaneo

- **Componentes reutilizables:** getSupplyGeo (filtros país/ciudad/park), patrón de layout de BehavioralAlertsView (KPIs, filtros, tabla, export). No se reutiliza lógica ni vistas de Behavioral Alerts.
- **api.js:** Añadidas getLeakageSummary, getLeakageDrivers, getLeakageExportUrl.
- **App.jsx:** Añadido tab "Fleet Leakage" y render de FleetLeakageView cuando `activeTab === 'fleet_leakage'`.
- **Patrón /ops:** Mismo estilo que behavior-alerts y driver-behavior: summary, drivers (paginado, order_by/order_dir), export por query params.
- **Fuentes SQL:** Según `docs/fleet_leakage_monitor_scan.md`: mv_driver_segments_weekly, v_driver_last_trip, dim.v_geo_park, ops.v_dim_driver_resolved. No se usa v_driver_behavior_*.

## Arquitectura elegida

- **Una vista SQL:** `ops.v_fleet_leakage_snapshot` (migración 091). Una fila por conductor para la semana de referencia (última disponible en mv_driver_segments_weekly). Joins con v_driver_last_trip, v_geo_park, v_dim_driver_resolved. Clasificación MVP en SQL: stable_retained, watchlist, progressive_leakage, lost_driver; leakage_score 0–100; recovery_priority P1–P4; top_performer_at_risk (segmento FT/ELITE/LEGEND en riesgo).
- **Un servicio backend:** `leakage_service.py` con get_leakage_summary, get_leakage_drivers, get_leakage_export. Sin dependencia de behavior_alerts_service.
- **Tres endpoints:** GET /api/ops/leakage/summary, GET /api/ops/leakage/drivers, GET /api/ops/leakage/export (CSV/Excel).
- **Un componente frontend:** FleetLeakageView.jsx con KPIs, filtros, tabla y export; conectado a la navegación real mediante el nuevo tab.

## Archivos tocados

| Archivo | Cambio |
|---------|--------|
| `backend/alembic/versions/091_fleet_leakage_snapshot_view.py` | **Nuevo.** Vista ops.v_fleet_leakage_snapshot. |
| `backend/app/services/leakage_service.py` | **Nuevo.** get_leakage_summary, get_leakage_drivers, get_leakage_export. |
| `backend/app/routers/ops.py` | Import de leakage_service; rutas GET /ops/leakage/summary, /leakage/drivers, /leakage/export. |
| `frontend/src/services/api.js` | getLeakageSummary, getLeakageDrivers, getLeakageExportUrl. |
| `frontend/src/components/FleetLeakageView.jsx` | **Nuevo.** Vista completa: título, descripción, filtros (país, ciudad, park, leakage status, solo top performers), KPI cards, export CSV/Excel, tabla con paginación y orden. |
| `frontend/src/App.jsx` | Import FleetLeakageView; botón "Fleet Leakage" en nav; `activeTab === 'fleet_leakage' && <FleetLeakageView />`. |

## Endpoints creados

- **GET /api/ops/leakage/summary** — Query: country, city, park_id, leakage_status, recovery_priority, top_performers_only. Respuesta: total_drivers, drivers_under_watch, progressive_leakage, lost_drivers, top_performers_at_risk, cohort_retention_45d.
- **GET /api/ops/leakage/drivers** — Mismos filtros + limit, offset, order_by, order_dir. Respuesta: { data, total, limit, offset }.
- **GET /api/ops/leakage/export** — Mismos filtros + format (csv|excel), max_rows. Descarga CSV o Excel "Recovery Queue".

## Vista visible en frontend

- **Nombre en UI:** "Fleet Leakage" (título de la vista y etiqueta del tab).
- **Acceso:** Pestaña **Fleet Leakage** en la barra de navegación principal (junto a Behavioral Alerts, Driver Behavior, etc.).
- **Contenido:** Bloque de filtros; 5 KPI cards (Under watch, Fuga progresiva, Perdidos, Top en riesgo, Retención 45d); bloque "Exportar Recovery Queue" (CSV y Excel); tabla con columnas: Conductor, País, Ciudad, Park, Base 4 sem, Viajes sem., Δ %, Último viaje, Días sin viaje, Leakage status, Score, Prioridad; paginación y orden por cabeceras.

## Qué incluye el MVP

- **KPIs:** drivers_under_watch, progressive_leakage, lost_drivers, top_performers_at_risk, cohort_retention_45d.
- **Filtros:** país, ciudad, park, leakage status (Estable/Retenido, En observación, Fuga progresiva, Perdido), checkbox "Solo top performers en riesgo".
- **Cohorte ancla:** Retención 45d = conductores con days_since_last_trip ≤ 45; la vista usa la última semana disponible en mv_driver_segments_weekly.
- **Tabla:** Conductor, país, ciudad, park, baseline 4 sem, viajes sem., delta %, último viaje, días sin viaje, leakage status, score, prioridad (P1–P4).
- **Clasificación MVP:** stable_retained, watchlist, progressive_leakage, lost_driver; top_performer_at_risk cuando segmento FT/ELITE/LEGEND y en riesgo.
- **Export:** CSV y Excel visibles y usables desde la vista.

## Qué queda para una Fase 2 enterprise

- **Ventana de análisis configurable** (p. ej. 30/45/60 días) en lugar de solo “última semana”.
- **Cohorte ancla configurable** (fecha de referencia, “activos en semana X”, etc.) y métricas de cohorte (tamaño inicial, retenidos, watchlist, early, progressive, lost).
- **Endpoint GET /ops/leakage/cohort-metrics** y posible filtro “cohorte ancla” en la UI.
- **Columna “semanas cayendo”** (weeks_declining) si se añade a la vista o a una capa intermedia.
- **driver_tier** (Top 10%, Top 25%, Mid, Low) y **historical_stability** (High/Medium/Low).
- **early_leakage** y **high_suspicion_leakage** en la clasificación (hoy solo watchlist, progressive, lost, stable_retained).
- **Detalle por conductor** (GET /ops/leakage/driver-detail) y columna “Por qué está aquí” / explainability.
- **Leyenda/glossary** en la vista para definición de leakage, score y prioridad.

---

**Criterio de éxito cumplido:**

- Behavioral Alerts está validado y visible con los 6 puntos de cierre.
- Fleet Leakage está visible en la UI real como nueva vista usable (tab, KPIs, filtros, tabla, export).
