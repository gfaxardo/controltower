# LG-OPS-DAILY-1A — OPTIMIZATION READINESS THRESHOLDS

**Phase:** Data Accumulation Period

---

## LG-OPT-1A UNLOCK CRITERIA

LG-OPT-1A (Program Optimization) remains **BLOCKED** until ALL thresholds are met:

### Hard Gates

| # | Gate | Threshold | Current | Status |
|---|------|-----------|---------|:---:|
| 1 | Movement snapshots | >= 14 days | 1 day | BLOCKED |
| 2 | Effectiveness scores | >= 14 days | 1 day | BLOCKED |
| 3 | RNA measurement | >= 14 days with contact data | 0 | BLOCKED |
| 4 | LoopControl outcomes | >= 50 contacts with results | 0 | BLOCKED |
| 5 | Scorecard stability | net_effect variance < 50% week-over-week | N/A | BLOCKED |
| 6 | Freshness P1 | 0 open P1 freshness issues | 1 (activity) | DOCUMENTED |

### Soft Gates

| # | Gate | Threshold |
|---|------|-----------|
| 7 | Export frequency | >= 5 exports/week |
| 8 | Dashboard uptime | >= 95% |
| 9 | Scheduler reliability | >= 95% successful ticks |

---

## ESTIMATED TIMELINE

With V2 pipeline running daily:

- **Week 1 (Jun 12-18):** 4-5 movement snapshots, 4-5 effectiveness days
- **Week 2 (Jun 19-25):** 9-10 days accumulated, coverage ~50-70%
- **Week 3 (Jun 26-Jul 2):** 14+ days, coverage ~80-95%
- **Week 4:** OPT thresholds met → LG-OPT-1A can activate

---

## UNLOCK PROCEDURE

When all hard gates are met:
1. Generate LG_OPS_DAILY_1A_CLOSURE_REPORT.md
2. Update `ai_current_phase.md`: ACTIVE → LG-OPT-1A
3. Open LG-OPT-1A with evidence-backed recommendations

---

## FORBIDDEN ACTIONS DURING ACCUMULATION

- [ ] Do NOT open LG-OPT-1A before thresholds
- [ ] Do NOT change RNA scoring weights
- [ ] Do NOT add new programs
- [ ] Do NOT modify Program Engine rules
- [ ] Do NOT automate contact execution
- [ ] Do NOT open Queue V2 or Control Loop V2
