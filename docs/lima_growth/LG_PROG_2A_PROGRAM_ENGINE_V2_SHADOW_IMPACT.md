# LG-PROG-2A — PROGRAM ENGINE V2 SHADOW + IMPACT CONTRACT

**Ticket:** LG-PROG-2A  
**Date:** 2026-06-11  
**Phase:** Lima Growth Foundation — Program Layer  
**Status:** IMPLEMENTED (SHADOW MODE) — 0 production impact  

---

## TASK 0 — GOVERNANCE

Control Foundation / Lima Growth. Shadow mode. Zero production impact. Compatible with active OMNI-P0 phase.

---

## TASK 1 — PROGRAM REGISTRY V2

9 programs seeded in `growth.yego_lima_program_v2_registry`:

| Priority | Program | Family | Target Segment | Purpose |
|----------|---------|--------|---------------|---------|
| 1 | HVR | RECOVERY | HVR_CANDIDATE | High-value drivers in decline |
| 2 | FIFTY_14 | ONBOARDING_GROWTH | NEW_ACTIVE | 50 trips in 14 days |
| 3 | NINETY_300 | ONBOARDING_GROWTH | NEW_ACTIVE | 300 trips in 90 days |
| 4 | ACTIVE_GROWTH | PRODUCTIVITY_GROWTH | ACTIVE_GROWTH | Growth for underperformers |
| 5 | TOP_RETENTION | RETENTION | TOP_PERFORMER | Retain top drivers |
| 6 | STABLE_MONITOR | MONITORING | STABLE | Passive monitoring |
| 7 | CHURN_RECOVERY | RECOVERY | CHURNED | Win back churning drivers |
| 8 | RNA_ONBOARDING | ACTIVATION | REGISTERED_NOT_ACTIVATED | Activate registered drivers |
| 9 | ARCHIVED_REACTIVATION | REACTIVATION | ARCHIVED | Reactivate archived drivers |

---

## TASK 2 — RULE CONFIG

18 rules seeded. Each program evaluates eligibility based on taxonomy segment + value/momentum conditions.

---

## TASK 3 — ELIGIBILITY V2

**68,004 eligibility rows** generated. Each driver can be eligible to multiple programs based on their taxonomy segment.

---

## TASK 4 — EXCLUSIVE ASSIGNMENT V2

**68,473 assignment rows** — one per driver. Lowest priority_order wins when multiple programs are eligible.

| Rule | Detail |
|------|--------|
| Max per driver | **1** |
| Resolution method | Lowest `priority_order` |
| Unassigned handling | `assigned_program_code = NULL` |

---

## TASK 5 — PRIORITY V2

**67,880 priority rows** with deterministic scoring per program. Top scores go to HVR drivers with largest volume drops.

---

## TASK 6 — TRANSITIONS

**68,473 transition rows** — first build = all PROGRAM_ENTRY or NO_CHANGE.

---

## TASK 7 — IMPACT CONTRACT

**68,473 impact rows** — all `PENDING` since 2026-06-10 is the current snapshot (no future data to measure impact against).

---

## TASK 8 — BUILD RESULT (2026-06-10)

### Program Distribution

| Program | Drivers | % |
|---------|---------|---|
| RNA_ONBOARDING | 50,181 | 73.3% |
| ARCHIVED_REACTIVATION | 10,743 | 15.7% |
| CHURN_RECOVERY | 3,486 | 5.1% |
| ACTIVE_GROWTH | 2,594 | 3.8% |
| **UNASSIGNED** | **593** | **0.9%** |
| TOP_RETENTION | 495 | 0.7% |
| HVR | 166 | 0.2% |
| FIFTY_14 | 124 | 0.2% |
| STABLE_MONITOR | 91 | 0.1% |

### UNASSIGNED Analysis

593 drivers (0.9%) have no assigned program. All are `REACTIVATED_ACTIVE` — drivers in the REACTIVATED lifecycle who are currently active (7d or 30d). No program in the registry targets this segment directly. These drivers need a dedicated program or should be merged into ACTIVE_GROWTH.

### Build Metrics

| Metric | Value |
|--------|-------|
| Registry programs | 9 |
| Rules seeded | 18 |
| Eligibility rows | 68,004 |
| Assignment rows | 68,473 |
| Priority rows | 67,880 |
| Transition rows | 68,473 |
| Impact rows | 68,473 (all PENDING) |
| Duration | 12 seconds |
| Exclusive assignment | 1 per driver confirmed |
| Multi-eligible drivers | (query WIP - json_array_length compat) |

---

## TASK 9 — EXPLAINABILITY

Each layer has explainability:

| Question | Source |
|----------|--------|
| WHY THIS PROGRAM? | `eligibility_daily.matched_rules_json` + `assignment_daily.assignment_reason` |
| WHY NOT OTHER PROGRAMS? | `assignment_daily.eligible_programs_json` + `excluded_programs_json` |
| WHERE DID DRIVER MOVE? | `assignment_transition` (prev/curr program + segment) |
| WHAT IMPACT? | `impact_daily` (baseline vs future, PENDING if no future data) |

---

## TASK 10 — ENDPOINTS

Router created: `app/routers/yego_lima_program_v2.py`

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/program-v2/summary?date=` | Program distribution |
| GET | `/program-v2/assignments?date=&program_code=&limit=` | Assignment list |
| GET | `/program-v2/driver/{id}?date=` | Single driver view |
| GET | `/program-v2/priority?date=&program_code=&limit=` | Priority queue |
| GET | `/program-v2/transitions?date=&limit=` | Daily transitions |
| GET | `/program-v2/impact?date=&program_code=&limit=` | Impact measurements |

---

## TASK 11 — COMPATIBILITY

| Component | Status |
|-----------|--------|
| Legacy program_eligibility | UNTOUCHED |
| Legacy prioritized_opportunity | UNTOUCHED |
| Legacy assignment_queue | UNTOUCHED |
| Control Loop | UNTOUCHED |
| Scheduler | UNTOUCHED |
| Taxonomy V2 | READ-ONLY |
| Activity Foundation | READ-ONLY |

---

## TASK 12 — BACKLOG UPDATED

New items added to `docs/backlog/BACKLOG_LIMA_GROWTH_ACTIVITY_TAXONOMY_PROGRAMS.md`:

- Program observability dashboard
- Lifecycle/Activity/Segment/Program visualization
- REACTIVATED_ACTIVE program (close the 593 UNASSIGNED gap)
- Queue V2 cutover
- Control Loop V2 cutover
- Impact measurement after 7-day window

---

## TASK 13 — GO / NO-GO

### Veredicto: **A) PROGRAM_ENGINE_V2_SHADOW_READY**

### Pass Criteria

| Criterion | Status |
|-----------|--------|
| Registry V2 seeded (9 programs) | PASS |
| Rules V2 seeded (18 rules) | PASS |
| Eligibility V2 built (68,004 rows) | PASS |
| Assignment V2 exclusive (1/driver) | PASS |
| Priority V2 built (67,880 rows) | PASS |
| Transitions table built (68,473 rows) | PASS |
| Impact table built with PENDING (68,473 rows) | PASS |
| Endpoints created (6 read-only) | PASS |
| Backlog updated | PASS |
| 0 production impact | PASS |

### Known Gap

| Gap | Detail |
|-----|--------|
| 593 UNASSIGNED | REACTIVATED_ACTIVE drivers have no matching program. Needs new program or ACTIVE_GROWTH expansion. |

---

## APPENDIX — Files

| File | Purpose |
|------|---------|
| `alembic/versions/203_yego_lima_program_v2.py` | Migration: 7 tables |
| `app/routers/yego_lima_program_v2.py` | 6 endpoints |
| `scripts/prog_2a_build.py` | Build script |

---

**LG-PROG-2A — CERTIFIED**

*Program Engine V2 shadow complete. 9 programs, 68K assignments, exclusive by priority.*  
*166 HVR candidates detected — highest priority interventions.*  
*All impact measurements set to PENDING (no future data window yet).*  
*593 REACTIVATED_ACTIVE drivers unassigned — gap documented for next iteration.*  
*Ready for observability dashboard and Queue V2 cutover.*
