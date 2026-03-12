# Behavioral Alerts — API

Base path: **/ops/behavior-alerts** (prefijo del router: `/ops`). Alternativa: **/controltower/behavior-alerts** (mismos endpoints y comportamiento).

## Endpoints

### GET /ops/behavior-alerts/summary

Devuelve KPIs según filtros activos.

**Query:** `week_start`, `from`, `to`, `country`, `city`, `park_id`, `segment_current`, `movement_type`, `alert_type`, `severity`, `risk_band`.

**Response:** `{ drivers_monitored, high_risk_drivers, medium_risk_drivers, critical_drops, moderate_drops, strong_recoveries, silent_erosion, high_volatility }`.

---

### GET /ops/behavior-alerts/insight

Texto de resumen automático para el panel de insight.

**Query:** `week_start`, `from`, `to`, `country`, `city`, `park_id`, `segment_current`, `movement_type`, `alert_type`, `severity`, `risk_band`.

**Response:** `{ summary: {...}, insight_text: "..." }`. El texto puede incluir mención de high_risk_drivers y medium_risk_drivers.

---

### GET /ops/behavior-alerts/drivers

Lista paginada de alertas (tabla).

**Query:** mismos filtros que summary + `limit` (default 500), `offset` (default 0), `order_by` (severity | delta_pct | week_start | **risk_score**), `order_dir` (asc | desc). Orden por defecto: risk_score DESC, delta_pct ASC.

**Response:** `{ data: [...], total, limit, offset }`. Cada fila: driver_key, driver_name, week_start, week_label, country, city, park_id, park_name, segment_current, **segment_previous**, **movement_type**, trips_current_week, avg_trips_baseline, delta_abs, delta_pct, alert_type, severity, **risk_score**, **risk_band**, y opcionalmente risk_score_behavior, risk_score_migration, risk_score_fragility, risk_score_value.

---

### GET /ops/behavior-alerts/driver-detail

Timeline de un conductor para drilldown.

**Query:** `driver_key` (obligatorio), `week_start`, `from`, `to`, `weeks` (default 8).

**Response:** `{ driver_key, data: [...], total, risk_reasons?: string[] }`. Cada fila incluye week_start, week_label, trips_current_week, segment_current, avg_trips_baseline, delta_pct, alert_type, severity, risk_score, risk_band y componentes del score. `risk_reasons` es una lista de textos explicativos para el bloque "Why flagged".

---

### GET /ops/behavior-alerts/export

Exportación con filtros activos.

**Query:** mismos filtros que summary + `format` (csv | excel), `max_rows` (default 10000, max 50000).

**Response:** CSV o Excel (attachment). Columnas: driver_key, driver_name, country, city, park_name, week_label, segment_current, **movement_type**, trips_current_week, avg_trips_baseline, delta_abs, delta_pct, alert_type, **alert_severity** (alias de severity), **risk_score**, **risk_band**. Orden por defecto: risk_score DESC, delta_pct ASC.

---

## Filtros comunes

| Parámetro        | Tipo   | Descripción                                                          |
|------------------|--------|----------------------------------------------------------------------|
| week_start       | date   | Una semana concreta (YYYY-MM-DD)                                     |
| from             | date   | Desde (rango)                                                        |
| to               | date   | Hasta (rango)                                                        |
| country          | string | País                                                                 |
| city             | string | Ciudad                                                               |
| park_id          | string | Park                                                                 |
| segment_current  | string | FT, PT, CASUAL, OCCASIONAL, DORMANT, ELITE, LEGEND                   |
| movement_type    | string | upshift, downshift, stable, drop, new                                 |
| alert_type       | string | Critical Drop, Moderate Drop, etc.                                    |
| severity         | string | critical, moderate, positive, neutral                                |
| risk_band        | string | stable, monitor, medium risk, high risk                              |

## Clasificación de alertas

- **Critical Drop:** avg_trips_baseline ≥ 40, delta_pct ≤ -30%, active_weeks_in_window ≥ 4.
- **Moderate Drop:** delta_pct entre -15% y -30%.
- **Silent Erosion:** 3+ semanas consecutivas a la baja (placeholder en vista).
- **Strong Recovery:** delta_pct ≥ +30%, active_weeks_in_window ≥ 3.
- **High Volatility:** stddev/avg > 0.5.
- **Stable Performer:** resto.

Severidad: critical (Critical Drop), moderate (Moderate Drop, Silent Erosion, High Volatility), positive (Strong Recovery), neutral (Stable Performer).
