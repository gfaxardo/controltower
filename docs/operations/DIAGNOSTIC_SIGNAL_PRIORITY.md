# DIAGNOSTIC SIGNAL PRIORITY

**Date**: 2025-05-25
**Purpose**: Rank missing signals by operational impact, not by technical availability

---

## Priority Framework

Each missing signal is scored on:
- **Impact** (1-5): How much operational value does it unlock?
- **Feasibility** (1-5): How easy is it to add to the fact table?
- **Urgency** (1-5): How often do operators ask for it?

Score = Impact × Urgency. Feasibility is a secondary filter.

---

## SIGNAL RANKING

### TIER 1 — Unblock immediately (highest impact)

| # | Signal | Dimensions Unblocked | Impact | Feasibility | Urgency | Score |
|---|---|---|---|---|---|---|
| 1 | `online_hours` | time_efficiency, productivity | 5 | 4 | 5 | **25** |
| 2 | `cancellation` | cancellation_behavior | 4 | 4 | 4 | **16** |
| 3 | `acceptance` | cancellation_behavior | 4 | 4 | 4 | **16** |

**Rationale**: 
- `online_hours` enables trips/hour (true productivity) and detects "online but not driving" (supply inefficiency)
- `cancellation` + `acceptance` detect behavioral deterioration (driver rejecting more, cancelling more) before trip count drops

---

### TIER 2 — Add next sprint

| # | Signal | Dimensions Unblocked | Impact | Feasibility | Urgency | Score |
|---|---|---|---|---|---|---|
| 4 | `zone` | geographic_behavior, city_mix | 4 | 3 | 3 | **12** |
| 5 | `revenue` | revenue_efficiency | 3 | 4 | 3 | **9** |
| 6 | `trip_hour` | time_efficiency | 3 | 3 | 3 | **9** |

**Rationale**:
- `zone` enables area coverage analysis — "are drivers spreading or concentrating?"
- `revenue` enables earnings/driver — "are trips declining because of demand or driver behavior?"
- `trip_hour` enables shift pattern detection — "is driver switching from peak to off-peak?"

---

### TIER 3 — Add when resources allow

| # | Signal | Dimensions Unblocked | Impact | Feasibility | Urgency | Score |
|---|---|---|---|---|---|---|
| 7 | `distance` | distance_efficiency | 2 | 4 | 2 | **4** |
| 8 | `duration` | time_efficiency | 2 | 4 | 2 | **4** |
| 9 | `tipo_servicio` | lob_mix | 2 | 2 | 1 | **2** |
| 10 | `avg_ticket` | revenue_efficiency | 2 | 4 | 1 | **2** |

**Rationale**:
- Distance/duration are nice-to-have efficiency metrics but lower operational priority
- `tipo_servicio` (service type: economy/premium) is useful for segmentation but lower urgency
- `avg_ticket` is derived from revenue/trips — add after revenue

---

## Technical Path

### For TIER 1 (online_hours, cancellation, acceptance)

The `public.trips_2026` fallback table likely already has these columns. Options:

**Option A**: Extend `ops.driver_daily_activity_fact` with pre-aggregated columns:
```sql
ALTER TABLE ops.driver_daily_activity_fact
  ADD COLUMN online_hours NUMERIC,
  ADD COLUMN cancelled_trips INT,
  ADD COLUMN accepted_trips INT;
```
Then populate via ETL from `trips_2026`.

**Option B**: Join with `trips_2026` on-the-fly in the MVP service. Risk: slower queries.

**Recommendation**: Option A — serves governance first.

---

## Decision Matrix (to be filled by operations team)

| Signal | Operations says "need this NOW"? | Why? |
|---|---|---|
| online_hours | _ | _ |
| cancellation | _ | _ |
| acceptance | _ | _ |
| zone | _ | _ |
| revenue | _ | _ |
