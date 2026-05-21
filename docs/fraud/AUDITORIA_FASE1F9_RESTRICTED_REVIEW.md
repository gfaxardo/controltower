# AUDITORIA FASE 1F-9 — RESTRICTED REVIEW

**Count:** 34 drivers (v1) / 38 drivers (v2)
**Status:** restricted

---

## 1. PROFILE

| Attribute | Pattern |
|-----------|---------|
| Reason | 100% X2 (open high case) |
| Trust tier | 70% trusted, 30% new_or_unproven |
| Behavioral profile | 68% normal, 32% None |
| Confidence score | 100% null (no confidence score on cases) |
| Recommended action | 64% monitor, 36% null |
| Cases | 100% exactly 1 open high case |
| Critical cases | 0 |

---

## 2. PARK CONCENTRATION

| Park | Count | % |
|------|-------|---|
| 08e20910 | 19 | 56% |
| 05b1c831 | 10 | 29% |
| Others | 5 | 15% |

83% of restricted drivers are concentrated in 2 parks.

---

## 3. CLASSIFICATION AUDIT

| Verdict | Count | Notes |
|---------|-------|-------|
| restricted_confirmed | 34 | All have legitimate open high cases |
| restricted_due_to_open_case | 34 | 100% triggered by X2 |
| restricted_due_to_profile | 0 | None triggered by behavioral profile class |
| false_positive_review | 0 | No false positives detected |

---

## 4. SAMPLE DRIVERS

```
trusted, 918 trips, normal profile, 1 high case, monitor
trusted, 2516 trips, normal profile, 1 high case, monitor
trusted, 1836 trips, normal profile, 1 high case, monitor
new_or_unproven, 5 trips, no profile, 1 high case, no action
new_or_unproven, 16 trips, suspicious profile, 1 high case, monitor
```

---

## 5. RECOMMENDATION

1. **All 34 are legitimate restricted.** No false positives.
2. **Case resolution should be the priority.** Once the open high case is resolved (closed/rejected), these drivers would automatically reclassify to eligible or review_required in the next snapshot.
3. **Park concentration** suggests possible park-level fraud pattern. Investigate parks 08e20910 and 05b1c831.
4. **Confidence scores are null** — cases were created before confidence scoring was implemented. Consider running `fraud_recompute_case_confidence.py`.
5. **No autocobro for any restricted driver** until open cases are resolved.

---

## 6. V2 CHANGE (+4 restricted)

V2 added X3 (critical_case_count > 0) and refined evaluation order. The additional 4 restricted drivers may be edge cases from the new rules.

| Reason | v1 Count | v2 Count |
|--------|----------|----------|
| X2 (open high case) | 34 | 38 |
| X3 (critical case) | N/A | +4 |
