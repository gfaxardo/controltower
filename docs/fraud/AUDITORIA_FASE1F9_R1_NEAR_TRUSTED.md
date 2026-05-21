# AUDITORIA FASE 1F-9 — R1: NEW_OR_UNPROVEN NEAR TRUSTED

**Count:** 1,762 drivers (8.6% of total)
**Status:** review_required (R1)

---

## 1. PROFILE

All R1 drivers are new_or_unproven with >=30 completed trips. This is the group closest to becoming "trusted" (requires 50 trips).

---

## 2. BREAKDOWN

| Trip Bucket | Profile | Cases | Count |
|------------|---------|-------|-------|
| 30-39 | no_profile | no_cases | 591 |
| 30-39 | normal | no_cases | 420 |
| 40-49 | no_profile | no_cases | 418 |
| 40-49 | normal | no_cases | 333 |

---

## 3. ANALYSIS

| Metric | Value |
|--------|-------|
| 40-49 trips (closest to trusted) | 751 (42.6%) |
| 30-39 trips | 1,011 (57.4%) |
| With normal profile | 753 (42.7%) |
| Without profile (no D-30 activity) | 1,009 (57.3%) |
| With open cases | 0 |
| With high/critical cases | 0 |

---

## 4. BUCKETS PROPOSED

### Near Eligible (v2)
Conditions: new_or_unproven + 40-49 trips + normal/watchlist profile + no cases
- Count in this dataset: 0 (all are new_or_unproven, the N2 rule fires before eligible)
- Note: R1 catches them first (>=30), so near_eligible N2 never fires for these drivers
- In v2, 40-49 trips + normal + no cases would go to review_required (R1), not near_eligible

### Review Required (v1/v2)
Conditions: new_or_unproven + >=30 trips
- All 1,762 drivers are review_required
- This is correct — they need more history before eligibility

---

## 5. RECOMMENDATION

1. Keep R1 drivers as review_required.
2. No automatic eligibility upgrade based on trip count alone.
3. Monitor 40-49 trip drivers — they will soon hit 50 and become trusted.
4. Once trusted + normal profile + no cases, they auto-classify as eligible in the next snapshot run.
5. The near_eligible category (N2) exists in v2 for future use if evaluation order changes to put near_eligible before review_required.
