# MOMENTUM VALIDATION REPORT

**Date**: 2025-05-25
**Status**: FRAMEWORK — awaiting operational sessions

---

## 1. DoD Same-Weekday Validation

| Question | How to validate | Expected |
|---|---|---|
| Does DoD label (VIE ▼ -12%) help spot issues faster? | Measure time-to-detect in daily mode with/without weekday focus | Under 5 seconds |
| Is the color (green/red) intuitive? | Ask operators what "green triangle up" means | "Improvement" or "growth" |
| Does weekday focus get used? | Track filter toggles per session | Used at least once per daily session |
| Are same-weekday comparisons correct? | Verify DOM→DOM, LUN→LUN with actual DB data | 100% correct (no cross-day comparison) |

### Known concerns
- When a weekday falls on a holiday, same-weekday comparison shows a false decline
- Current period being "in progress" shows partial comparison (~ suffix) — operators may misunderstand

---

## 2. WoW Validation

| Question | How to validate | Expected |
|---|---|---|
| Does WoW detect real operational deterioration? | Compare WoW signal against actual operational events (holidays, promotions, incidents) | Correlation > 70% |
| Is 2+ consecutive WoW decline actionable? | Ask operators: "Would this trigger an investigation?" | "Yes" for cities with high trip concentration |
| Is the WoW label clear on weekly grain? | "Does 'WoW' label make sense on weekly view?" | Should say "Semanal" not "WoW" for Spanish operators |

---

## 3. MoM Validation

| Question | How to validate | Expected |
|---|---|---|
| Does MoM add useful context in Projection mode? | Compare scenarios: Projection cell with MoM vs without | MoM present → operator understands trend context |
| Does MoM conflict with attainment? | Check cells where MoM is UP but attainment is RED (or vice versa) | Operator should understand both signals independently |
| Is the MoM comparison window correct? | Verify previous month is the correct baseline | 100% |

---

## 4. Priority Strip Validation

| Question | How to validate | Source |
|---|---|---|
| Are the top-5 correct? | Compare priority strip ranking against operational knowledge (known problems) | Operational knowledge matches strip ranking |
| Are false positives frequent? | Count cases where strip shows "critical decline" but operator says "this is normal" | < 20% false positives |
| Is the critical/accelerating/consecutive classification useful? | Ask operators to rank usefulness of each level | Critical = most useful, single_decline = least useful |
| Is the "!!" double-exclamation intuitive? | Ask operators what "!!" means before explaining | "Urgent" or "severe" |

---

## 5. Consecutive Declines Validation

| Question | How to validate | Expected |
|---|---|---|
| Are 2+ consecutive declines operationally relevant? | Compare vs operational events | Each 3+ consecutive decline matches a real event |
| Is the threshold (3% decline per period) appropriate? | Check if single-period noise triggers "consecutive" classification | False positives < 20% |

---

## Validation Matrix (to be filled)

| Metric | DoD | WoW | MoM | Strip | Consc. |
|---|---|---|---|---|---|
| Operator usefulness (1-5) | _ | _ | _ | _ | _ |
| False positive rate | _ | _ | _ | _ | _ |
| False negative rate | _ | _ | _ | _ | _ |
| Time-to-understand (seconds) | _ | _ | _ | _ | _ |
| Actions triggered | _ | _ | _ | _ | _ |
