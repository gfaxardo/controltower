# Behavioral Alerts — Logic and Risk Score

**Project:** YEGO Control Tower  
**Feature:** Behavioral Alerts + Driver Risk Score  
**Purpose:** Document alert classification rules and Driver Risk Score formula for auditability.

---

## 1. Conceptual model

- **Grain:** driver-week (one row per driver per week_start).
- **Current week:** trips_current_week, segment_current (and optionally segment_previous, movement_type from migration data).
- **Baseline window:** Configurable N weeks (4 / 6 / 8) **strictly before** the current week (current week excluded).
- **Baseline metrics:** avg_trips_baseline, median_trips_baseline, stddev_trips_baseline, min_trips_baseline, max_trips_baseline, active_weeks_in_window, weeks_declining_consecutively, weeks_rising_consecutively.
- **Derived:** delta_abs = trips_current_week - avg_trips_baseline; delta_pct = (trips_current_week - avg_trips_baseline) / avg_trips_baseline; z_score_simple = (trips_current_week - avg_trips_baseline) / stddev_trips_baseline (when stddev > 0).
- **Classification:** alert_type and severity (see below).
- **Driver Risk Score:** 0–100 composite score with four components and risk_band (see below).

---

## 2. Alert classification rules

Evaluation order is **priority order** (first match wins). All conditions must hold unless stated otherwise.

| alert_type        | Conditions | severity  |
|-------------------|------------|-----------|
| **Critical Drop** | avg_trips_baseline >= 40 AND delta_pct <= -30% AND active_weeks_in_window >= 4 | critical  |
| **Moderate Drop** | delta_pct > -30% AND delta_pct <= -15% | moderate  |
| **Silent Erosion** | weeks_declining_consecutively >= 3 (and not already Critical or Moderate Drop) | moderate  |
| **Strong Recovery** | delta_pct >= +30% AND active_weeks_in_window >= 3 | positive   |
| **High Volatility** | (stddev_trips_baseline / avg_trips_baseline) > 0.5 (and none of the above) | moderate  |
| **Stable Performer** | None of the above | neutral   |

- **Severity** is derived from alert_type: Critical Drop → critical; Moderate Drop, Silent Erosion, High Volatility → moderate; Strong Recovery → positive; Stable Performer → neutral.
- Percentages in conditions are applied to decimal form (e.g. -30% means delta_pct <= -0.30).

---

## 3. Driver Risk Score (0–100)

Transparent, explainable score for operational prioritization. **Not a black box:** formula and constants are fixed and documented.

### 3.1 Components (sum = risk_score, capped at 100)

**A) Behavior Deviation Score (0–40)**  
- Based on: negative delta_pct, weeks_declining_consecutively, negative z_score_simple.  
- Example implementation: up to 20 points from delta_pct (linear scale from 0 at delta_pct=0 to 20 at delta_pct <= -1); up to 10 from consecutive declining weeks; up to 10 from negative z_score. Component capped at 40.

**B) Segment Migration Risk (0–30)**  
- Based on: movement_type (downshift / drop) and segment level of segment_previous (higher segment = higher penalty).  
- Example: downshift = 15, drop = 25; extra penalty when segment_previous is FT/ELITE/LEGEND (e.g. +5). Component capped at 30.

**C) Activity Fragility Score (0–20)**  
- Based on: low active_weeks_in_window (e.g. < 3) and high volatility (stddev/avg > 0.5).  
- Example: up to 10 for few active weeks, up to 10 for high volatility. Component capped at 20.

**D) Value / Priority Weight (0–10)**  
- Based on: higher avg_trips_baseline and higher segment (ordering).  
- Increases score when the driver is historically valuable and in risk (for prioritization). Example: normalize avg_trips_baseline and segment ordering to 0–5 each; sum capped at 10.

### 3.2 Risk bands

| risk_score | risk_band   |
|------------|-------------|
| 0–24       | stable      |
| 25–49      | monitor     |
| 50–74      | medium risk |
| 75–100     | high risk   |

### 3.3 Auditability

- Exact constants and formulas are implemented in SQL (view 085) and repeated in code comments.
- Optional columns risk_score_behavior, risk_score_migration, risk_score_fragility, risk_score_value expose component breakdown for drilldown and export.

---

## 4. Segment taxonomy (reference)

Canonical segments from ops.driver_segment_config (after migration 078):

- DORMANT: 0 trips (ordering 1)
- OCCASIONAL: 1–4 (2)
- CASUAL: 5–19 (3)
- PT: 20–59 (4)
- FT: 60–119 (5)
- ELITE: 120–179 (6)
- LEGEND: 180+ (7)

---

## 5. What will NOT be touched

- Migration, Lifecycle, Supply MVs and views.
- ops.driver_segment_config (read-only for this feature).
- Other Control Tower tabs and APIs.

---

## 6. Risks and pending refinements

- **Baseline window 4/8:** View currently implements 6-week baseline; 4/8 may be applied in API/UI only until baseline view is extended with multiple windows.
- **weeks_declining_consecutively:** Currently 0 in baseline view (081); Silent Erosion may not fire until this is computed. Risk score can still use delta_pct and z_score.
- **Score tuning:** Constants in Risk Score (e.g. 20/10/10 for A, 15/25 for B) may be refined after operational use; changes must be documented here and in SQL comments.

---

## 7. Deliverables / Archivos tocados

**Migraciones:**  
- `backend/alembic/versions/084_behavior_baseline_segment_movement.py` — vista baseline con segment_previous, movement_type.  
- `backend/alembic/versions/085_behavior_alerts_risk_score.py` — vista de alertas con risk_score, risk_band, componentes; recreación de la MV e índice risk_band.

**Backend:**  
- `backend/app/services/behavior_alerts_service.py` — filtros movement_type, risk_band; summary high_risk_drivers, medium_risk_drivers; driver detail risk_reasons; export columnas nuevas.  
- `backend/app/routers/ops.py` — query params risk_band, movement_type en endpoints behavior-alerts.  
- `backend/app/routers/controltower.py` — router /controltower con behavior-alerts.  
- `backend/app/main.py` — inclusión del router controltower.

**Frontend:**  
- `frontend/src/components/BehavioralAlertsView.jsx` — filtros Movement type y Risk band; KPIs Alto riesgo / Riesgo medio; columnas Risk Score y Risk Band; drilldown "Por qué se destaca"; panel de ayuda con Risk Score y taxonomía.  
- `frontend/src/services/api.js` — getBehaviorAlertsExportUrl con parámetros (filters ya incluyen movement_type, risk_band).

**Documentación:**  
- `docs/behavioral_alerts_architecture_scan.md` — Phase 0 (taxonomía, fuente de verdad, qué no se toca, Risk Score planned).  
- `docs/behavioral_alerts_logic.md` — modelo, reglas de alertas, fórmula Risk Score, riesgos, deliverables.  
- `docs/behavioral_alerts_api.md` — filtros, columnas, prefijo /controltower.  
- `docs/behavioral_alerts_qa_checklist.md` — ítems risk_score, risk_band, filtros, KPIs, drilldown, export.  
- `docs/behavioral_alerts_performance.md` — MV, índices, refresh_driver_behavior_alerts(), orden de refresh.

**Objetos SQL:**  
- `ops.v_driver_behavior_baseline_weekly` (reemplazo 084), `ops.v_driver_behavior_alerts_weekly` (reemplazo 085), `ops.mv_driver_behavior_alerts_weekly` (recreación en 085), `ops.refresh_driver_behavior_alerts()`.
