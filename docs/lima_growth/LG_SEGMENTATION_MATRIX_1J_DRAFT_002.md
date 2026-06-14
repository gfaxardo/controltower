# LG-SEGMENTATION-MATRIX-1J — Universe Segmentation Matrix + DRAFT_002

**Date:** 2026-06-14
**Phase:** LG-SEGMENTATION-MATRIX-1J (Segmentation + DRAFT_002)
**Mode:** DESIGN + SIMULATION
**Status:** READY_FOR_OPERATOR_REVIEW

---

## 1. Executive Decision

### LG_SEGMENTATION_MATRIX_1J_READY_FOR_OPERATOR_REVIEW

DRAFT_002 created with 19 fine segments. 41 rules. Simulated against 2026-06-15 worklist. Cemetery split by inactivity bucket (61-180d, >180d). Recovery split by inactivity bucket (7-14d, 15-30d, 31-60d) and value tier. Active Growth split by weekly trips band (1-10, 11-30, 31-50, 51-99). Protected at 75w threshold. No lifecycle segments populated (current data has no drivers with <7d inactive).

---

## 2. Segmentation Principles

1. Mutually exclusive: one driver = one segment via priority order
2. Inactivity-first: Cemetery > Recovery > Lifecycle > Protected > No Data
3. Fine-grained: split by inactivity bucket where operationally meaningful
4. Value-aware: Recovery split by value_tier (HIGH vs not HIGH)
5. Band-aware: Active Growth split by weekly trips range
6. Configurable: all thresholds in rules table, not hardcoded

---

## 3. Proposed Fine Segments (19)

| Priority | Code | Label | Rule Summary |
|----------|------|-------|-------------|
| 1 | CEMETERY_61_180 | Cemetery 61-180d | inactivity 61-180 |
| 2 | CEMETERY_180_PLUS | Cemetery >180d | inactivity >180 |
| 3 | RECOVERY_HIGH_7_14 | Recovery High 7-14d | inactive 7-14, value HIGH |
| 4 | RECOVERY_HIGH_15_30 | Recovery High 15-30d | inactive 15-30, value HIGH |
| 5 | RECOVERY_HIGH_31_60 | Recovery High 31-60d | inactive 31-60, value HIGH |
| 6 | RECOVERY_LOW_7_14 | Recovery Low 7-14d | inactive 7-14, value LOW/DEFAULT |
| 7 | RECOVERY_LOW_15_30 | Recovery Low 15-30d | inactive 15-30, value LOW/DEFAULT |
| 8 | RECOVERY_LOW_31_60 | Recovery Low 31-60d | inactive 31-60, value LOW/DEFAULT |
| 9 | NEW_0_14_TO_50 | New 0-14d | age 0-14, trips<50, active<7d |
| 10 | REACTIVATED_TO_50 | Reactivated | react anchor, age≤14, trips<50 |
| 11 | RAMP_15_45_TO_100W | Ramp Up 15-45d | age 15-45, wk<100, active<7d |
| 12 | CONSOLIDATION_46_90 | Consolidation 46-90d | age 46-90, wk<100, active<7d |
| 13 | ACTIVE_LOW_1_10W | Active Low 1-10/wk | age>90, wk 1-10, active<7d |
| 14 | ACTIVE_MID_11_30W | Active Mid 11-30/wk | age>90, wk 11-30, active<7d |
| 15 | ACTIVE_CORE_31_50W | Active Core 31-50/wk | age>90, wk 31-50, active<7d |
| 16 | ACTIVE_NEAR_51_99W | Active Near 51-99/wk | age>90, wk 51-99, active<7d |
| 17 | PROTECTED_75W | Protected >=75/wk | wk>=75 |
| 18 | PROTECTED_NEW_50 | Protected New >=50 | age≤14, trips>=50 |
| 19 | NO_DATA | No Data | fallback |

---

## 4. Protected Rule Decision

| Rule | Drivers | Decision |
|------|---------|----------|
| weekly >=100 | 33 | Too strict |
| **weekly >=75** | **90** | **Selected for DRAFT_002** |
| weekly >=50 | 546 | Too permissive |

---

## 5. Simulation Result (DRAFT_002 vs 2026-06-15)

| Segment | Drivers |
|---------|---------|
| CEMETERY_180_PLUS | 8,021 |
| CEMETERY_61_180 | 4,382 |
| RECOVERY_HIGH_7_14 | 2,718 |
| RECOVERY_HIGH_31_60 | 1,507 |
| RECOVERY_LOW_7_14 | 1,029 |
| RECOVERY_HIGH_15_30 | 888 |
| **TOTAL** | **18,545** |

Lifecycle segments (NEW, RAMP, CONSOLIDATION, ACTIVE, PROTECTED) = 0. Current worklist data shows all drivers have >=7d inactivity. No truly "active" drivers in today's data.

---

## 6. DRAFT_001 vs DRAFT_002

| Metric | DRAFT_001 | DRAFT_002 |
|--------|-----------|-----------|
| Segments | 10 | 19 |
| Cemetery split | No | Yes (61-180, >180) |
| Recovery split | No (by value only) | Yes (by inactivity bucket + value) |
| Protected threshold | 100w (0 drivers) | 75w (90 eligible) |
| Active Growth split | No | Yes (4 bands) |

---

## 7. Exclusivity Validation

18,545 drivers = 18,545 assignments. 0 unassigned. 0 duplicates. All drivers assigned exactly once.

---

## 8. No Production Impact

Worklist unchanged (55,635 rows). Control Loop unchanged (batch 20260615: 6,114 READY). No ACTIVE config version.

---

## 9. Operator Review Matrix

| Segment | Definition | In simulation? | Requires review |
|---------|-----------|---------------|-----------------|
| Cemetery 61-180d | inactivity 61-180d | 4,382 | Review threshold |
| Cemetery >180d | inactivity >180d | 8,021 | Review threshold |
| Recovery High 7-14d | inactive 7-14d, high value | 2,718 | **P0: 2,718 drivers for agents** |
| Recovery High 15-30d | inactive 15-30d, high value | 888 | **P1: channel decision** |
| Recovery High 31-60d | inactive 31-60d, high value | 1,507 | **P1: channel decision** |
| Recovery Low segments | inactive 7-60d, low value | 1,029 | Mass channel candidate |

---

## 10. Verdict

### LG_SEGMENTATION_MATRIX_1J_READY_FOR_OPERATOR_REVIEW

DRAFT_002 with fine segmentation ready for operator review. 19 segments, 41 rules. Simulation produces valid exclusive classification. Activation remains blocked pending operator approval of segment definitions and Recovery bucket thresholds.

---

*Segmentation matrix complete. 19 fine segments. Ready for operator review before activation gate.*
