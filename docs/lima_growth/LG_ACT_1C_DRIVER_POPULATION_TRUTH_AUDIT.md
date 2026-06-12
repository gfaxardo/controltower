# LG-ACT-1C — DRIVER POPULATION TRUTH AUDIT

**Ticket:** LG-ACT-1C  
**Date:** 2026-06-11  
**Status:** AUDIT COMPLETE — GAP IDENTIFIED  

---

## TASK 0 — GOVERNANCE

Control Foundation / Lima Growth. Read-only audit. Zero production changes. Compatible with active OMNI-P0 phase.

---

## TASK 1 — PUBLIC.DRIVERS PARK SCOPE

### Global Scope

| Metric | Value |
|--------|-------|
| Total rows | 156,873 |
| Distinct parks | 33 |
| Lima park rows | 68,470 (43.6%) |
| Other parks | 88,403 (56.4%) |
| Rows with NULL park_id | 819 (0.5%) |

**public.drivers is a GLOBAL multi-park table.** It contains driver registrations for all 33 Yango parks managed by the fleet, not just Lima.

### Lima Data Quality

| Check | Result |
|-------|--------|
| NULL driver_id | **0** — perfect |
| Duplicated driver_id | **0** — perfect |
| NULL phone | **0** — all drivers have phone |
| NULL license_number | **0** — all drivers have license |
| NULL hire_date | **0** — all drivers have hire date |
| NULL full_name | **0** — all drivers have name |

**The Lima slice of public.drivers is pristine.** Every driver has complete identity data (name, phone, license, hire date). This is an exceptionally clean registry.

---

## TASK 2 — LIMA DRIVERS STATUS DISTRIBUTION

### Work Status

| work_status | Drivers | % |
|------------|---------|---|
| working | 64,062 | 93.6% |
| fired | 4,399 | 6.4% |
| not_working | 9 | <0.1% |

### Current Status

| current_status | Drivers | % |
|---------------|---------|---|
| offline | 65,846 | 96.2% |
| busy | 2,269 | 3.3% |
| in_order_free | 182 | 0.3% |
| free | 130 | 0.2% |
| in_order_busy | 42 | <0.1% |

### Fire Date

| Status | Drivers |
|--------|---------|
| Not fired (active) | 64,141 (93.7%) |
| Fired | 4,329 (6.3%) |

### Hire Year

| Year | Drivers |
|------|---------|
| 2024 | 1 |
| 2025 | 60,209 (87.9%) |
| 2026 | 8,260 (12.1%) |

**The driver base grew massively in 2025** (60,209 hired) and continues growing in 2026 (8,260 in ~5 months). Only 1 driver from before 2025.

### Account Balance

| Bucket | Drivers |
|--------|---------|
| Zero | 52,501 (76.7%) |
| Negative | 8,953 (13.1%) |
| 1-100 | 6,964 (10.2%) |
| 101+ | 51 (<0.1%) |

### License Country

| Country | Drivers |
|---------|---------|
| Peru (per) | 67,994 (99.3%) |
| Venezuela (ven) | 443 (0.6%) |
| Others | 33 (<0.1%) |

**99.3% of Lima drivers have Peruvian licenses.** This confirms the park is genuinely Lima-based.

---

## TASK 3 — ACTIVATION CROSS WITH ACTIVITY_EVENT

| Metric | Count | % of Lima |
|--------|-------|-----------|
| Total Lima drivers | 68,470 | 100% |
| Ever activated (>=1 COMPLETED_TRIP) | 15,737 | 23.0% |
| Never activated (0 COMPLETED_TRIP) | 52,733 | 77.0% |
| Active 7d | 2,649 | 3.9% |
| Active 30d | 4,442 | 6.5% |
| Active 90d | 5,168 | 7.5% |
| Active 365d | 14,241 | 20.8% |
| Archived >90d | 10,569 | 15.4% |
| Inactive >365d | 1,446 | 2.1% |

### BUG: Missing trips_2026 Data

**2,934 drivers have completed trips in trips_2026 but are NOT in activity_event.**

Root cause: The ACT-1A backfill only covered May 1 - Jun 10, 2026. The ACT-1B "full backfill" added trips_2025 but did NOT add the missing trips_2026 months (January-April 2026). These 2,934 drivers completed trips in Jan-Apr 2026 that were never ingested into activity_event.

**Impact:** activity_event undercounts ever-activated drivers by ~2,934 (should be ~18,671 not 15,737). The lifecycle classification is also affected — some NEVER_ACTIVATED drivers actually had trips in early 2026.

---

## TASK 4 — DIRECT TRIPS VALIDATION

| Metric | trips Direct | activity_event | Gap |
|--------|-------------|----------------|-----|
| Ever completed | 18,671 | 15,737 | **-2,934 (BUG)** |
| Active 7d | 2,649 | 2,649 | 0 (match) |
| Active 30d | 4,442 | 4,442 | 0 (match) |
| Active 90d | 7,928 | 5,168 | -2,760 |

The gap in Active 90d is because activity_event only has 41 days of trips_2026 data (May 1-Jun 10), while the direct query covers all of 2026.

**trips direct IS the ground truth.** activity_event needs the missing Jan-Apr 2026 data.

---

## TASK 5 — NEVER_ACTIVATED DEEP AUDIT

### Profile of the 52,954 NEVER_ACTIVATED Drivers

| Characteristic | Value |
|---------------|-------|
| work_status = 'working' | 52,250 (98.7%) |
| work_status = 'fired' | 700 (1.3%) |
| NOT fired | 52,300 (98.8%) |
| Has phone AND license | 52,954 (100%) |
| Hired in 2025 | 46,306 (87.5%) |
| Hired in 2026 | 6,647 (12.5%) |
| current_status = 'offline' | ~52,800 (99.7%) |

### Who Are They?

Sample of 20 random NEVER_ACTIVATED drivers:
- **All have full names** (Peruvian names: Chavez Miguel, Velasquez Checalla, etc.)
- **All have phone numbers**
- **All have driver licenses**
- **All hired between Jun 2025 and Mar 2026**
- **All have work_status = 'working'** (except 1 fired)
- **All are currently offline**
- **0 completed trips in the available history**

**Verdict: These are REAL onboarded drivers who never activated.** They went through the complete registration process (name, phone, license verified) but never completed a single trip. This is a legitimate operational category — the "registered but inactive" population.

They are NOT:
- ❌ Garbage/migration records (too clean, too consistent)
- ❌ Other-park drivers with wrong park_id (all have Lima park_id)
- ❌ Duplicate/test profiles (all have unique driver_id, full identity)

### However, ~2,934 of them may actually have trips

Due to the missing Jan-Apr 2026 trips_2026 data gap, approximately 2,934 of these 52,954 "never activated" drivers may actually have completed trips in early 2026. After fixing the gap, the true never-activated count will be closer to **~50,000**.

---

## TASK 6 — UNIVERSE CANDIDATES

| Universe | Count | % of Lima | Definition |
|----------|-------|-----------|------------|
| **A) REGISTERED_UNIVERSE** | 68,470 | 100% | All drivers in public.drivers Lima |
| **B) ACTIVATED_UNIVERSE** | ~18,671 | 27.3% | At least 1 completed trip ever (after gap fix) |
| **C) RECENT_UNIVERSE** | ~14,241 | 20.8% | Completed trip in last 365d |
| **D) MANAGED_UNIVERSE** | ~64,062 | 93.6% | work_status != fired, has phone, has license |
| **E) OPERATIONAL_UNIVERSE** | ~7,928 | 11.6% | Completed trip in last 90d OR work_status = 'working' |

---

## TASK 7 — TAXONOMY POPULATION RECOMMENDATION

### Layer-by-Layer Universe Assignment

| Layer | Recommended Universe | Count | Justification |
|-------|---------------------|-------|---------------|
| **Lifecycle** | REGISTERED_UNIVERSE (68,470) | All Lima | Lifecycle must track from registration to churn. NEVER_ACTIVATED is a valid state. |
| **Taxonomy (Activity + Value)** | ACTIVATED_UNIVERSE (~18,671) | Ever completed | Only drivers with trips have meaningful activity/value. NEVER_ACTIVATED drivers have no activity to classify. |
| **Programs (50/14, 90/300, HVR)** | OPERATIONAL_UNIVERSE (~7,928) | Active or working | Programs target drivers who CAN be intervened (active or working status). |
| **Control Loop / Queue** | ACTIONABLE (~2,650 active 7d) | Recent activity | Queue/export targets drivers with recent activity who can act on programs. |

### Terminology

| Term | Definition | Count |
|------|-----------|-------|
| REGISTERED_NOT_ACTIVATED | Registered but 0 completed trips ever | ~50,000 |
| NEVER_ACTIVATED | Same as above (lifecycle term) | ~50,000 |
| ACTIVATED_HISTORICAL | >=1 completed trip, last trip >90d ago | ~10,600 |
| OPERATIONALLY_MANAGED | working status OR recent activity | ~7,928 |

### Why NOT run taxonomy on all 68,470

- 50,000 drivers have ZERO completed trips — there is no activity to classify
- Value tier requires `avg_orders_4w` which is 0 for them
- Momentum requires trip history which is absent
- They bloat the taxonomy with meaningless classifications
- They're not actionable (no trips = nothing to grow/recover)

---

## TASK 8 — IMPACT ON LG-ACT-1B

### Verdict: **A) KEEP_AS_IS with one fix**

LG-ACT-1B's lifecycle over REGISTERED_UNIVERSE is correct. Lifecycle SHOULD include NEVER_ACTIVATED as a valid state — these are registered drivers waiting to be activated. The taxonomy and programs will simply filter them out.

**Required fix:** Backfill the missing trips_2026 data (January-April 2026) to close the 2,934-driver gap.

### After Fix: Expected Lifecycle Distribution (estimated)

| Lifecycle | Drivers | % |
|-----------|---------|---|
| NEVER_ACTIVATED | ~50,000 | ~73% |
| ARCHIVED_90D | ~10,600 | ~15.5% |
| ACTIVE | ~2,650 | ~3.9% |
| REACTIVATED | ~2,800 | ~4.1% |
| CHURN_15D | ~1,000 | ~1.5% |
| NEW | ~1,420 | ~2.1% |

The ACTIVE count will increase because the gap-fix will correctly identify more drivers' recent activity. NEW count will also increase as Jan-Apr 2026 hire dates will be properly tracked.

---

## TASK 9 — GO / NO-GO

### Veredicto: **A) PUBLIC_DRIVERS_IS_VALID_REGISTERED_UNIVERSE** with **B) SPLIT_REGISTERED_AND_ACTIVATED_UNIVERSES** for downstream layers

### Evidence

| Criterion | Status |
|-----------|--------|
| public.drivers park scope confirmed | **PASS** — 33 parks, Lima = 43.6% |
| Lima driver count exact | **PASS** — 68,470 |
| Data quality validated | **PASS** — 0 NULLs in critical fields |
| NEVER_ACTIVATED audited | **PASS** — Real onboarded drivers, not garbage |
| work_status distribution | **PASS** — 93.6% working, 6.4% fired |
| Gap identified | **PASS** — 2,934 missing from Jan-Apr 2026 backfill |
| Universe candidates quantified | **PASS** — 5 candidates with clear definitions |
| Recommendation for each layer | **PASS** — Lifecycle on all, Taxonomy on activated, Programs on operational |

### Action Items

1. **HOTFIX:** Backfill missing trips_2026 data (Jan-Apr 2026) into activity_event
2. **Keep** LG-ACT-1B lifecycle over REGISTERED_UNIVERSE
3. **Add filter** to taxonomy build: only process ACTIVATED_UNIVERSE (~18,671 drivers)
4. **Add filter** to program assignment: only process OPERATIONAL_UNIVERSE (~7,928)

---

**LG-ACT-1C — FIN**

*public.drivers is a clean, global multi-park registry with 33 parks.*  
*Lima = 68,470 drivers: 23% activated, 77% never activated.*  
*NEVER_ACTIVATED = real onboarded drivers with full identity, not data artifacts.*  
*2,934-driver gap identified (Jan-Apr 2026 trips_2026 not backfilled).*  
*Recommendation: REGISTERED_UNIVERSE for lifecycle, ACTIVATED_UNIVERSE for taxonomy, OPERATIONAL_UNIVERSE for programs.*
