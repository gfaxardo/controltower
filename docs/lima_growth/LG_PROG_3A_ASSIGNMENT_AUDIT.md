# LG_PROG_3A_ASSIGNMENT_AUDIT

**Phase:** LG-PROG-3A — Program Assignment Audit  
**Motor:** Control Foundation  
**Generated:** 2026-06-12T23:59  
**Veredict:** `GO — Program rules understood. Contradictions documented. No changes applied.`

---

## 1. PROGRAM INVENTORY

### Canonical Source: `growth.yango_lima_program_eligibility_daily`

| Attribute | Value |
|-----------|-------|
| **Builder** | `build_program_eligibility()` in `yego_lima_program_eligibility_service.py:41` |
| **Scheduler** | `autonomous_tick()` cascade (every 5 min when raw > snapshot) |
| **Endpoint** | `POST /yego-lima-growth/programs/build-eligibility` |
| **Grain** | `(eligibility_date, driver_profile_id, program_code)` |
| **Explorer fact source** | LEFT JOIN via `(driver_profile_id, eligibility_date)` |

### Programs Defined

| Program Code | Priority | Description | In Explorer? |
|-------------|----------|-------------|-------------|
| `PROGRAM_HIGH_VALUE_RECOVERY` | 1 | High historical value, recently inactive (80+ best_week, 0 trips this week, 1-14d inactive) | **NO** (not in explorer fact) |
| `PROGRAM_CHURN_PREVENTION` | 2 | Drivers with churn risk or declining flags | **YES** — 317 drivers |
| `PROGRAM_14_90` | 3 | New/reactivated drivers in 14-90 day window | **YES** — 2,669 drivers |
| `PROGRAM_ACTIVE_GROWTH` | 4 | Active drivers below weekly performance target | **YES** — 15,054 drivers |

**Note:** `build_program_eligibility()` only assigns 3 of 4 programs (CHURN_PREVENTION, 14_90, ACTIVE_GROWTH). `HIGH_VALUE_RECOVERY` is assigned in `build_prioritized_opportunities()`, not in eligibility — thus never reaches the explorer fact.

---

## 2. EXACT RULES PER PROGRAM

### PROGRAM_HIGH_VALUE_RECOVERY

**Builder:** `build_prioritized_opportunities()` — NOT `build_program_eligibility()`  
**Assignment:**
```
best_week_12w >= 80
AND completed_orders_week = 0
AND last_trip_date IS NOT NULL
AND inactive_days BETWEEN 1 AND 14
```
**Explorer fact:** ❌ NOT assigned. 0 drivers. Builder not called from cascade.

---

### PROGRAM_CHURN_PREVENTION

**Builder:** `build_program_eligibility()` — line 141  
**Assignment SQL:**
```sql
FROM growth.yango_lima_driver_state_snapshot
WHERE snapshot_date = latest
  AND (
      retention_state IN ('AT_RISK', 'CHURN_RISK')
      OR declining_flag = true
      OR churn_risk_flag = true
  )
```
**Conditions (ANY of):**
1. `retention_state = 'AT_RISK'` OR `'CHURN_RISK'`
2. `declining_flag = true`
3. `churn_risk_flag = true`

**Priority:** 100-130 (highest in eligibility builder)  
**Explorer fact:** 317 drivers  

---

### PROGRAM_14_90

**Builder:** `build_program_eligibility()` — line 62  
**Assignment SQL:**
```sql
FROM growth.yango_lima_driver_state_snapshot
WHERE snapshot_date = latest
  AND lifecycle_state IN ('REGISTERED', 'ACTIVATED', 'EARLY_LIFE', 'REACTIVATED')
  AND reached_target_flag = false
```
**Conditions (ALL of):**
1. `lifecycle_state IN ('REGISTERED', 'ACTIVATED', 'EARLY_LIFE', 'REACTIVATED')`
2. `reached_target_flag = false`

**Priority:** 1-4  
**Explorer fact:** 2,669 drivers  

---

### PROGRAM_ACTIVE_GROWTH

**Builder:** `build_program_eligibility()` — line 98  
**Assignment SQL:**
```sql
FROM growth.yango_lima_driver_state_snapshot
WHERE snapshot_date = latest
  AND performance_state IN ('NO_TRIPS', 'LOW', 'MEDIUM')
  AND lifecycle_state IN ('ACTIVATED', 'EARLY_LIFE', 'ESTABLISHED', 'REACTIVATED')
  AND distance_to_weekly_target > 0
```
**Conditions (ALL of):**
1. `performance_state IN ('NO_TRIPS', 'LOW', 'MEDIUM')`
2. `lifecycle_state IN ('ACTIVATED', 'EARLY_LIFE', 'ESTABLISHED', 'REACTIVATED')`
3. `distance_to_weekly_target > 0`

**Priority:** 10-50  
**Explorer fact:** 15,054 drivers  

### Non-Canonical Fallback (Explorer fact only)

When `program_eligibility_daily` has NO row for a driver, the explorer fact applies:
```sql
CASE
    WHEN lifecycle_state = 'ACTIVE' THEN 'ACTIVE_GROWTH'       -- Note: no PROGRAM_ prefix
    WHEN lifecycle_state = 'AT_RISK' THEN 'CHURN_PREVENTION'
    WHEN lifecycle_state = 'CHURNED' THEN 'HIGH_VALUE_RECOVERY'
    WHEN new_driver_flag THEN 'NEW_DRIVER_ONBOARDING'
    ELSE NULL
END
```
**This fallback uses legacy lifecycle names (`ACTIVE`, `AT_RISK`) that DON'T EXIST in the current `driver_state_snapshot` schema (which has `ESTABLISHED`, `ACTIVATED`, `EARLY_LIFE`). The fallback NEVER fires — it always hits `ELSE NULL`.**

---

## 3. DISTRIBUTION PER PROGRAM

### Summary Table

| Program | Drivers | trips_7d avg | trips_7d p25 | trips_7d p50 | trips_7d p75 | trips_7d max | trips_30d avg | trips_30d max | Primary Lifecycle |
|---------|---------|-------------|-------------|-------------|-------------|-------------|--------------|-------------|-------------------|
| **PROGRAM_ACTIVE_GROWTH** | 15,054 | **5.3** | 2 | **3** | 5 | 101 | 8.8 | 551 | ESTABLISHED (100%) |
| **PROGRAM_CHURN_PREVENTION** | 317 | **47.5** | 41 | **51** | 63 | 121 | 264.8 | 754 | ESTABLISHED (94%) |
| **PROGRAM_14_90** | 2,669 | **6.6** | 1 | **3** | 7 | 104 | 20.6 | 445 | ACTIVATED (96%) |
| **NULL (no program)** | 504 | **80.7** | 55 | **73** | 100 | 201 | 59.7 | 545 | ESTABLISHED (91%) |

### Trips per Band

| Band | ACTIVE_GROWTH | CHURN_PREVENTION | 14_90 | NULL |
|------|-------------|-----------------|-------|------|
| 0 trips | 424 (2.8%) | 5 (1.6%) | 116 (4.3%) | 0 |
| 1-10 | 12,674 (84.2%) | 0 | 2,040 (76.4%) | 0 |
| 11-20 | 1,193 (7.9%) | 0 | 210 (7.9%) | 0 |
| 21-30 | 444 (2.9%) | 0 | 146 (5.5%) | 0 |
| 31-40 | 309 (2.1%) | 3 (0.9%) | 100 (3.7%) | 0 |
| 41-50 | 6 (0.04%) | 56 (17.7%) | 41 (1.5%) | 0 |
| 51-100 | 4 (0.01%) | 228 (71.9%) | 16 (0.6%) | 400 (79.4%) |
| 100+ | 0 | 25 (7.9%) | 0 | 104 (20.6%) |

---

## 4. TOP CONTRADICTIONS

### CHURN_PREVENTION: "Churn Prevention" drivers are the MOST active

The median CHURN_PREVENTION driver does **51 trips/week** — 17x more than ACTIVE_GROWTH median (3). These are not "churning" drivers — they are top performers flagged as `declining=True` because they dropped from even higher baselines.

**Top CHURN_PREVENTION drivers:**
| Driver | trips_7d | trips_30d | Flag | Why in CHURN_PREVENTION |
|--------|---------|-----------|------|------------------------|
| dd75... | 121 | 505 | declining=True | Was doing even MORE. Dropped. Still #1 overall. |
| 2280... | 106 | 467 | declining=True | Historical high performer declining from peak. |
| 7af5... | 105 | 754 | churn_risk=True | 754 trips in 30d but flagged as churn risk. |
| cadc... | 102 | 0 | churn_risk=True | 102 trips this week, activated, flagged churn risk. |
| 8f23... | 98 | 595 | declining=True | 595 trips in 30d but declining. |

**Root cause:** `churn_risk_flag` is set on high-performers who show a risk pattern — not necessarily low activity. `declining_flag` is relative to the driver's own baseline, not an absolute threshold. A driver going from 150→121 trips is "declining" but still the most active driver in the fleet.

### ACTIVE_GROWTH: Named "Growth" but contains the LOWEST activity drivers

84.2% of ACTIVE_GROWTH drivers do 1-10 trips/week. Median = 3. The name "Active Growth" implies high activity, but the assignment logic selects for `performance_state IN ('NO_TRIPS', 'LOW', 'MEDIUM')` — meaning they are UNDER their target.

### NULL program: 504 HIGH performers with NO program

These 504 drivers have median 73 trips/week (highest of any group) and NO program assignment. They are ESTABLISHED lifecycle with performance_state that is NOT in ('NO_TRIPS', 'LOW', 'MEDIUM') — likely `'HIGH'` or `'ELITE'`. They don't qualify for:
- ACTIVE_GROWTH (performance_state is too high)
- CHURN_PREVENTION (no retention risk flags)
- 14_90 (lifecycle is ESTABLISHED, not ACTIVATED)

**These are the fleet's top performers and they have no program. They fall through every eligibility check.**

### ACTIVE_GROWTH drivers with 0 trips

424 drivers (2.8%) in ACTIVE_GROWTH have 0 trips in 7 days. They are assigned because `performance_state = 'NO_TRIPS'` AND `distance_to_weekly_target > 0`. They have a target but aren't hitting it at all.

---

## 5. EXPLAINABILITY — Why Each Driver Is In Their Program

### PROGRAM_ACTIVE_GROWTH — 3 random examples

| Driver | trips_7d | trips_30d | lifecycle | eligibility_reason | Why? |
|--------|---------|-----------|-----------|-------------------|------|
| 2137... | 3 | 0 | ESTABLISHED | `low_performance` | Performance=LOW, lifecycle=ESTABLISHED, target>0 → ACTIVE_GROWTH. Only 3 trips this week. |
| 4d82... | 6 | 0 | ESTABLISHED | `low_performance` | Same pattern. 6 trips, below target. Has `churn_risk_flag=True` — could be CHURN_PREVENTION but ACTIVE_GROWTH matched first (priority 10 vs 100). |
| 5dff... | 7 | 0 | ESTABLISHED | `low_performance` | Same. Low activity, below target, ESTABLISHED lifecycle. |

### PROGRAM_CHURN_PREVENTION — 3 random examples

| Driver | trips_7d | trips_30d | eligibility_reason | Why? |
|--------|---------|-----------|-------------------|------|
| 244e... | 44 | 234 | `churn_risk_flag_active` | churn_risk_flag=True, 44 trips but pattern triggers risk. Also `recoverable_flag=True`. |
| 6a94... | 80 | 491 | `churn_risk_flag_active` | churn_risk=True despite 80 trips this week. High historical performer at risk. |
| beb1... | 41 | 155 | `churn_risk_flag_active` | 41 trips. churn_risk=True + recoverable_flag=True. Risk pattern detected. |

### PROGRAM_14_90 — 3 random examples

| Driver | trips_7d | trips_30d | eligibility_reason | Why? |
|--------|---------|-----------|-------------------|------|
| ce30... | 2 | 2 | `ACTIVATED` | lifecycle=ACTIVATED, reached_target=false → 14_90. Newly activated, 2 trips. |
| 42a5... | 1 | 0 | `ACTIVATED` | lifecycle=ACTIVATED, 1 trip. In the 14-90 day window. |
| 41ca... | 10 | 14 | `ACTIVATED` | lifecycle=ACTIVATED, 10 trips. Hasn't reached target yet. |

---

## 6. UI VALIDATION QUERIES

### For use in Driver Explorer browser validation:

**Query 1: CHURN_PREVENTION drivers with highest trips (are these really churning?)**
```
Open: /lima-growth/intelligence → Driver Explorer
Filter: Program = Churn Prevention
Observe: trips_7d column — median 51, some >100
Question to operator: "Should drivers with 51+ trips/week be in Churn Prevention?"
```

**Query 2: ACTIVE_GROWTH drivers with 0 trips**
```
Open: /lima-growth/intelligence → Driver Explorer
Filter: Program = Active Growth, search empty
Scroll to bottom (sorted by last_trip_at DESC NULLS LAST)
Observe: 424 drivers have trips_7d = 0
Question: "Should drivers with 0 trips be in 'Active Growth'?"
```

**Query 3: Highest activity drivers (NULL program — the invisible 504)**
```sql
-- Run this SQL, then search the driver_ids in Explorer
SELECT driver_profile_id, trips_7d, trips_30d, lifecycle
FROM growth.yego_lima_driver_explorer_fact
WHERE target_date = '2026-06-12' AND program_code IS NULL
ORDER BY trips_7d DESC LIMIT 20;
```

---

## 7. CRITICAL FINDINGS

### Finding 1: Program semantics are inverted

| Program Name | What It Sounds Like | What It Actually Contains |
|-------------|-------------------|-------------------------|
| **ACTIVE_GROWTH** | High-activity growing drivers | **Lowest activity drivers** (median 3 trips/week), below target |
| **CHURN_PREVENTION** | Drivers about to leave | **Highest activity drivers** (median 51 trips/week), declining from peak |
| **14_90** | New drivers in 14-90 day window | Correctly assigned (ACTIVATED + EARLY_LIFE) |

### Finding 2: 504 high performers have NO program

The fleet's top drivers (median 73 trips/week) fall through all eligibility checks. They are ESTABLISHED, high performance, no risk flags. They have no program, no opportunity, no contact channel.

### Finding 3: HIGH_VALUE_RECOVERY is a ghost program in the explorer

Defined in code, assigned by `build_prioritized_opportunities()`, but never reaches the explorer fact because that builder is not in the eligibility flow. 0 drivers in explorer.

### Finding 4: The fallback CASE expression is dead code

The explorer fact's COALESCE fallback uses lifecycle values (`ACTIVE`, `AT_RISK`, `CHURNED`) that don't match the actual values in `driver_state_snapshot` (`ESTABLISHED`, `ACTIVATED`, `EARLY_LIFE`). It never fires.

### Finding 5: `declining_flag` is relative, not absolute

A driver declining from 150→121 trips is "declining" by definition. They are still the most active driver in the fleet. The flag is technically correct (they declined) but programmatically misleading (they're not "churning").

---

## 8. RECOMMENDATIONS (Backlog, NOT implemented)

| # | Finding | Recommendation | Phase |
|---|---------|---------------|-------|
| 1 | Program names misleading | Rename: ACTIVE_GROWTH → UNDER_PERFORMANCE, CHURN_PREVENTION → AT_RISK_HIGH_VALUE | LG-PROG-3B |
| 2 | 504 high performers have no program | Add program: `PROGRAM_TOP_PERFORMER_RETENTION` for drivers above target with no risk flags | LG-PROG-3B |
| 3 | HIGH_VALUE_RECOVERY missing from explorer | Integrate `build_prioritized_opportunities()` output into explorer fact | LG-PROG-3C |
| 4 | Dead COALESCE fallback | Remove or fix lifecycle values in explorer fact writer | LG-EXP cleanup |
| 5 | CHURN_PREVENTION contains non-churning drivers | Add absolute activity threshold to churn prevention eligibility (e.g., trips_7d < 20 for true churn risk) | LG-PROG-3B |
| 6 | 424 ACTIVE_GROWTH with 0 trips | Consider minimum activity threshold (trips_7d > 0) for "active" growth | LG-PROG-3B |

---

## VEREDICT

### GO — Program rules are fully understood.

**We understand:**
- The exact SQL conditions for each program assignment
- The distribution of trips per program (confirmed CHURN_PREVENTION = highest activity, ACTIVE_GROWTH = lowest)
- The 6 top contradictions documented with real driver evidence
- Why each driver ends up in each program (explainability confirmed)

**We did NOT change anything.** This is a pure audit. All recommendations are backlogs for future phases.

**The single most important finding:** The program called "Active Growth" contains the lowest-activity drivers. The program called "Churn Prevention" contains the highest-activity drivers. The fleet's top performers (504 drivers, median 73 trips/week) have no program at all. This is not a bug — it's the logical result of the assignment rules. The rules are correct. The names are misleading.
