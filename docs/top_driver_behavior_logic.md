# Top Driver Behavior — Logic and Benchmarks

**Project:** YEGO Control Tower  
**Feature:** Top Driver Behavior (Elite/Legend patterns and playbook insights)

---

## 1. Purpose

Discover **operational behavior patterns** of Elite and Legend drivers so their behaviors can be taught, nudged, or replicated. Benchmark-oriented: what do top performers do differently?

---

## 2. Input population

- **Primary:** segment_current IN ('ELITE', 'LEGEND').  
- **Optional comparison:** segment_current = 'FT'.  
- **Source:** ops.mv_driver_behavior_alerts_weekly (and baseline for extra metrics) or ops.mv_driver_segments_weekly; filter by segment_week / segment_current.

---

## 3. Metrics to derive (where data supports)

| Metric | Description | Source / note |
|--------|-------------|----------------|
| **active_weeks** | Count of weeks with trips in window | active_weeks_in_window (baseline); or COUNT(week_start) per driver in range. |
| **avg_weekly_trips** | Mean trips per week in window | AVG(trips_current_week) or avg_trips_baseline. |
| **consistency_score** | Low variance vs mean (e.g. 1 - CV or stable weeks %) | stddev_trips_baseline, avg_trips_baseline from baseline view. |
| **pct_weeks_high_segment** | % of weeks in ELITE/LEGEND (or FT+) | From driver-week rows: COUNT(segment IN ('ELITE','LEGEND')) / COUNT(*). |
| **city / park concentration** | Where top drivers concentrate | GROUP BY city, park_id; driver count or trip share. |
| **day_of_week** | Best day contribution (if available) | Requires trip-level or daily data; document if not available. |
| **time_slot** | Best time-slot (if available) | Requires time-of-day; document if not available. |

---

## 4. Benchmarks (aggregate)

- **Elite vs Legend:** Avg trips per week, consistency, active_weeks; side-by-side.  
- **Elite/Legend vs FT:** Same metrics; highlight gaps (e.g. "Elite drivers show 20% higher consistency than FT").  
- **Top city/park:** Where Elite and Legend drivers concentrate (driver count, trip share).  
- **Recovery speed:** If we have weeks_declining/rising or movement_type, proportion of top drivers that recover quickly after a drop (optional).

---

## 5. Playbook-style insights (operational)

- "Elite drivers show stronger weekly consistency than FT drivers."  
- "Legend drivers concentrate more volume in specific parks/days."  
- "FT drivers who already resemble Elite patterns (high consistency, high active_weeks) are near-upgrade candidates."  
- "Recoverable Elite behavior signatures: high baseline, one-off drop, then recovery."  
- Generated from benchmark comparisons and rules; stored as text or computed in API.

---

## 6. Outputs

- **Summary:** Total Elite drivers, total Legend drivers, total FT (optional); date range.  
- **Benchmarks table:** segment_current (ELITE, LEGEND, FT), avg_weekly_trips, consistency_score, pct_weeks_high_segment, active_weeks_avg.  
- **Patterns table:** e.g. by city, by park — driver count, avg trips, share of segment.  
- **Playbook insights:** List of 3–5 short textual insights for the UI.  
- **Export:** Elite list, Legend list, or benchmark summary (CSV/Excel).

---

## 7. Data availability note

- **day_of_week / time_slot:** Not in current mv_driver_behavior_alerts_weekly or baseline view. Omit or leave as "TBD" until trip-level or daily driver activity is available.  
- **Consistency:** From baseline (stddev, avg); compute as coefficient of variation or stable-weeks %.  
- **Concentration:** From existing geo (city, park_id) in alerts MV.

---

## 8. Objects

- **ops.v_top_driver_behavior_weekly:** Driver-week rows for segment_current IN ('ELITE','LEGEND','FT') from alerts MV; optional computed consistency_score.  
- **ops.v_top_driver_behavior_benchmarks:** Aggregates by segment_current (and optionally week_start): avg_trips, consistency, pct_high_weeks, driver_count.  
- **ops.v_top_driver_behavior_patterns:** Aggregates by segment_current, city, park_id: driver_count, avg_trips, share.
