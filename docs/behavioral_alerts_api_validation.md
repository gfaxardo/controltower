# Behavioral Alerts — API Validation

**Date:** 2026-03-11  
**Phase:** 4 — Backend route validation

---

## Implemented routes

All under router prefix **/ops** (ops.router) and **/controltower** (controltower.router). Base paths:

| Method | Path | Description |
|--------|------|-------------|
| GET | /ops/behavior-alerts/summary | KPIs |
| GET | /ops/behavior-alerts/insight | Insight text |
| GET | /ops/behavior-alerts/drivers | Paginated drivers list |
| GET | /ops/behavior-alerts/driver-detail | Driver timeline (driver_key required) |
| GET | /ops/behavior-alerts/export | CSV/Excel export |

Same paths under **/controltower** (e.g. /controltower/behavior-alerts/summary).

---

## Query parameters (all endpoints that accept filters)

| Param | Type | Example |
|-------|------|--------|
| from | date | 2025-01-01 |
| to | date | 2025-03-01 |
| week_start | date | 2025-02-03 |
| country | string | Spain |
| city | string | Madrid |
| park_id | string | 1 |
| segment_current | string | FT, PT, CASUAL, … |
| movement_type | string | upshift, downshift, stable, drop, new |
| alert_type | string | Critical Drop, … |
| severity | string | critical, moderate, positive, neutral |
| risk_band | string | stable, monitor, medium risk, high risk |

Drivers list also: **limit** (default 500), **offset** (default 0), **order_by** (risk_score | severity | delta_pct | week_start), **order_dir** (asc | desc).  
Driver-detail: **driver_key** (required), **weeks** (default 8).  
Export: **format** (csv | excel), **max_rows** (default 10000, max 50000).

---

## Expected response shapes

### GET .../summary

```json
{
  "drivers_monitored": 1234,
  "critical_drops": 56,
  "moderate_drops": 78,
  "strong_recoveries": 12,
  "silent_erosion": 5,
  "high_volatility": 20,
  "high_risk_drivers": 30,
  "medium_risk_drivers": 45
}
```

### GET .../drivers

```json
{
  "data": [
    {
      "driver_key": "...",
      "driver_name": "...",
      "week_start": "2025-02-03",
      "week_label": "S5-2025",
      "country": "...",
      "city": "...",
      "park_id": "...",
      "park_name": "...",
      "segment_current": "FT",
      "segment_previous": "FT",
      "movement_type": "stable",
      "trips_current_week": 45,
      "avg_trips_baseline": 52.5,
      "delta_abs": -7.5,
      "delta_pct": -0.143,
      "alert_type": "Moderate Drop",
      "severity": "moderate",
      "risk_score": 42,
      "risk_band": "monitor"
    }
  ],
  "total": 1234,
  "limit": 500,
  "offset": 0
}
```

### GET .../driver-detail

```json
{
  "driver_key": "...",
  "data": [ { "week_start": "...", "trips_current_week": 45, "segment_current": "FT", "avg_trips_baseline": 52, "delta_pct": -0.13, "alert_type": "...", "severity": "...", "risk_score": 42, "risk_band": "monitor" } ],
  "total": 8,
  "risk_reasons": ["baseline drop -14%", "historically high-volume driver"]
}
```

---

## Required response fields (Behavioral Alerts + Risk Score)

- **summary:** drivers_monitored, critical_drops, moderate_drops, strong_recoveries, silent_erosion, high_volatility, **high_risk_drivers**, **medium_risk_drivers**.
- **drivers (each row):** avg_trips_baseline, delta_pct, alert_type, severity, **segment_previous**, **movement_type**, **risk_score**, **risk_band**.
- **driver-detail:** risk_score, risk_band, **risk_reasons** (array of strings).
- **export columns:** driver_key, driver_name, country, city, park_name, week_label, segment_current, **movement_type**, trips_current_week, avg_trips_baseline, delta_abs, delta_pct, alert_type, **alert_severity**, **risk_score**, **risk_band**.

---

## Live validation during closure

- **Not run** — DB was at 080 (migrations 081–085 not confirmed at head). Calling these endpoints would query `ops.v_driver_behavior_alerts_weekly`, which does not exist until 085 is applied, and would return 500.
- **Recommended (after migrations at 085):**
  1. Start backend: `uvicorn app.main:app --reload` (from backend dir).
  2. `GET http://localhost:8000/ops/behavior-alerts/summary?from=2025-01-01&to=2025-03-01` → 200, JSON with keys above.
  3. `GET http://localhost:8000/ops/behavior-alerts/drivers?from=2025-01-01&to=2025-03-01&limit=5` → 200, `data` array with risk_score, risk_band, segment_previous, movement_type.
  4. Pick a driver_key from (3), then `GET .../driver-detail?driver_key=<id>&from=2025-01-01&to=2025-03-01` → 200, risk_reasons present when applicable.
  5. `GET .../export?from=2025-01-01&to=2025-03-01&format=csv` → 200, CSV with header including movement_type, alert_severity, risk_score, risk_band.

---

## Pass/fail (to be filled after DB at 085)

| Route | Params used | HTTP | Response shape | New fields | Pass/Fail |
|-------|--------------|------|-----------------|------------|-----------|
| summary | from, to | — | — | high_risk_drivers, medium_risk_drivers | Pending |
| drivers | from, to, limit=5 | — | — | risk_score, risk_band, segment_previous, movement_type | Pending |
| driver-detail | driver_key, from, to | — | — | risk_reasons | Pending |
| export | from, to, format=csv | — | — | movement_type, alert_severity, risk_score, risk_band | Pending |

**Missing fields (if any):** To be noted after live run.
