# OPERATIONAL SESSION LOG

**Date**: 2025-05-25
**Purpose**: Template and instructions for real operational validation sessions

---

## INSTRUCTIONS

1. Use the system as if you were a real operator/manager.
2. Do NOT simulate — work with real data, real scenarios.
3. Record observations immediately after each session.
4. Do NOT try to "prove the system works." Look for friction honestly.
5. If something is useless — say so. If something is confusing — say so.

---

## SESSION TEMPLATE

```
---
session_id: VAL-001
date: YYYY-MM-DD
operator_role: [operations / city manager / country manager / supply / analyst]
duration_minutes: XX
system_mode: [evolution / projection]
grain_used: [daily / weekly / monthly]
---

### Objective
What was the operator trying to do?
[Example: Check if CALI trips dropped this Friday vs last Friday]

### First impression
What caught their eye first?
[Example: The red cell in CALI trips column]

### What worked
- [Example: DoD label "VIE ▼ -12%" immediately showed the problem]
- [Example: Clicking the cell opened useful drill]

### What didn't work
- [Example: Attainment % (87%) distracted from momentum -12%]
- [Example: Too many columns — needed weekday focus but didn't know]

### Confusion points
- [Example: Didn't understand "parcial" label on current week]
- [Example: "Gap -1.5K" vs "DoD ▼ -12%" — which one matters?]

### Missing signals
- [Example: Wish I could see driver count per city]
- [Example: No way to compare two cities side by side]

### Action taken
- [Example: Called city manager about CALI drop]
- [Example: No action — just monitoring]

### Would they use this again?
- [Yes / No / Maybe if___]

### Cognitive load (1-5)
[1 = instantly understood, 5 = overwhelming]
Score: __

### Notes
```

---

## ACCUMULATED SESSIONS

### Session VAL-001
_(to be filled by operator)_

### Session VAL-002
_(to be filled by operator)_

### Session VAL-003
_(to be filled by operator)_

---

## TREND TRACKING

| Metric | Session 1 | Session 2 | Session 3 | Trend |
|---|---|---|---|---|
| Cognitive load (1-5, lower=better) | _ | _ | _ | _ |
| Time to find top issue (seconds) | _ | _ | _ | _ |
| Actions taken per session | _ | _ | _ | _ |
| Confusion points | _ | _ | _ | _ |
| "Would use again" | _ | _ | _ | _ |
