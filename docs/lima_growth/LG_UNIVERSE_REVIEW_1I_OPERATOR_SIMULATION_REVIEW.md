# LG-UNIVERSE-REVIEW-1I — Operator Simulation Review

**Date:** 2026-06-14
**Phase:** LG-UNIVERSE-REVIEW-1I (Operator Review)
**Mode:** REVIEW — No activation
**Status:** CREATE_DRAFT_002

---

## 1. Executive Decision

### LG_UNIVERSE_REVIEW_1I_CREATE_DRAFT_002

DRAFT_001 classification is more accurate (prioritizes inactivity over lifecycle), but the Recovery High spike (877→5,113) and Protected=0 require threshold tuning before activation. Recommend creating DRAFT_002 with tuned thresholds.

---

## 2. Simulation Reviewed

| Field | Value |
|-------|-------|
| Simulation ID | `cfe63cd3...` |
| Version | UNIVERSE_V2_DRAFT_001 |
| Source date | 2026-06-15 |
| Total drivers | 18,545 |
| Changed | 6,142 (33.1%) |
| Exportable delta | +28 |
| Risk flags | LARGE_UNIVERSE_SHIFT, PROTECTED_TOO_LOW |

---

## 3. Current vs Simulated Counts

| Universe | Current | Simulated | Delta | Analysis |
|----------|---------|-----------|-------|----------|
| Cemetery | 12,403 | 12,403 | 0 | Unchanged. Correct. |
| Recovery High | 877 | 5,113 | **+4,236** | Correctly catches high-value inactive drivers previously misclassified as Active Growth |
| Recovery Low | 2,989 | 1,029 | -1,960 | Low-value inactive drivers. Many reclassified. |
| Active Growth | 1,652 | 0 | -1,652 | All AG drivers moved to Recovery. Inactivity 7-60d correctly prioritized over lifecycle. |
| Consolidation | 344 | 0 | -344 | Same as AG. |
| Ramp Up | 204 | 0 | -204 | Same as AG. |
| New | 48 | 0 | -48 | Same as AG. |
| Protected | 28 | 0 | -28 | 100/wk threshold too demanding. Only 28 meet it. |
| REACTIVATED | 0 | 0 | 0 | No reactivation anchor data available. |
| No Data | 0 | 0 | 0 | — |

**Key finding:** V2 correctly prioritizes inactivity over lifecycle windows. A driver inactive 7-60 days is in Recovery regardless of age. This is more operationally accurate than V1 which kept them in Active Growth.

---

## 4. Top Moves

| From | To | Drivers | Meaning |
|------|----|---------|---------|
| ACTIVE_GROWTH → RECOVERY_HIGH | 1,652 | Correct: inactive 7-60d, high value |
| RECOVERY_LOW → RECOVERY_HIGH | 1,029 | Value tier reclassification |
| RAMP_UP → RECOVERY_LOW | 204 | Inactive 7-60d, low value |
| CONSOLIDATION → RECOVERY_HIGH | 344 | Inactive 7-60d, high value |
| NEW → RECOVERY_LOW | 48 | Inactive 7-60d, low value |

**Summary:** The moves represent a shift from lifecycle-based classification (V1) to inactivity+value-based classification (V2). This is the intended behavior of V2 rules.

---

## 5. Recovery High Audit (5,113 drivers)

**Sample:** 10 drivers with avg inactivity 25.4d, avg weekly_trips 12.1, mostly HIGH value tier.

**Findings:**
1. Most are genuinely high value (historical best_week_12w >= 50)
2. Yes, they are inactive 7-60 days
3. Agent call is appropriate for high value, but 5,113 is too many for agent team alone
4. 5,113 / 50 = **103 agents needed** — likely exceeds capacity
5. Recommend: **SPLIT** Recovery High into 7-14d (agent) and 15-60d (WhatsApp/call center)
6. Or: **TIGHTEN** high_value threshold from 50 to 75

---

## 6. Protected Audit (0 drivers)

| Weekly Trips | Drivers |
|-------------|---------|
| >=100 | 33 |
| >=75 | 90 |
| >=50 | 546 |
| >=30 | 3,339 |
| >=20 | 6,373 |

**Findings:**
1. Only 33 drivers meet 100/wk — extremely demanding for Lima
2. 546 drivers meet 50/wk — reasonable Protected floor
3. Protected=0 is NOT acceptable for operations
4. Recommend: **LOWER_TO_75W** or **LOWER_TO_50W_AND_ACTIVE**

---

## 7. Active Growth Audit

| Band | Drivers | avg_wk |
|------|---------|--------|
| 1-10 | 795 | 3.3 |
| 11-20 | 270 | 14.8 |
| 21-30 | 155 | 24.7 |
| 31-40 | 150 | 34.4 |
| 41-50 | 96 | 44.4 |
| 51-75 | 149 | 59.3 |
| 76-99 | 37 | 84.4 |

795 drivers in 1-10 band are essentially inactive. Recommend moving 1-10 band to a LOW_ACTIVE or merged with Recovery monitoring.

---

## 8. Workload / Capacity Review

| Universe | Drivers | Channel | Agents (50/d) |
|----------|---------|---------|---------------|
| Recovery High | 5,113 | Agent | **103** ⚠️ |
| Recovery Low | 1,029 | SMS/WhatsApp | — |
| TOTAL | 6,142 | | |

**Warning:** 103 agents needed for Recovery High alone. If capacity is 20 agents, only 1,000 drivers per day. Recommend splitting by inactivity bucket or tightening value threshold.

---

## 9. DRAFT_002 Decision

### CREATE DRAFT_002 with:

| Tuning | Current (DRAFT_001) | Proposed (DRAFT_002) |
|--------|--------------------|-----------------------|
| Recovery High threshold | best_week_12w >=50 AND 7-60d inactive | best_week_12w >= **75** AND **7-14d** inactive |
| Recovery Mid (new) | — | best_week_12w >=50 AND **15-30d** inactive. Channel: Call/WhatsApp |
| Recovery Low | value_tier != HIGH, 7-60d | value_tier != HIGH, 7-60d. Channel: SMS (unchanged) |
| Protected threshold | weekly >=100 | **weekly >=75** (or best_week >=100 AND weekly >=50) |

---

## 10. Operator Decision Pack

| # | Decision | Options | Recommendation |
|---|----------|---------|---------------|
| 1 | Recovery High threshold | KEEP 50 / TIGHTEN to 75 | TIGHTEN to 75 |
| 2 | Recovery High inactivity window | 7-60d / SPLIT 7-14d+15-30d | SPLIT |
| 3 | Protected threshold | 100w / 75w / 50w | 75w |
| 4 | Active Growth low band (1-10) | KEEP / MOVE to LOW_ACTIVE | MOVE |
| 5 | Create DRAFT_002 | YES / NO | YES |
| 6 | Activate after DRAFT_002 | CONDITIONAL | Only if 3 gates pass |

---

## 11. Verdict

### LG_UNIVERSE_REVIEW_1I_CREATE_DRAFT_002

DRAFT_001 correctly prioritizes inactivity over lifecycle. But Recovery High spike and Protected=0 require threshold tuning before activation. DRAFT_002 must address: Recovery High split by inactivity window + tightened value threshold, Protected lowered to 75w, low-band Active Growth moved to monitored status.

**Activation remains blocked.** Next: create DRAFT_002, simulate, and re-review before LG-UNIVERSE-ACTIVATE-1J.

---

*Review complete. 6,142 changed correctly identified. Threshold tuning required.*
