# FALSE POSITIVE AUDIT FRAMEWORK

**Date**: 2025-05-25
**Purpose**: Structured framework to identify and reduce false positives

---

## 1. KNOWN FALSE POSITIVE PATTERNS

### Momentum
| Pattern | Expected rate | Mitigation |
|---|---|---|
| Holiday weekday showing "decline" vs normal weekday | ~2-3 days/month | Holiday calendar exclusion |
| First/last day of month showing partial comparison | Daily | ~ suffix already shown |
| Week 1 of monthly cycle (ramp-up) classified as "declining" vs week 4 (peak) | Monthly | Rolling 4-week average instead of single comparison |
| Driver returning from vacation classified as "growing +200%" | Per driver | Exclude drivers with days_since_last > 7 from delta calculation |

### Behavioral MVP
| Pattern | Expected rate | Mitigation |
|---|---|---|
| Weekend-only driver flagged as "inactive_risk" on Monday | ~10% of drivers | Minimum trips threshold (< 5 trips = exclude from classification) |
| Driver switching parks flagged as "declining" in old park | During rebalancing | Park-level classification or park-agnostic baseline |
| Seasonal drop (rainy season) classified as "at_risk" | Seasonal | Compare vs same month last year, not previous month |

### Priority Strip
| Pattern | Expected rate | Mitigation |
|---|---|---|
| Single-day blip triggering "consecutive decline" + "critical" | Rare | Minimum 2% threshold for daily (already 10%) |
| Small city (< 100 trips) triggering HIGH severity | Small cities | Minimum trip volume threshold for severity |

---

## 2. FALSE POSITIVE AUDIT RUBRIC

For each alert/classification encountered:

```
---
alert_id: FP-001
date: YYYY-MM-DD
type: [momentum / behavioral / priority_strip]
specific_alert: [e.g. "MEDELLIN critical decline -45%"]
---

### Context
What was happening operationally?
[Holiday weekend, natural volume drop, nothing wrong]

### Why false positive?
[Decline was holiday-related, not operational problem]

### Severity overstatement?
Current severity: critical | Should be: normal

### Should system have known?
[Yes — holiday calendar exists but not integrated]

### Remedy
[Add holiday exclusion to comparison logic]
```

---

## 3. ALERT FATIGUE METRICS

Track per session:

| Metric | Target | Actual (fill) |
|---|---|---|
| Alerts shown per session | < 5 critical | _ |
| Total alerts (all severities) | < 15 | _ |
| Alerts acted upon | > 50% of critical | _ |
| Alerts dismissed as "noise" | < 20% | _ |
| Time spent reading alerts vs scanning matrix | < 30% of session time | _ |

### Alert Fatigue Threshold
- If > 40% of alerts are dismissed as noise → severity thresholds need recalibration
- If < 20% of critical alerts trigger action → "critical" is overused
- If operator stops reading priority strip after 3 sessions → strip is noise

---

## 4. MISLEADING COMPARISON PATTERNS

| Comparison | Potential misleading case |
|---|---|
| DoD same-weekday | Holiday weekday vs normal weekday — shows artificial decline |
| WoW | Week with 5 working days vs week with 4 (holiday) |
| MoM | February (28 days) vs March (31 days) — volume comparison unfair |
| Delta pct | Small denominator (10 trips → 8 trips = -20%, not operationally significant) |

---

## 5. AUDIT LOG (to be filled)

| ID | Date | Type | Current severity | True severity | Action |
|---|---|---|---|---|---|
| FP-001 | _ | _ | _ | _ | _ |
| FP-002 | _ | _ | _ | _ | _ |
| FP-003 | _ | _ | _ | _ | _ |
