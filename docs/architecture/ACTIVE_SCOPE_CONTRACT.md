# ACTIVE SCOPE CONTRACT

**Version:** 1.0.0
**Date:** 2026-06-13
**Status:** DEFINITIVE
**Purpose:** Define current active scope to prevent proactivity outside phase, premature engine activation, and unauthorized redesigns.

---

## 1. Purpose

This contract defines the current active scope for YEGO Control Tower development. It prevents:

- Scope creep
- Unprompted proactive actions
- Premature engine activation
- Unauthorized redesigns
- Implementation of findings that belong in backlog
- Mixing audit, design, and implementation without gates

---

## 2. Current Active Domain

**Lima Growth Machine**

---

## 3. Current Active Phase

**Control Foundation Closure / Growth Machine Closure**

Current status:

- Growth Machine = **Closure Candidate** (FH-1C passed)
- CLOSED pending observation of `driver_history_weekly` full weekly cycle (expected after Monday 2026-06-15)
- Do NOT open higher engines

---

## 4. In Scope Now

- Driver Explorer validation
- Program assignment audit
- Program explainability audit
- Program contract audit
- UI checkpoints (Lima Growth V2)
- Data consistency between: Explorer, Programs, Segments, Movement, RNA, Effectiveness
- Freshness only when it blocks active UI or certified serving facts
- Closure certification
- Documentation of backlog
- Scope governance
- Growth Machine weekly cycle observation (FH-1C pending)

---

## 5. Out of Scope Now

- Forecast Engine (blocked)
- Suggestion Engine (blocked)
- Decision Engine (blocked)
- Action Engine (blocked)
- AI Copilot (blocked)
- Learning Engine (blocked)
- Program Registry V3 implementation
- Lifecycle State Machine implementation
- Temporal Program Assignment Engine implementation
- Commission Engine implementation
- Full Health redesign
- SLA redesign unless it blocks active UI or certified serving facts
- Scheduler redesign
- New dashboards
- New automations
- New campaigns
- New program rules
- New scoring engines
- Campaign Execution Engine
- Agent Workstation

---

## 6. Deferred / Backlog

- Program Registry V3
- Lifecycle-driven State Machine
- Temporal Program Assignment Engine
- Weekly Cohort Measurement
- Commission Measurement Layer
- Health Contract V2
- Movement Scoring
- RNA Scoring Hardening
- Top Performer Program
- High/Low Value Recovery Model
- Program Migration Rules
- Program Optimization
- Control Loop V2
- Queue V2
- Execution Layer

---

## 7. Scope Escalation Test

Before ANY implementation, answer:

| # | Question |
|---|----------|
| 1 | Does this block an active UI workflow? |
| 2 | Does this block a certified active table? |
| 3 | Does this block Driver Explorer / Programs / Segments / Movement / RNA / Effectiveness? |
| 4 | Does this require changing writers, schedulers, program rules, segmentation, or eligibility? |
| 5 | Is this a future engine? |
| 6 | Can this be documented instead of implemented? |
| 7 | Is this a real operator blocker or only an architectural improvement? |
| 8 | Is the rollback clear? |

**Rule:** If it does not block active operation → **DO NOT IMPLEMENT.** Only document, backlog, continue current scope.

---

## 8. Implementation Gate

Implementation is allowed ONLY if:

- Issue blocks active UI
- Issue causes 500 / timeout / wrong visible data
- Issue affects a certified serving fact
- Issue affects freshness required by active UI
- Issue affects Driver Explorer / Programs / Segments / Movement / RNA / Effectiveness
- Rollback is clear
- UI checkpoint is defined
- No higher engine is opened

Otherwise: **NO IMPLEMENTATION.**

---

## 9. Audit vs Design vs Implementation Rule

| Mode | Rule |
|------|------|
| **AUDIT** | Permitted if it does NOT modify rules, writers, schedulers, UI, or DB. |
| **DESIGN** | Permitted only as documentation/backlog. |
| **IMPLEMENTATION** | Permitted only if it passes the Implementation Gate (Section 8). |

---

## 10. UI Checkpoint Rule

Every phase that touches UI, endpoint, or serving MUST include:

- Exact route
- Exact tab
- Exact filters
- Expected visible result
- PASS / FAIL criteria
- Operator validation
- Screenshot or evidence requirement if applicable

No phase is complete without UI checkpoint if it touches UI, endpoint, or serving.

---

## 11. Backlog Rule

If a finding falls outside active scope:

1. Document it
2. Classify it as Deferred / Backlog
3. Do NOT implement it
4. Continue the primary objective

---

## 12. Prompt Rule

Every future implementation prompt MUST include:

1. PRE-CHECK OBLIGATORIO (read mandatory docs)
2. ACTIVE_SCOPE_CONTRACT check
3. Affected motor
4. Affected phase
5. Affected tables
6. Affected writer
7. Freshness impact
8. Risks
9. Rollback
10. Scope Escalation Test (all 8 questions)
11. UI checkpoint if applicable

---

## 13. GO / NO-GO Rule

**GO requires:**

- Scope compliance
- No out-of-scope implementation
- Clear evidence
- Rollback defined
- UI checkpoint if applicable
- Documentation updated if canonical contract changed

**NO-GO if:**

- Implementation drifted outside active scope
- New engine opened
- Program rules changed without approval
- Writers/schedulers changed without explicit gate
- UI touched without checkpoint
- Freshness/health redesigned without active blocker

---

## 14. Update Policy

Update this contract when:

- Active phase changes
- A domain moves from Closure Candidate to CLOSED
- A deferred item becomes active
- A new blocker changes priority
- TRUTH_MAP_V2 changes active state

Do NOT update to justify an already-completed implementation.

---

## 15. Production Cutover Exception — Lima Growth Machine

**Effective:** 2026-06-13
**Reference:** `docs/lima_growth/LG_PROD_SCOPE_1A_PRODUCTION_CUTOVER_SCOPE_OVERRIDE.md`

As of 2026-06-13, Lima Growth Machine has an **operator-approved production cutover exception** for Exclusive Program Assignment V1.

### What is authorized

- Exclusive program assignment (1 driver = 1 program)
- Deterministic assignment resolution
- Explorer/Programs/Opportunity synchronization with new assignment
- UI validation of exclusive lists
- Dry-run before production

### What remains blocked

- Program Registry V3 (complete)
- Lifecycle State Machine (complete)
- Diagnostic Engine (2A.3)
- Forecast, Suggestion, Decision, Action, AI Copilot, Learning Engines
- Health Contract V2 redesign
- SLA redesign
- New dashboards, campaigns, automations, scoring engines

### Note

This exception does NOT declare Growth Machine CLOSED. CLOSED still requires weekly cycle evidence (`driver_history_weekly` week 06-08). All other ACTIVE_SCOPE_CONTRACT rules (Sections 7-14) remain in effect.

---

## 16. Lima Growth North Star

**Reference:** `docs/lima_growth/LG_NORTH_STAR_EXCLUSIVE_LISTS_CONTRACT.md`

The active north star for Lima Growth Machine is the creation of **daily refreshed mutually exclusive operational driver lists**, exportable to Control Loop and measurable by action impact.

Dashboards, health banners, explanations, and visualizations are **secondary** unless they directly support: list generation, Control Loop export, action tracking, or impact measurement.

### North Star Test

All future Growth Machine prompts must answer:

1. Does this improve exclusive dynamic lists?
2. Does this improve daily refresh correctness?
3. Does this improve Control Loop export?
4. Does this improve action tracking?
5. Does this improve daily/weekly impact measurement?
6. Does this improve assignment explainability?
7. Does this improve movement traceability between exclusive lists?

**If NO to all → document/backlog. Do NOT implement.**

**Rule:** If a Growth Machine task changes assignment/list logic but does not preserve reason/evidence/transition traceability, it cannot be certified.

---

*This contract is mandatory reading before any implementation planning in YEGO Control Tower. Referenced by TRUTH_MAP_V2.md. Violations are NO-GO.*
