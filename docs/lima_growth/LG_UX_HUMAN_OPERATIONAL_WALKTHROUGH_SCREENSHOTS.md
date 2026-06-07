# LG-UX-R2.9B — Walkthrough Screenshots Index

**Date:** 2026-06-06
**Evidence location:** `exports/audits/lima_growth/walkthrough_screenshots/`

---

## Screenshot Inventory

| File | Scenario | Section |
|------|:---:|---------|
| `00_initial_load.png` | — | Initial page load (Lima Growth V2 dashboard) |
| `e1_today_action_plan.png` | E1 | Today's Action Plan — operational status + KPIs |
| `e2_config_capacity.png` | E2 | Control Config — capacity table + utilization |
| `e3_policy_panel.png` | E3 | Program Capacity Policy — allocation modes + status |
| `e4_queue_build.png` | E4 | Execution Queue — build result + policy info |
| `e5_config_full.png` | E5 | Full Control Config scrolled — Allocation Trace + remediation |
| `e6_action_plan.png` | E6 | Today's Action Plan — top priorities |

---

## API Evidence (smoke tests)

All endpoints verified:

```
GET  /operational-summary?date=2026-06-02        → 200 (universe=18475, actionable=500)
GET  /today-action-plan?date=2026-06-02          → 200 (READY_WITH_BLOCKERS, 6 actions)
GET  /capacity/allocation-trace?date=2026-06-02  → 200 (unassigned=190)
GET  /program-capacity-policy?date=2026-06-02    → 200 (4 programs, STRICT_PRIORITY)
GET  /assignment-queue/build-audit?date=2026-06-02 → 200 (policy_applied=true)
POST /program-capacity-policy/simulate            → 200 (HYBRID: unassigned=220)
```

---

## Walkthrough Findings

Full findings exported to: `exports/audits/lima_growth/walkthrough_findings.json`

14 findings recorded across 6 scenarios. 5 API-level PASS, 9 WARN (UI navigation/label issues).
