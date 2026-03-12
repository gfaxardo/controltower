# Behavioral Alerts — Rendimiento y refresh

**Project:** YEGO Control Tower  
**Feature:** Behavioral Alerts + Driver Risk Score

---

## 1. Vista vs materialized view

- **Vista:** `ops.v_driver_behavior_alerts_weekly` (definida en migración 085). Cada consulta ejecuta el SELECT sobre baseline + risk components. Puede ser lenta con muchos driver-weeks.
- **MV opcional:** `ops.mv_driver_behavior_alerts_weekly` — copia materializada de la vista. El servicio lee de la vista; si la MV existe, el optimizador puede usarla cuando se consulta la vista según configuración del esquema. En la práctica, el backend puede apuntar a la MV para listados y resúmenes (consultar `behavior_alerts_service`: lee de la vista; si en el futuro se quiere usar solo la MV, se cambiaría el FROM en el servicio).
- **Recomendación:** En entornos con alto volumen de driver-weeks, usar la MV y ejecutar `ops.refresh_driver_behavior_alerts()` tras el refresh de supply/lifecycle para tener respuestas rápidas.

---

## 2. Índices (MV)

Tras la migración 085, la MV tiene:

| Índice | Columnas | Uso |
|--------|----------|-----|
| ux_mv_driver_behavior_alerts_weekly_driver_week | (driver_key, week_start) | Unicidad y lookups por conductor/semana |
| ix_mv_driver_behavior_alerts_week_start | week_start | Filtro por rango de fechas |
| ix_mv_driver_behavior_alerts_country | country | Filtro por país |
| ix_mv_driver_behavior_alerts_city | city | Filtro por ciudad |
| ix_mv_driver_behavior_alerts_park_id | park_id | Filtro por park |
| ix_mv_driver_behavior_alerts_alert_type | alert_type | Filtro por tipo de alerta |
| ix_mv_driver_behavior_alerts_severity | severity | Filtro por severidad |
| ix_mv_driver_behavior_alerts_risk_band | risk_band | Filtro por banda de riesgo (nuevo en 085) |

REFRESH MATERIALIZED VIEW CONCURRENTLY requiere el índice único para poder ejecutarse sin bloquear lecturas.

---

## 3. Función de refresh

- **Función:** `ops.refresh_driver_behavior_alerts()`  
- **Acción:** `REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_behavior_alerts_weekly;`  
- **Cuándo ejecutar:** Después de actualizar datos de supply y driver lifecycle (mv_driver_segments_weekly, mv_driver_weekly_stats, etc.), para que las alertas y el risk score reflejen los últimos segmentos y viajes.  
- **Tiempo aproximado:** Depende del volumen (decenas de segundos a pocos minutos con millones de filas). Ejecutar en ventana de mantenimiento si el refresh es pesado.

---

## 4. Orden de refresh recomendado

1. Refresh de MVs de lifecycle/supply (mv_driver_weekly_stats, mv_driver_segments_weekly, etc.).  
2. `ops.refresh_driver_behavior_alerts()` (actualiza la MV de alertas).  

Las vistas de baseline (081/084) y alertas (085) dependen de `mv_driver_segments_weekly` y de las tablas de geo/driver; no hay que refrescar vistas, solo la MV de alertas si se usa.

---

## 5. Referencias

- Migración 083: creación de la MV y de `refresh_driver_behavior_alerts()`.  
- Migración 085: redefinición de la vista con risk_score/risk_band y recreación de la MV con índice `risk_band`.
