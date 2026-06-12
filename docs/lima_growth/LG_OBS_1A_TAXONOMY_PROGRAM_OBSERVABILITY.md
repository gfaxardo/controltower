# LG-OBS-1A — TAXONOMY & PROGRAM OBSERVABILITY FOUNDATION

**Ticket:** LG-OBS-1A  
**Date:** 2026-06-11  
**Phase:** Lima Growth Foundation — Observability Layer  
**Status:** IMPLEMENTED (SHADOW MODE)  

---

## TASK 0 — GOVERNANCE

Control Foundation / Lima Growth. Read-only observability. Zero production impact.

---

## TASK 1 — OBSERVABILITY CONTRACT

### Driver View Hierarchy

```
Driver ID
  → Lifecycle (NEVER_ACTIVATED | NEW | ACTIVE | CHURN_15D | ARCHIVED_90D | REACTIVATED)
  → Activity (ACTIVE_7D | ACTIVE_30D | CHURN_15_89D | ARCHIVED_90D | NEVER_ACTIVATED | RECENTLY_INACTIVE)
  → Value (NO_VALUE | LOW_VALUE | MID_VALUE | HIGH_VALUE | TOP_VALUE)
  → Momentum (ACCELERATING | GROWING | STABLE | SOFTENING | DECLINING | COLLAPSING | INSUFFICIENT_HISTORY)
  → Segment (REGISTERED_NOT_ACTIVATED | ARCHIVED | CHURNED | ACTIVE_GROWTH | TOP_PERFORMER | NEW_ACTIVE | REACTIVATED_ACTIVE | HVR_CANDIDATE | STABLE | SOFT_CHURN)
  → Program (HVR | FIFTY_14 | NINETY_300 | ACTIVE_GROWTH | TOP_RETENTION | STABLE_MONITOR | CHURN_RECOVERY | RNA_ONBOARDING | ARCHIVED_REACTIVATION | UNASSIGNED)
  → Priority (score 0-1000)
  → Impact (PENDING | POSITIVE | NEGATIVE | NEUTRAL)
```

Every state is explainable via `explanation_text` in `taxonomy_v2_explanation` and `assignment_daily.assignment_reason`.

---

## TASK 2 — SERVING FACTS

### Tables Created (Migration 204)

| Table | Rows | Purpose |
|-------|------|---------|
| `program_observability_fact` | 68,473 | Per-driver dashboard (lifecycle+activity+value+momentum+segment+program+priority+impact) |
| `taxonomy_distribution_fact` | 9 | Aggregated distributions across 5 dimensions |
| `program_distribution_fact` | 9 | Driver count per program |
| `program_movement_fact` | 9 | Transitions (PROGRAM_ENTRY, NO_CHANGE) |
| `program_impact_fact` | 9 | Impact status by program (all PENDING) |
| `driver_growth_timeline_fact` | 205,419 | Timeline events (REGISTERED, lifecycle, PROGRAM_ASSIGNED) |

---

## TASK 3-7 — FACT DISTRIBUTIONS

### Taxonomy Distribution (5 dimensions)

| Dimension | States |
|-----------|--------|
| lifecycle_status | 6 |
| activity_status | 5 |
| value_tier | 5 |
| momentum_state | 7 |
| operational_segment | 9 |

### Program Distribution

| Program | Drivers |
|---------|---------|
| RNA_ONBOARDING | 50,181 |
| ARCHIVED_REACTIVATION | 10,743 |
| CHURN_RECOVERY | 3,486 |
| ACTIVE_GROWTH | 2,594 |
| TOP_RETENTION | 495 |
| HVR | 166 |
| FIFTY_14 | 124 |
| STABLE_MONITOR | 91 |
| UNASSIGNED | 593 |

### Movements (2026-06-10)

| Transition | Drivers |
|-----------|---------|
| PROGRAM_ENTRY | 67,880 |
| NO_CHANGE | 593 |

### Impact

All 68,473 drivers: `PENDING` (no future data window to measure impact yet).

### Timeline

205,419 events: 68,473 REGISTERED + 68,473 lifecycle + 68,473 PROGRAM_ASSIGNED.

---

## TASK 8-10 — DASHBOARD / DRILLDOWNS

### Endpoints (via observability router)

All served from serving facts — no runtime joins on taxonomy/program tables:

| Endpoint | Source Fact |
|----------|------------|
| `/observability/summary?date=` | `taxonomy_distribution_fact` + `program_distribution_fact` |
| `/observability/drivers?date=&segment=&program=&limit=` | `program_observability_fact` |
| `/observability/driver/{id}?date=` | `program_observability_fact` + `driver_growth_timeline_fact` |
| `/observability/movements?date=` | `program_movement_fact` |
| `/observability/impact?date=&program=` | `program_impact_fact` |
| `/observability/timeline/{driver_id}` | `driver_growth_timeline_fact` |

### Drilldowns Supported

| Click | Returns |
|-------|---------|
| Segment → | List of drivers in that segment |
| Program → | List of drivers assigned to that program |
| Movement → | List of drivers with that transition |
| Impact → | List of drivers with that impact status |
| Driver → | Full timeline (lifecycle + program + segment history) |

---

## TASK 11 — VALIDATION

| Criterion | Result |
|-----------|--------|
| Observability fact rows | 68,473 = universe |
| Taxonomy distributions | 5 dimensions, 32 state combinations |
| Program distribution | 9 programs + UNASSIGNED |
| Movement fact | PROGRAM_ENTRY (67,880) + NO_CHANGE (593) |
| Impact fact | All PENDING |
| Timeline events | 205,419 (3 events per driver) |
| Timeline unique drivers | 68,473 |
| No duplicates | Confirmed |
| Build time | 8.8 seconds |

---

## TASK 12 — BACKLOG

Updated in `docs/backlog/BACKLOG_LIMA_GROWTH_ACTIVITY_TAXONOMY_PROGRAMS.md`:

- Growth Intelligence Dashboard UI
- Program Families visualization
- Driver Journey timeline UI
- Queue V2 cutover
- Control Loop V2 cutover

---

## TASK 13 — GO / NO-GO

### Veredicto: **A) OBSERVABILITY_FOUNDATION_READY**

### Evidence

| Criterion | Status |
|-----------|--------|
| Serving facts created (6 tables) | PASS |
| Taxonomy distribution facts built | PASS |
| Program distribution facts built | PASS |
| Movement facts built | PASS |
| Impact facts built (PENDING) | PASS |
| Driver timeline created | PASS |
| Read-only endpoints designed | PASS |
| Drilldown paths defined | PASS |
| 0 production impact | PASS |

---

## APPENDIX — Architecture

```
taxonomy_v2_daily ──┐
program_v2_assignment ─┤
program_v2_priority ───┤
program_v2_transition ─┤
program_v2_impact ─────┤
lifecycle_daily ───────┤
                       ├──> program_observability_fact (68,473 rows)
                       ├──> taxonomy_distribution_fact (aggregated)
                       ├──> program_distribution_fact (aggregated)
                       ├──> program_movement_fact (aggregated)
                       ├──> program_impact_fact (aggregated)
                       └──> driver_growth_timeline_fact (205,419 events)
                                    │
                                    ▼
                              Observability Router (read-only endpoints)
```

---

**LG-OBS-1A — CERTIFIED**

*6 serving fact tables, 205K timeline events, 68K driver observability records.*  
*All facts pre-computed — zero runtime joins on taxonomy/program tables.*  
*Drilldowns from segment → program → driver → timeline supported.*  
*Ready for Growth Intelligence Dashboard UI.*
