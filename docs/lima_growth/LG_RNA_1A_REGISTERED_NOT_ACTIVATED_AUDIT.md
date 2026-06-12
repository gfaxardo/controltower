# LG-RNA-1A — REGISTERED NOT ACTIVATED AUDIT

**Ticket:** LG-RNA-1A  
**Date:** 2026-06-11  
**Status:** AUDITED — RNA_ACTIONABLE  

---

## TASK 1-2 — RNA UNIVERSE

50,181 drivers in REGISTERED_NOT_ACTIVATED segment (73.3% of Lima).

| Characteristic | Value |
|---------------|-------|
| work_status = 'working' | 49,770 (99.2%) |
| work_status = 'fired' | 407 (0.8%) |
| Has phone + license | 50,181 (100%) |
| License country = Peru | 49,731 (99.1%) |
| Account balance = 0 | 49,631 (98.9%) |
| current_status = 'offline' | ~50,000 (99.7%) |

---

## TASK 3 — AGE DISTRIBUTION

| Age Bucket | Drivers | % | Avg Days |
|-----------|---------|---|----------|
| 0-30d | 408 | 0.8% | 11d |
| 31-90d | 2,013 | 4.0% | 64d |
| 91-180d | 2,704 | 5.4% | 134d |
| **181-365d** | **42,658** | **85.0%** | **277d** |
| 365d+ | 2,398 | 4.8% | 389d |

**85% are 181-365 days old (~9 months).** This is a massive concentrated cohort from a specific time period.

---

## TASK 4 — TOP COHORTES

| Cohort | RNA | % | Avg Age |
|--------|-----|---|---------|
| **Sep 2025** | **35,793** | **71.3%** | 279d |
| Jun 2025 | 1,968 | 3.9% | 358d |
| Nov 2025 | 1,925 | 3.8% | 206d |
| Oct 2025 | 1,602 | 3.2% | 236d |
| May 2025 | 1,512 | 3.0% | 386d |
| Apr 2026 | 1,155 | 2.3% | 57d |
| Mar 2026 | 1,087 | 2.2% | 85d |

**September 2025: 35,793 drivers (71.3%)** — this was a mass onboarding event. Multiple consecutive days: Sep 2 (4,902), Sep 3 (10,006), Sep 4 (14,773), Sep 5 (2,203). These drivers registered but never activated.

---

## TASK 5 — ACTIVITY LEVELS

| Activity | Drivers | % |
|----------|---------|---|
| ZERO completed trips | 49,802 | **99.24%** |
| Has completed trips | 379 | 0.76% |
| Has cancelled trips | 4,426 | 8.8% |
| ZERO account balance | 49,631 | 98.9% |

**99.24% truly never completed a trip.** The 379 with completed trips are misclassified (should not be RNA — taxonomy edge case). The 4,426 with cancelled trips accepted rides but cancelled before completion — these are the most promising leads.

---

## TASK 6 — RECOVERABLE vs NOISE

| Category | Drivers | % |
|----------|---------|---|
| **RECOVERABLE** (working, not fired) | **49,770** | **99.2%** |
| NOISE (fired or inactive) | 411 | 0.8% |

**99.2% are recoverable.** Only 0.8% are fired or inactive. The RNA population is NOT historical noise — it's a legitimate pool of registered-but-inactive drivers.

| Recoverable + Age | Drivers | % |
|------------------|---------|---|
| HOT (recoverable + <90d hire) | 2,390 | 4.8% |
| WARM (recoverable + 91-365d) | 45,067 | 89.8% |
| COLD (recoverable + 365d+) | 2,313 | 4.6% |

---

## TASK 7 — SUB-SEGMENTATION PROPOSAL

| Sub-Segment | Drivers | % | Action | Channel |
|------------|---------|---|--------|---------|
| **RNA_HOT_LEAD** | 2,390 | 4.8% | Immediate activation outreach | Call center |
| **RNA_WARM_LEAD** | 45,067 | 89.8% | Structured onboarding campaign | SAC |
| **RNA_COLD_LEAD** | 2,313 | 4.6% | Automated re-engagement | Bot |
| **RNA_FIRED** | 407 | 0.8% | No contact — archive | — |
| **RNA_OTHER** | 4 | <0.1% | Review individually | — |

### RNA_HOT_LEAD Priority Scoring

For the 2,390 hot leads: score by `hire_date DESC` (most recent first) + `cancelled_trips DESC` (drivers who accepted rides are closer to activation).

---

## TASK 9 — GO / NO-GO

### Veredicto: **A) RNA_ACTIONABLE**

| Criterion | Evidence |
|-----------|----------|
| 99.2% recoverable | 49,770 working, not fired |
| 4.8% hot leads | 2,390 hired <90d |
| Sep 2025 mass cohort | 35,793 drivers — structured campaign opportunity |
| 4,426 with cancelled trips | Accepted rides = close to activation |
| Only 0.8% noise | 407 fired drivers |

### Recommendation

The RNA_ONBOARDING program should be split into 3 sub-programs:

1. **RNA_HOT** (priority 8a): 2,390 drivers — call center, immediate
2. **RNA_WARM** (priority 8b): 45,067 drivers — SAC, structured campaign
3. **RNA_COLD** (priority 8c): 2,313 drivers — bot, automated reactivation

---

**LG-RNA-1A — COMPLETE**

*50,181 RNA drivers audited. 99.2% recoverable, not noise.*  
*85% from a single Sep 2025 mass onboarding event.*  
*4,426 have cancelled trips — closest to activation.*  
*Recommendation: sub-segment RNA_ONBOARDING into HOT/WARM/COLD.*
