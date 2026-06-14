# LG-GOV-SCOPE-1A — ACTIVE SCOPE CONTRACT CERTIFICATION

**Date:** 2026-06-13
**Commit base:** d6099657449c7358c4a415fed020c3a9fa1402ed
**Motor:** Governance / Control Foundation guardrail
**Phase:** Growth Machine Closure / Scope Governance
**Status:** CERTIFIED

---

## 1. Objective

Establish and certify a definitive Active Scope Contract to prevent:

- Scope creep during Growth Machine Closure
- Premature activation of blocked engines
- Unauthorized implementation of backlog items
- Mixing audit, design, and implementation without gates
- Proactive changes not requested by the operator

## 2. Documents Read

- `ai_operating_system.md`
- `ai_current_phase.md`
- `docs/architecture/TRUTH_MAP_V2.md`
- `docs/architecture/KNOWN_CONSTRAINTS.md`
- `docs/architecture/GROWTH_MACHINE_CANONICAL.md`
- `docs/architecture/FRESHNESS_CERTIFICATION.md`

## 3. Files Created / Updated

| File | Action | Lines |
|------|--------|-------|
| `docs/architecture/ACTIVE_SCOPE_CONTRACT.md` | Created | ~200 |
| `docs/architecture/TRUTH_MAP_V2.md` | Updated | +4 |
| `docs/lima_growth/LG_GOV_SCOPE_1A_ACTIVE_SCOPE_CONTRACT_CERTIFICATION.md` | Created | This file |

## 4. Scope Problem Detected

During Growth Machine Closure auditing and FH-1 remediation, the following patterns were observed that required governance:

- Audit findings were documented alongside design proposals, creating ambiguity about what should be implemented
- Backlog items (Program Registry V3, Lifecycle State Machine, etc.) were referenced without clear deferral status
- No explicit Implementation Gate existed — findings could become implementations without operator approval
- No Prompt Rule existed — future AI sessions lacked a standard pre-check

The Active Scope Contract addresses all of these gaps.

## 5. Rules Added

| Rule | Section | Purpose |
|------|---------|---------|
| In Scope Now | 4 | Defines what is currently active and implementable |
| Out of Scope Now | 5 | Explicitly blocks premature engines and features |
| Deferred / Backlog | 6 | Documents findings for future phases without implementing |
| Scope Escalation Test | 7 | 8-question gate before any implementation |
| Implementation Gate | 8 | Conditions that must be met to allow implementation |
| Audit vs Design vs Implementation | 9 | Separates three modes of work |
| UI Checkpoint Rule | 10 | Required for any phase touching UI, endpoint, or serving |
| Backlog Rule | 11 | Forces documentation instead of implementation for out-of-scope findings |
| Prompt Rule | 12 | Standard pre-check for all future prompts |
| GO / NO-GO Rule | 13 | Certification criteria |
| Update Policy | 14 | When the contract should be updated |

## 6. In Scope Now

- Driver Explorer validation
- Program assignment/explanability/contract audits
- UI checkpoints (Lima Growth V2)
- Data consistency across Explorer, Programs, Segments, Movement, RNA, Effectiveness
- Freshness only when it blocks active UI or certified serving facts
- Closure certification
- Scope governance

## 7. Out of Scope Now

Forecast, Suggestion, Decision, Action, AI Copilot, Learning Engines. Program Registry V3, Lifecycle State Machine, Temporal Program Assignment Engine, Commission Engine. Full Health/SLA/Scheduler redesigns. New dashboards, campaigns, program rules, scoring engines. Campaign Execution Engine, Agent Workstation.

## 8. Deferred / Backlog

15 items deferred including Program Registry V3, Lifecycle State Machine, Commission Measurement, Health Contract V2, Movement Scoring, RNA Scoring Hardening, Control Loop V2, Queue V2, and Execution Layer.

## 9. How Future Prompts Must Change

Every future implementation prompt must include:

1. PRE-CHECK OBLIGATORIO
2. ACTIVE_SCOPE_CONTRACT read
3. Answers to all 10 checklist questions (motor, phase, contract, tables, writer, freshness, endpoint, legacy, risk, rollback)
4. Scope Escalation Test (8 questions)
5. UI checkpoint definition if applicable

## 10. Validation

| Check | Result |
|-------|--------|
| No backend changes | PASS |
| No frontend changes | PASS |
| No DB changes | PASS |
| No migrations | PASS |
| No scheduler changes | PASS |
| No Program Engine changes | PASS |
| No Growth Machine functional changes | PASS |
| Only docs created/updated | PASS |
| TRUTH_MAP_V2 references contract | PASS |

## 11. Verdict

**LG_GOV_SCOPE_1A_CERTIFIED**

The Active Scope Contract is in effect as of 2026-06-13. All future implementation prompts for YEGO Control Tower must pass the Scope Escalation Test and Implementation Gate defined in `docs/architecture/ACTIVE_SCOPE_CONTRACT.md`.
