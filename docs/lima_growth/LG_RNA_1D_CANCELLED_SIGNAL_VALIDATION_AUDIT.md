# LG-RNA-1D — CANCELLED SIGNAL VALIDATION AUDIT

**Ticket:** LG-RNA-1D  
**Date:** 2026-06-11  
**Status:** SIGNAL VALIDATED — HIGH INTENT  

---

## TASK 1 — RNA_CANCELLED UNIVERSE + PERCENTILES

| Metric | Value |
|--------|-------|
| RNA with cancelled | 4,426 |
| Total cancelled events | 682,476 |
| **Avg** per driver | **154.2** ← distorted by outliers |
| **Median** per driver | **6** ← the real typical driver |
| P75 | 16 |
| P90 | 57 |
| P95 | 389 |
| P99 | 4,150 |
| Max | 15,265 |

**The average of 154.2 is meaningless.** The distribution is heavily right-skewed. The median RNA driver has only 6 cancellations in their entire history. 163 drivers have >1,000 cancellations, inflating the average. The percentiles tell the real story.

---

## TASK 2 — DUPLICATE AUDIT

| Check | Result |
|-------|--------|
| Total events | 682,476 |
| Unique (source_system, source_table, source_trip_id) | 682,476 |
| **Duplicates** | **0** |
| NULL source_trip_id | 0 |
| Repeated timestamps (same driver+ts) | 3 |

**Zero duplicates.** The UNIQUE constraint on (source_system, source_table, source_trip_id) is working perfectly. Every cancelled event is a distinct real trip.

---

## TASK 3 — CANCELLATION MEANING

### All 682,476 events have `condicion = 'Cancelado'` — consistent.

### Cancellation Reasons (Ranked)

| Reason | Events | % | Drivers | Interpretation |
|--------|--------|---|---------|---------------|
| **El conductor rechazó la solicitud** | 326,724 | 47.9% | 2,656 | Driver actively REJECTED the trip |
| **El conductor no aceptó la solicitud** | 222,066 | 32.5% | 3,734 | Driver didn't accept (timeout/passive) |
| Viaje cancelado por el cliente | 91,187 | 13.4% | 2,065 | Passenger cancelled |
| Error al asignar al conductor | 23,944 | 3.5% | 1,357 | System assignment error |
| Notificación tardó demasiado | 13,753 | 2.0% | 937 | Technical delay |
| Other | 4,802 | 0.7% | — | autoreorder, expire, admin, etc. |

### Key Insight

**80.4% of "cancelled" trips are driver-side actions** — the driver either actively rejected the trip or didn't accept it in time. Only 13.4% were cancelled by passengers.

This means "cancelled" for RNA drivers is primarily a signal of **driver engagement without completion** — they see trip requests, interact with them (accept/reject/timeout), but never complete a trip. This is exactly the behavioral pattern that an RNA activation program targets.

---

## TASK 4 — RECENCY

Cancellations span from April 2025 to June 2026. The recency distribution shows activity across all time windows, with concentration in the last 30-90 days for the most active drivers.

---

## TASK 5 — OUTLIER AUDIT

### Top 20 by Cancelled Events

| Driver | Name | Cancels | Active Days | Period |
|--------|------|---------|------------|--------|
| 73bc6502... | PEREZ VILLANUEVA AGA | 15,265 | 241 | Jul 2025 - May 2026 |
| 8269b980... | Parra Hidalgo Nelson | 14,261 | 240 | Sep 2025 - May 2026 |
| 73b95483... | Hernandez Bustamante | 12,703 | 169 | Oct 2025 - Jun 2026 |
| 46986311... | Gutierrez Urbano Ale | 10,799 | 216 | Sep 2025 - Jun 2026 |
| ... | (16 more) | 6,000-10,000 | 127-368 | 2025-2026 |

**All top outliers are real drivers with real names**, active across 127-368 distinct days. They interact with the platform constantly but never complete a single trip.

### Extreme Daily Bursts

| Driver | Date | Cancels in 1 Day |
|--------|------|-----------------|
| 1a947b39... | 2026-03-28 | **436** |
| 0a8113de... | 2026-01-17 | 346 |
| 060730be... | 2025-11-01 | 331 |

These drivers receive and reject hundreds of trip requests in a single day. They keep the app open, get offers, and consistently decline them.

### Drivers with >1,000 Cancellations: **163**

These 163 drivers (3.7% of RNA_CANCELLED) account for a disproportionate share of events. They represent a distinct behavioral pattern — chronic rejecters who may have a specific reason for never completing (vehicle issue, license problem, pay dispute).

---

## TASK 6 — RNA_CANCELLED SEGMENT QUALITY

| Quality | Drivers | % | Definition | Actionable? |
|---------|---------|---|-----------|-------------|
| **HIGH_INTENT** | **631** | 14.3% | Cancel ≤30d, active ≥2 days | **YES — P0** |
| **MEDIUM_INTENT** | **1,020** | 23.0% | Cancel ≤90d, ≥2 events | **YES — P1** |
| LOW_INTENT | 2,091 | 47.2% | ≥2 events, old | Monitor |
| SINGLE_CANCEL | 684 | 15.5% | Only 1 cancel ever | Low priority |

**Total actionable: 1,651 drivers (37.3% of RNA_CANCELLED).**

---

## TASK 7 — PILOT RECOMMENDATION

### Pilot 1: HIGH_INTENT Cancelled (P0)

| Parameter | Value |
|-----------|-------|
| Size | **631 drivers** |
| Channel | Call center |
| Message | "Vemos que recibís viajes pero no los completás. ¿Podemos ayudarte?" |
| Success | Completed trip within 7 days |
| Exclusion | Outliers with >5,000 cancels (possible app/account issue, not activation problem) |

### Pilot 2: MEDIUM_INTENT (P1)

| Parameter | Value |
|-----------|-------|
| Size | 1,020 drivers |
| Channel | WhatsApp / SAC |
| Message | "Hace poco rechazaste algunos viajes. ¿Qué necesitás para completar tu primer viaje?" |
| Success | Completed trip within 14 days |

### Outlier Handling

The 163 drivers with >1,000 cancellations should be **investigated separately** — they may have account, vehicle, or payment issues that prevent completion regardless of motivation.

---

## TASK 8 — TAXONOMY / PROGRAM IMPLICATION

The cancelled signal is strong enough to warrant a **priority boost within RNA_ONBOARDING** rather than a separate program:

```
RNA_ONBOARDING priority score += cancelled_intent_bonus
  where cancelled_intent_bonus = 
    HIGH_INTENT: +500
    MEDIUM_INTENT: +200
    LOW_INTENT: +50
```

This keeps the program structure simple while prioritizing the most promising leads.

---

## TASK 9 — GO / NO-GO

### Veredicto: **A) CANCELLED_SIGNAL_VALID_HIGH_INTENT**

| Criterion | Status |
|-----------|--------|
| Zero duplicates | PASS |
| 80% driver-side actions (rejection/non-acceptance) | PASS (real behavior, not noise) |
| 631 HIGH_INTENT actionable | PASS |
| 1,020 MEDIUM_INTENT actionable | PASS |
| Real driver identities (not artifacts) | PASS |
| Median = 6, avg distorted by outliers | PASS (understood) |
| Pilot design ready | PASS |

---

**LG-RNA-1D — VALIDATED**

*The cancelled signal is real, unique, and meaningful.*  
*80% are driver rejections — active engagement without completion.*  
*1,651 drivers ready for pilot (631 HIGH + 1,020 MEDIUM intent).*  
*Recommendation: priority boost within RNA_ONBOARDING, not separate program.*
