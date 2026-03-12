# Driver Behavioral Deviation Engine — Lógica y reglas

**Proyecto:** YEGO Control Tower  
**Módulo:** Driver Behavior (additive, no destructivo)

---

## 1. Ventanas de tiempo

- **Ventana reciente (recent_window):** N semanas usadas para medir el comportamiento actual. Opciones soportadas: 4, 8, 16, 32.
- **Ventana baseline:** M semanas anteriores, **excluyendo** la ventana reciente (sin solapamiento). Mismas opciones 4, 8, 16, 32.
- **Semana de referencia (as_of_week):** Fecha de inicio de semana de cierre. Si no se indica, se usa la semana más reciente disponible en `ops.mv_driver_segments_weekly`.
- **Origen de datos:** `ops.mv_driver_segments_weekly` (trips_completed_week, segment_week por driver_key, week_start). Baseline se calcula sobre semanas en el rango `[ref - (recent + baseline), ref - recent)`.

---

## 2. Días desde último viaje e inactividad

- **days_since_last_trip:** Días desde el último viaje completado del conductor. Origen: `ops.v_driver_last_trip` (last_trip_date desde `ops.v_driver_lifecycle_trips_completed`, MAX(completion_ts)::date por conductor_id).
- **Cálculo:** `(reference_week + 6) - last_trip_date` (días hasta el fin de la semana de referencia).
- **inactivity_status (umbrales iniciales):**
  - **active:** 0–3 días
  - **cooling:** 4–7 días
  - **dormant_risk:** 8–14 días
  - **churn_risk:** 15+ días

---

## 3. Tipos de alerta (prioridad de evaluación)

1. **Churn Risk:** days_since_last_trip >= 15  
2. **Dormant Risk:** days_since_last_trip >= 8 (y < 15)  
3. **Sharp Degradation:** delta_pct <= -30%  
4. **Moderate Degradation:** delta_pct entre -15% y -30%  
5. **Sustained Degradation:** declining_weeks_consecutive >= 3  
6. **Recovery:** delta_pct >= +25%  
7. **High Volatility:** (baseline_stddev / baseline_avg) > 0.5  
8. **Stable:** resto

---

## 4. Estado conductual (Behavior direction)

Valores mostrados en UI:

- **Empeorando:** delta_pct < -5% O declining_weeks >= 2 O days_since_last_trip >= 8  
- **Recuperando:** delta_pct >= 25% O rising_weeks >= 2  
- **Mejorando:** delta_pct > 5% (y no Recuperando)  
- **Volátil:** alert_type = High Volatility  
- **Estable:** resto

---

## 5. Driver Degradation Risk Score (0–100)

Componentes (explicables):

- **A) Desviación (0–40):** Severidad de la caída vs baseline. `min(40, (-delta_pct) * 40)` cuando delta_pct < 0.
- **B) Persistencia (0–20):** declining_weeks_consecutive * 5, cap 20.
- **C) Inactividad (0–20):** days_since_last_trip, cap 20.
- **D) Valor operativo (0–20):** baseline_avg_weekly_trips (peso por volumen), cap 20.

**Bandas:**

- 0–24: **stable**  
- 25–49: **monitor**  
- 50–74: **medium risk**  
- 75–100: **high risk**

---

## 6. Acción y canal sugeridos

- **Dormant Risk / Churn Risk:** Reactivación, canal reactivation_whatsapp  
- **Sharp Degradation:** Retención prioritaria, canal outbound_retention_call  
- **Moderate Degradation:** Contacto lealtad, canal loyalty_call  
- **Recovery:** Refuerzo recuperación, canal coaching_push  
- **Resto:** Solo seguimiento, canal monitor_only  

**rationale_short:** Texto corto operativo, p. ej. “-52% vs baseline, 3 sem empeorando, 9 días sin viaje”.

---

## 7. Persistencia (rachas)

- **declining_weeks_consecutive:** Semanas consecutivas (dentro de la ventana reciente) en que viajes_semana < viajes_semana_anterior (orden descendente por week_start).
- **rising_weeks_consecutive:** Igual para viajes_semana > viajes_semana_anterior.  
Calculados en el servicio con CTE `week_series` + ventana LAG sobre `ops.mv_driver_segments_weekly`.

---

## 8. Fuentes SQL utilizadas

- `ops.mv_driver_segments_weekly` — driver_key, week_start, park_id, trips_completed_week, segment_week  
- `ops.v_driver_last_trip` — driver_key, last_trip_date  
- `dim.v_geo_park` (o equivalente) — park_id, country, city, park_name  
- `ops.v_dim_driver_resolved` (o equivalente) — driver_id, driver_name  

No se usan para este módulo: `v_driver_behavior_alerts_weekly`, `v_action_engine_*`, ni endpoints `/ops/behavior-alerts/*` o `/ops/action-engine/*` para alimentar la pantalla Driver Behavior.
