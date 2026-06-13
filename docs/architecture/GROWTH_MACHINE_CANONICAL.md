# GROWTH MACHINE — CANONICAL DOCUMENTATION

**Version:** 1.0.0
**Date:** 2026-06-13
**Status:** FIRST DRAFT — Evidence-based from live repo audit
**Engine:** Control Foundation (#1) / Lima Growth subsystem

---

## 1. OVERVIEW

The Growth Machine (Lima Growth) is the YEGO Lima driver growth operations subsystem. It manages the complete lifecycle of driver engagement: identity resolution, state classification, program eligibility, daily opportunity lists, action tracking, impact measurement, and segment migration analysis.

**Scope:** Lima fleet only (park_id: `08e20910d81d42658d4334d3f6d10ac0`)

---

## 2. ARCHITECTURE

### 2.1 Pipeline

```
YANGO FLEET API (external)
    │
    ▼
yango_raw_ingestion_service.py
    │
    ▼
Driver360 (growth.yango_lima_driver_360_daily)
    │
    ▼
Driver History (growth.yango_lima_driver_history_daily/weekly)
    │
    ▼
State Snapshots (growth.yango_lima_driver_state_snapshot)
    │
    ▼
Program Eligibility (yego_lima_program_eligibility_service.py)
    │
    ▼
Opportunity Lists (growth.yango_lima_daily_opportunity_list)
    │
    ▼
Action Tracking (control loop: actions → impact → attribution)
    │
    ▼
Segment Migration & Attribution (feedback loop)
```

### 2.2 State-Based Loyalty Architecture

```
Driver360 ──→ State Snapshot ──→ Program Eligibility ──→ Opportunity Lists ──→ Actions ──→ Impact
```

States: LOYAL, ACTIVE, DECLINING, CHURN_RISK, CHURNED, NEW, REACTIVATED, RECOVERED

---

## 3. DATA TABLES (all in `growth` schema)

### 3.1 Core Tables

| Table | Purpose |
|-------|---------|
| `growth.yango_lima_driver_history_daily` | Daily driver activity history |
| `growth.yango_lima_driver_history_weekly` | Weekly driver activity history |
| `growth.yango_lima_driver_360_daily` | Daily Driver360 view |
| `growth.yango_lima_driver_state_snapshot` | Daily driver state classification |
| `growth.yango_lima_daily_opportunity_list` | Daily actionable driver lists |
| `growth.yango_lima_program_eligibility` | Driver program eligibility |

### 3.2 Control Loop Tables

| Table | Purpose |
|-------|---------|
| `growth.*_actions` | Action registry (STATUS: UNKNOWN — exact table name needs verification) |
| `growth.*_segment_transitions` | Segment transition tracking (STATUS: UNKNOWN — verify exact table) |
| `growth.*_impact` | Daily impact measurements (STATUS: UNKNOWN — verify exact table) |
| `growth.*_attribution` | Impact attribution data (STATUS: UNKNOWN — verify exact table) |

**NEEDS VERIFICATION: YES** — Exact table names in growth schema for actions, transitions, impact, and attribution. Derived from service imports in `yego_lima_growth_control_loop.py`.

---

## 4. SERVICE MAP

### 4.1 Core Pipeline Services

| Service | File | Responsibility |
|---------|------|----------------|
| `yango_raw_ingestion_service.py` | `backend/app/services/` | Raw data ingestion from Yango Fleet API |
| `yego_lima_driver_360_service.py` | `backend/app/services/` | Driver360 profile building |
| `yego_lima_driver_state_service.py` | `backend/app/services/` | Daily state classification |
| `yego_lima_program_eligibility_service.py` | `backend/app/services/` | Program eligibility rules |
| `yego_lima_daily_opportunity_service.py` | `backend/app/services/` | Opportunity list generation |
| `yego_lima_daily_refresh_service.py` | `backend/app/services/` | Daily refresh orchestration |
| `yego_lima_freshness_service.py` | `backend/app/services/` | Pipeline freshness monitoring |
| `yego_lima_scheduler_service.py` | `backend/app/services/` | Refresh scheduling |
| `yego_lima_daily_pipeline_service.py` | `backend/app/services/` | Pipeline execution |
| `yego_lima_v2_daily_pipeline_service.py` | `backend/app/services/` | V2 pipeline |

### 4.2 Control Loop Services

| Service | File | Responsibility |
|---------|------|----------------|
| `yego_lima_control_loop_service.py` | `backend/app/services/` | Control loop summary, agent tracking |
| `yego_lima_actionable_list_service.py` | `backend/app/services/` | Actionable list management |
| `yego_lima_action_registry_service.py` | `backend/app/services/` | Action CRUD |
| `yego_lima_action_impact_service.py` | `backend/app/services/` | Daily impact calculation |
| `yego_lima_segment_migration_service.py` | `backend/app/services/` | Segment transition tracking |
| `yego_lima_list_outcome_service.py` | `backend/app/services/` | List outcome measurement |
| `yego_lima_impact_attribution_service.py` | `backend/app/services/` | Impact attribution |
| `yego_lima_queue_operational_service.py` | `backend/app/services/` | Queue management |
| `yego_lima_queue_summary_service.py` | `backend/app/services/` | Queue summaries |
| `yego_lima_today_action_plan_service.py` | `backend/app/services/` | Today's action plan |

### 4.3 Analysis & Export Services

| Service | File | Responsibility |
|---------|------|----------------|
| `yego_lima_executive_metrics_service.py` | `backend/app/services/` | Executive dashboard metrics |
| `yego_lima_export_service.py` | `backend/app/services/` | Export pipeline |
| `yego_lima_loopcontrol_export_service.py` | `backend/app/services/` | Loopcontrol export |
| `yego_lima_result_sync_service.py` | `backend/app/services/` | Result synchronization |
| `yego_lima_effectiveness_service.py` | `backend/app/services/` | Effectiveness measurement |
| `yego_lima_explainability_service.py` | `backend/app/services/` | Explainability layer |
| `yego_lima_movement_service.py` | `backend/app/services/` | Movement analytics |
| `yego_lima_productivity_service.py` | `backend/app/services/` | Driver productivity |
| `yego_lima_lifecycle_service.py` | `backend/app/services/` | Driver lifecycle tracking |
| `yego_lima_universe` (router + DB queries) | `backend/app/routers/` | Universe governance |

### 4.4 Program & Policy Services

| Service | File | Responsibility |
|---------|------|----------------|
| `yego_lima_program_status_service.py` | `backend/app/services/` | Program status display |
| `yego_lima_program_display_service.py` | `backend/app/services/` | Program UI display |
| `yego_lima_program_explainability_service.py` | `backend/app/services/` | Program explainability |
| `yego_lima_program_capacity_policy_service.py` | `backend/app/services/` | Capacity policy |
| `yego_lima_opportunity_policy_service.py` | `backend/app/services/` | Opportunity policy |
| `yego_lima_priority_allocation_service.py` | `backend/app/services/` | Priority allocation |
| `yego_lima_channel_allocation_service.py` | `backend/app/services/` | Channel allocation |

---

## 5. ENDPOINTS (by domain group)

### 5.1 Universe Governance
| Method | Endpoint | Router |
|--------|----------|--------|
| GET | `/yego-lima-growth/universe/*` | `yego_lima_universe.py` |

### 5.2 Control Loop
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/yego-lima-growth/control-loop/build-actionable-lists` | Build daily lists |
| POST | `/yego-lima-growth/control-loop/close-unmanaged-items` | Close pending |
| GET | `/yego-lima-growth/control-loop/actionable-list` | List actions |
| POST | `/yego-lima-growth/control-loop/actions` | Create action |
| PATCH | `/yego-lima-growth/control-loop/actions/{id}/status` | Update status |
| POST | `/yego-lima-growth/control-loop/build-daily-impact` | Build impact |
| GET | `/yego-lima-growth/control-loop/agent-performance-summary` | Agent perf |
| GET | `/yego-lima-growth/control-loop/driver-impact-timeline/{id}` | Driver timeline |
| POST | `/yego-lima-growth/control-loop/build-segment-transitions` | Build transitions |
| POST | `/yego-lima-growth/control-loop/build-list-outcomes` | Build outcomes |
| GET | `/yego-lima-growth/control-loop/transition-summary` | Transition summary |
| GET | `/yego-lima-growth/control-loop/movement-matrix` | Movement matrix |
| GET | `/yego-lima-growth/control-loop/list-outcome-summary` | Outcome summary |
| POST | `/yego-lima-growth/control-loop/build-impact-attribution` | Build attribution |
| GET | `/yego-lima-growth/control-loop/attribution-summary` | Attribution |
| GET | `/yego-lima-growth/control-loop/top-performing-agents` | Top agents |
| GET | `/yego-lima-growth/control-loop/top-performing-campaigns` | Top campaigns |

### 5.3 Queue Operational
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/yego-lima-growth/queue/*` | Queue operations |

### 5.4 Pipeline & Freshness
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/yego-lima-growth/pipeline/*` | Pipeline triggers |
| GET | `/yego-lima-growth/freshness/*` | Freshness status |

### 5.5 Driver Explorer
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/yego-lima-growth/driver/*` | Driver detail |
| GET | `/yego-lima-growth/explorer/*` | Driver explorer |

### 5.6 Programs & Policy
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/yego-lima-growth/programs/*` | Program status |
| GET | `/yego-lima-growth/policy/*` | Policy management |

**NEEDS VERIFICATION: YES** — Exact endpoints for queue, pipeline, freshness, driver explorer, programs, and policy require deeper router file audit. The count of 100+ endpoints across 50+ routers needs detailed enumeration.

---

## 6. FRONTEND

### 6.1 Pages

| Page | Path | Status |
|------|------|--------|
| `LimaGrowthDashboardV2.jsx` | `frontend/src/pages/` | ACTIVE — V2 |
| `LimaGrowthDashboardUI1A.jsx` | `frontend/src/pages/` | LEGACY — UI1A |
| `LimaGrowthDashboard.jsx` | `frontend/src/pages/` | ROOT (router) |
| `LimaGrowthDashboard.legacy.jsx` | `frontend/src/pages/` | LEGACY |

### 6.2 V2 Structure

```
pages/lima-growth-v2/
    ├── components/     # V2-specific components
    ├── design/         # Design system
    ├── hooks/          # Custom hooks
    └── sections/       # Section components
```

### 6.3 UI1A Structure (Legacy)

```
pages/lima-growth-ui1a/
    ├── components/
    ├── hooks/
    └── sections/
```

---

## 7. PROGRAMS (Canonical)

| Program | Code | Target |
|---------|------|--------|
| LOYALTY_14_90 | PROGRAM_14_90 | Early-life drivers (14-90 day tenure) |
| ACTIVE_GROWTH | PROGRAM_ACTIVE_GROWTH | Underperforming active drivers |
| CHURN_PREVENTION | PROGRAM_CHURN_PREVENTION | At-risk or churned drivers |

---

## 8. UNIVERSES

| Universe | Definition | Window |
|----------|------------|--------|
| Registered | All drivers ever seen for Lima fleet | All time |
| Historical | Drivers with completed orders in history | 2025-02 to today |
| Active 90D | Drivers with >=1 order in last 90 days | Rolling 90d |
| Active 30D | Drivers with >=1 order in last 30 days | Rolling 30d |
| Active 7D | Drivers with >=1 order in last 7 days | Rolling 7d |
| Active Daily | Drivers with >=1 order on a single day | 1 day |
| Opportunity | Drivers eligible for daily action | 1 day |

**Lima Filter:** `park_id = 08e20910d81d42658d4334d3f6d10ac0`

---

## 9. MEASUREMENT FRAMEWORK

### 9.1 Daily Impact Metrics

For each action, the system calculates:
- `completed_orders_day`, `supply_hours_day`
- `baseline_*_7d`: 7-day average before action
- `delta_*_vs_baseline`: difference vs baseline
- `moved_segment_flag`, `improved_orders_flag`, `improved_supply_flag`
- `reactivated_flag`, `reached_target_flag`

### 9.2 Agent Performance

- `assigned_items`, `action_confirmed_count`, `action_attempted_count`
- `confirmation_rate`, `contacted_rate`
- `avg_delta_orders`, `avg_delta_supply`
- `moved_segment_count`, `reactivated_count`

### 9.3 Attribution Scopes

- AGENT — By action owner
- CAMPAIGN — By campaign code
- SEGMENT — By driver segment
- ACTION_TYPE — By action category
- ACTION_CHANNEL — By contact channel

---

## 10. CERTIFICATION STATUS

| Certification | Document | Status |
|---------------|----------|--------|
| Canonicalization | `LG_CAN_1A_CANONICALIZATION_CERTIFICATION.md` | CERTIFIED |
| Movement Backfill | `LG_CAN_1B_CANONICAL_MOVEMENT_BACKFILL_CERTIFICATION.md` | CERTIFIED |
| Freshness Recovery | `LG_CAN_1C_FRESHNESS_RECOVERY_CERTIFICATION.md` | CERTIFIED |
| Operational Closure | `LG_CF_OPERATIONAL_CLOSURE.md` | CLOSED |
| Queue Operationalization | `LG_UX_R2_5_QUEUE_OPERATIONALIZATION.md` | CERTIFIED |
| Control Loop | `LG_CF_OPERATIONAL_CLOSURE.md` | CLOSED |
| Result Sync | `LG_C2_0_RESULT_SYNC_CERTIFICATION.md` | CERTIFIED |
| Movement Attribution | `LG_ATTR_1_0A_MOVEMENT_ATTRIBUTION_FOUNDATION.md` | CERTIFIED |

---

## 11. KNOWN GAPS

| Gap | Status | Priority |
|-----|--------|----------|
| Exact growth schema table names for actions/impact/attribution | NEEDS VERIFICATION | MEDIUM |
| Full endpoint enumeration for 50+ routers | NEEDS VERIFICATION | LOW |
| UI1A → V2 migration status | NEEDS VERIFICATION | MEDIUM |
| Loopcontrol export pipeline status | LIKELY ACTIVE — verify | LOW |

---

## 12. CROSS-REFERENCES

- [SYSTEM_MAP.md](SYSTEM_MAP.md) — Full system map
- [KNOWN_CONSTRAINTS.md](KNOWN_CONSTRAINTS.md) — Known constraints
- [CONTROL_LOOP_CANONICAL.md](CONTROL_LOOP_CANONICAL.md) — Control loop domain
- [YANGO_API_CANONICAL.md](YANGO_API_CANONICAL.md) — Yango API domain
- [UNIVERSE_GOVERNANCE.md](../lima_growth/UNIVERSE_GOVERNANCE.md) — Universe definitions
- [CONTROL_LOOP_FOUNDATION.md](../lima_growth/CONTROL_LOOP_FOUNDATION.md) — Control loop stack
- [STATE_BASED_LOYALTY_ARCHITECTURE.md](../lima_growth/STATE_BASED_LOYALTY_ARCHITECTURE.md) — State architecture
- [DRIVER_ACTIVITY_TRUTH_RECONCILIATION_REPORT.md](../lima_growth/DRIVER_ACTIVITY_TRUTH_RECONCILIATION_REPORT.md) — Truth reconciliation
- [LG_NORTH_STAR_EXCLUSIVE_LISTS_CONTRACT.md](../lima_growth/LG_NORTH_STAR_EXCLUSIVE_LISTS_CONTRACT.md) — North Star: exclusive dynamic lists, mutual exclusivity, daily refresh, Control Loop export, impact measurement

---

## NORTH STAR: Exclusive Dynamic Operational Lists

**Reference:** `docs/lima_growth/LG_NORTH_STAR_EXCLUSIVE_LISTS_CONTRACT.md`

The final product of Lima Growth Machine is a daily refreshed system of mutually exclusive operational driver lists.

### Principles
- 1 driver = 1 assigned operational universe per day.
- Eligibility may be multi-signal; final assignment is exclusive.
- Lists refresh daily with recent operational behavior.
- Export to Control Loop.
- Action tracking by channel/person/outcome.
- Daily and weekly impact measurement.

### Operational Universes (Hierarchical)
1. New/Reactivated Activation (0-14 days)
2. Ramp-Up (15-45 days)
3. Consolidation (46-90 days)
4. Active Growth (90+ days, by productivity band)
5. Recovery — High Value / Low Value
6. Cemetery — long churned/archived

### Governance
Future Growth Machine work must pass the North Star Test: does it improve exclusive lists, daily refresh, Control Loop export, action tracking, or impact measurement? If not, document/backlog.

---

*Generated from live repo audit. Evidence sources: `backend/app/routers/yego_lima_growth_control_loop.py`, `backend/app/routers/yego_lima_universe.py`, `backend/app/routers/yego_lima_control_loop_router.py`, `backend/app/services/yego_lima_*.py` (50+ files), `docs/lima_growth/*.md` (100+ docs), `frontend/src/pages/lima-growth-*/`.*
