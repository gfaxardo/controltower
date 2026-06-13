# LG-PROD-SCOPE-1A — Production Cutover Scope Override

**Date:** 2026-06-13
**Phase:** Production Cutover Scope Override
**Mode:** GOVERNANCE DOCUMENT — AUTHORIZATION ONLY, NO IMPLEMENTATION YET
**Predecessor:** `LG_CLOSURE_1A_GROWTH_MACHINE_CLOSURE_CANDIDATE_REPORT.md` (`83b88fa`)

---

## 1. Executive Decision

**Growth Machine remains Closure Candidate Operable, but enters Production Cutover Mode for Exclusive Program Assignment V1.**

Weekly cycle evidence (`driver_history_weekly` week 06-08) remains pending but is **no longer blocking** cutover implementation work. The operator requires Monday production readiness.

**This override does NOT declare Growth Machine CLOSED. CLOSED still requires weekly cycle evidence.**

## 2. Operator Requirement

The operator requires that by Monday:
1. Program lists are **exclusive** (1 driver = 1 assigned program).
2. New program criteria are applied.
3. Explorer, Programs, and Opportunity are synchronized.
4. UI is operable with correct counts.
5. Rollback is clear and immediate.

## 3. Scope Override — What Is Authorized

### Permitted (Exclusive Program Assignment Cutover V1)

- Exclusive program assignment contract definition
- Deterministic assignment resolution (1 driver = 1 program)
- Latest-date Explorer synchronization with new assignment
- Programs/Explorer reconciliation
- Opportunity list regeneration using new exclusive assignment
- UI validation of resulting lists
- Dry-run before production
- Feature flag or endpoint fallback if possible

### Blocked (No Authorization Granted)

- Program Registry V3 (complete)
- Lifecycle State Machine (complete)
- Temporal Program Assignment Engine
- Commission Engine
- Campaign Execution Engine
- Agent Workstation
- Diagnostic Engine
- Forecast Engine
- Suggestion Engine
- Decision Engine
- Action Engine
- AI Copilot
- Learning Engine
- Health Contract V2 redesign
- SLA redesign
- New dashboards
- New automations
- New scoring engines

## 4. Production Cutover Principles

| Principle | Rule |
|-----------|------|
| **Exclusivity** | 1 driver = 1 assigned program in production. |
| **Eligibility** | Can remain multi-program. Eligibility is informational. |
| **Assignment** | Must be exclusive and deterministic. |
| **Explorer** | Must show current assigned program (not stale). |
| **Programs** | May show eligibility, but must clearly distinguish from assignment. |
| **Opportunity** | Must consume exclusive assigned program. |
| **Writers** | No legacy writers. Canonical writers only. |
| **Data** | No DELETE/TRUNCATE destructive. No backfill without dry-run. |
| **Rollback** | Mandatory — old assignment logic must be restorable. |

## 5. Cutover Gates

| Gate | Name | Description |
|------|------|-------------|
| **Gate 1** | Contract Freeze | Program criteria and assignment contract locked. No further changes until Monday validation. |
| **Gate 2** | Dry-Run Counts | Simulate new assignment on latest data. Compare with current. Publish counts. |
| **Gate 3** | Implementation | Apply exclusive assignment logic. Update Explorer sync. Regenerate opportunity lists. |
| **Gate 4** | Backend/API Smoke | All endpoints return correct counts. No duplication regression. |
| **Gate 5** | UI Validation | Explorer, Programs, Opportunity tabs show correct exclusive assignment counts. |
| **Gate 6** | Production GO/NO-GO | Operator validates. GO = live Monday. NO-GO = rollback. |

## 6. Backlog Preserved

The following remain **deferred and blocked.** This cutover does NOT authorize them:

- Monday weekly cycle evidence (`driver_history_weekly` week 06-08)
- Program Registry V3
- Lifecycle State Machine
- Temporal Assignment Engine
- Health Contract V2
- Control Loop V2
- Queue V2
- Execution Layer
- Diagnostic Engine 2A.3
- Commission Measurement Layer
- Movement Scoring
- RNA Scoring Hardening
- Top Performer Program
- Program Migration Rules
- Program label/copy layer (tooltips)
- Eligibility column in Explorer
- Stale assignment badge

## 7. Rollback Policy

| Mechanism | Detail |
|-----------|--------|
| Git | Revert cutover commits. |
| Data | No DELETE/TRUNCATE. Historical rows preserved. |
| Assignment | Old logic restorable — keep prior contract/code reference. |
| Snapshot | Snapshot Explorer fact and eligibility before any write if later required. |
| Feature Flag | If implemented, disable flag to restore previous behavior. |

## 8. Prompt Rule for Cutover Phase

Every subsequent implementation prompt within this cutover must include:

1. PRE-CHECK OBLIGATORIO
2. ACTIVE_SCOPE_CONTRACT + **LG-PROD-SCOPE-1A**
3. Affected motor
4. Affected phase
5. Affected tables
6. Affected writer
7. Freshness impact
8. Risks
9. Rollback
10. Scope Escalation Test
11. UI checkpoint if applicable
12. Current gate (1-6)

## 9. Verdict

### **LG_PROD_SCOPE_1A_APPROVED**

Production Cutover Mode is authorized for Exclusive Program Assignment V1. All other engines, Program Registry V3, State Machine, and backlog items remain blocked. Growth Machine remains NOT CLOSED — weekly cycle evidence pending.

---

*Scope override in effect. Implementation not yet started. Proceed to Gate 1: Contract Freeze.*
