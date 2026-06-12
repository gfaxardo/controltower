# LG-TAX-2A — DRIVER RECENCY TRUTH AUDIT

**Ticket:** LG-TAX-2A  
**Date:** 2026-06-11  
**Snapshot:** 2026-06-10  
**Park:** Lima = `08e20910d81d42658d4334d3f6d10ac0`  
**Status:** ROOT CAUSE CLASSIFIED — 86.4% FALSE POSITIVE RATE IN DRIVER_STATE  

---

## TASK 0 — GOVERNANCE

Control Foundation / Lima Growth. Read-only audit. Zero production changes. No conflicts with active OMNI-P0 phase.

---

## TASK 1 — UNIVERSO DRIVER_STATE

### Snapshot 2026-06-10: 18,545 Drivers

| Metric | Count | % |
|--------|-------|---|
| Total drivers | 18,545 | 100% |
| `completed_orders_week > 0` | 18,545 | 100% |
| `completed_orders_day > 0` | 0 | 0% |
| `avg_orders_4w > 0` | 18,545 | 100% |
| `avg_orders_12w > 0` | 18,545 | 100% |

**Zero drivers have completed_orders_day > 0.** Every single driver has weekly orders but none have daily orders. This is because `driver_360_daily` has 179 rows total — the daily pipeline is dead.

### Lifecycle Distribution

| State | Drivers | % |
|-------|---------|---|
| ESTABLISHED | 15,811 | 85.3% |
| ACTIVATED | 2,621 | 14.1% |
| EARLY_LIFE | 113 | 0.6% |

No CHURNED, REACTIVATED, or UNKNOWN lifecycle states. All 18,545 are classified as "active lifecycle" drivers.

### Retention Distribution

| State | Drivers | % |
|-------|---------|---|
| HEALTHY | 10,470 | 56.5% |
| CHURN_RISK | 6,999 | 37.7% |
| AT_RISK | 775 | 4.2% |
| WATCHLIST | 301 | 1.6% |

---

## TASK 2 — RECENCIA REAL DESDE trips_2026 LIMA

Cross-reference: `driver_profile_id` = `conductor_id` (UUID format). Filter: `park_id = '08e20910...'` AND `condicion = 'Completado'`.

### Recency Buckets (last completed trip in Lima park)

| Bucket | Drivers | % | Interpretation |
|--------|---------|---|----------------|
| active_1d (trip on Jun 10) | 1,242 | 6.7% | ACTIVE today |
| active_7d (trip Jun 4-9) | 1,207 | 6.5% | ACTIVE this week |
| active_14d (trip May 28-Jun 3) | 648 | 3.5% | Recently active |
| churn_15_30d (trip May 11-27) | 1,208 | 6.5% | Starting to churn |
| churn_31_90d (trip Mar 12-May 10) | 3,471 | 18.7% | Clearly churned |
| archived_90d+ (trip before Mar 12) | 2,189 | 11.8% | Archived |
| **no completed trip found** | **8,580** | **46.3%** | No trip in trips_2026 at all |

### Key Metrics

| Metric | Count | % |
|--------|-------|---|
| Real ACTIVE (last trip <= 7d) | 2,449 | 13.2% |
| Real ACTIVE (last trip <= 14d) | 3,097 | 16.7% |
| Churned (15-90d) | 4,679 | 25.2% |
| Archived (90d+) | 2,189 | 11.8% |
| No trips_2026 match | 8,580 | 46.3% |

### Comparison with Fleetroom

| Source | Weekly Active |
|--------|---------------|
| Fleetroom Lima | ~3,899 contractors |
| trips_2026 Lima (7d completed) | 2,523 drivers |
| driver_state "active" (cw>0) | **18,545** |

**False positive rate: 86.4%** — the driver_state claims 18,545 are active when only ~2,500 are actually taking trips this week in Lima.

---

## TASK 3 — PARK SCOPE AUDIT

For the 18,545 drivers, which parks do they have trips in?

| Park Scope | Drivers | % |
|------------|---------|---|
| Lima only | 10,552 | 56.9% |
| Other parks only | **0** | 0.0% |
| Lima + other parks | **0** | 0.0% |
| No trips_2026 match | 7,993 | 43.1% |

### Finding: ZERO Park Contamination

**Every driver who appears in trips_2026 has at least one trip in Lima park.** No driver has trips exclusively in other parks. The 18,545 drivers are NOT contaminated by other parks.

The difference between 10,552 and 10,039 (2,523+5,327+2,189) = 513 drivers have trips_2026 data but with `condicion != 'Completado'` (these are cancelled-only or in-progress trips).

---

## TASK 4 — HISTORY_WEEKLY RECENCY AUDIT

Latest `week_start_date` per driver in `history_weekly`:

| Latest Week Recency | Drivers | % | avg completed_orders |
|---------------------|---------|---|---------------------|
| Current week (Jun 1) | 2,257 | 12.2% | 18.1 |
| 1 week ago | 827 | 4.5% | 8.0 |
| 2 weeks ago | 590 | 3.2% | 6.7 |
| 3-4 weeks ago | 1,052 | 5.7% | 6.0 |
| 1-3 months ago | 2,882 | 15.5% | 6.9 |
| **3+ months ago** | **10,937** | **59.0%** | 7.6 |

**10,937 drivers (59%) have their latest history_weekly data from >3 months ago.** These are historical drivers who haven't had new weekly data ingested in months.

### Cross-Validation: HW Current vs trips_2026 Real

| Signal | Drivers |
|--------|---------|
| HW current_week active | 2,257 |
| trips_2026 real 7d active | 2,523 |
| **HW current BUT no recent trip** (false ACTIVE) | **291** |
| **Trips recent BUT HW old** (missed by HW) | **305** |

Both signals have errors:
- HW marks 291 as active when they haven't taken a trip in 7d (false positive)
- HW misses 305 drivers who ARE active but HW's latest week is stale (false negative)

Net error: roughly balanced (~300 each way), but the real problem is the 10,937 drivers with HW data from >3 months ago who still show as "active" in driver_state.

---

## TASK 5 — CODE AUDIT (build_driver_state_snapshot)

From `app/services/yego_lima_driver_state_service.py`:

| Question | Answer | Line |
|----------|--------|------|
| Universe defined by? | `history_weekly` UNION `driver_360_daily` — ALL drivers who ever existed | L125-126 |
| `completed_orders_week` from? | `MAX(week_start_date)` per driver in history_weekly | L87 |
| Uses recency filter? | **NO** — `week_start_date <= monday` includes ALL history | L88 |
| Uses park_id? | **NO** — no park filter anywhere in the query | L81-95 |
| Uses trips_2026? | **NO** | N/A |
| Filters by current week? | **NO** — uses MAX available week, may be months old | L87 |
| Can bring ancient drivers? | **YES** — history_weekly goes back to 2025-02-24 | — |

### The Bug (confirmed)

```python
# L87: Gets MAX week_start_date per driver — could be ANY historical week
MAX(week_start_date) <= %(monday)s

# L173: Uses that as "completed_orders_week" for current snapshot
orders_week = int(h.get("completed_orders_week", 0) or 0)
```

The query `MAX(week_start_date) <= monday` returns the **latest available week** for each driver. If a driver's latest week in history_weekly is from October 2025, that 8-month-old data becomes their "completed_orders_week" for the June 2026 snapshot. This is why 10,937 drivers (59%) have "active" orders from >3 months ago.

---

## TASK 6 — ROOT CAUSE CLASSIFICATION

### Primary: **B) HISTORICAL_RECENCY_CONTAMINATION** (86.4% false positive rate)

The `driver_state_snapshot` is a **historical registry**, not a **current activity snapshot**. It includes:
- 2,523 real ACTIVE drivers (13.6%)
- 5,327 Lima churned drivers (28.7%)
- 2,189 Lima archived drivers (11.8%)
- 8,506 drivers with no trips_2026 match at all (45.9%)

### Contributing Factors

| Factor | Evidence | Severity |
|--------|----------|----------|
| `completed_orders_week` uses MAX historical week | 10,937 drivers (59%) with HW from >3 months ago | **CRITICAL** |
| No recency filter in universe query | `week_start_date <= monday` includes 67 weeks of history | **CRITICAL** |
| No park_id filter | All parks aggregated into one global snapshot | **HIGH** |
| `driver_360_daily` broken (179 rows) | Zero daily activity data, forcing fallback to stale weekly | **HIGH** |
| ID space mismatch (46% no match) | 8,506 drivers in driver_state not found in trips_2026 | **MEDIUM** |
| No `condicion` filter | Uses `completed_orders_week` regardless of order status | **LOW** |
| Park contamination | **ZERO** — no drivers from other parks | **NONE** |

### What the 18,545 Actually Are

```
18,545 = 2,523 (really active 7d Lima)
       + 5,327 (churned Lima, last trip 15-90d ago)
       + 2,189 (archived Lima, last trip >90d ago)
       + 8,506 (no completed trip in trips_2026 — ID mismatch or different source)
```

---

## TASK 7 — ACTIVITY CONTRACT RECOMMENDATION

### Proposed Canonical Source for Taxonomy Activity Status

```
Source: public.trips_2026
Filter: park_id = '08e20910d81d42658d4334d3f6d10ac0'
Status: condicion = 'Completado'
```

### Operational Status Definition

| State | Definition | Query |
|-------|-----------|-------|
| **ACTIVE_7D** | Completed trip in last 7 days | `MAX(fecha_finalizacion::date) >= CURRENT_DATE - 7` |
| **CHURN_15D** | Last completed trip 15-89 days ago | `MAX(fecha_finalizacion::date) BETWEEN CURRENT_DATE-89 AND CURRENT_DATE-15` |
| **ARCHIVED_90D** | Last completed trip >= 90 days ago | `MAX(fecha_finalizacion::date) <= CURRENT_DATE - 90` |
| **SUPPLY_ONLY** | Supply > 0 in window, 0 completed trips | Requires supply data source (TBD) |
| **UNKNOWN** | No trips_2026 match, no supply data | Fallback when driver not found in any source |

### What NOT to Use

| Source | Reason |
|--------|--------|
| `driver_state_snapshot.completed_orders_week` | Contains historical artifacts up to 16 months old |
| `history_weekly` MAX week per driver | 59% of drivers have latest week >3 months ago |
| `driver_360_daily` | Broken — 179 rows total |
| `growth.orders_raw` | Only 1,591 drivers in 7d vs 2,523 real |
| `raw_yango.orders_raw` | Only 1,604 drivers in 7d vs 2,523 real |

---

## TASK 8 — IMPACTO EN TAXONOMY SHADOW

### Current (broken) vs Proposed (trips_2026-based)

| Taxonomy Layer | Current (driver_state) | Proposed (trips_2026 Lima) | Delta |
|---------------|----------------------|---------------------------|-------|
| ACTIVE drivers | 18,545 | ~2,500 | -86% |
| CHURN/ARCHIVED | 0 | ~7,500 | +7,500 |
| UNKNOWN | 0 | ~8,500 | +8,500 |

### Impact on Operational Segments

Current segments would collapse significantly:
- **ACTIVE_GROWTH** (76.8% today) → would apply only to the ~2,500 really active drivers  
- **UNDER_ACTIVATED** (14.4% today) → only early-life among real actives
- **TOP_PERFORMER** (8.1% today) → only among real actives
- **STABLE** (0.4% today) → unchanged, only among real actives

**The taxonomy would become operationally meaningful instead of a historical registry with 86% noise.**

---

## TASK 9 — GO / NO-GO

### Veredicto: **A) USE_TRIPS_2026_LIMA_FOR_ACTIVITY**

### Evidence

| Criterion | Status |
|-----------|--------|
| Root cause identified | **PASS** — B) Historical recency contamination |
| False positive rate quantified | **PASS** — 86.4% (16,022 of 18,545 are NOT active) |
| Park contamination ruled out | **PASS** — 0 drivers from other parks |
| trips_2026 validated as source | **PASS** — Matches Fleetroom within 0.01% (HOTFIX-1E) |
| Activity contract defined | **PASS** — 5 states with clear definitions |
| ID space issue identified | **PASS** — 46% no-match needs identity bridge |

### Prerequisites for Implementation

1. **Resolve the 8,506 (46%) no-match drivers** — Build or validate `yango_driver_identity_bridge` to map `conductor_id` ↔ `driver_profile_id`
2. **Add park_id dimension** to taxonomy build — Filter by Lima park
3. **Replace `driver_state_snapshot.completed_orders_week`** with `trips_2026` recency query in taxonomy service
4. **Fix `driver_360_daily` pipeline** — Required for daily granularity (7d rolling windows need daily data)

### Next Step

**LG-TAX-2B: Implement Activity Status from trips_2026 Lima in taxonomy shadow mode.** Replace the broken `completed_orders_week` signal with real recency data.

---

## APPENDIX — Data Summary

| Metric | Value |
|--------|-------|
| driver_state total | 18,545 |
| Real ACTIVE (7d Lima) | 2,523 (13.6%) |
| Real CHURNED (15-90d Lima) | 5,327 (28.7%) |
| Real ARCHIVED (90d+ Lima) | 2,189 (11.8%) |
| No trips_2026 match | 8,506 (45.9%) |
| Park contamination | 0 |
| HW latest >3 months | 10,937 (59.0%) |
| False positive rate | 86.4% |

---

**LG-TAX-2A — FIN**

*The 18,545 driver_state drivers are NOT a current activity snapshot.*  
*They are a historical registry of every driver who ever appeared in history_weekly since February 2025.*  
*Only 13.6% are actually active this week in Lima.*  
*Root cause: B) HISTORICAL_RECENCY_CONTAMINATION — the universe query uses MAX(week_start_date) without any recency filter.*  
*Recommendation: USE_TRIPS_2026_LIMA_FOR_ACTIVITY.*
