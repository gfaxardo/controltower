# Driver Behavioral Deviation Engine — Propuesta técnica y UX

**Project:** YEGO Control Tower  
**Date:** 2026-03-11  
**Modo:** Aditivo; no reemplaza Behavioral Alerts ni Action Engine.

---

## 1. Objetivo del módulo

Responder a nivel **conductor**:

- ¿Qué conductores están empeorando o recuperándose respecto a su propio historial?
- ¿En cuánto? (delta %)
- ¿Desde cuándo? (semanas consecutivas, días desde último viaje)
- ¿Qué tan urgente es actuar? (risk score, banda)
- ¿Qué acción y canal sugerir?

**Capas:**

- **Macro (existente):** evolución semanal, supply, migración, cohortes — sin cambios.
- **Micro / operativa (nueva):** desviación por conductor, ventanas de baseline, inactividad, recuperación, urgencia.

---

## 2. Modelo conceptual (Phase 1)

- **Ventana reciente (recent window):** últimas N semanas (ej. 4).
- **Ventana baseline:** M semanas **anteriores** a la reciente, sin solapamiento (ej. 16).
- **Referencia:** semana “as-of” = última semana cerrada en datos o seleccionada.
- **Métricas por conductor:**
  - recent_avg_weekly_trips = media de viajes/semana en ventana reciente.
  - baseline_avg_weekly_trips = media en ventana baseline.
  - delta_pct = (recent_avg - baseline_avg) / baseline_avg.
- **Opciones UI:** recent_window ∈ {4, 8, 16, 32}, baseline_window ∈ {8, 16, 32}; combinaciones válidas (baseline excluye la reciente).

---

## 3. Capa de datos (Phase 2)

- **ops.v_driver_last_trip:** driver_key, last_trip_date (desde ops.v_driver_lifecycle_trips_completed). Para days_since_last_trip e inactivity_status.
- **Lógica driver-level:** en **servicio backend** (SQL parametrizado) sobre ops.mv_driver_segments_weekly + geo + nombre + v_driver_last_trip:
  - Agregar por conductor con ventanas configurables (recent_weeks, baseline_weeks, reference_week).
  - Calcular: recent_window_trips, recent_avg_weekly_trips, baseline_* , delta_abs, delta_pct, z_score_simple, declining_weeks_consecutive, rising_weeks_consecutive, current_segment (última semana en ventana reciente).
  - Unir days_since_last_trip = (reference_date - last_trip_date); inactivity_status (Active / Cooling / Dormant Risk / Churn Risk).
  - Clasificar alert_type, severity, risk_score, risk_band, suggested_action, suggested_channel, rationale_short.

No se crean vistas estáticas con ventanas fijas; la flexibilidad se resuelve en el servicio.

---

## 4. Días desde último viaje (Phase 3)

- **days_since_last_trip:** (fecha de referencia del cierre de la ventana reciente − last_trip_date). Fecha de referencia = fin de la última semana de la ventana reciente (o CURRENT_DATE si es la semana actual).
- **inactivity_status:**
  - Active: 0–3 días
  - Cooling: 4–7 días
  - Dormant Risk: 8–14 días
  - Churn Risk: 15+ días

Umbrales documentados; en el futuro pueden ser configurables.

---

## 5. Clasificación de alertas (Phase 4)

| alert_type | Regla |
|------------|--------|
| Sharp Degradation | delta_pct ≤ -30% |
| Moderate Degradation | -30% < delta_pct ≤ -15% |
| Sustained Degradation | declining_weeks_consecutive ≥ 3 (y no ya Sharp/Moderate por delta) |
| Recovery | delta_pct ≥ +25% |
| Dormant Risk | days_since_last_trip ≥ 8 |
| High Volatility | baseline_stddev / baseline_avg alto (ej. > 0.5) y no encaja en otros |
| Stable | resto |

Prioridad de aplicación: Dormant Risk y degradaciones tienen prioridad; luego Recovery, Volatility, Stable. severity: critical / moderate / positive / neutral según alert_type.

---

## 6. Dirección conductual (Phase 5)

Campo visible **Estado conductual / Behavior direction:**

- **Empeorando:** delta negativo y/o declining_weeks ≥ 2.
- **Recuperando:** delta positivo y recovery o rising_weeks.
- **Mejorando:** delta positivo sin “recuperación” fuerte.
- **Estable:** delta cercano a cero, sin streaks fuertes.
- **Volátil:** High Volatility o alta variabilidad.

Derivado de delta_pct, declining_weeks_consecutive, rising_weeks_consecutive, alert_type.

---

## 7. Risk score 0–100 (Phase 6)

- **A) Severidad desviación (0–40):** magnitud del delta negativo (y opcionalmente z_score).
- **B) Persistencia (0–20):** declining_weeks_consecutive.
- **C) Inactividad (0–20):** days_since_last_trip (más días = más puntos).
- **D) Valor/operatividad (0–20):** baseline_avg y/o segmento actual.

Bandas: 0–24 stable, 25–49 monitor, 50–74 medium risk, 75–100 high risk.

**risk_explanation_short:** texto corto, ej. “-52% vs baseline, 3 semanas empeorando, 9 días sin viaje”.

---

## 8. Acción sugerida (Phase 7)

- **suggested_action:** preventive outreach, reactivation WhatsApp, outbound retention call, loyalty call, monitor only, coaching, etc.
- **suggested_channel:** outbound_call, whatsapp, loyalty_call, diagnostic_contact, monitor_only.
- **rationale_short:** una frase operativa.

Reglas por alert_type y risk_band (ej. Dormant Risk → reactivation; Sharp Degradation → retention call).

---

## 9. API (Phase 8)

- GET /ops/driver-behavior/summary
- GET /ops/driver-behavior/drivers
- GET /ops/driver-behavior/driver-detail
- GET /ops/driver-behavior/export (CSV)

Filtros: recent_window, baseline_window, country, city, park_id, segment_current, alert_type, severity, risk_band, inactivity_status, min_baseline_trips (opcional). Export respeta los mismos filtros.

---

## 10. UX (Phases 9–16)

- **Tab:** “Driver Behavior” junto a Behavioral Alerts y Action Engine.
- **Filtros:** ventanas, país, ciudad, parque, segmento, alert_type, severity, risk_band, inactivity_status; opcionales min baseline trips / min delta.
- **KPIs:** conductores monitoreados, sharp degradation, sustained degradation, recovery, dormant risk, high value at risk, avg days since last trip.
- **Tabla principal:** Driver, País, Ciudad, Parque, Segmento, Recent avg trips, Baseline avg, Delta %, Estado conductual, Días desde último viaje, Persistencia, Alert type, Risk score, Risk band, Suggested action, Acción (drilldown).
- **Drilldown:** ventanas usadas, timeline de viajes, segment history, baseline vs recent, days_since_last_trip, streaks, explicación del risk score, acción y rationale; gráfico de tendencia si hay datos.
- **Panel de ayuda:** explicación de ventana reciente, baseline, delta, days_since_last_trip, estado conductual, alert_type, risk score, acción; aclaración de que los módulos semanales existentes siguen siendo macro.
- **Colores:** empeorando/rojo, recuperando/mejorando/verde, estable/gris, volátil/morado, moderate/ámbar; risk high/red, medium/amber, monitor/azul, stable/neutral; inactivity active/green, cooling/amber, dormant/churn/red. Delta negativo/rojo, positivo/verde, cero/gris.
- **Export:** CSV con driver_key, driver_name, country, city, park_name, recent_window, baseline_window, recent_avg_trips, baseline_avg_trips, delta_pct, days_since_last_trip, alert_type, risk_score, risk_band, suggested_action.

---

## 11. Verificación y entregables

- **Wiring:** docs/driver_behavior_ui_wiring_report.md — cadena DB → servicio → ruta → frontend → tab visible.
- **Render:** docs/driver_behavior_render_validation.md — pasos para validar que el usuario puede responder: ¿empeora o mejora?, ¿respecto a qué baseline?, ¿desde cuándo?, ¿días sin viaje?, ¿urgencia?, ¿qué acción?
- **Legacy:** La UI visible de “Driver Behavior” debe usar **solo** /ops/driver-behavior/*. No deben alimentarla /controltower/*, /ops/behavior-alerts/* ni /ops/action-engine/* para este módulo.

---

**Scan:** docs/driver_behavior_deviation_scan.md  
**Propuesta:** este documento.  
**Implementación:** fases 2–21 según especificación.
