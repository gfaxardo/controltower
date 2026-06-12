# LG-RNA-1B — MASS COHORT + MISCLASSIFICATION AUDIT

> **Ticket:** LG-RNA-1B  
> **Date:** 2026-06-11  
> **Motor:** Lima Growth  
> **Status:** AUDITED — RNA_STRUCTURE_VALID  

---

## 1. RNA UNIVERSE

**50,181 drivers** in REGISTERED_NOT_ACTIVATED segment (73.3% of Lima's 68,473 drivers).

---

## 2. ORIGEN: SEP 2025 MASS ONBOARDING

### 2.1 Source

All 35,793 Sep 2025 RNA drivers were registered through the **normal Yango platform onboarding flow** — no batch import script, no CSV upload. The data entered `public.drivers` via standard Yango API sync (`POST /v1/parks/driver-profiles/list`).

### 2.2 Campaign / Batch

No `campaign_id`, `source`, or `utm` fields track acquisition source in `public.drivers`. The `campaign_id_external` fields in the control loop and action ledger track **outbound** campaigns TO drivers, not inbound acquisition. The mass onboarding was a platform-side event (Yango app signups), not a CT-initiated import.

### 2.3 Exact Dates — Mass Creation Event

| Date | Drivers Registered (all) | RNA from this date |
|------|--------------------------|---------------------|
| **Sep 2** | 5,468 | 4,994 |
| **Sep 3** | 11,006 | 10,188 |
| **Sep 4** | **16,300** | **15,013** |
| **Sep 5** | 2,548 | 2,256 |
| **Sep 8** | 1,749 | 1,587 |
| Other Sep dates | ~2,000 | ~1,755 |

**Peak day: Sep 4, 2025 — 16,300 drivers registered, 15,013 still RNA today.**

The Sep 2-5 window alone accounts for **32,981 RNA drivers** (65.7% of all RNA). This is the single largest cohort in Lima history. Outside Sep 2025, the next highest daily registration is 284 (Jul 3, 2025).

### 2.4 Why Mass?

The concentration of 35,793 registrations in a single month (vs ~2,000/month in other periods) confirms this was a **deliberate mass onboarding campaign** by Yango Operations — likely a driver recruitment drive in Lima. These drivers completed registration (name, phone, license verified, `work_status = 'working'`) but **never completed a single trip**.

---

## 3. 379 RNA WITH COMPLETED TRIPS — MISCLASSIFICATION AUDIT

### 3.1 Scope

379 drivers classified as `REGISTERED_NOT_ACTIVATED` in taxonomy V2 but with `completed_trips_90d > 0` in `lifecycle_daily`. All 379 have `lifecycle_status = 'NEVER_ACTIVATED'` — which is **incorrect** for drivers who have completed trips.

### 3.2 Top Misclassified Drivers (sample)

| Driver | Hire | 90d Trips | 30d Trips | Last Trip | Days Since |
|--------|------|-----------|-----------|-----------|------------|
| 18c8898b... | Sep 2025 | 1,359 | 338 | May 31 | 10 |
| 3952cf0b... | Mar 2026 | 1,327 | 290 | May 27 | 14 |
| 73bc6502... | Jul 2025 | 1,292 | 224 | May 30 | 11 |
| 6d0b8a34... | Sep 2025 | 1,240 | 379 | Jun 2 | 8 |
| 37049016... | Sep 2025 | 1,146 | 315 | May 31 | 10 |

These are **high-volume drivers** — one has 1,359 trips in 90 days but is classified as "Never Activated." They should be in segments like ACTIVE_GROWTH, TOP_PERFORMER, or STABLE.

### 3.3 Root Cause

The taxonomy V2 correctly identifies the misclassification: `tax_lifecycle = NEVER_ACTIVATED` matches `real_lifecycle = NEVER_ACTIVATED`. Both are wrong. The bug is upstream in `growth.yego_lima_driver_lifecycle_daily`:

- `lifecycle_status = 'NEVER_ACTIVATED'`  
- `completed_trips_90d = 1,359`  

The lifecycle builder (`yego_lima_lifecycle_service.py`) is not updating `lifecycle_status` from `NEVER_ACTIVATED` to `ACTIVE`/`NEW` when trips exist. This affects **379 drivers**.

### 3.4 Why They Ended Up RNA

| Layer | Value | Correct? |
|-------|-------|----------|
| lifecycle_status (source) | NEVER_ACTIVATED | **WRONG** — has 1,359 trips |
| activity_status (computed) | NEVER_ACTIVATED | **WRONG** — cascaded from lifecycle |
| value_tier | NO_VALUE | Wrong — cascaded |
| momentum_state | INSUFFICIENT_HISTORY | Wrong — cascaded |
| operational_segment | REGISTERED_NOT_ACTIVATED | **WRONG** — cascaded |

The taxonomy cascade works correctly given its inputs. The bug is that the **lifecycle_daily table has incorrect `lifecycle_status` for 379 drivers**. These drivers need a lifecycle rebuild.

---

## 4. RNA CLASSIFICATION BY BEHAVIOR

| Behavior | Drivers | % | Definition |
|----------|---------|---|------------|
| **RNA_MASS_COHORT** | 35,627 | 71.0% | Sep 2025 mass onboarding (Sep 1-30), never activated |
| **RNA_NEVER_TOUCHED** | 14,175 | 28.2% | Registered outside Sep 2025, 0 trips |
| **RNA_MISCLASSIFIED** | 379 | 0.8% | Has trips in last 90d — should NOT be RNA |
| **TOTAL** | **50,181** | 100% | |

### 4.1 RNA_MASS_COHORT Detail

| Sub-cohort | Drivers | Avg Age |
|------------|---------|---------|
| Sep 2-5 peak | 32,981 | 280.6 days |
| Sep other days | 2,646 | 271.8 days |

### 4.2 RNA_NEVER_TOUCHED Detail

14,175 drivers registered outside the Sep 2025 mass event, with 0 completed trips ever. Spread across all other months (Jun-Nov 2025, Mar-Apr 2026). Average age: 228 days.

### 4.3 RNA_DORMANT

The query returned 0 because the 379 drivers with trips all have trips WITHIN the last 90 days (active or recently active). None are "dormant" (>90d since last trip). If any exist, they'd be drivers who activated, stopped, and then were recycled back to NEVER_ACTIVATED — a lifecycle transition bug.

---

## 5. PROPOSED RNA TAXONOMY V3

### 5.1 Current (V2)

```
REGISTERED_NOT_ACTIVATED = 1 bucket, 50,181 drivers
```

### 5.2 Proposed (V3)

| Segment | Drivers | % | Definition | Program |
|---------|---------|---|------------|---------|
| **RNA_MASS_COHORT** | 35,627 | 71.0% | Sep 2025 mass onboarding | RNA_WARM (SAC campaign) |
| **RNA_NEVER_TOUCHED** | 14,175 | 28.2% | Registered, 0 trips, non-Sep | RNA_COLD (bot reactivation) |
| **RNA_MISCLASSIFIED** | 379 | 0.8% | Has recent trips | FIX — remove from RNA |
| **RNA_FIRED** | 407 | 0.8% | Fired/inactive | Archive |

### 5.3 Classification Rules

```sql
CASE
  WHEN work_status = 'fired' OR active = false
    THEN 'RNA_FIRED'
  WHEN completed_trips_90d > 0
    THEN 'RNA_MISCLASSIFIED'  -- Should be handled by lifecycle fix
  WHEN hire_date BETWEEN '2025-09-01' AND '2025-09-30'
    THEN 'RNA_MASS_COHORT'
  ELSE 'RNA_NEVER_TOUCHED'
END
```

### 5.4 Program Mapping

| RNA Sub-Segment | Program | Priority | Channel | Action |
|-----------------|---------|----------|---------|--------|
| RNA_MASS_COHORT | RNA_WARM | 8b | SAC | Structured onboarding campaign for 35K Sep cohort |
| RNA_NEVER_TOUCHED | RNA_COLD | 8c | Bot | Automated re-engagement |
| RNA_MISCLASSIFIED | (remove from RNA) | — | — | Fix lifecycle, reassign to correct program |
| RNA_FIRED | (archive) | — | — | No contact |

---

## 6. BACKLOG UPDATE

### 6.1 New Tickets

| Ticket | Description | Priority |
|--------|-------------|----------|
| **LG-RNA-1C** | RNA Taxonomy V3 Implementation — implement 4-segment classification in taxonomy config, rebuild observability | P1 |
| **LG-RNA-1D** | Lifecycle Misclassification Fix — fix 379 drivers with incorrect `NEVER_ACTIVATED` status, rebuild lifecycle_daily for affected drivers | **P0** |
| **LG-RNA-1E** | RNA Mass Cohort Campaign Design — design structured SAC campaign for 35K Sep 2025 cohort | P2 |

### 6.2 Updated Backlog

| Ticket | Status |
|--------|--------|
| LG-RNA-1A | COMPLETED — RNA universe audit |
| LG-RNA-1B | COMPLETED — Mass cohort + misclassification (this report) |
| LG-RNA-1C | BACKLOG — Taxonomy V3 |
| LG-RNA-1D | BACKLOG — Lifecycle fix (P0) |
| LG-RNA-1E | BACKLOG — Campaign design |

---

## 7. GO / NO-GO

### 7.1 Classification

**A) RNA_STRUCTURE_VALID**

The RNA structure (REGISTERED_NOT_ACTIVATED segment) is valid for 99.2% of its members. Only 379 drivers (0.8%) are misclassified and need a lifecycle fix. The segmentation of the 50,181 into MASS_COHORT (71%) vs NEVER_TOUCHED (28%) is clean and actionable.

### 7.2 Criteria

| Criterion | Status |
|-----------|--------|
| RNA segment is real (not garbage data) | PASS — 99.2% working, not fired |
| Mass cohort identified and dated | PASS — Sep 2-5, 2025, 32,981 drivers |
| Misclassification quantified and root-caused | PASS — 379 drivers, lifecycle bug upstream |
| New taxonomy proposed | PASS — 4 segments (MASS_COHORT, NEVER_TOUCHED, MISCLASSIFIED, FIRED) |
| Backlog updated | PASS — 3 new tickets |
| No program engine / movement / control loop touched | PASS |

---

## 8. FIRMA

| Campo | Valor |
|-------|-------|
| **Auditado por** | LG-RNA-1B Mass Cohort + Misclassification Audit |
| **Fecha** | 2026-06-11 |
| **Motor** | Lima Growth |
| **Clasificación** | `RNA_STRUCTURE_VALID` |
| **Próxima acción** | LG-RNA-1D — Lifecycle Misclassification Fix (P0) |
