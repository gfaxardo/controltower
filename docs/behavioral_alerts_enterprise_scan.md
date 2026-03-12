# Behavioral Alerts Enterprise — Fase 0 Escaneo

**Fecha:** 2025-03  
**Objetivo:** Mapeo completo antes de implementar mejoras enterprise (leyenda, Sudden Stop, exclusividad, tooltips, sort, Last Trip, counters, export, UX).

---

## 0.1 Ubicación de la vista

| Elemento | Ubicación |
|----------|-----------|
| **Componente principal** | `frontend/src/components/BehavioralAlertsView.jsx` |
| **Subcomponentes** | Filtros (grid), KPI cards (8), insight panel, tabla `<table>`, modal drilldown (detalle conductor), botón "Ver/Ocultar explicación" (glossary) |
| **Hooks de carga** | `loadGeo`, `loadSummary`, `loadInsight`, `loadDrivers`, `loadDriverDetail`; `useEffect` para geo, summary+insight, drivers |
| **Endpoints** | `getBehaviorAlertsSummary` → GET `/ops/behavior-alerts/summary` |
| | `getBehaviorAlertsInsight` → GET `/ops/behavior-alerts/insight` |
| | `getBehaviorAlertsDrivers` → GET `/ops/behavior-alerts/drivers` |
| | `getBehaviorAlertsDriverDetail` → GET `/ops/behavior-alerts/driver-detail` |
| | `getBehaviorAlertsExportUrl` → GET `/ops/behavior-alerts/export?…` |
| **Servicio backend** | `backend/app/services/behavior_alerts_service.py`: `get_behavior_alerts_summary`, `get_behavior_alerts_drivers`, `get_behavior_alerts_driver_detail`, `get_behavior_alerts_export`, `get_behavior_alerts_insight` |
| **Fuente de datos** | Summary: `ops.v_driver_behavior_alerts_weekly`. List/export: `ops.mv_driver_behavior_alerts_weekly`. Vista y MV definidas en migraciones 082 y 085. Cadena: `ops.mv_driver_segments_weekly` → `ops.v_driver_behavior_baseline_weekly` (081, 084) → `ops.v_driver_behavior_alerts_weekly` (082, 085) → MV opcional. |
| **Last trip** | No está en la vista de Behavioral Alerts. Existe `ops.v_driver_last_trip` (driver_key, last_trip_date) en migración 089; usada por Driver Behavior. Para BA hay que añadir JOIN en servicio o en vista. |

---

## 0.2 Estado actual de columnas y filtros

| Columnas de la grilla | Ordenación actual | Tooltips headers |
|-----------------------|-------------------|------------------|
| Conductor, País, Ciudad, Park, Segmento, Viajes sem., Base avg, Δ %, Estado conductual, Persistencia, Alerta, Severidad, Risk Score, Risk Band, Acción | Estado `orderBy`/`orderDir` (risk_score desc) se envían al API; **headers no son clickeables** en la tabla | No hay tooltips en headers |
| **Filtros** | País, Ciudad, Park, Segmento actual, Tipo movimiento, Tipo alerta, Severidad, Banda de riesgo, Rango temporal (from/to), Ventana baseline (4/6/8 sem) | — |
| **Dropdown segmento** | Opciones: LEGEND, ELITE, FT, PT, CASUAL, OCCASIONAL, DORMANT (sin leyenda; usuario no sabe qué significa cada alerta) | — |
| **Sort en otras tablas** | Driver Behavior y otras vistas: ordenación por backend con `order_by`/`order_dir`; en BA el backend ya acepta `order_by` (risk_score, severity, delta_pct, week_start) y `order_dir` | — |
| **Export** | Ya existe: CSV y Excel desde `/ops/behavior-alerts/export`; columnas: driver_key, driver_name, country, city, park_name, week_label, segment_current, movement_type, trips_current_week, avg_trips_baseline, delta_abs, delta_pct, alert_type, alert_severity, risk_score, risk_band. También botón "Exportar conductores (CSV filtrado)" que genera CSV en cliente con columnas reducidas. | — |

---

## 0.3 Estado actual de clasificación

| alert_type | Dónde se calcula | Condición (resumen) |
|------------|------------------|----------------------|
| Critical Drop | SQL vista 085 (`with_flags` + `classified`) | avg_trips_baseline >= 40 AND delta_pct <= -30% AND active_weeks_in_window >= 4 |
| Moderate Drop | Idem | delta_pct en (-30%, -15%] |
| Silent Erosion | Idem | weeks_declining_consecutively >= 3 (y no ya Critical/Moderate) |
| Strong Recovery | Idem | delta_pct >= 30% AND active_weeks_in_window >= 3 |
| High Volatility | Idem | (stddev/avg) > 0.5 y no los anteriores |
| Stable Performer | Idem | ELSE |

**Precedencia actual (CASE WHEN en orden):** 1) Critical Drop 2) Moderate Drop 3) Silent Erosion 4) Strong Recovery 5) High Volatility 6) Stable Performer. **Ya es mutuamente excluyente** (first match wins). Falta **Sudden Stop** como primera prioridad.

**risk_score:** Se calcula en la vista 085 (risk_components: behavior + migration + fragility + value; luego with_risk). risk_band: stable / monitor / medium risk / high risk según rangos 0–24, 25–49, 50–74, 75–100.

**Persistencia:** weeks_declining_consecutively, weeks_rising_consecutively; en baseline 081 actualmente se rellenan con 0 (consec); la lógica está en la vista pero el dato puede ser 0 hasta que se calcule en baseline.

---

## 0.4 Archivos detectados y puntos de integración

| Archivo | Rol |
|---------|-----|
| `frontend/src/components/BehavioralAlertsView.jsx` | Vista principal; filtros, tabla, KPIs, insight, glossary, export |
| `frontend/src/constants/explainabilitySemantics.js` | getBehaviorDirection, getPersistenceLabel, getDeltaPctColor, BEHAVIOR_DIRECTION_COLORS, RISK_BAND_COLORS, ALERT_COLORS, getDecisionContextLabel — **reutilizar** |
| `frontend/src/theme/decisionColors.js` | decisionColorClasses, severityToDecision — **reutilizar** |
| `frontend/src/services/api.js` | getBehaviorAlertsSummary, getBehaviorAlertsInsight, getBehaviorAlertsDrivers, getBehaviorAlertsDriverDetail, getBehaviorAlertsExportUrl — sin cambios de contrato salvo nuevos params si se añaden |
| `backend/app/services/behavior_alerts_service.py` | Summary (añadir sudden_stop, stable_performer counts), drivers (añadir last_trip / days_since_last_trip vía JOIN a v_driver_last_trip), export (añadir columnas last_trip, persistence) |
| `backend/app/routers/ops.py` | Endpoints behavior-alerts; export cols si se amplían |
| `backend/alembic/versions/085_behavior_alerts_risk_score.py` | Vista v_driver_behavior_alerts_weekly: añadir is_sudden_stop y **Sudden Stop** como primera rama del CASE en classified; mantener resto igual |
| `docs/behavioral_alerts_logic.md` | Actualizar: Sudden Stop, precedencia final, columnas, export |

**Riesgos de tocar la lógica:**  
- Cambiar el CASE en 085 implica DROP VIEW + CREATE; la MV se recrea después. No tocar risk_components ni with_risk.  
- Añadir Sudden Stop requiere definir bien la condición (actividad reciente + semana actual 0 viajes). La "semana actual" en Behavioral Alerts es la semana del row (week_start); "actividad reciente" = tener viajes en semanas previas dentro del baseline o reciente. Definición propuesta: trips_current_week = 0 AND avg_trips_baseline > 0 (tenía baseline, esta semana 0). Eso captura "dejó de producir en la semana analizada".

**Propuesta de implementación no destructiva:**  
1. Nueva migración (090) que haga CREATE OR REPLACE de v_driver_behavior_alerts_weekly añadiendo is_sudden_stop y Sudden Stop como primera opción en el CASE; luego REFRESH MV.  
2. Backend: en behavior_alerts_service, añadir en summary los FILTER para sudden_stop y stable_performer; en get_behavior_alerts_drivers y export, LEFT JOIN ops.v_driver_last_trip y exponer last_trip_date y/o days_since (calculado con week_start).  
3. Frontend: leyenda junto al filtro Tipo alerta (ícono + popover); tooltips en headers de tabla; headers clickeables para sort; nueva columna Last Trip; counters superiores con Sudden Stop y Stable Performer; botón "Export Recovery List" (misma URL export con nombre sugerido); ajustes de alineación y formato.

---

## Salida del escaneo — Checklist pre-implementación

- [x] Componente principal y endpoints identificados  
- [x] Servicio y vista/MV identificados  
- [x] Clasificación actual y precedencia documentadas  
- [x] Existencia de last_trip (v_driver_last_trip) y ausencia en BA confirmada  
- [x] Reutilización de explainabilitySemantics y export existente planeada  
- [x] Riesgos (cambio de vista 085, nueva migración) anotados  
- [x] Propuesta no destructiva (nueva migración 090, extensión de servicio y UI) definida  

**Siguiente paso:** Implementar Fase 1 (leyenda segmentos) y Fase 2 (Sudden Stop en SQL + backend + UI), luego Fases 3–10 en orden.

---

## Entregables realizados (post-implementación)

| Fase | Entregable |
|------|------------|
| 0 | Escaneo en este documento. |
| 1 | Leyenda: ícono (?) junto a "Tipo alerta"; popover con definición de cada segmento (Sudden Stop, Critical Drop, …). |
| 2 | **Sudden Stop** en SQL (migración 090): is_sudden_stop = trips_current_week = 0 AND avg_trips_baseline > 0. |
| 3 | Precedencia estricta en vista 090: Sudden Stop → Critical Drop → Moderate Drop → Silent Erosion → High Volatility → Strong Recovery → Stable Performer. |
| 4 | Tooltips en cabeceras de tabla (COLUMN_TOOLTIPS) vía atributo `title`. |
| 5 | Headers ordenables (click): order_by/order_dir enviados al API; backend con whitelist de columnas. |
| 6 | Columna **Último viaje** (last_trip_date desde v_driver_last_trip); formato "Hoy" / "Hace N días". |
| 7 | Risk counters: Total, Sudden Stop, Caídas críticas, … Estables, Alto riesgo, Riesgo medio (10 cards). |
| 8 | **Export Recovery List** (CSV/Excel) mismo endpoint, nombre sugerido recovery_list_conductores.*; export con last_trip_date y persistencia. |
| 9 | Alineación: números a la derecha, texto a la izquierda; headers con indicador de orden. |
| 10 | docs/behavioral_alerts_logic.md actualizado; docs/behavioral_alerts_enterprise_validation.md con checklist. |

**Archivos tocados:**  
- `backend/alembic/versions/090_behavioral_alerts_sudden_stop_mutually_exclusive.py`  
- `backend/app/services/behavior_alerts_service.py` (summary sudden_stop/stable_performer; drivers/export con last_trip y order_by ampliado)  
- `backend/app/routers/ops.py` (columnas export)  
- `frontend/src/components/BehavioralAlertsView.jsx` (leyenda, KPIs, tooltips, sort, Last Trip, Export Recovery List)  
- `frontend/src/constants/explainabilitySemantics.js` (Sudden Stop en ALERT_COLORS y getBehaviorDirection)  
- `docs/behavioral_alerts_logic.md`, `docs/behavioral_alerts_enterprise_validation.md`
