# State-Based Loyalty Architecture — YEGO Lima Growth Tower

## Fase 2D-R — Canonical States + Daily Opportunity Engine + Legacy Deprecation

---

## 1. Why SEGMENT ≠ PROGRAM ≠ LIST

The old architecture mixed three distinct concepts:

| Concept | Wrong (Old) | Right (New) |
|---------|-------------|-------------|
| Driver State | `segment_level_1/2/3` mixed lifecycle + loyalty + cohort | `lifecycle_state` + `performance_state` + `retention_state` |
| Program | `LEALTAD_1_14_90` treated as segment L2 | `PROGRAM_14_90` is an operational program that consumes states |
| Daily List | Actionable list treated as permanent state | Daily opportunity list generated fresh from programs |

**Principle**: Programs consume states. Lists are generated daily from programs and rules. Lists are NOT permanent states.

---

## 2. Lifecycle State

What stage the driver is in their lifecycle.

| State | Description |
|-------|-------------|
| `PROSPECT` | Not yet registered |
| `REGISTERED` | Registered but never activated |
| `ACTIVATED` | Had first trip, still early (<90 days) |
| `EARLY_LIFE` | First 14 days since first week |
| `ESTABLISHED` | Active with stable history (>90 days) |
| `REACTIVATED` | Returned after inactivity > recovery_days |
| `CHURNED` | No activity > churn_days |
| `UNKNOWN` | Insufficient data |

---

## 3. Performance State

How the driver performs vs weekly target.

| State | Rule |
|-------|------|
| `NO_TRIPS` | 0 trips this week |
| `LOW` | trips <= target * low_performance_ratio (0.4) |
| `MEDIUM` | trips <= target * medium_performance_ratio (0.8) |
| `TARGET` | trips <= target |
| `HIGH` | trips > target |
| `UNKNOWN` | No data |

---

## 4. Retention State

Risk of driver churning.

| State | Rule |
|-------|------|
| `HEALTHY` | Active, stable or growing |
| `WATCHLIST` | Slight decline vs 4-week average |
| `AT_RISK` | Decline >= DECLINE_WARNING_PCT (15%) |
| `CHURN_RISK` | Decline >= DECLINE_RISK_PCT (30%) or near churn threshold |
| `UNKNOWN` | No data |

---

## 5. Operational Programs

Programs evaluate eligibility from driver states. A driver can be in multiple programs simultaneously.

### PROGRAM_14_90
- **Goal**: Activate and accelerate early-life drivers
- **Eligibility**: lifecycle_state IN (REGISTERED, ACTIVATED, EARLY_LIFE, REACTIVATED), still in 14/90 window, NOT reached target

### PROGRAM_ACTIVE_GROWTH
- **Goal**: Increase trips for underperforming drivers
- **Eligibility**: performance_state IN (NO_TRIPS, LOW, MEDIUM), lifecycle IN (ACTIVATED, EARLY_LIFE, ESTABLISHED, REACTIVATED), distance_to_target > 0

### PROGRAM_CHURN_PREVENTION
- **Goal**: Retain at-risk drivers
- **Eligibility**: retention_state IN (AT_RISK, CHURN_RISK) OR declining_flag OR churn_risk_flag

---

## 6. Daily Opportunity Engine

Each day, the engine:

1. Reads `program_eligibility_daily` (latest)
2. Reads `driver_state_snapshot` (latest)
3. Generates `daily_opportunity_list` fresh for the day
4. Each opportunity has `management_status = PENDING_ACTION`
5. Previous day's PENDING are NOT carried forward

### Opportunity Types

| Type | Maps from Program |
|------|-------------------|
| `OPPORTUNITY_14_90` | PROGRAM_14_90 |
| `OPPORTUNITY_ACTIVE_GROWTH` | PROGRAM_ACTIVE_GROWTH |
| `OPPORTUNITY_CHURN_PREVENTION` | PROGRAM_CHURN_PREVENTION |

---

## 7. Daily Reset

- Lists are generated fresh each day (no carry-forward)
- Previous day PENDING_ACTION items are closed as NO_ACTION by `close-unmanaged-opportunities`
- Historical records are preserved
- Each day is a clean slate

---

## 8. Connection to Control Loop

```
Driver360 Daily ──→ Driver State Snapshot
                         │
                    Program Eligibility
                         │
                  Daily Opportunity Lists
                         │
                    Action Registry
                         │
                    Daily Impact
                         │
                  Segment Transitions
                         │
                  Impact Attribution
```

---

## 9. What is Deprecated (LEGACY)

| Item | Status | Replacement |
|------|--------|-------------|
| `growth.yango_lima_driver_segment_snapshot` | LEGACY (preserved) | `driver_state_snapshot` |
| `growth.yango_lima_actionable_list_daily` | LEGACY (preserved) | `daily_opportunity_list` |
| `segment_level_1/2/3` | LEGACY (preserved) | `lifecycle_state/performance_state/retention_state` |
| `LEALTAD_1_14_90` / `LEALTAD_2_ACTIVE_GROWTH` / `LEALTAD_3_CHURN_PREVENTION` | LEGACY (preserved) | `OPPORTUNITY_14_90` / `OPPORTUNITY_ACTIVE_GROWTH` / `OPPORTUNITY_CHURN_PREVENTION` |
| Legacy endpoints (read-only) | Preserved for backward compat | New `/state`, `/programs`, `/opportunities` endpoints |

Old tables and logic are NOT deleted. They are marked LEGACY and preserved for backward compatibility.

---

## 10. Future Dashboard

When the dashboard is built (future phase), it will show:

- **Lifecycle distribution**: how many drivers in each lifecycle state
- **Performance distribution**: how drivers perform vs targets
- **Retention distribution**: how many at-risk drivers
- **Program counts**: how many eligible per program
- **Opportunity counts**: how many generated per day
- **Management status**: PENDING vs CONFIRMED vs NO_ACTION
- **Segment movement**: drivers improving/worsening day over day

---

## New Tables

| Table | Grain | Purpose |
|-------|-------|---------|
| `growth.yango_lima_driver_state_snapshot` | snapshot_date + driver_profile_id | Canonical driver states |
| `growth.yango_lima_program_eligibility_daily` | eligibility_date + driver_profile_id + program_code | Program eligibility evaluation |
| `growth.yango_lima_daily_opportunity_list` | opportunity_date + driver_profile_id + opportunity_type | Daily actionable opportunities |

## New Settings

| Setting | Default | Purpose |
|---------|---------|---------|
| `LIMA_GROWTH_NEW_DRIVER_WINDOW_DAYS` | 14 | Days for EARLY_LIFE classification |
| `LIMA_GROWTH_RETENTION_WINDOW_DAYS` | 90 | Window for lifecycle transition |
| `LIMA_GROWTH_LOW_PERFORMANCE_RATIO` | 0.4 | LOW performance threshold |
| `LIMA_GROWTH_MEDIUM_PERFORMANCE_RATIO` | 0.8 | MEDIUM performance threshold |

## New Endpoints

All under `/yego-lima-growth`:

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/state/build-driver-states` | Build driver state snapshot |
| GET | `/state/summary` | State distribution |
| GET | `/state/drivers` | List drivers by state |
| GET | `/state/driver/{id}` | Single driver state |
| POST | `/programs/build-eligibility` | Build program eligibility |
| GET | `/programs/summary` | Program counts |
| GET | `/programs/drivers` | List drivers by program |
| POST | `/opportunities/build-daily` | Generate daily opportunities |
| POST | `/opportunities/close-unmanaged` | Close unmanaged from previous day |
| GET | `/opportunities/daily` | Query daily opportunities |
| POST | `/opportunities/assign-agent` | Assign agent to opportunity |
| POST | `/opportunities/link-action` | Link action to opportunity |
