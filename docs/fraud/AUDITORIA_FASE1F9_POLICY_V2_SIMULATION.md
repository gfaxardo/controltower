# AUDITORIA FASE 1F-9 — POLICY V2 SIMULATION

**Date:** 2026-05-21
**Policy v1:** autocobro_v1_preview
**Policy v2:** autocobro_v2_preview

---

## 1. V1 vs V2 DISTRIBUTION

| Category | V1 Count | V1 % | V2 Count | V2 % | Delta |
|----------|----------|------|----------|------|-------|
| eligible | 13,190 | 64.3% | 5,606 | 27.3% | -7,584 |
| near_eligible | N/A | - | 0 | 0.0% | NEW |
| review_required | 4,443 | 21.7% | 1,763 | 8.6% | -2,680 |
| stale_profile | N/A | - | 2,680 | 13.1% | NEW |
| profile_gap | N/A | - | 0 | 0.0% | NEW |
| restricted | 34 | 0.2% | 38 | 0.2% | +4 |
| unknown | 2,838 | 13.8% | 2,838 | 13.8% | 0 |
| unclassified | N/A | - | 7,580 | 37.0% | NEW |
| **TOTAL** | **20,505** | **100%** | **20,505** | **100%** | - |

---

## 2. DELTA ANALYSIS

### -7,584 eligible → unclassified
Drivers that v1 classified as "eligible" by default (bug: default status was "eligible").
All are new_or_unproven with 3-29 trips.
- 5,433 have no behavioral profile
- 2,149 have normal profile  
- 2 have watchlist profile

These are NOT eligible — they lack either trusted tier or sufficient trip history.

### -2,680 review_required → stale_profile
R5 drivers moved to their own category.
All are trusted 50+ trips but absent from driver_risk_snapshot (no D-30 activity).
This is a better classification: they're not "review required" (ambiguous), they're "stale" (need recent activity).

### 0 near_eligible
No trusted drivers exist with 40-49 trips in this dataset.
The N1/N2 rules are correct but not triggered by current data.

### 0 profile_gap
All drivers in driver_risk_snapshot have behavioral profiles (100% coverage within risk snapshot).
No processing gaps detected.

### +4 restricted
Additional drivers caught by refined rules (X3: critical_case_count).
All restricted drivers continue to have legitimate open high cases.

---

## 3. V2 TOP REASONS

| Reason | Count | % |
|--------|-------|---|
| unclassified | 7,580 | 37.0% |
| E1, E2, E3, E4, E5, E6, E7, E8, E9, E10 (eligible) | 5,606 | 27.3% |
| U3 (< 3 trips) | 2,838 | 13.8% |
| S1 (stale profile) | 2,680 | 13.1% |
| R1 (new_or_unproven >=30) | 1,762 | 8.6% |

---

## 4. V2 CHANGES FROM V1

| Change | Description |
|--------|-------------|
| Default status | Changed from "eligible" to "unclassified" (critical bug fix) |
| stale_profile | New category for trusted 50+ without D-30 activity |
| profile_gap | New category for processing gaps (empty in current data) |
| near_eligible | New category for drivers close to trusted threshold |
| E5 | Added critical_case_count = 0 check |
| E10 | Added recommended_action not in restricted list check |
| X3 | Added critical_case_count > 0 check |
| Evaluation order | unknown → restricted → stale_profile → profile_gap → review_required → near_eligible → eligible |

---

## 5. VEREDICT

**V2 is more accurate and operationally safe than V1.**

- 7,584 false positive eligible drivers removed
- 2,680 stale profiles properly categorized
- All 34 restricted remain restricted (no relaxation)
- 100% of eligible drivers in V2 meet all 10 eligibility rules
- Unclassified drivers (37%) are correctly identified as needing more data
