# OV2-MVP.3 — OPERATIONAL TRIAL FRAMEWORK

> **Fase:** OV2-MVP.3 — Operational Acceptance Trial
> **Sub-document:** Trial Framework
> **Fecha:** 2026-06-12

---

## 1. TRIAL DURATION

| Type | Duration | Rationale |
|------|----------|-----------|
| **Minimum** | 1 week | At least 5 operational days to catch daily patterns |
| **Recommended** | 2 weeks | Covers 2 full business cycles (week 1 + week 2 patterns) |
| **Ideal** | 4 weeks | Full month cycle: plan, execution, closure |

**Decision: Start with 2-week trial. Extend to 4 if acceptance score < 85% at week 2.**

---

## 2. PARTICIPANTS

| Role | Persona | V2 Tasks |
|------|---------|----------|
| **Operator** | Daily fleet monitoring | Review trips, drivers, revenue, freshness |
| **Manager** | Weekly performance review | Compare week-over-week, check business slices |
| **Analyst** | Deep dives | Drill cells, inspect parks, verify coverage |
| **Supply** | Driver operations | Review active drivers, TPD, park comparison |
| **Revenue** | Financial tracking | Review revenue, GMV, avg ticket |

---

## 3. TASKS OBSERVED

| # | Task | Priority | Success Criteria |
|---|------|----------|-----------------|
| 1 | Open V2 from navigation | P0 | Navigable in < 3 clicks |
| 2 | Set date range (yesterday) | P0 | Correct data loads |
| 3 | Filter by city | P1 | Data filtered correctly |
| 4 | Filter by park | P1 | Park-level data visible |
| 5 | Filter by business slice | P1 | Slice data isolated |
| 6 | Switch grain (day→week→month) | P1 | Correct aggregation |
| 7 | View trips trend | P0 | Values consistent with V1 |
| 8 | View revenue trend | P0 | Values consistent with V1 |
| 9 | Check data freshness | P0 | Status bar shows age |
| 10 | Identify signal colors | P0 | Green/red/amber meaning clear |
| 11 | Check source (CT/Yango) | P1 | Source badge visible |
| 12 | Inspect a cell | P1 | Drill data shows parks/drivers |
| 13 | Fullscreen mode | P2 | Full view without sidebar |
| 14 | Cross-reference V1 for verification | P0 | V2 values match V1 |
| 15 | Complete 1 full day without V1 | P0 | 0 V1 visits during trial day |

---

## 4. METRICS

| Metric | Target | Measurement |
|--------|--------|-------------|
| V2 sessions/day | ≥ 3 | Route visit count |
| V1 sessions/day | ≤ 1 (verification only) | Route visit count |
| V2/V1 ratio | ≥ 3:1 | Sessions V2 / Sessions V1 |
| Acceptance score | ≥ 85% | Formula (see Acceptance Score doc) |
| Friction reports | ≤ 5 P0/P1 in 2 weeks | Friction log count |
| Time to task completion | ≤ 2 min per task | Observed per session |

---

## 5. ACCEPTANCE CRITERIA

| Criterion | Threshold | Weight |
|-----------|-----------|--------|
| All P0 tasks completed successfully | 100% | 30% |
| V2/V1 ratio ≥ 3:1 | Yes | 25% |
| Acceptance score ≥ 85% | Yes | 25% |
| ≤ 5 P0/P1 friction reports | Yes | 10% |
| Operator confidence (survey) | ≥ 4/5 | 10% |

**GO: All 5 criteria must pass. Partial: 4/5. Blocked: ≤3/5.**
