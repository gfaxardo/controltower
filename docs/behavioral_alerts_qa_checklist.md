# Behavioral Alerts — QA Checklist

## No romper funcionalidad existente

- [ ] Migration (Supply > Migration) sigue funcionando: datos y drilldown.
- [ ] Driver Lifecycle: series, summary, drilldown por park sin cambios.
- [ ] Driver Supply Dynamics: Overview, Composition, Alerts sin cambios.
- [ ] Real LOB y resto de pestañas cargan igual.

## Behavioral Alerts

- [ ] La pestaña "Behavioral Alerts" aparece junto a Driver Lifecycle y Driver Supply Dynamics.
- [ ] Filtros: fecha desde/hasta, ventana baseline (4/6/8), país, ciudad, park, segmento actual, **tipo movimiento** (upshift, downshift, stable, drop, new), tipo alerta, severidad, **banda de riesgo** (stable, monitor, medium risk, high risk) aplican a KPIs, tabla y export.
- [ ] KPI cards: Conductores monitoreados, **Alto riesgo**, **Riesgo medio**, Caídas críticas, Caídas moderadas, Recuperaciones fuertes, Erosión silenciosa, Alta volatilidad.
- [ ] Panel de insight muestra texto automático según conteos (incluye mención de high/medium risk si aplica).
- [ ] Tabla de alertas: columnas Driver, País, Ciudad, Park, Segmento, Viajes sem., Base avg, Δ abs, Δ %, Alerta, Severidad, **Risk Score**, **Risk Band** (badge), Tendencia, Acción.
- [ ] Orden por defecto: **risk_score DESC**, luego delta_pct; también por severidad y delta_pct (asc/desc).
- [ ] Clic en fila o "Ver detalle" abre drilldown del conductor.
- [ ] Drilldown: **bloque "Por qué se destaca este conductor"** con risk_score, risk_band y lista risk_reasons; timeline últimas 8 semanas (viajes, segmento, base, Δ %, alerta).
- [ ] Panel de ayuda incluye **Driver Risk Score** (0-100, bandas) y **taxonomía de segmentos** (DORMANT 0, OCCASIONAL 1-4, CASUAL 5-19, PT 20-59, FT 60-119, ELITE 120-179, LEGEND 180+).
- [ ] Export CSV y Excel respetan filtros activos (incl. movement_type, risk_band) y descargan con columnas: driver_key, driver_name, country, city, park_name, week_label, segment_current, **movement_type**, trips_current_week, avg_trips_baseline, delta_abs, delta_pct, alert_type, **alert_severity**, **risk_score**, **risk_band**.

## Lógica de datos

- [ ] La línea base excluye la semana actual (6 semanas estrictamente anteriores en la vista).
- [ ] segment_previous y movement_type provienen de mv_driver_segments_weekly (prev_segment_week, segment_change_type).
- [ ] Clasificación de alertas: Critical Drop, Moderate Drop, Silent Erosion, Strong Recovery, High Volatility, Stable Performer y severidad correctas.
- [ ] **Risk Score (0-100)** y **risk_band** coherentes con la fórmula documentada en behavioral_alerts_logic.md (componentes A-D, bandas stable/monitor/medium risk/high risk).

## Rendimiento

- [ ] Resumen y tabla cargan en tiempo aceptable (< 15–30 s según volumen).
- [ ] Si se usa la MV, `ops.refresh_driver_behavior_alerts()` actualiza sin errores.

## Instrucciones de prueba

1. Aplicar migraciones 081, 082, 083, **084**, **085** (y 080 si no está): `alembic upgrade head`.
2. Backend: `uvicorn app.main:app --reload`. Probar GET `/ops/behavior-alerts/summary?from=2025-01-01&to=2025-03-01` y que la respuesta incluya `high_risk_drivers` y `medium_risk_drivers`. Probar también `/controltower/behavior-alerts/summary` con los mismos parámetros.
3. Frontend: `npm run dev`. Ir a la pestaña "Behavioral Alerts", elegir rango y filtros (incl. tipo movimiento y banda de riesgo), comprobar KPIs (alto riesgo, riesgo medio), tabla con Risk Score y Risk Band, orden por risk_score, drilldown "Por qué se destaca" con risk_reasons.
4. Export: hacer clic en "Exportar CSV" y comprobar que el archivo incluye movement_type, alert_severity, risk_score, risk_band.
5. Comprobar que Supply > Migration y Driver Lifecycle siguen operativos.
