# AUDITORIA FASE 1F-9 — EXCEPTION DISTRIBUTION

**Policy:** autocobro_v1_preview
**Date:** 2026-05-21

---

## 1. REVIEW_REQUIRED (4,443 - 21.7%)

| Reason | Code | Count | % of RR |
|--------|------|-------|---------|
| Trusted 50+ without behavioral profile | R5 | 2,680 | 60.3% |
| New or unproven >=30 trips | R1 | 1,762 | 39.7% |
| Suspicious profile | R2 | 1 | 0.02% |
| Medium confidence cases | R3 | 0 | - |
| Fraud candidate no high cases | R4 | 1 | 0.02% |

### R5 Sub-breakdown
| Sub-type | Count | Description |
|----------|-------|-------------|
| R5A (no risk snapshot) | 2,680 | Historical trusted, not in driver_risk_snapshot |
| R5B (in risk snapshot, no profile) | 0 | Would indicate processing gap |

**Recommendation:** R5A drivers are historical trusted with no D-30 activity. In v2, these become `stale_profile` instead of `review_required`.

### R1 Sub-breakdown
| Trip bucket | Profile | Cases | Count |
|------------|---------|-------|-------|
| 30-39 | no_profile | no_cases | 591 |
| 30-39 | normal | no_cases | 420 |
| 40-49 | no_profile | no_cases | 418 |
| 40-49 | normal | no_cases | 333 |

**Recommendation:** R1 is 50/50 split between 30-39 and 40-49 trips. Drivers with 40-49 + normal profile + no cases are near the trusted threshold. v2 adds `near_eligible` for trusted drivers but these are new_or_unproven.

---

## 2. UNKNOWN (2,838 - 13.8%)

| Reason | Code | Count | % of Unknown |
|--------|------|-------|-------------|
| < 3 trips | U3 | 2,838 | 100% |
| Missing trust_tier | U1 | 0 | - |
| trust_tier = unknown | U2 | 0 | - |

### U3 Detail
| Trips | Trust tier | Count |
|-------|-----------|-------|
| 1 | new_or_unproven | 1,793 |
| 2 | new_or_unproven | 1,045 |

**Recommendation:** All unknown drivers have exactly 1-2 completed trips. These are brand new drivers with no behavioral evidence. U3 is correct classification.

---

## 3. RESTRICTED (34 - 0.2%)

| Park | Count | % of Restricted |
|------|-------|-----------------|
| 08e20910 | 19 | 55.9% |
| 05b1c831 | 10 | 29.4% |
| Others | 5 | 14.7% |

**Common profile:** trusted + normal profile + 1 open high case + no confidence score
**Reason rule:** 100% X2 (open high case)
**Recommended action:** 64% "monitor", 36% null

**Classification:**
- restricted_confirmed: 34 (100%) - all have open high cases
- restricted_due_to_open_case: 34 (100%)
- false_positive: 0

**Recommendation:** All 34 are legitimately restricted due to open high cases. No false positives detected. Case resolution should precede any autocobro decision.

---

## 4. ELIGIBLE (13,190 - 64.3%)

**Bug detected:** Drivers with new_or_unproven + trips<30 were falling through to "eligible" by default. v2 fixes this with unclassified catch-all.

True eligible count in v2: **5,606 (27.3%)**
False positives corrected: **7,584 (37.0%)**

---

## 5. TOP REASON CODES (v1)

| Reason | Count | % |
|--------|-------|---|
| eligible (all rules) | 7,580 | 37.0% |
| E1, E2, E3 (partial) | 5,610 | 27.4% |
| U3 (< 3 trips) | 2,838 | 13.8% |
| R5 (trusted no profile) | 2,680 | 13.1% |
| R1 (new_or_unproven >=30) | 1,762 | 8.6% |

---

## 6. SAMPLES

### Eligible (v1)
```
id=002f9243... park=08e209 trust=trusted trips=935 profile=normal cases=0
id=003afbbe... park=05b1c8 trust=new_or_unproven trips=17 profile=normal cases=0
id=0027a5db... park=56e460 trust=new_or_unproven trips=5 profile=None cases=0  <-- BUG
```

### Review Required
```
id=002820e0... park=05b1c8 trust=trusted trips=153 profile=None (R5)
id=002a5536... park=08e209 trust=new_or_unproven trips=37 profile=None (R1)
id=003963a6... park=05b1c8 trust=trusted trips=408 profile=None (R5)
```

### Restricted
```
id=16f3b5b4... park=e081e2 trust=trusted trips=918 profile=normal high_case=1
id=16f9f70d... park=08e209 trust=trusted trips=2516 profile=normal high_case=1
id=1b20e6bd... park=08e209 trust=trusted trips=1836 profile=normal high_case=1
```

### Unknown
```
id=002c3f0d... park=8d3b13 trust=new_or_unproven trips=1 profile=None
id=00342fc1... park=ae57aa trust=new_or_unproven trips=1 profile=None
id=003c614e... park=08e209 trust=new_or_unproven trips=1 profile=None
```
