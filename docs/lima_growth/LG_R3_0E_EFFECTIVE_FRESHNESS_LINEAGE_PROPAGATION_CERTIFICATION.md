# LG-INFRA-R3.0E — Effective Freshness & Lineage Propagation Certification

**Date:** 2026-06-07
**Phase:** LG-INFRA-R3.0E
**Status:** CERTIFIED — FALSE FRESHNESS DETECTED & DOCUMENTED

---

## 1. EXECUTIVE SUMMARY

**FALSE FRESHNESS: DETECTED. EFFECTIVE FRESHNESS: CERTIFIED.**

The system was previously reporting 6 downstream layers as "FRESH" because their `layer_date = 2026-06-05`. However, the effective source date is **2026-06-01** — the data is 6 days stale, propagated through the entire chain. The governance endpoint now reports `STALE_PROPAGATED` for affected layers and `OPERABLE_WARNING` for the overall system.

---

## 2. EFFECTIVE SOURCE DATE PER LAYER

| Layer | Layer Date | Effective Source | Source Layer | Status |
|-------|-----------|-----------------|--------------|--------|
| norm_orders | **2026-06-01** | 2026-06-01 | NONE | **STALE** (source) |
| history_daily | 2026-06-01 | 2026-06-01 | norm_orders | STALE |
| history_weekly | 2026-06-01 | 2026-06-01 | history_daily | STALE |
| **snapshot** | **2026-06-05** | **2026-06-01** | history_weekly | **STALE_PROPAGATED** |
| eligibility | 2026-06-05 | 2026-06-01 | snapshot | STALE_PROPAGATED |
| opportunity | 2026-06-05 | 2026-06-01 | eligibility | STALE_PROPAGATED |
| prioritized | 2026-06-05 | 2026-06-01 | opportunity | STALE_PROPAGATED |
| queue | 2026-06-05 | 2026-06-01 | prioritized | STALE_PROPAGATED |
| serving | 2026-06-05 | 2026-06-01 | queue | STALE_PROPAGATED |

---

## 3. LINEAGE PROPAGATION

```
norm_orders (2026-06-01) ──STALE──► history_daily (06-01)
                                         │
                                         ▼
                                  history_weekly (06-01)
                                         │
                    ┌────────────────────┘
                    ▼
              snapshot (06-05)  ◄── STALE_PROPAGATED
                    │              (source=06-01, generated=06-05)
                    ▼
              eligibility (06-05) ◄── STALE_PROPAGATED
                    │
                    ▼
              opportunity (06-05) ◄── STALE_PROPAGATED
                    │
                    ▼
              prioritized (06-05) ◄── STALE_PROPAGATED
                    │
                    ▼
              queue (06-05) ◄── STALE_PROPAGATED
                    │
                    ▼
              serving (06-05) ◄── STALE_PROPAGATED
```

**6 layers are STALE_PROPAGATED**: they were generated for 06-05 but use data from 06-01.

---

## 4. FALSE FRESHNESS

### Before (R3.0C)

| Layer | Status |
|-------|:---:|
| snapshot | FRESH |
| eligibility | FRESH |
| opportunity | FRESH |
| prioritized | FRESH |
| queue | FRESH |
| serving | FRESH |

**This was FALSE.** The layers were "freshly generated" but built from 6-day-old stale data.

### After (R3.0E)

| Layer | Status |
|-------|:---:|
| snapshot | STALE_PROPAGATED |
| eligibility | STALE_PROPAGATED |
| opportunity | STALE_PROPAGATED |
| prioritized | STALE_PROPAGATED |
| queue | STALE_PROPAGATED |
| serving | STALE_PROPAGATED |

**This is the TRUTH.**

---

## 5. OPERABILITY RULES

| Status | Condition |
|--------|-----------|
| **OPERABLE** | All layers have effective_source = layer_date AND max_date >= today |
| **OPERABLE_WARNING** | Downstream functional but effective_source is stale (current state) |
| **NOT_OPERABLE** | Snapshot, eligibility, or prioritized has 0 rows |

---

## 6. GOVERNANCE ENDPOINT V2

`GET /yego-lima-growth/freshness-chain/status`

Returns per layer:
- `layer_date`: when the layer was generated
- `effective_source_date`: the TRUE max date of upstream data
- `effective_freshness`: FRESH / STALE / STALE_PROPAGATED / EMPTY / MISSING
- `propagated`: true if staleness was inherited from upstream

---

## 7. FILES UPDATED

| File | Change |
|------|--------|
| `backend/app/services/yego_lima_freshness_chain_service.py` | V2: effective_source_date + propagated staleness |
| `docs/lima_growth/LG_R3_0E_EFFECTIVE_FRESHNESS_LINEAGE_PROPAGATION_CERTIFICATION.md` | This document |

---

## 8. FINAL VEREDICT

```
GO — FALSE FRESHNESS CORRECTED
```

| Question | Answer |
|----------|:---:|
| ¿Existe falsa frescura? | **YES** — detected in R3.0C, corrected in R3.0E |
| ¿Se corrigió? | **YES** — STALE_PROPAGATED status added |
| ¿Effective Freshness certificada? | **YES** |
| ¿Control Foundation puede cerrarse? | **NO** — Yango ingestion must be restored first |
| ¿Cuál es la fecha efectiva real? | **2026-06-01** (6 days behind) |
| ¿Primera capa stale? | **norm_orders** (2026-06-01) |
| ¿Capas que heredan stale? | **6**: snapshot through serving |
| ¿UI muestra la verdad? | **YES** — endpoint reports STALE_PROPAGATED honestly |

**Remediation: Restore Yango API ingestion to bring effective source date current.**
