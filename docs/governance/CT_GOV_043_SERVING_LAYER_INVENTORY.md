# CT-GOV-043 — Serving Layer Inventory

**Date:** 2026-06-08
**Motor:** Control Foundation / Global Freshness Governance
**Status:** CANONICAL

---

## 1. SERVING LAYERS

### 1.1 Omniview

| Layer | Source Tables | Refresh Owner | Scheduler | Layer Date | Eff Source Date |
|-------|--------------|---------------|-----------|------------|-----------------|
| day_fact | trips_2026, driver_day_slice_fact | APScheduler 04:00 daily | `omniview_business_slice_real_refresh` | D-1 (06-06) | trips_2026 max (06-06) |
| week_fact | day_fact + driver_day_slice_fact | bridge cascade orchestrator | Manual/on-demand | 06-01 (STALE) | day_fact max |
| month_fact | day_fact + driver_day_slice_fact | bridge cascade orchestrator | Manual/on-demand | 06-01 (OK) | day_fact max |
| serving_snapshot | day_fact, week_fact, month_fact | refresh_omniview_v2_snapshots | cascade orchestrator | 06-05 | day_fact max |
| driver_day_slice_fact | trips_2026 | build_driver_bridge_direct | cascade orchestrator | D-0 | trips_2026 |

### 1.2 Lima Growth

| Layer | Source Tables | Refresh Owner | Scheduler | Layer Date | Eff Source Date |
|-------|--------------|---------------|-----------|------------|-----------------|
| orders_raw | Yango API, raw_yango | normalization (upsert_raw_orders) | On-demand/lab | 06-04 | Yango API last fetch |
| driver_history_daily | trips_2025, trips_2026 | bootstrap_history | Manual/lab | 06-04 | trips max date |
| driver_history_weekly | history_daily | auto-aggregation | Daily pipeline | 06-01 (week) | history_daily max |
| driver_state_snapshot | history_weekly + driver_360 | build_driver_state_snapshot | Daily pipeline | 06-05 | history_weekly max |
| program_eligibility | snapshot | build_program_eligibility | Daily pipeline | 06-05 | snapshot date |
| prioritized_opportunity | daily_opportunity_list | build_prioritized_opportunities | Policy engine | 06-05 | opportunity date |
| assignment_queue | prioritized | create_assignment_batch | Daily refresh | 06-05 | prioritized date |
| serving_fact (8) | multiple operational tables | generate_all_serving_facts | Daily refresh | 06-05 | operational dates |
| intraday_signal | orders_raw, assignment_queue | autonomous_tick | APScheduler 5min | 06-05 | orders_raw max |

### 1.3 Loyalty (Yango)

| Layer | Source Tables | Refresh Owner | Layer Date |
|-------|--------------|---------------|------------|
| loyalty_sub50_weekly | driver_360 + history_weekly | build_loyalty_sub50 | 06-02 |

### 1.4 Scout Liquidator

| Layer | Source Tables | Refresh Owner | Layer Date |
|-------|--------------|---------------|------------|
| Not operational | — | — | — |

### 1.5 Projection Engine

| Layer | Source Tables | Refresh Owner | Layer Date |
|-------|--------------|---------------|------------|
| omniview_projection_daily_fact | plan tables | projection service | Current month |

---

## 2. OWNERSHIP SUMMARY

| Domain | Active Schedulers | Refresh Cadence | Gap Risk |
|--------|:---:|----------------|:---:|
| Omniview | 3 APScheduler jobs | day: 04:00, week: manual, month: manual | week_fact 48d behind |
| Lima Growth | 1 APScheduler job (5min) + manual pipeline | daily pipeline + 5min tick | history bootstrap gap |
| Loyalty | Manual | on-demand | Dormant |
| Scout | None | N/A | N/A |
| Projection | None | on-demand | Current month only |

---

## FIRMA

```
CT-GOV-043 SERVING LAYER INVENTORY
Date: 2026-06-08
Status: CANONICAL
```
