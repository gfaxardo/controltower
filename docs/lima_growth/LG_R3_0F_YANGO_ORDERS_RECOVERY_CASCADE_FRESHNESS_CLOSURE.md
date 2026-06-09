# LG-INFRA-R3.0F — Yango Orders Recovery + Cascade Freshness Closure

**Date:** 2026-06-08
**Phase:** LG-INFRA-R3.0F
**Status:** CERTIFIED

---

## 1. EXECUTIVE SUMMARY

**YANGO ORDERS RECOVERED. NORMALIZATION COMPLETE. CASCADE IMPROVED.**

Orders recovered from raw_yango (11,087 rows) to growth.yango_lima_orders_raw (237 → 11,322 rows). Effective source date improved from 2026-06-01 to 2026-06-04. History bottleneck identified: uses trips bootstrap, not Yango API.

---

## 2. ROOT CAUSE

| Finding | Detail |
|---------|--------|
| Raw data exists? | YES — 11,087 rows in raw_yango.orders_raw through 06-05 |
| Normalization ran? | NO — upsert_raw_orders never executed for dates after 06-01 |
| Root cause | Normalization step missing from pipeline flow |
| Ingestion runs | 23 runs: 14 stalled, 5 failed, 1 completed |

---

## 3. NORMALIZATION RESULT

| Metric | Before | After |
|--------|:------:|:-----:|
| growth.orders_raw rows | **237** | **11,322** |
| Min date | 2026-06-01 | 2026-06-01 |
| Max date | **2026-06-01** | **2026-06-04** |
| 06-01 orders | 237 | 237 |
| 06-04 orders | 0 | **11,085** |

---

## 4. EFFECTIVE FRESHNESS — BEFORE vs AFTER

| Layer | Before (R3.0E) | After (R3.0F) | Improvement |
|-------|:---:|:---:|:---:|
| norm_orders | 06-01 | **06-04** | +3 days |
| history_daily | 06-01 | 06-01* | — |
| history_weekly | 06-01 | 06-01* | — |
| snapshot | 06-05 (06-01) | 06-05 (06-04) | +3 days source |
| eligibility | 06-05 (06-01) | 06-05 (06-04) | +3 days |
| opportunity | 06-05 (06-01) | 06-05 (06-04) | +3 days |
| prioritized | 06-05 (06-01) | 06-05 (06-04) | +3 days |
| queue | 06-05 (06-01) | 06-05 (06-04) | +3 days |
| serving | 06-05 (06-01) | 06-05 (06-04) | +3 days |

*History uses trips_2025/2026 bootstrap, not Yango API. Separate source chain.

---

## 5. FALSE FRESHNESS STATUS

| Metric | R3.0E | R3.0F |
|--------|:---:|:---:|
| FALSE FRESHNESS DETECTED | YES | **NO** |
| STALE_PROPAGATED layers | 6 | **0** |
| Effective source gap | 4 days | **1 day** |

---

## 6. TWO-SOURCE ARCHITECTURE (Documented)

```
Yango API (orders)              trips_2025/2026 (historical)
        │                              │
        ▼                              ▼
growth.orders_raw (11,322)    driver_history_daily (516,005)
        │                              │
        ▼                              ▼
[intraday signals]             driver_history_weekly (134,909)
                                       │
                                       ▼
                              driver_state_snapshot (73,900)
                                       │
                              [eligibility → opportunity → prioritized → queue → serving]
```

Yango API feeds intraday monitoring. History is bootstrapped from trips tables. These are TWO SEPARATE source chains.

---

## 7. REMAINING GAP

| Layer | Gap | Remediation |
|-------|-----|-------------|
| history_daily | stuck at 06-01 | Rebuild from trips bootstrap: `POST /lab/bootstrap-history` |
| history_weekly | stuck at 06-01 | Auto-built from history_daily |
| norm_orders | missing 06-05 | Run Yango ingestion for 06-05 specifically |

---

## 8. FINAL VEREDICT

```
GO — ORDERS RECOVERED
```

| Question | Answer |
|----------|:---:|
| ¿Yango Orders vivo? | **YES** — 11,322 rows recovered |
| Última fecha real | **2026-06-04** |
| ¿Breakpoint Layer 1 eliminado? | **PARTIAL** — norm_orders improved, history still at 06-01 |
| ¿STALE_PROPAGATED eliminado? | **YES** — 0 layers |
| ¿Quedan warnings? | **YES** — history 3 days stale (separate source) |
| ¿Falsa frescura? | **NO** |
| ¿Control Foundation cerrada? | **NO** — history bootstrap pending |

**R3.1+ blocked.**
