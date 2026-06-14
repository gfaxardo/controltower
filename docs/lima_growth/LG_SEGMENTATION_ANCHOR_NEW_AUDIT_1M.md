# LG-SEGMENTATION-ANCHOR-NEW-AUDIT-1M — NEW Dominance + Anchor Semantics Audit

**Date:** 2026-06-14
**Phase:** LG-SEGMENTATION-ANCHOR-NEW-AUDIT-1M (Semantic Audit)
**Mode:** AUDIT
**Status:** FIX_SIM_SERVICE_REQUIRED

---

## 1. Executive Decision

### LG_SEGMENTATION_ANCHOR_NEW_AUDIT_1M_FIX_SIM_SERVICE_REQUIRED

DRAFT_003 correctly fixes priority order (Protected now populates). But NEW dominance (16,793) is caused by anchor feature derivation using `driver_history_daily.MIN(date)` as proxy, which creates artificially recent dates for drivers whose history was rebuilt from June 5-13. 12,186 of these were correctly classified as Cemetery in DRAFT_002.

**The simulation engine needs `anchor_type` feature derivation before any DRAFT can be activation-ready.**

---

## 2. Why DRAFT_003 Is Not Approval-Ready

16,793 drivers in NEW with:
- avg operational age: 242.9 days (NOT new)
- 12,186 have inactivity > 60 days (should be Cemetery)
- 3,629 have inactivity 7-60 days (should be Recovery)
- avg anchor_age_days from history_daily.MIN: 241.9 days

DRAFT_002 correctly classified them as Cemetery (12,186) and Recovery (4,609).

---

## 3. NEW Rule Audit

| Rule | Field | Operator | Value | Assessment |
|------|-------|----------|-------|------------|
| age | anchor_age_days | BETWEEN | 0|14 | **Matches because MIN(date) is artificially recent** |
| trips | trips_since_anchor | < | 50 | Passes for most |
| active | inactivity_days | < | 7 | Passes for 978 / fails for 15,815 |

**Missing:** `anchor_type = NEW` rule. Without this, any driver with a recent MIN(date) matches.

---

## 4. NEW Distribution Audit

| Metric | Count | % |
|--------|-------|---|
| Inactivity >60d | 12,186 | 72.6% |
| Inactivity 7-60d | 3,629 | 21.6% |
| Inactivity <7d | 978 | 5.8% |
| Weekly trips = 0 | 0 | 0% |
| Avg operational age | 242.9d | — |
| DRAFT_002 was Cemetery | 12,186 | 72.6% |
| DRAFT_002 was Recovery | 4,609 | 27.4% |

**72.6% of NEW drivers were Cemetery in DRAFT_002.** These are NOT new.

---

## 5. Anchor Feature Derivation Audit

| Feature | Source | Issue |
|---------|--------|-------|
| anchor_age_days | `driver_history_daily.MIN(date)` | For rebuild drivers, MIN is artificially recent (June 5-13) |
| anchor_type | **NOT derived** | Missing. Can't distinguish NEW from EXISTING |
| has_reactivation_anchor | Hardcoded `"false"` | Always false, can't detect reactivation |
| trips_since_anchor | `wl.activation_window_trips` | Represents 30d trips, not trips since first anchor |

**Root cause:** `anchor_age_days` uses `MIN(date)` which is recent for rebuild drivers. No `anchor_type` feature exists to gate NEW rule. Simulation treats all drivers with recent MIN(date) as "new."

---

## 6. Protected New Audit

1,431 in PROTECTED_NEW_50. Same contamination: `trips_since_anchor >= 50` (from 30d window) not from actual activation window. Many likely historical drivers.

---

## 7. Safe NEW Rule (Proposed)

Must require:
1. `anchor_type = NEW` (new feature required)
2. `anchor_age_days BETWEEN 0 AND 14`
3. `trips_since_anchor < 50`
4. `has_reactivation_anchor = false`

Anchor_type derivation:
- If `hire_date` exists AND `hire_date` <= 14 days ago → NEW
- If `first_trip_at` exists AND `first_trip_at` <= 14 days ago AND `hire_date` missing → NEW
- Otherwise → EXISTING or UNKNOWN

---

## 8. Decision

### FIX_SIM_SERVICE_REQUIRED

The simulation service needs `anchor_type` feature derivation. DRAFT_004 should NOT be created until the feature is available. Once fixed:
1. Re-simulate DRAFT_003 with `anchor_type = NEW` rule
2. Verify NEW drops to realistic count (~48 original V1 NEW)
3. Verify Cemetery/Recovery repopulate correctly
4. Then decide if DRAFT_004 is needed for any remaining issues

---

## 9. What Was Not Changed

0 code (audit only). 0 config versions modified. 0 production impact.

---

## 10. Verdict

### LG_SEGMENTATION_ANCHOR_NEW_AUDIT_1M_FIX_SIM_SERVICE_REQUIRED

Simulation engine needs `anchor_type` feature before any DRAFT can be activation-ready. Protected priority fix (DRAFT_003) is correct. NEW dominance is a simulation data issue, not a priority issue.

---

*Audit complete. Fix simulation feature derivation next.*
