# AUDITORIA FASE 1F-9 — R5: TRUSTED WITHOUT BEHAVIORAL PROFILE

**Count:** 2,680 drivers (13.1% of total)
**Status v1:** review_required (R5)
**Status v2:** stale_profile (S1)

---

## 1. PROBLEM STATEMENT

2,680 drivers are trusted with >=50 trips but have no behavioral profile.

---

## 2. ROOT CAUSE ANALYSIS

| Sub-type | Count | Description |
|----------|-------|-------------|
| R5A (no risk snapshot) | 2,680 | Not in fraud.driver_risk_snapshot at all |
| R5B (in risk snapshot, no profile) | 0 | In risk snapshot but behavioral_profile_class IS NULL |

**Conclusion:** 100% of R5 drivers are R5A — they have zero presence in driver_risk_snapshot. This means:
- They have no D-30 activity (no trips in the last 30 days to compute a behavioral profile)
- They are historical trusted drivers who haven't driven recently
- The behavioral profile batch runner (routine_behavioral_driver_profile) requires >=3 trips in D-30 to compute a profile
- These drivers may have 50+ total trips but 0 recent trips

---

## 3. IMPLICATIONS

| Risk | Assessment |
|------|-----------|
| Are they inactive? | Likely. No D-30 activity = no behavioral profile. |
| Are they safe for autocobro? | Unknown — no recent behavioral evidence. |
| Should they be eligible? | No — lack of recent data creates blind spot. |
| Should they be restricted? | No — no negative signals, just missing data. |
| Best classification | stale_profile — not blocked, but needs recent activity to be eligible. |

---

## 4. V2 CLASSIFICATION

In v2 policy, R5A drivers are classified as `stale_profile` (S1):
- They are NOT eligible (no profile)
- They are NOT restricted (no negative signals)
- They are NOT unknown (they have trust tier and trip history)
- They need recent D-30 activity to generate a behavioral profile and become eligible

**Rule S1:** `trusted_50plus_no_risk_snapshot` — trusted, >=50 trips, not in driver_risk_snapshot

---

## 5. PROFILE GAP (R5B)

Count: 0 drivers.

R5B would be drivers who ARE in the risk snapshot but don't have a behavioral profile. This indicates a processing gap. Currently, all 8,575 drivers in driver_risk_snapshot have behavioral profiles (100% coverage within the risk snapshot). 

---

## 6. RECOMMENDATION

1. **R5A (stale_profile):** Keep as v2 stale_profile. These drivers need recent activity to re-qualify.
2. **R5B (profile_gap):** If any appear in future, investigate processing issue.
3. **Autocobro decision:** Do NOT enable autocobro for stale_profile without manual review of recent activity.
4. **Monitoring:** Track how many stale_profile drivers become active and get reclassified in subsequent runs.
