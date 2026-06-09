# CT-GOV-043 — Freshness SLA Registry

**Date:** 2026-06-08
**Motor:** Control Foundation / Global Freshness Governance
**Status:** CANONICAL

---

## 1. SLA BY DOMAIN

### Omniview

| Layer | Target Freshness | Max Gap | Current | Compliant? |
|-------|:---:|:---:|:---:|:---:|
| RAW trips | D-1 | 48h | D-1 (06-06) | YES |
| day_fact | D-1 | 48h | 06-06 | YES |
| week_fact | D-7 | 14d | 06-01 (48d!) | **NO** |
| month_fact | D-30 | 45d | 06-01 | YES |
| serving_snapshot | D-2 | 72h | 06-05 | YES |
| operating_date | D-1 | 48h | 06-06 | YES |

### Lima Growth

| Layer | Target Freshness | Max Gap | Current | Compliant? |
|-------|:---:|:---:|:---:|:---:|
| orders_raw | D-1 | 48h | 06-04 | OK |
| history_daily | D-1 | 48h | 06-04 | OK |
| history_weekly | D-7 | 14d | 06-01 | OK (week boundary) |
| driver_state_snapshot | D-1 | 48h | 06-05 | YES |
| program_eligibility | D-0 | 24h | 06-05 | YES |
| prioritized_opportunity | D-0 | 24h | 06-05 | YES |
| assignment_queue | D-0 | 24h | 06-05 | YES |
| serving_fact (8) | D-0 | 24h | 06-05 | YES |
| intraday_signal | 5min | 1h | 06-05 (last tick) | YES |

### Loyalty

| Layer | Target Freshness | Current | Compliant? |
|-------|:---:|:---:|:---:|
| loyalty_sub50 | D-7 | 06-02 | NO |

---

## 2. SLA VIOLATIONS

| # | Domain | Layer | Gap | Severity | Remediation |
|---|--------|-------|-----|:---:|-------------|
| 1 | Omniview | week_fact | 48 days | **CRITICAL** | Run bridge cascade: day_fact -> week_fact |
| 2 | Lima Growth | history_weekly | 7 days | LOW | Week boundary — auto-resolves next Monday |
| 3 | Loyalty | loyalty_sub50 | 6 days | MEDIUM | Run `build_loyalty_sub50` |

---

## 3. MONITORING REQUIREMENTS

| Check | Frequency | Owner |
|-------|-----------|-------|
| SLA compliance scan | Daily 06:00 | APScheduler / governance watchdog |
| Gap alert if > max | Every 15 min | Omniview watchdog |
| False freshness scan | On every refresh | Freshness chain service |
| STALE_PROPAGATED check | On every serving generation | Effective source date contract |

---

## FIRMA

```
CT-GOV-043 FRESHNESS SLA REGISTRY
Date: 2026-06-08
Status: CANONICAL
```
