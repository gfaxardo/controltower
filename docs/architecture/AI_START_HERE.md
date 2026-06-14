# AI START HERE

**Version:** 1.0.0
**Date:** 2026-06-13
**Purpose:** Mandatory entry point for any AI analyzing, designing, or implementing changes in YEGO Control Tower.

---

## STOP

Before analyzing, designing, or implementing any change, read these documents in order:

### 1. REQUIRED — Always read first

| # | Document | Why |
|---|----------|-----|
| 1 | `ai_operating_system.md` | Engine architecture, core principles, mandatory rules |
| 2 | `ai_current_phase.md` | Active phase, blocked engines, forbidden changes |
| 3 | `docs/architecture/TRUTH_MAP_V2.md` | **Definitive.** Every critical table: writer, readers, scheduler, freshness, owner, risk |
| 4 | `docs/architecture/KNOWN_CONSTRAINTS.md` | Forbidden actions, certified modules, quarantine code, danger zones |

### 2. REQUIRED — Then read only the domain(s) affected

| Domain | Document |
|--------|----------|
| Omniview V2 | `docs/architecture/OMNIVIEW_V2_CANONICAL.md` |
| Growth Machine | `docs/architecture/GROWTH_MACHINE_CANONICAL.md` |
| Control Loop (Plan Data) | `docs/architecture/CONTROL_LOOP_CANONICAL.md` |
| Yango API / Loyalty | `docs/architecture/YANGO_API_CANONICAL.md` |
| System overview | `docs/architecture/SYSTEM_MAP.md` |

### 3. REQUIRED — Lima Growth Machine North Star Check

Before any Growth Machine work, read:

| # | Document | Why |
|---|----------|-----|
| 1 | `docs/lima_growth/LG_NORTH_STAR_EXCLUSIVE_LISTS_CONTRACT.md` | North Star contract: exclusive dynamic lists, daily refresh, Control Loop export, action tracking, impact measurement |
| 2 | `docs/lima_growth/LG_NORTH_1A_EXCLUSIVE_LISTS_GOVERNANCE_CERTIFICATION.md` | Governance certification of the North Star |
| 3 | `docs/lima_growth/LG_PROD_SCOPE_1A_PRODUCTION_CUTOVER_SCOPE_OVERRIDE.md` | Production cutover exception: authorized scope |
| 4 | `docs/lima_growth/LG_NORTH_PRECHECK_1B_MVP_GAP_SCAN.md` | Latest MVP gap scan and phasing |

**North Star:**

The final product of Lima Growth Machine is not the dashboard. The final product is **daily refreshed mutually exclusive operational driver lists**, exportable to Control Loop and measurable by daily/weekly action impact.

**North Star Test:**

Every Growth Machine task must answer:

| # | Question |
|---|----------|
| 1 | Does this improve exclusive dynamic lists? |
| 2 | Does this improve daily refresh correctness? |
| 3 | Does this improve Control Loop export? |
| 4 | Does this improve action tracking? |
| 5 | Does this improve daily/weekly impact measurement? |
| 6 | If NO to all, why is this being done now? |

**Rule:** If the answer is NO to all → document/backlog. Do NOT implement.

Do NOT open Diagnostic Engine, Forecast, Suggestion, Decision, Action, AI Copilot, or Learning until Growth Machine MVP cutover is complete and certified.

---

## PRECEDENCE

If any conflict exists between sources, the precedence order is:

```
TRUTH_MAP_V2.md
    ↓ (prevails over)
ai_current_phase.md
    ↓ (prevails over)
ai_operating_system.md
    ↓ (prevails over)
Domain canonical docs (OMNIVIEW_V2, GROWTH_MACHINE, etc.)
    ↓ (prevails over)
KNOWN_CONSTRAINTS.md
    ↓ (prevails over)
Historical audit reports (*.md in root, docs/control_foundation/)
    ↓ (prevails over)
Code comments
    ↓ (prevails over)
Context from previous conversations
```

**Exception:** Evidence from actual running code (live DB schema, executed SQL logs, running scheduler status) prevails over ALL documentation if it contradicts.

---

## PHASE STATUS

### ACTIVE (can implement changes)

| Engine | Phase | Focus |
|--------|-------|-------|
| Control Foundation | OMNI-P0 Recovery | Vs Proy canonicalization, Revenue serving, cell contract, CLOSED/PARTIAL visibility, real semantic certification |
| Omniview V2 | Closure | Stabilize bridge cascade, eliminate multi-writers, create serving views for day/week, activate scheduler, connect UI |
| Growth Machine | Closure | Resolve `driver_history_weekly` bootstrap gap, protect DELETEs with transactions, complete freshness coverage |

### READY NEXT (prepare, do not activate yet)

| Engine | Pre-requisite |
|--------|---------------|
| Diagnostic Engine 2A.3 | OMNI-P0 closed with real GO |

### BLOCKED (do not implement)

| Engine | Blocked by |
|--------|------------|
| Forecast Engine | Control Foundation not closed with real GO |
| Suggestion Engine | Forecast Engine not active |
| Decision Engine | Suggestion Engine not active |
| Action Engine | Decision Engine not active |
| AI Copilot | All prior engines not completed |
| Learning Engine | No historical action data (min 3 months required) |

---

## BEFORE IMPLEMENTING ANYTHING

Answer these 7 questions. If you cannot answer all 7, do not implement:

| # | Question | Must Reference |
|---|----------|----------------|
| 1 | **Which engine?** (CF, DX, GM, etc.) | `ai_operating_system.md` engine list |
| 2 | **Which phase?** (OMNI-P0, GM closure, etc.) | `ai_current_phase.md` |
| 3 | **Which table(s)?** | `TRUTH_MAP_V2.md` per-table section |
| 4 | **Which writer(s)?** | `TRUTH_MAP_V2.md` Writers field |
| 5 | **What freshness impact?** | `TRUTH_MAP_V2.md` Freshness contract field |
| 6 | **What risk is introduced?** | `TRUTH_MAP_V2.md` Risk field + `KNOWN_CONSTRAINTS.md` |
| 7 | **What is the rollback?** | Your own analysis |

---

## RULES

### Absolute prohibitions

- **Never revive legacy.** Code in `LEGACY_ACTIVO`, `LEGACY_MUERTO`, or `PENDIENTE_DE_DEPRECACIÓN` categories must not be extended, refactored, or used as base for new features.
- **Never create parallel writers.** If `TRUTH_MAP_V2.md` shows a table is already `MULTI_WRITER`, do not add another writer. Consolidate instead.
- **Never create parallel refresh mechanisms.** If a table already has a canonical refresh path, do not add another scheduler or cron job for it.
- **Never create parallel engines.** Only 1 engine ACTIVE at a time. Only 1 READY NEXT. Everything else is BACKLOG.
- **Never touch certified modules without impact justification.** Refer to `KNOWN_CONSTRAINTS.md` Section 2 for the certified module list.

### Priorities

- **Prioritize ownership governance.** Every table must have exactly 1 owner service. Tables in `MULTI_WRITER` state are bugs, not features.
- **Prioritize freshness governance.** Every critical table must be in `serving_registry` (for OV2 tables) or `yego_lima_freshness_registry` + `yego_lima_serving_freshness_fact` (for Growth Machine tables). Tables without freshness coverage must be covered before new features are added.

### Reference

- **TRUTH_MAP_V2.md is the source of truth for table-level architecture.** It contains writer, reader, scheduler, refresh, and freshness data for every critical table, backed by exact file+line evidence.

---

## QUICK REFERENCE: CRITICAL TABLES

| Table | Writers | Scheduler | Freshness | Risk |
|-------|---------|-----------|-----------|------|
| `ops.driver_day_slice_fact` | 2 | cascade (cron) | cascade-only | MEDIUM |
| `ops.real_business_slice_day_fact` | 4 | cascade + job | service-only | HIGH |
| `ops.real_business_slice_week_fact` | **7 (1 BROKEN)** | cascade + job | service-only | **CRITICAL** |
| `ops.real_business_slice_month_fact` | 3 | cascade | service-only | MEDIUM |
| `growth.yango_lima_driver_history_weekly` | 1 | **NONE** | chain-only | HIGH |
| `growth.yango_lima_driver_state_snapshot` | 1 | tick (5min) | comprehensive | MEDIUM |
| `growth.yango_lima_program_eligibility_daily` | 1 | tick (5min) | covered | LOW |
| `growth.yango_lima_daily_opportunity_list` | 1 | tick (5min) | chain-only | LOW |
| `growth.yego_lima_control_loop_state` | 1 | tick (5min) | **NONE** | MEDIUM |

---

## QUICK REFERENCE: TOP GAPS

| # | Gap | Action Required |
|---|-----|-----------------|
| G1 | `week_fact`: 7 writers + 1 BROKEN | Consolidate, block broken script, deprecate legacy path |
| G2 | `driver_history_weekly`: no scheduler | Add to autonomous tick or cascade |
| G3 | `day_fact`, `week_fact`, `month_fact`: not in `serving_registry` | Register all three |
| G4 | `control_loop_state`: no freshness | Add to freshness chain + registry |
| G5 | `driver_day_slice_fact`: 2 writers | Deprecate legacy `build_driver_day_slice_fact.py` |
| G6 | `day_fact`: 2 competing refresh mechanisms | Consolidate to OV2 cascade |

---

*This document is the mandatory first read for any AI session. It is referenced from `TRUTH_MAP_V2.md`.*
