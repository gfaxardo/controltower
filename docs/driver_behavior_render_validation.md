# Driver Behavioral Deviation Engine — Render Validation (Phase 19)

**Proyecto:** YEGO Control Tower  
**Objetivo:** Validar que un usuario puede responder en la UI las preguntas operativas clave.

---

## Preguntas que el usuario debe poder responder

1. **¿Este conductor empeora o mejora?**  
   Columna “Estado” (behavior_direction): Empeorando, Recuperando, Mejorando, Estable, Volátil.  
2. **¿Respecto a qué baseline?**  
   Filtros “Ventana reciente” y “Ventana baseline” + texto en ayuda y en el modal de detalle (“Ventana reciente X sem., baseline Y sem.”).  
3. **¿Desde cuándo?**  
   Columna “Persistencia” (X sem. empeorando / X sem. recuperando) y en detalle el rationale_short.  
4. **¿Cuántos días desde el último viaje?**  
   Columna “Días sin viaje” y en detalle “Días desde último viaje”.  
5. **¿Qué tan urgente es intervenir?**  
   Columnas “Risk” (score 0–100) y “Banda” (stable, monitor, medium risk, high risk). Colores semánticos (rojo/ámbar/gris/verde).  
6. **¿Qué acción debo tomar?**  
   Columna “Acción sugerida” y en detalle “Acción sugerida” + “Rationale”.

---

## Pasos de validación manual

1. **Arrancar backend y frontend**  
   - Backend: desde `backend`, ejecutar el servidor (uvicorn u otro).  
   - Frontend: desde `frontend`, `npm run dev`.  
   - Asegurar que la migración 089 está aplicada (`alembic upgrade head`) para que exista `ops.v_driver_last_trip`.

2. **Abrir la pestaña Driver Behavior**  
   - En la barra de pestañas, clic en “Driver Behavior”.  
   - Verificar que se muestra el título “Driver Behavior” y el párrafo que diferencia este módulo de Behavioral Alerts y Action Engine.

3. **Comprobar filtros y KPIs**  
   - Cambiar “Ventana reciente” (4/8/16/32) y “Ventana baseline” (4/8/16/32).  
   - Verificar que los KPIs (Conductores monitoreados, Degradación fuerte, Recuperación, etc.) y la tabla se actualizan.  
   - Opcional: filtrar por país/ciudad/park, segmento, tipo alerta, banda de riesgo, estado de inactividad. Comprobar que la tabla y los KPIs reflejan los filtros.

4. **Comprobar tabla**  
   - Verificar que existen columnas: Conductor, País, Ciudad, Park, Segmento, Recent avg, Baseline avg, Δ %, Estado, Días sin viaje, Persistencia, Alerta, Risk, Banda, Acción sugerida, Acción.  
   - Comprobar que “Estado” muestra chips (Empeorando/Recuperando/Mejorando/Estable/Volátil) con colores coherentes (rojo/verde/gris/púrpura).  
   - Comprobar que “Días sin viaje” y “Risk”/“Banda” son legibles y coherentes con “Alerta” y “Acción sugerida”.

5. **Comprobar drilldown**  
   - Clic en una fila o en “Ver detalle”.  
   - Verificar que el modal muestra: nombre conductor, ventanas reciente/baseline, recent avg, baseline avg, delta %, días desde último viaje, estado conductual, risk score/banda, acción sugerida, rationale.  
   - Si el backend devuelve `weekly`, verificar que se muestra el gráfico “Viajes por semana (reciente + baseline)”.

6. **Comprobar ayuda**  
   - Clic en “Ver explicación: Ventanas, Delta, Días sin viaje, Riesgo, Acción”.  
   - Verificar que el texto explica ventana reciente, baseline, delta, días desde último viaje, estado conductual, tipo alerta, risk score, acción sugerida y la diferencia con los módulos semanales (macro vs individual).

7. **Comprobar export**  
   - Clic en “Exportar CSV (filtros activos)”.  
   - Verificar que se descarga un CSV con columnas acordes (driver_key, driver_name, country, city, park_name, recent_window_weeks, baseline_window_weeks, recent_avg_weekly_trips, baseline_avg_weekly_trips, delta_pct, behavior_direction, days_since_last_trip, alert_type, risk_score, risk_band, suggested_action) y que las filas coinciden con los filtros aplicados (p. ej. solo un país si se filtró por país).

8. **No usar paths legacy**  
   - En DevTools → Network, filtrar por “driver-behavior”. Verificar que las peticiones son a `/api/ops/driver-behavior/summary`, `/api/ops/driver-behavior/drivers`, `/api/ops/driver-behavior/driver-detail`, `/api/ops/driver-behavior/export`.  
   - No debe haber llamadas a `behavior-alerts` ni `action-engine` al usar solo la pestaña Driver Behavior.

---

## Resultado esperado

Tras seguir los pasos anteriores, un usuario puede:

- Identificar qué conductores empeoran o mejoran.  
- Entender respecto a qué baseline (ventanas configuradas).  
- Ver desde cuándo (persistencia) y días desde último viaje.  
- Priorizar por riesgo (score y banda).  
- Ver la acción sugerida y el rationale.  
- Exportar la lista filtrada.

Si en algún paso la UI no muestra datos o hay error de red, revisar: (1) que el backend esté levantado y que `/ops/driver-behavior/summary` responda; (2) que la base tenga datos en `ops.mv_driver_segments_weekly` y que `ops.v_driver_last_trip` exista y tenga filas si se usa last_trip_date.
