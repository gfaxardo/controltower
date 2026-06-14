# LG-SEGMENTATION-REVIEW-1K — Operator Review of DRAFT_002

**Date:** 2026-06-14
**Phase:** LG-SEGMENTATION-REVIEW-1K (Segmentation Review)
**Mode:** REVIEW
**Status:** CREATE_DRAFT_003

---

## 1. Executive Decision

### LG_SEGMENTATION_REVIEW_1K_CREATE_DRAFT_003

DRAFT_002 has correct fine-grained segmentation (19 codes, 41 rules). But the priority order has a critical flaw: Cemetery and Recovery rules are evaluated BEFORE Protected and Lifecycle rules. This means all drivers with inactivity >= 7 days are caught by Cemetery/Recovery and never reach Protected (75w) or Active Growth rules.

**Recommendation:** Create DRAFT_003 where Protected is evaluated FIRST (before Cemetery/Recovery), so drivers meeting the protection threshold are excluded from worklists regardless of inactivity.

---

## 2. Remote Commit Gate

`e25e847` confirmed on origin/master. PASS.

---

## 3. Source Coverage Review

| Source | Count | Status |
|--------|-------|--------|
| Worklist 2026-06-15 | 18,545 drivers | Current |
| Daily history | 18,727 drivers | Complete |
| Simulation DRAFT_002 | 18,545 assigned | 0 unassigned, 0 duplicates |

---

## 4. Priority Order Review (Current DRAFT_002)

| Priority | Segment Type | Problem |
|----------|-------------|---------|
| 1-2 | Cemetery (>60d inactive) | Catches all long-inactive drivers |
| 3-8 | Recovery (7-60d inactive) | **Catches drivers BEFORE Protected can evaluate** |
| 9-16 | Lifecycle (New, Ramp, Consolidation, Active) | **Never reached** because Recovery catches 7-60d first |
| 17-18 | Protected (75w, New 50) | **Never reached** — 321 drivers with weekly>=75 already in Cemetery/Recovery |
| 19 | No Data | Never reached |

---

## 5. Protected 75W Audit

**321 drivers** with weekly >= 75. All assigned to Cemetery (217) or Recovery (104) — none to Protected.

| Current Segment | Drivers | avg_wk | avg_inact | Issue |
|----------------|---------|--------|-----------|-------|
| CEMETERY_180_PLUS | 162 | 108.9 | 296.2 | Cemetery catches >180d inactive first |
| RECOVERY_HIGH_7_14 | 103 | 90.3 | 13.6 | Recovery catches 7-14d inactive before Protected |
| CEMETERY_61_180 | 55 | 102.5 | 125.7 | Same as above |

**Root cause:** Protected (priority 17) is evaluated AFTER Cemetery (1-2) and Recovery (3-8). Drivers with inactivity >7d are caught by Cemetery/Recovery before reaching Protected.

---

## 6. Lifecycle Empty Audit

| Condition | Drivers |
|-----------|---------|
| Inactivity < 7d | 2,276 |
| Anchor age >90d | 15,811 |

2,276 drivers should match ACTIVE rules (age>90 AND wk 1-99 AND inactive<7). But all 18,545 are in Cemetery or Recovery. The lifecycle features ARE available; the priority order prevents them from matching.

---

## 7. Recovery High 7-14 Audit

2,718 drivers. Avg inactivity 10.9d, avg weekly 12.4. These are genuinely inactive 7-14 days with high value. Correctly classified. The issue is NOT with Recovery classification but with Protected having lower priority.

---

## 8. Operator Decision Matrix

| # | Decision | Option A | Option B | Recommendation |
|---|----------|---------|----------|---------------|
| 1 | Protected placement | Before Recovery (priority 1) | After Recovery (current) | **Before Recovery** — drives meeting 75w should be Protected regardless of inactivity |
| 2 | Cemetery placement | Before Protected | After Protected | **After Protected** — a driver with 100w and 200d inactive is Cemetery, not Protected. But a driver with 100w and 10d inactive is Protected. |
| 3 | Recovery placement | Before Lifecycle (current) | After Lifecycle | **After Lifecycle** for drivers with <7d inactive. Keep before for 7-60d. |
| 4 | Protected threshold | 75w | 50w | Review with operator |
| 5 | Create DRAFT_003 | Yes | No | **Yes** — fix priority order |

---

## 9. Recommended Priority for DRAFT_003

```
1. NO_DATA (catch missing data first)
2. PROTECTED_75W (weekly >= 75)
3. PROTECTED_NEW_50 (new drivers who achieved 50)
4. NEW_0_14_TO_50 (new drivers, active, below 50)
5. REACTIVATED_TO_50
6. RECOVERY_HIGH_7_14
7. RECOVERY_HIGH_15_30
8. RECOVERY_HIGH_31_60
9. RECOVERY_LOW_7_14
10. RECOVERY_LOW_15_30
11. RECOVERY_LOW_31_60
12. RAMP_15_45
13. CONSOLIDATION_46_90
14. ACTIVE_LOW_1_10W
15. ACTIVE_MID_11_30W
16. ACTIVE_CORE_31_50W
17. ACTIVE_NEAR_51_99W
18. CEMETERY_61_180
19. CEMETERY_180_PLUS
```

---

## 10. Verdict

### LG_SEGMENTATION_REVIEW_1K_CREATE_DRAFT_003

DRAFT_002 segmentation is correct but priority order prevents Protected and Lifecycle from matching. DRAFT_003 must: (1) evaluate Protected before Recovery, (2) evaluate Lifecycle before Recovery for active drivers (<7d inactive), (3) keep Cemetery last.

**Activation remains blocked until DRAFT_003 is simulated and reviewed.**

---

*Review complete. Priority order flaw identified. Ready for DRAFT_003.*
