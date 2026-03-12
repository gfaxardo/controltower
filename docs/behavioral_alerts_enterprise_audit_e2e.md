# Auditoría E2E — Behavioral Alerts Enterprise (persistencia visual y funcional)

**Fecha:** 2025-03-12  
**Objetivo:** Verificar y corregir que las mejoras de Behavioral Alerts estén visibles y operativas en la UI real.

---

## FASE 0 — MAPEO REAL DE LA VISTA RENDERIZADA

| Item | Valor |
|------|--------|
| **Ruta real** | Tab de navegación "Behavioral Alerts" en `App.jsx` → `activeTab === 'behavioral_alerts'`. No hay path de URL (SPA por tabs). |
| **Componente real** | `frontend/src/components/BehavioralAlertsView.jsx` — único componente que renderiza esta vista. |
| **Endpoint real (summary)** | `GET /api/ops/behavior-alerts/summary` (params: from, to, country, city, park_id, segment_current, movement_type, alert_type, severity, risk_band). |
| **Endpoint real (insight)** | `GET /api/ops/behavior-alerts/insight` (mismos params). |
| **Endpoint real (drivers)** | `GET /api/ops/behavior-alerts/drivers` (params anteriores + limit, offset, order_by, order_dir). |
| **Endpoint real (export)** | `GET /api/ops/behavior-alerts/export?format=csv|excel` (mismos filtros). |
| **Tabla y filtros** | Propios del componente (no reutilizable externo). Filtros en bloque superior; tabla en `<table>` con overflow-x-auto. |

**Archivos duplicados / no usados detectados:**

- **No hay duplicados.** La única vista de Behavioral Alerts es la pestaña que renderiza `BehavioralAlertsView`.
- `DriverBehaviorView.jsx` es un módulo distinto ("Driver Behavior"), no una variante de Behavioral Alerts.
- Los endpoints también se exponen bajo `/controltower/behavior-alerts/*` (alias); el frontend usa `/ops/behavior-alerts/*`.

---

## FASE 1 — AUDITORÍA DE VISIBILIDAD UI (estado en código y tras correcciones)

| Punto | Estado | Notas |
|-------|--------|--------|
| 1. Opción "Sudden Stop" en dropdown de alertas | **OK visible** | `alertTypes` incluye `'Sudden Stop'`; el select "Tipo alerta" lo muestra. |
| 2. Ícono/trigger de leyenda junto al filtro | **OK visible (corregido)** | Antes: botón "?" pequeño (w-4 h-4). Ahora: botón "? Leyenda" con texto, más descubrible. |
| 3. Columna "Último viaje" | **OK visible** | Columna en la grilla; `formatLastTrip(r.last_trip_date)`; tooltip por header y celda; min-width para no comprimirse. |
| 4. Headers clickeables con indicador de orden | **OK visible (mejorado)** | `handleSort` + `sortIcon`; indicador ↑/↓ en azul y negrita cuando la columna está ordenada; ↕ cuando no. |
| 5. Counters/cards nuevas arriba | **OK visible (ajustado)** | Grid de KPI (Total, Sudden Stop, Caídas críticas, … Estables, Alto riesgo, Riesgo medio). Grid reducido a máx 5 columnas para que no se compriman. |
| 6. Botón "Export Recovery List" | **OK visible (destacado)** | Bloque "Exportar datos" con título; "Recovery List (recomendado)" + botones CSV/Excel con borde verde y mayor tamaño. |
| 7. Tooltips de cabeceras | **OK visible (corregido)** | `COLUMN_TOOLTIPS` con key `'Último viaje'` añadida (antes solo 'Last Trip'); `title={COLUMN_TOOLTIPS[label]}` en cada `<th>`. |

---

## FASE 2 — AUDITORÍA DE DATOS (backend)

| Dato | Origen | Estado |
|------|--------|--------|
| sudden_stop en summary | `get_behavior_alerts_summary` → `COUNT(*) FILTER (WHERE alert_type = 'Sudden Stop')` | **OK** |
| stable_performer en summary | Idem con `alert_type = 'Stable Performer'` | **OK** |
| last_trip_date en filas (drivers) | `get_behavior_alerts_drivers` → `LEFT JOIN ops.v_driver_last_trip lt` → `lt.last_trip_date` | **OK** |
| summary/counters para sudden_stop / stable_performer | Respuesta de `/ops/behavior-alerts/summary` con keys sudden_stop, stable_performer, etc. | **OK** |
| Export ampliado (last_trip_date) | `get_behavior_alerts_export` incluye `lt.last_trip_date` en SELECT y cols en router | **OK** |
| Filtro alert_type = 'Sudden Stop' | `_build_where` con `alert_type = %s`; frontend envía "Sudden Stop" | **OK** |

**Conclusión FASE 2:** Backend devuelve sudden_stop, last_trip_date, summary por tipo de alerta y export ampliado. No se requieren cambios en backend para persistencia visual.

---

## FASE 3 — CORRECCIONES APLICADAS (persistencia visual, no destructivas)

1. **Dropdown "Sudden Stop"** — Ya estaba en el select; sin cambio.
2. **Trigger de leyenda** — Botón cambiado de "?" pequeño a "? Leyenda" (texto + borde), más visible.
3. **Columna "Último viaje"** — Tooltip de cabecera corregido (key `'Último viaje'` en COLUMN_TOOLTIPS). Min-width en `<th>` y `<td>` para que no se comprima; mensaje de ayuda sobre scroll horizontal.
4. **Indicador de orden** — sortIcon devuelve JSX con ↑/↓ en azul y negrita cuando la columna está ordenada; ↕ con opacidad cuando no.
5. **Cards/counters** — Grid de 10 columnas en xl cambiado a máx 5 columnas (grid-cols-2 hasta lg:grid-cols-5) para que las cards no queden demasiado estrechas.
6. **Export Recovery List** — Bloque dedicado "Exportar datos" con título; Recovery List (CSV/Excel) con borde verde y mayor tamaño; texto "Recovery List (recomendado)".
7. **Tooltips de cabeceras** — Añadida key `'Último viaje'` en COLUMN_TOOLTIPS para que el tooltip de la columna "Último viaje" sea descubrible.

---

## FASE 4 — VALIDACIÓN EVIDENCIABLE

**Archivos tocados:**

- `frontend/src/components/BehavioralAlertsView.jsx`

**Componente renderizado:** `BehavioralAlertsView` (cuando `activeTab === 'behavioral_alerts'` en `App.jsx`).

**Endpoints usados:**

- `GET /api/ops/behavior-alerts/summary`
- `GET /api/ops/behavior-alerts/insight`
- `GET /api/ops/behavior-alerts/drivers`
- `GET /api/ops/behavior-alerts/export`

**Campos presentes en payload (ejemplo):**

- **Summary:** drivers_monitored, sudden_stop, critical_drops, moderate_drops, silent_erosion, strong_recoveries, high_volatility, stable_performer, high_risk_drivers, medium_risk_drivers.
- **Drivers (filas):** driver_key, driver_name, country, city, park_name, segment_current, trips_current_week, avg_trips_baseline, delta_pct, alert_type, severity, risk_score, risk_band, **last_trip_date**, etc.

**Checklist final (elementos visibles esperados en la UI):**

| # | Elemento | Esperado |
|---|----------|----------|
| 1 | Sudden Stop visible en dropdown | Opción "Sudden Stop" en el select "Tipo alerta". |
| 2 | Leyenda visible | Botón "? Leyenda" junto a la etiqueta "Tipo alerta"; al hacer clic se muestra el panel de leyenda de alertas. |
| 3 | Último viaje visible | Columna "Último viaje" en la tabla; valores tipo "Hoy", "Hace N días" o fecha; cabecera con tooltip. |
| 4 | Sort visible | Cabeceras ordenables con ↕; al ordenar, ↑ o ↓ en azul en la columna activa. |
| 5 | Counters visibles | Bloque de tarjetas con Total en alertas, Sudden Stop, Caídas críticas, … Estables, Alto riesgo, Riesgo medio. |
| 6 | Export visible | Bloque "Exportar datos" con "Export Recovery List (CSV)" y "(Excel)" destacados en verde. |

---

## FASE 5 — DUPLICADOS O LEGACY

- **No se encontró** implementación en una vista equivocada ni componente no usado.
- La única vista de Behavioral Alerts es la pestaña que usa `BehavioralAlertsView`; no hay lógica duplicada que consolidar.

---

## Criterio de éxito

El usuario, al entrar a la pestaña **Behavioral Alerts**, debe ver de forma clara:

- Sudden Stop en el filtro "Tipo alerta".
- Botón "? Leyenda" para ayuda de segmentos.
- Columna "Último viaje" en la tabla (con posible scroll horizontal en pantallas pequeñas).
- Ordenamiento visible en cabeceras (↑/↓).
- Cards de KPIs (Total, Sudden Stop, Estables, etc.).
- Botones "Export Recovery List" en el bloque de exportación.

Si algo de lo anterior no se ve, el trabajo no se considera terminado.
