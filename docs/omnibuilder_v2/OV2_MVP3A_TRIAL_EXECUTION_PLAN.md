# OV2-MVP.3A — TRIAL EXECUTION PLAN

> **Fase:** OV2-MVP.3A — Operational Trial Execution
> **Sub-document:** Execution Plan
> **Fecha:** 2026-06-12

---

## 1. TRIAL DATES

| Field | Value |
|-------|-------|
| Start | 2026-06-16 (Monday) |
| End | 2026-06-27 (Friday) |
| Duration | 2 weeks (10 operational days) |
| Mid-review | 2026-06-20 (Friday, end of Week 1) |
| Final review | 2026-06-27 (Friday, end of Week 2) |

---

## 2. PARTICIPANTS

| Role | Responsibilities | V2 Tasks |
|------|-----------------|----------|
| **Operator** | Daily fleet monitoring | 7 daily tasks |
| **Manager** | Weekly performance review | 4 weekly tasks |
| **Analyst** | Deep dives + monthly closure | 3 monthly + 5 deep dive tasks |
| **Supply** | Driver operations | Review drivers, TPD, parks |
| **Revenue** | Financial tracking | Review revenue, GMV, ticket |

---

## 3. CRITICAL TASKS (21 tasks from inventory)

| Priority | Tasks | V2 Ready |
|----------|-------|----------|
| P0 (9 tasks) | Daily fleet + weekly + monthly reviews | 9/9 |
| P1 (10 tasks) | Deep dives, filters, drill | 10/10 |
| P2 (2 tasks) | Reports, export | 0/2 |

---

## 4. FRICTION REPORTING CHANNEL

- **Primary:** Direct entry in `OV2_MVP3A_FRICTION_LOG.md`
- **Fallback:** Verbal report to trial coordinator → logged within 24h
- **Triage cadence:** Daily (end of day review)

---

## 5. TRIAGE RESPONSIBILITY

| Role | Name | Responsibility |
|------|------|----------------|
| Trial Coordinator | AI Operator (this session) | Daily checkpoint, friction triage, P0/P1 fixes |
| Operations Lead | TBD | Participant coordination, feedback collection |

---

## 6. DAILY RHYTHM

```
09:00 — Trial day starts
09:30 — Operators begin using V2
12:00 — Midday check (any blockers?)
17:00 — End-of-day checkpoint
17:30 — Friction log review + triage
18:00 — P0 fixes deployed (if any)
```

---

## 7. WEEK 1 GOALS

- All participants complete 5 days with V2 as primary
- V2/V1 ratio ≥ 2:1 by Friday
- ≤ 3 P0 frictions
- ≤ 5 P1 frictions
- Quick fixes applied for P0/P1

---

## 8. WEEK 2 GOALS

- V2/V1 ratio ≥ 4:1
- 0 P0 frictions
- ≤ 2 P1 frictions (trending down from week 1)
- Operator confidence survey completed
- Final acceptance score computed

---

## 9. VERIFICATION

At trial end:
- Run `ov2_mvp3a_compute_acceptance_score.py` with trial data
- Check `/ops/omniview-v2/usage-metrics` for session counts
- Review `OV2_MVP3A_FRICTION_LOG.md` for resolved vs open
- Collect operator surveys (min 3 responses)
- Produce `OV2_MVP3A_OPERATIONAL_TRIAL_EXECUTION_REPORT.md`
