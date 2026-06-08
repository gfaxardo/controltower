# OV2-G.1 — SINGLE CANONICAL WEEKLY CHAIN

> **Date:** 2026-06-08
> **Status:** CHAIN CERTIFIED — 1 writer per layer

---

## 1. CANONICAL CHAIN

```
RAW (trips_2026)
  → 1 writer: ELT ingestion (external)
  → Freshness: MAX(fecha_inicio_viaje)

BRIDGE (driver_day_slice_fact)
  → 1 writer: build_driver_bridge_direct.py
  → Scheduler: cascade only
  → Freshness: MAX(activity_date)

DAY (real_business_slice_day_fact)
  → 1 writer: rebuild_day_from_bridge.py
  → Scheduler: cascade only
  → Freshness: MAX(trip_date)

WEEK (real_business_slice_week_fact)
  → 1 writer: rebuild_week_from_day_and_bridge.py
  → Scheduler: cascade only
  → Freshness: MAX(week_start)

MONTH (real_business_slice_month_fact)
  → 1 writer: rebuild_month_from_day_and_bridge.py
  → Scheduler: cascade only
  → Freshness: MAX(month)
```

## 2. VERIFICATION

| Layer | Writer Count | Status |
|-------|-------------|--------|
| RAW | 1 (external) | ✅ |
| BRIDGE | 1 | ✅ |
| DAY | 1 | ✅ |
| WEEK | 1 | ✅ |
| MONTH | 1 | ✅ |
| SNAPSHOT | 1 | ✅ |

## 3. EXCEPTIONS

| Exception | Resolution |
|-----------|------------|
| Legacy scheduler jobs (nd=0, nw=0, nm=0) | Code in place, but __pycache__ can regress |
| Manual rebuild scripts exist | Used for recovery only, not scheduled |

---

*End of Canonical Weekly Chain*
