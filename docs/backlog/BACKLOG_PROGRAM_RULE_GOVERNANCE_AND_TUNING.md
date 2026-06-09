# BACKLOG — Program Rule Governance & Tuning (Read-Only)

**Date:** 2026-06-07
**Phase:** BACKLOG (PENDING)
**Registry:** LG-INFRA-R1.5

---

## NEED

Today program eligibility rules are embedded in service code (`program_eligibility_service.py`). Operators cannot see what rules put a driver into a program, what parameters are configured, or preview changes before applying them.

---

## OBJECTIVE

Make program rules **visible and auditable** (read-only first) before building a full Program Builder (R3.1).

---

## PHASE 1: READ-ONLY VISIBILITY (This Backlog)

### 1.1 Rule Registry Per Program

| Program | Rules (Current) |
|---------|----------------|
| PROGRAM_CHURN_PREVENTION | Decline evidence, distance_to_target > critical_threshold, retention_state = CHURN_RISK |
| PROGRAM_14_90 | Inactive 14-90 days, last_order_at within range, lifecycle = CHURNED or REACTIVATED |
| PROGRAM_ACTIVE_GROWTH | Active drivers, below target, trips_per_hour < threshold |
| PROGRAM_HIGH_VALUE_RECOVERY | High historical value, recently inactive, hibernate/top driver criteria |

### 1.2 Configurable Parameters

All program eligibility parameters should be externalized to a config table:

```sql
CREATE TABLE growth.yego_lima_program_rule_config (
    rule_id         uuid PRIMARY KEY,
    program_code    text NOT NULL,
    rule_name       text NOT NULL,
    rule_type       text NOT NULL,  -- THRESHOLD, RANGE, FLAG, FORMULA
    parameter_name  text NOT NULL,
    parameter_value text NOT NULL,
    comparison_op   text,           -- >, <, =, BETWEEN, IN
    is_active       boolean DEFAULT true,
    version         integer DEFAULT 1,
    effective_from  date,
    description     text,
    created_at      timestamptz DEFAULT now()
);
```

### 1.3 Visibility Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/yego-lima-growth/programs/rules` | All rules per program |
| GET | `/yego-lima-growth/programs/rules/{program_code}` | Rules for one program |
| GET | `/yego-lima-growth/programs/rules/audit/{driver_id}` | What rules put this driver in their programs |

### 1.4 UI View

- Rule name + parameter + current value + operator
- Version number
- Effective date
- Preview: "This rule would match N drivers today"
- Comparison: before/after parameter change
- Audit: "Driver X is in PROGRAM_CHURN_PREVENTION because: distance_to_target (12) < critical_threshold (50)"

---

## PHASE 2: PROGRAM BUILDER (R3.1 — BLOCKED)

Full Program Builder with:
- Drag-and-drop rule composition
- Multi-rule AND/OR logic
- Universe preview before publish
- Rollback / version history
- A/B testing framework
- Impact simulation

**BLOCKED until Control Foundation achieves real GO.**

---

## DEPENDENCIES

| Dependency | Status |
|-----------|:---:|
| driver_state_snapshot | EXISTS |
| program_eligibility_daily | EXISTS |
| Rule config table | PENDING (this backlog) |
| UI parameter panel | PENDING |
| Rule audit endpoint | PENDING |

---

## ESTIMATION

| Item | Effort |
|------|--------|
| Rule config table + migration | 1 hora |
| Rule extraction from existing code | 2 horas |
| Read-only endpoints | 2 horas |
| UI parameter panel | 2 horas |
| Audit endpoint | 1 hora |
| Testing | 2 horas |
| **Total Phase 1** | **~10 horas** |

---

## RESTRICTIONS

- NO Program Builder (R3.1+) until GO
- Read-only first
- No rule modification via UI yet
- Audit trail for rule visibility
- Preview before any future changes

---

## FIRMA

```
BACKLOG REGISTRY ENTRY
Program Rule Governance & Tuning (Read-Only)
Registered: 2026-06-07
Phase: LG-INFRA-R1.5
Status: BACKLOG — PENDING
Priority: MEDIUM
Blocked by: None (standalone phase)
Next review: Post R1.5 closure
```
