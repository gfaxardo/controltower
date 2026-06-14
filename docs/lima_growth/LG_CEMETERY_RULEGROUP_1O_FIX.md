# LG-CEMETERY-RULEGROUP-1O — Cemetery Rule Grouping Fix

**Date:** 2026-06-14
**Phase:** LG-CEMETERY-RULEGROUP-1O (Cemetery Fix + Governance)
**Mode:** BUGFIX + GOVERNANCE
**Status:** OPERATOR_REVIEW_READY

---

## 1. Executive Decision

### LG_CEMETERY_RULEGROUP_1O_PASS_OPERATOR_REVIEW_READY

Cemetery=0 fixed. Root cause: split rule groups with OR logic. All 41 rules consolidated to single `entry` group. Persistence script created. Re-simulated: Cemetery=12,144, all 19 segments populated. Exportable delta=-111.

---

## 2. Root Cause

Recovery universes had rules in TWO groups: `entry` (inactivity) + `value_high/value_low` (value tier). The rule evaluator uses OR across groups. A driver with inactivity >60 but value_tier=HIGH matched Recovery because the value group passed alone, even though the inactivity group failed.

**Fix:** All rules for each segment must be in the SAME group → AND logic within segment. `UPDATE growth.universe_rule_config SET rule_group='entry' WHERE version_id=%s`.

---

## 3. Persistence Method

Script: `backend/scripts/growth/fix_universe_v2_draft003_rule_groups.py`
- Targets only DRAFT_003
- Idempotent (safe to re-run)
- Does NOT touch ACTIVE/DRAFT_001/DRAFT_002
- Does NOT touch production worklist or Control Loop

---

## 4. Simulation After Fix (DRAFT_003)

| Segment Family | Drivers |
|---------------|---------|
| Cemetery | 12,144 |
| Recovery | 3,018 |
| Active Growth | 1,951 |
| Ramp + Consolidation | 749 |
| Protected | 336 |
| Reactivated | 250 |
| New | 35 |
| NO_DATA | 62 |
| Exportable delta | -111 |

---

## 5. No Production Impact

Worklist unchanged. Control Loop unchanged. No ACTIVE config.

---

## 6. Verdict

### LG_CEMETERY_RULEGROUP_1O_PASS_OPERATOR_REVIEW_READY

Fix persisted. Simulation valid. All 19 segments populated. Ready for operator review before activation gate.

---

*Cemetery fix complete. DRAFT_003 ready for operator approval.*
