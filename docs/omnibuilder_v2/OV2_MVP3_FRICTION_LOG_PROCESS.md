# OV2-MVP.3 — FRICTION LOG PROCESS

> **Fase:** OV2-MVP.3 — Operational Acceptance Trial
> **Sub-document:** Friction Log Process
> **Fecha:** 2026-06-12

---

## PURPOSE

Simple mechanism to capture issues encountered during the trial. NOT a bug tracker. NOT a feature request system. This is operational friction: "something made my job harder."

---

## CLASSIFICATION

| Level | Definition | Examples | Response |
|-------|-----------|----------|----------|
| **P0** | Blocked task completely | Matrix didn't load, auth failed, wrong data | Fix within 24h |
| **P1** | Made task significantly harder | Badge missing, filter unclear, value format confusing | Fix within trial week |
| **P2** | Minor annoyance | Layout shift, small label misalignment | Fix in next phase |
| **P3** | Suggestion / nice-to-have | "It would be nice to have X" | Backlog |

---

## LOG FORMAT

```markdown
## Friction #{id}

- **Date:** YYYY-MM-DD
- **Role:** operator / manager / analyst
- **Task:** [from critical task inventory]
- **Severity:** P0 / P1 / P2 / P3
- **Description:** [1-2 sentences]
- **Expected:** [what should have happened]
- **Actual:** [what happened]
- **V1 behavior:** [does V1 do it differently?]
- **Resolution:** [if fixed]
```

---

## PROCESS

1. **Capture** — Operator reports friction (verbal, chat, or direct log entry)
2. **Triage** — Assign P0/P1/P2/P3 within same day
3. **Fix** — P0 within 24h, P1 within trial week, P2/P3 backlogged
4. **Verify** — Operator confirms fix works
5. **Close** — Entry marked resolved

---

## WEEKLY REVIEW

At end of each trial week:
- Count by severity
- Top 3 friction sources
- Resolution rate (% fixed vs open)
- Trend: increasing or decreasing?

---

## TARGETS

| Metric | Target |
|--------|--------|
| Total P0 in trial | 0 |
| Total P1 in trial | ≤ 5 |
| P0 resolution time | ≤ 24h |
| P1 resolution time | ≤ 1 week |
