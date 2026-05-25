# OPERATIONAL VALIDATION SCENARIOS

**Date**: 2025-05-25
**Purpose**: Define real-world scenarios to validate Control Tower operational utility

---

## SCENARIO A: Daily Operations — Same-Weekday Deterioration

| Field | Value |
|---|---|
| **Role** | Operations manager monitoring daily city performance |
| **Grain** | Daily — weekday focus VIE |
| **Mode** | Evolution or Projection |
| **Trigger** | Friday trips dropped vs previous Friday |

### Questions to validate
1. Does the DoD label "VIE" + green/red color help spot the issue faster than scanning raw numbers?
2. Is the momentum color (green/red) more useful than the attainment color (green/amber/red dot)?
3. Does the operator click the cell to drill? Or do they ignore it?
4. Does the weekday focus filter get used? Or is it always reset to "todos"?

---

## SCENARIO B: Weekly Operations — WoW Deterioration

| Field | Value |
|---|---|
| **Role** | City manager checking weekly trends |
| **Grain** | Weekly |
| **Mode** | Evolution |
| **Trigger** | Two consecutive weeks of declining trips |

### Questions to validate
1. Does the WoW label on the momentum row help connect the current week to last week?
2. Does the priority strip show this city at the top?
3. Is "consecutive decline" visible without extra clicks?
4. Does the operator use the momentum drill toggle?

---

## SCENARIO C: Monthly Operations — MoM Performance

| Field | Value |
|---|---|
| **Role** | Country manager reviewing monthly KPIs |
| **Grain** | Monthly |
| **Mode** | Projection (Vs Proyección) |
| **Trigger** | Monthly attainment < 80% AND MoM decline |

### Questions to validate
1. Is the dual display (momentum MoM + attainment %) cognitively clear?
2. Does momentum (MoM decline) attract more attention than attainment?
3. When attainment is red AND momentum is red, does the operator understand both signals?
4. Is the projection drill useful for root cause? Or is it noise?

---

## SCENARIO D: Supply — Driver Deterioration Detection

| Field | Value |
|---|---|
| **Role** | Supply manager monitoring driver health |
| **Grain** | N/A (Behavioral MVP) |
| **Trigger** | 15% of drivers classified as "declining" or "at_risk" |

### Questions to validate
1. Is the "at_risk" classification actionable? What does the operator do with it?
2. Are the dominant factors (trip_decline, inactivity_risk) clear and useful?
3. Do operators want more detail (city breakdown, park breakdown)?
4. Is the 28-day window appropriate for operational decisions?

---

## SCENARIO E: Monitoring — Top Deterioration Scan

| Field | Value |
|---|---|
| **Role** | Operations analyst doing morning scan |
| **Grain** | Any |
| **Mode** | Any |
| **Trigger** | Daily check-in — "what's wrong today?" |

### Questions to validate
1. What does the operator look at FIRST?
2. How long does it take to answer "what needs attention today?"?
3. Is the priority strip the first thing they read? Or do they go straight to the matrix?
4. What information is NEVER looked at?

---

## SCENARIO F: Drill — Root Cause Investigation

| Field | Value |
|---|---|
| **Role** | Operations analyst investigating a specific city/line deterioration |
| **Grain** | Any |
| **Mode** | Projection |
| **Trigger** | Clicking a red cell to understand why |

### Questions to validate
1. Does the operator use the Momentum tab or the Plan vs Real tab?
2. Is the "Plan vs Real" default correct? Or should Momentum be first?
3. Is the fullscreen drill useful? Or is the side panel enough?
4. Does the root cause analysis (gap decomposition) make sense to operators?

---

## SCENARIO G: Freshness / Trust Issues

| Field | Value |
|---|---|
| **Role** | Operations manager encountering stale data |
| **Grain** | Any |
| **Trigger** | Data freshness degraded, trust warnings visible |

### Questions to validate
1. Does the operator notice the freshness/trust indicators?
2. Do they understand what "stale data" means?
3. Do they act differently on stale vs fresh data?
4. Is the integrity broken banner clear enough?

---

## USAGE GRID (to fill during sessions)

| Scenario | Operator understood in <30s? | Action taken? | Confusion? | Missing signal? |
|---|---|---|---|---|
| A (Daily DoD) | _ | _ | _ | _ |
| B (Weekly WoW) | _ | _ | _ | _ |
| C (Monthly MoM) | _ | _ | _ | _ |
| D (Supply) | _ | _ | _ | _ |
| E (Morning scan) | _ | _ | _ | _ |
| F (Drill) | _ | _ | _ | _ |
| G (Freshness) | _ | _ | _ | _ |
