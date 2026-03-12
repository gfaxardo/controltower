# Action Engine — Logic and Cohort Definitions

**Project:** YEGO Control Tower  
**Feature:** Action Engine (actionable cohorts and recommended actions)

---

## 1. Purpose

Transform driver-level signals (Behavioral Alerts, Risk Score, segment, movement) into **actionable operational cohorts** and **recommended actions** so operators know whom to contact first and why.

---

## 2. Input signals (from ops.mv_driver_behavior_alerts_weekly)

- week_start, week_label, driver_key, driver_name, country, city, park_id, park_name  
- segment_current, segment_previous, movement_type  
- trips_current_week, avg_trips_baseline, delta_abs, delta_pct  
- alert_type, severity, risk_score, risk_band  
- active_weeks_in_window, weeks_declining_consecutively (from baseline)

---

## 3. Cohort definitions (initial set)

Evaluation order: first match wins (priority order). All conditions per driver-week.

| # | Cohort | Definition (SQL-friendly) | Suggested action | Priority |
|---|--------|----------------------------|------------------|----------|
| 1 | **High Value Deteriorating** | segment_current IN ('FT','ELITE','LEGEND') AND (risk_band = 'high risk' OR risk_band = 'medium risk') AND delta_pct < -0.15 | Priority contact / loyalty / retention call | high |
| 2 | **Silent Erosion** | weeks_declining_consecutively >= 3 AND alert_type NOT IN ('Critical Drop','Moderate Drop') | Preventive outreach / performance check-in | high |
| 3 | **Recoverable Mid Performers** | segment_current IN ('CASUAL','PT') AND (alert_type = 'Strong Recovery' OR (delta_pct > 0 AND risk_band IN ('stable','monitor'))) | Soft nudge / coaching / small incentive | medium |
| 4 | **Near Upgrade Opportunity** | segment_current IN ('CASUAL','PT') AND movement_type = 'upshift' AND delta_pct > 0 | Behavioral coaching / targeted nudge | medium |
| 5 | **Near Drop Risk** | segment_current IN ('FT','ELITE','LEGEND','PT') AND movement_type IN ('downshift','drop') OR (delta_pct < -0.10 AND risk_band IN ('medium risk','monitor')) | Containment / preventive contact | high |
| 6 | **Volatile Drivers** | alert_type = 'High Volatility' | Diagnostic contact / pattern review | medium |
| 7 | **High Value Recovery Candidates** | avg_trips_baseline >= 40 AND delta_pct < -0.20 AND delta_pct > -0.50 AND segment_current IN ('FT','ELITE','LEGEND') | Fast-track recovery action | high |

- **Cohort type** stored as text: `high_value_deteriorating`, `silent_erosion`, `recoverable_mid_performers`, `near_upgrade_opportunity`, `near_drop_risk`, `volatile_drivers`, `high_value_recovery_candidates`.  
- Drivers can appear in more than one cohort (e.g. High Value Deteriorating and Near Drop Risk); for reporting we take the **first** matching cohort per priority order above, or allow multi-label in a separate design (here: single primary cohort per row for simplicity).

---

## 4. Cohort prioritization

- **suggested_priority:** high | medium | low (from table above).  
- **Cohort priority score (for ordering):** Combine: cohort_size (larger = more impact), average risk_score (higher = more urgent), share of FT/ELITE/LEGEND (higher = more value at risk). Formula example: `priority_score = cohort_size * 0.4 + avg_risk_score * 0.4 + (pct_high_segment * 100) * 0.2`; then order cohorts by priority_score DESC.  
- **suggested_channel:** loyalty_call | outbound_call | whatsapp_coaching | preventive_outreach | diagnostic_contact | soft_nudge (mapped from cohort type in implementation).

---

## 5. Action recommendation layer

| Cohort | action_name | action_objective | recommended_channel | urgency |
|--------|-------------|-------------------|---------------------|--------|
| High Value Deteriorating | Protect Elite/Legend in decline | Prevent loss of premium supply | loyalty_call | high |
| Silent Erosion | Stop silent erosion | Detect hidden deterioration early | preventive_outreach | high |
| Recoverable Mid Performers | Push recovering PT/Casual upward | Accelerate conversion to higher productivity | whatsapp_coaching | medium |
| Near Upgrade Opportunity | Promote near-upgrade drivers | Lock in upward movement | soft_nudge | medium |
| Near Drop Risk | Contain FT at risk of downgrade | Prevent collapse to lower segment | outbound_call | high |
| Volatile Drivers | Understand volatile drivers | Avoid unreliable supply | diagnostic_contact | medium |
| High Value Recovery Candidates | Rescue high-value recoverable | High ROI reactivation | outbound_call | high |

- **why_this_matters:** Short text per cohort (e.g. "These drivers are high value and declining; early contact can prevent churn.").

---

## 6. Outputs

- **Cohorts aggregate:** For each (week_start, cohort_type): cohort_size, avg_risk_score, avg_delta_pct, avg_baseline_value, dominant_segment, suggested_priority, suggested_channel, action_name, action_objective.  
- **Driver list per cohort:** Filter mv_driver_behavior_alerts_weekly by same rules as cohort; exportable.  
- **Recommended actions panel:** Top 3–5 actions by priority_score (or urgency) for the selected week/range.

---

## 7. Files and objects

- **Views:** ops.v_action_engine_cohorts_weekly (aggregate), ops.v_action_engine_recommendations_weekly (optional; can be derived from cohorts).  
- **Driver-level cohort tag:** Computed in view or in API from mv_driver_behavior_alerts_weekly using the same rules; used for cohort-detail and export.
