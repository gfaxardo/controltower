# Behavioral Alerts Enterprise — Validación y checklist

**Módulo:** Behavioral Alerts (vista enterprise).  
**Referencia:** docs/behavioral_alerts_enterprise_scan.md, docs/behavioral_alerts_logic.md.

---

## Clasificación y precedencia

- [ ] Un conductor con semana actual 0 viajes y baseline > 0 aparece como **Sudden Stop** (y no como Critical Drop u otro).
- [ ] Un conductor que cumple Critical Drop no aparece como Moderate Drop ni Stable.
- [ ] Un conductor estable (ninguna alerta) aparece como **Stable Performer**.
- [ ] Un conductor en fuerte recuperación (delta ≥ 30%, etc.) aparece como **Strong Recovery**.
- [ ] Precedencia verificada: Sudden Stop > Critical Drop > Moderate Drop > Silent Erosion > High Volatility > Strong Recovery > Stable Performer.

## UI

- [ ] **Leyenda de segmentos:** junto al filtro "Tipo alerta" hay un ícono (?) que al hacer clic abre un popover con la leyenda de cada alerta (Sudden Stop, Critical Drop, …). Cierre con "Cerrar" o clic fuera.
- [ ] **Tooltips de columnas:** al pasar el cursor por los headers de la tabla (Conductor, País, Viajes sem., Base avg, Δ %, etc.) se muestra el tooltip con la definición.
- [ ] **Ordenación:** al hacer clic en un header ordenable (Conductor, País, Ciudad, Park, Segmento, Viajes sem., Base avg, Δ %, Alerta, Severidad, Risk Score, Risk Band, Último viaje) la tabla se reordena; el indicador (↑/↓) muestra el sentido.
- [ ] **Columna Último viaje:** muestra "Hoy", "Hace N días" o "—"; el tooltip en la celda muestra la fecha exacta si existe.
- [ ] **Risk counters:** la banda superior muestra Total en alertas, Sudden Stop, Caídas críticas, Caídas moderadas, Erosión silenciosa, Recuperaciones, Alta volatilidad, Estables, Alto riesgo, Riesgo medio.
- [ ] **Export Recovery List:** los botones "Export Recovery List (CSV)" y "(Excel)" descargan el mismo dataset que Exportar CSV/Excel, con nombre sugerido recovery_list_conductores.*.

## Export

- [ ] El export (CSV/Excel) incluye columnas: driver_key, driver_name, country, city, park_name, week_label, segment_current, movement_type, trips_current_week, avg_trips_baseline, delta_abs, delta_pct, weeks_declining_consecutively, weeks_rising_consecutively, alert_type, alert_severity, risk_score, risk_band, last_trip_date.
- [ ] El archivo se descarga correctamente con los filtros aplicados.

## Performance y robustez

- [ ] La tabla carga en tiempo razonable; no hay loops ni renders excesivos.
- [ ] Paginación y filtros siguen funcionando tras los cambios.
- [ ] Al cambiar ordenación, se mantiene la página o se resetea a 0 según diseño (actualmente se resetea a página 0).

## Limitaciones conocidas

- **Baseline window:** la vista SQL usa ventana fija de 6 semanas; el selector 4/6/8 en la UI puede no cambiar la ventana en backend hasta que la vista soporte múltiples ventanas.
- **weeks_declining_consecutively / weeks_rising_consecutively:** en algunas instalaciones el baseline puede devolver 0; Silent Erosion y persistencia dependen de este dato.
- **MV:** si se usa la materialized view, ejecutar `ops.refresh_driver_behavior_alerts()` tras refrescar supply/lifecycle para ver datos actualizados.

## Migración 090

- Tras desplegar, ejecutar: `alembic upgrade head` para aplicar **090_behavioral_alerts_sudden_stop_mutually_exclusive** (añade Sudden Stop y refuerza precedencia en la vista y MV).
- Después, refrescar la MV si aplica: `SELECT ops.refresh_driver_behavior_alerts();`
