# LG-UX-0A — UI COVERAGE MATRIX

**Date:** 2026-06-11

---

## ASSET VISIBILITY MATRIX

| Asset | Currently Visible? | Tab | Drildown | Priority |
|-------|-------------------|-----|----------|----------|
| Universe (total drivers) | YES | Overview | Driver Explorer | P0 |
| Freshness / Operability | YES | Overview (banner) | Growth Health API | P0 |
| driver_state_snapshot | YES | Segments, Overview | Per-driver detail | P0 |
| lifecycle_classification | PARTIAL | Segments (by lifecycle_state) | Per-driver lifecycle | P0 |
| taxonomy segments | PARTIAL | Segments (limited) | Per-layer drilldown | P1 |
| program_eligibility | YES | Programs | Per-program driver list | P0 |
| prioritized_opportunity | PARTIAL | Programs | Actionable vs total | P0 |
| assignment_queue | YES | Queue | Program + channel breakdown | P0 |
| control_loop_state | NO | — | — | P1 |
| serving_facts (8 types) | YES | Behind serving-first endpoints | Cache status | P0 |
| movement (transitions) | NO | — | — | P1 |
| movement (decisions) | NO | — | — | P1 |
| RNA (loyalty) | YES | Yango Loyalty (separate) | City comparison | P1 |
| campaign_effectiveness | NO | — | — | P2 |
| intraday_signals | NO | — | — | P2 |
| list_history | PARTIAL | Per-driver detail | History timeline | P1 |
| driver_360 | PARTIAL | Driver Explorer | Per-driver full profile | P1 |
| loopcontrol_export | YES | Queue overview | Export status | P0 |
| capacity_config | YES | Queue detail | Channel utilization | P1 |
| policy_config | NO | — | — | P2 |
| freshness_registry | YES | Governance | Component detail | P1 |
| scheduler_status | YES | Governance | Tick log | P1 |
| V2 shadow tables | NO (by design) | — | — | P3 |
| taxonomy_v2_explanation | NO | — | — | P1 |

## INVISIBLE ASSETS — Gap Analysis

### Not visible, needs tab:

| Asset | Reason | Priority |
|-------|--------|----------|
| control_loop_state | 668 drivers in workflow, no UI visibility | P1 |
| movement (transitions + decisions) | 1,205 transitions + 5,558 decisions traceable | P1 |
| intraday_signals | 310 signals tracking contact outcomes | P2 |
| campaign_effectiveness | Pre/post impact measurement available | P2 |
| policy_config | Active policy rules not exposed | P2 |

### Not visible, needs drilldown:

| Asset | Where | Priority |
|-------|-------|----------|
| taxonomy layers (value, momentum, persona) | Segments tab → drilldown | P1 |
| taxonomy_v2_explanation | Driver Explorer → "Why this segment?" | P1 |
| list_history | Driver Explorer → History timeline | P1 |

### Visible, complete:

| Asset | Where | Notes |
|-------|-------|-------|
| All 5 production tables | Overview, Programs, Segments, Queue | FRESH today |
| Freshness/operability | Growth Health banner | 3 endpoints operational |
| Scheduler | Governance tab | 580 successful ticks |
| Export status | Queue overview | LoopControl integration |

## ZERO INVISIBLE IMPORTANT ASSETS

After adding the proposed tabs:
- Movement tab: covers transitions + decisions + list_history
- Driver Explorer: covers 360 + taxonomy explanation + history
- Governance: covers freshness + scheduler + operability
- RNA tab: covers loyalty (currently separate system)

All important operational assets become visible.
