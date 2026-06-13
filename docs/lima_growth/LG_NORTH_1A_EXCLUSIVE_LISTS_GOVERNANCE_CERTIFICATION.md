# LG-NORTH-1A — Exclusive Lists Governance Certification

**Date:** 2026-06-13
**Phase:** Lima Growth North Star Governance Update
**Mode:** DOCUMENTATION / GOVERNANCE ONLY — NO IMPLEMENTATION
**Status:** CERTIFIED

---

## 1. Objective

Establish the definitive North Star for Lima Growth Machine: the final product is daily refreshed mutually exclusive operational driver lists, not the dashboard. This governs all future actions.

## 2. Operator Requirement

The operator requires a system of daily exclusive operational lists that:
- Assign each driver to at most one operational universe per day
- Are refreshed daily with recent behavior
- Export to Control Loop or CRM
- Track actions taken
- Measure impact daily and weekly

## 3. Documents Created / Updated

| File | Action | Lines |
|------|--------|-------|
| `docs/lima_growth/LG_NORTH_STAR_EXCLUSIVE_LISTS_CONTRACT.md` | Created | ~220 |
| `docs/architecture/ACTIVE_SCOPE_CONTRACT.md` | Updated (+Section 16) | +20 |
| `docs/architecture/GROWTH_MACHINE_CANONICAL.md` | Updated (+North Star section) | +25 |
| `docs/architecture/TRUTH_MAP_V2.md` | Updated (+North Star note) | +1 |
| `docs/lima_growth/LG_NORTH_1A_EXCLUSIVE_LISTS_GOVERNANCE_CERTIFICATION.md` | Created | This file |

## 4. North Star Definition

**The final product of Lima Growth Machine is not the dashboard.** It is a daily refreshed system of mutually exclusive operational driver lists, exportable to Control Loop and measurable by impact.

## 5. Exclusive Operational Universes

| # | Universe | Window | Goal |
|---|----------|--------|------|
| 1 | New/Reactivated Activation | 0-14 days | 50 trips in activation window |
| 2 | Ramp-Up | 15-45 days | Reach 100 trips/week |
| 3 | Consolidation | 46-90 days | Sustain 100 trips/week |
| 4 | Active Growth | 90+ days | Move one productivity band upward |
| 5 | Recovery (High/Low Value) | Recently inactive | Reactivation |
| 6 | Cemetery | Long churned | Separate from active ops |

## 6. MVP Requirements

- Daily exclusive list generation
- One driver = one operational universe
- Every list has objective, entry/exit criteria, priority, measurement target
- Control Loop export
- Action tracking
- Daily/weekly impact measurement

## 7. Control Loop Export Requirement

Minimum export contract defined with 11 fields: driver_id, assigned_universe, program_code, objective, reason, priority, recommended_action, target_metric, baseline_metric, generated_date, owner/channel.

## 8. Action Measurement Requirement

System must measure: who contacted, channel, date/time, outcome, next state, baseline trips, post-contact trips (7d/30d), daily impact, weekly impact.

## 9. What Is Accessory

Dashboards, charts, health redesign, AI suggestions, new campaigns, advanced explanations, Program Registry V3 — all secondary to exclusive list generation.

## 10. Future Prompt Rule — North Star Test

Every Growth Machine task must answer:
1. Does it improve exclusive dynamic lists?
2. Does it improve daily refresh correctness?
3. Does it improve Control Loop export?
4. Does it improve action tracking?
5. Does it improve impact measurement?

**If NO to all → document/backlog. Do NOT implement.**

## 11. Verdict

### **LG_NORTH_1A_CERTIFIED**

The North Star is exclusive dynamic operational lists. The dashboard is navigation, not the destination. All future Growth Machine work is governed by the North Star Test.

---

*Certification complete. No implementation.*
