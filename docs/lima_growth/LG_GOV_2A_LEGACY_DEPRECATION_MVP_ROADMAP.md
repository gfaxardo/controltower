# LG-GOV-2A — LIMA GROWTH LEGACY DEPRECATION + MVP ROADMAP

**Ticket:** LG-GOV-2A  
**Date:** 2026-06-11  
**Phase:** Lima Growth Foundation — Governance  
**Status:** MVP ROADMAP READY  

---

## TASK 0 — GOVERNANCE

Control Foundation / Lima Growth. Audit and roadmap only. Zero production changes.

---

## TASK 1 — LEGACY INVENTORY

### Legacy Tables (Lima Growth)

| Table | Rows | Status | Issue |
|-------|------|--------|-------|
| `yango_lima_driver_state_snapshot` | 18,545 | **ACTIVE (production)** | completed_orders_week is stale (uses MAX historical week). 86% false positive rate for activity. |
| `yango_lima_driver_history_weekly` | 135,812 | **ACTIVE (production)** | No park filter. 59% of drivers have latest week >3 months ago. |
| `yango_lima_driver_360_daily` | 179 | **BROKEN** | Pipeline not running since Jun 2. |
| `yango_lima_program_eligibility_daily` | 226,432 | **ACTIVE (production)** | Multi-program overlap (49% in 2+ programs). |
| `yango_lima_prioritized_opportunity_daily` | 44,367 | **ACTIVE (production)** | Based on legacy eligibility. |
| `yego_lima_assignment_queue` | 2,104 | **ACTIVE (production)** | Production queue — do not touch. |
| `yego_lima_control_loop_state` | 668 | **ACTIVE (production)** | Production control loop — do not touch. |
| `yango_lima_loopcontrol_campaign_export` | 54 | **ACTIVE (production)** | Production export — do not touch. |
| `yego_lima_program_registry` | 4 programs | **ACTIVE (production)** | Legacy programs (HVR, CHURN_PREVENTION, 14_90, ACTIVE_GROWTH). |

### Legacy Services

| Service | File | Status |
|---------|------|--------|
| Program eligibility | `yego_lima_program_eligibility_service.py` | ACTIVE — hardcoded rules, overlapping programs |
| Opportunity policy | `yego_lima_opportunity_policy_service.py` | ACTIVE — based on program codes |
| Priority allocation | `yego_lima_priority_allocation_service.py` | ACTIVE — STRICT_PRIORITY mode |
| Queue export | `yego_lima_loopcontrol_export_service.py` | ACTIVE — exports to LoopControl |
| Driver state builder | `yego_lima_driver_state_service.py` | ACTIVE — builds broken snapshot |
| Autonomous tick | `yego_lima_scheduler_service.py` | ACTIVE — 5-min tick |

### Legacy Endpoints (routers with `/yego-lima-growth/` prefix)

43 router files. Active endpoints for:
- Program status, eligibility, explainability
- Pipeline, scheduler
- Capacity, allocation, worklist
- Assignment queue, export, result sync
- Today action plan, operational summary
- Freshness, governance, diagnostic trace

---

## TASK 2 — NEW WORKFLOW INVENTORY

### Certified Foundation (ACT series)

| Table | Rows | Status |
|-------|------|--------|
| `yego_lima_driver_activity_event` | 18,154,342 | **CERTIFIED** — 17 months, Lima only, completed+cancelled |
| `yego_lima_driver_activity_daily` | 682,013 | **CERTIFIED** |
| `yego_lima_driver_activity_weekly` | 169,893 | **CERTIFIED** |
| `yego_lima_driver_activity_monthly` | 67,481 | **CERTIFIED** |
| `yego_lima_driver_lifecycle_daily` | 68,473 | **CERTIFIED** |
| `yego_lima_driver_lifecycle_event` | 48,611 | **CERTIFIED** |

### Taxonomy V2 (TAX series)

| Table | Rows | Status |
|-------|------|--------|
| `yego_lima_driver_taxonomy_v2_daily` | 68,473 × 4 days | **CERTIFIED** |
| `yego_lima_driver_taxonomy_v2_explanation` | 342,365 × 4 days | **CERTIFIED** |
| `yego_lima_taxonomy_v2_config` | 25 params | **CERTIFIED** |

### Program Engine V2 (PROG series)

| Table | Rows | Status |
|-------|------|--------|
| `yego_lima_program_v2_registry` | 10 programs | **CERTIFIED** |
| `yego_lima_program_v2_rule_config` | 21 rules | **CERTIFIED** |
| `yego_lima_program_v2_eligibility_daily` | 68,597 | **CERTIFIED** |
| `yego_lima_program_v2_assignment_daily` | 68,473 | **CERTIFIED** |
| `yego_lima_program_v2_priority_daily` | 67,880 | **CERTIFIED** |
| `yego_lima_program_v2_assignment_transition` | 68,473 | **CERTIFIED** |
| `yego_lima_program_v2_impact_daily` | 68,473 | **CERTIFIED** |

### Observability + Movement + Effectiveness

| Table | Rows | Status |
|-------|------|--------|
| `program_observability_fact` | 68,473 | **CERTIFIED** |
| `taxonomy_distribution_fact` | 9 | **CERTIFIED** |
| `program_distribution_fact` | 9 | **CERTIFIED** |
| `program_movement_fact` | 9 | **CERTIFIED** |
| `driver_growth_timeline_fact` | 205,419 | **CERTIFIED** |
| `driver_movement_fact` | 68,473 × 1 day | **CERTIFIED** |
| `program_effectiveness_fact` | 10 | **CERTIFIED** |

### RNA Audits (RNA series)

4 audit documents completed. RNA population validated as actionable.

---

## TASK 3 — CLASSIFICATION MATRIX

### Legacy Components

| Component | Classification | Reason | Replacement | Phase |
|-----------|---------------|--------|-------------|-------|
| `driver_state_snapshot.completed_orders_week` | **DEPRECATE** | Uses MAX historical week, not current. 86% false positive. | `activity_daily.completed_orders` | PHASE 1 |
| `driver_history_weekly` (latest week) | **DEPRECATE** | 59% stale. No park filter. | `activity_weekly` (Lima filtered) | PHASE 1 |
| `driver_360_daily` | **DEPRECATE** (until fixed) | Pipeline broken, 179 rows. | `activity_daily` | PHASE 1 |
| `program_eligibility_daily` | **REPLACE** | Multi-program overlap. Hardcoded rules. | `program_v2_eligibility_daily` | PHASE 3 |
| `prioritized_opportunity_daily` | **REPLACE** | Based on legacy eligibility. | `program_v2_priority_daily` | PHASE 3 |
| `assignment_queue` | **BLOCKED** | Production — touched by LoopControl export. | Queue V2 (post-MVP) | PHASE 6 |
| `control_loop_state` | **BLOCKED** | Production — touched by agents. | Control Loop V2 (post-MVP) | PHASE 6 |
| `loopcontrol_campaign_export` | **BLOCKED** | Production export pipeline. | Export V2 (post-MVP) | PHASE 6 |
| `program_registry` (legacy 4 programs) | **DEPRECATE** | Replaced by 10-program V2 registry. | `program_v2_registry` | PHASE 3 |
| `taxonomy_v1_daily` | **ARCHIVE_LATER** | Built on stale data. V2 certified. | `taxonomy_v2_daily` | PHASE 2 |
| Legacy program services (eligibility, policy, allocation) | **DEPRECATE** | Hardcoded. Non-exclusive. | Program V2 services | PHASE 3 |

### New Workflow Components (All KEEP)

All ACT, TAX, PROG, MOV, OBS, IMP series tables and services are **KEEP** and **EXPAND**.

---

## TASK 4 — ENDPOINT MAP

### Legacy Endpoints Status

| Endpoint Group | Status | Banner |
|---------------|--------|--------|
| Program status/summary | KEEP (reads legacy) | Add `[LEGACY]` banner |
| Pipeline run/status | KEEP | Reads scheduler |
| Scheduler control | KEEP | Production scheduler |
| Capacity/allocation | KEEP (reads legacy) | Add `[LEGACY]` banner |
| Assignment queue | KEEP (production) | No change |
| Export/result sync | KEEP (production) | No change |
| Today action plan | KEEP | Reads legacy |

### New Endpoints (Read-Only, Shadow)

| Endpoint Group | Prefix | Status |
|---------------|--------|--------|
| Lifecycle | `/yego-lima-growth/lifecycle/` | Implemented |
| Taxonomy V2 | (via observability) | Via OBS facts |
| Program V2 | `/yego-lima-growth/program-v2/` | Router created |
| Observability | `/yego-lima-growth/observability/` | Router created |
| Movement | (via observability) | Via OBS facts |
| Effectiveness | (via observability) | Via OBS facts |

---

## TASK 5 — SCHEDULER MAP

### Current Scheduled Jobs

| Job | Frequency | What It Does | Gap |
|-----|-----------|-------------|-----|
| `lima_growth_autonomous_tick` | Every 5 min | Raw ingestion + cascade detection + control loop sync | **Does NOT build taxonomy/lifecycle/programs** |
| `serving_fact_daily_refresh` | Daily 05:00 | Omniview serving facts | Omniview only, not Lima Growth |
| `omniview_cascade_refresh` | Daily 04:00 | Bridge + day + week + month + snapshot | Omniview only |

### Gaps

| Missing Job | What It Should Do | Frequency |
|------------|-------------------|-----------|
| `lifecycle_daily_build` | Rebuild lifecycle_daily from activity_event | Daily 02:00 |
| `taxonomy_v2_daily_build` | Rebuild taxonomy_v2_daily from lifecycle | Daily 03:00 |
| `program_v2_daily_build` | Rebuild program assignment + priority | Daily 03:30 |
| `movement_daily_detect` | Compare today vs yesterday taxonomy + programs | Daily 04:00 |
| `observability_rebuild` | Rebuild all serving facts | Daily 04:30 |
| `effectiveness_correlate` | Correlate programs → next-day movements | Daily 04:30 |

---

## TASK 6 — MVP ROADMAP

### Phase 1: Scheduler Certification (2 days)

- Add lifecycle + taxonomy + program build to autonomous tick
- Validate daily pipeline produces consistent snapshots
- Build 7 consecutive days of data
- Verify movement detection across multiple day pairs

### Phase 2: Serving Governance (1 day)

- Ensure all serving facts rebuild daily
- Add freshness checks
- Add degraded state handling
- Verify 68,473 drivers tracked every day

### Phase 3: Growth Intelligence Dashboard MVP (3 days)

Read-only dashboard consuming serving facts:

**Tabs:**
1. **Overview** — Lifecycle distribution, segment distribution, program distribution, active drivers
2. **Programs** — Per-program driver counts, priority queue, top scores
3. **Segments** — Segment transition matrix, segment distribution
4. **Movement** — Daily movement rate, top transitions, positive/negative moves
5. **RNA Intelligence** — RNA sub-segments, contactability, cancelled-only
6. **Driver Explorer** — Search by driver ID, full timeline view

### Phase 4: Explainability + Drilldown (2 days)

- Click segment → list drivers
- Click program → list drivers
- Click driver → full profile (lifecycle, activity, value, momentum, segment, program, timeline)
- "Why?" button on every state

### Phase 5: CSV Export (1 day)

- Controlled export of driver lists by segment/program
- No production export pipeline
- Manual CSV generation for campaigns

### Phase 6: Queue V2 / Control Loop V2 (post-MVP)

- Replace legacy assignment queue with V2
- Replace legacy control loop with V2
- Connect to LoopControl export
- Full production cutover

---

## TASK 7 — UI NORTH STAR

### Principles

1. **Low cognitive load** — Overview first, details on demand
2. **Progressive drilldown** — Segment → Program → Driver → Timeline
3. **"Why?" always available** — Every classification has persisted explanation
4. **No runtime heavy queries** — All served from pre-computed facts
5. **Degraded state visible** — "PENDING" for impact, "INSUFFICIENT_HISTORY" for momentum
6. **Traceability by layer** — Lifecycle → Activity → Value → Momentum → Segment → Program

### Tabs Layout

```
┌──────────────────────────────────────────────────────┐
│ Growth Intelligence                       2026-06-10 │
├──────────┬─────────┬──────────┬────────┬─────────────┤
│ Overview │Programs │ Segments │Movement│ RNA Intel   │
├──────────┴─────────┴──────────┴────────┴─────────────┤
│                                                       │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────┐ │
│  │Lifecycle│ │Activity │ │ Value   │ │ Momentum    │ │
│  │6 states │ │5 states │ │5 states │ │ 7 states    │ │
│  └─────────┘ └─────────┘ └─────────┘ └─────────────┘ │
│                                                       │
│  ┌──────────────────────┐ ┌─────────────────────────┐ │
│  │ Segments (11)        │ │ Programs (10)           │ │
│  │ RNA: 50,181          │ │ RNA_ONBOARDING: 50,181  │ │
│  │ ACTIVE_GROWTH: 2,594 │ │ ACTIVE_GROWTH: 2,594    │ │
│  │ HVR_CANDIDATE: 166   │ │ HVR: 166               │ │
│  └──────────────────────┘ └─────────────────────────┘ │
│                                                       │
│  ┌──────────────────────────────────────────────────┐ │
│  │ Movement Today: 1,019 transitions (1.49%)        │ │
│  │ +475 positive  -54 negative                       │ │
│  └──────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

---

## TASK 9 — GO / NO-GO

### Veredicto: **A) MVP_ROADMAP_READY**

| Criterion | Status |
|-----------|--------|
| Legacy inventory complete | PASS (9 tables, 6 services, 43 endpoints) |
| New workflow inventory complete | PASS (24 tables, 4 layers) |
| Classification matrix | PASS (KEEP/DEPRECATE/REPLACE/BLOCKED) |
| Endpoint map | PASS (legacy + new shadow endpoints) |
| Scheduler gaps identified | PASS (6 missing daily jobs) |
| MVP roadmap | PASS (6 phases, ~12 days) |
| UI north star | PASS (6 tabs, 6 principles) |

### Next Immediate Step

**LG-SCH-2A: Scheduler Certification** — Add daily pipeline jobs to autonomous tick for 7+ consecutive days of data.

---

**LG-GOV-2A — COMPLETE**

*Legacy deprecation plan: 3 tables DEPRECATE, 3 REPLACE, 3 BLOCKED.*  
*New workflow: 24 certified tables across Activity, Taxonomy, Programs, Observability.*  
*MVP Roadmap: 6 phases, 12 days to Growth Intelligence Dashboard.*  
*Next: LG-SCH-2A (Scheduler Certification).*
