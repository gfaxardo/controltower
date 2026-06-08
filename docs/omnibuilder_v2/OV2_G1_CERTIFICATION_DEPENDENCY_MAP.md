# OV2-G.1 — CERTIFICATION DEPENDENCY MAP

> **Date:** 2026-06-08
> **Status:** MAP DEFINED

---

```
                       ┌─────────────────────┐
                       │   public.trips_2026  │  ← RAW (ELT source)
                       │   raw_yango.*        │
                       └────────┬────────────┘
                                │
                       ┌────────▼────────────┐
                       │ driver_day_slice_fact│  ← BRIDGE
                       │ Owner: build_bridge  │     Writer: build_driver_bridge_direct.py
                       │ Scheduler: cascade   │     Freshness: trips_2026 MAX
                       └────────┬────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                  │
     ┌────────▼────────┐ ┌─────▼──────┐  ┌────────▼────────┐
     │ day_fact        │ │ week_fact  │  │ month_fact      │
     │ (REAL_SHARED)   │ │(REAL_SHARED)│  │ (REAL_SHARED)   │
     │ Writer: rebuild │ │Writer: day  │  │ Writer: day     │
     │ _day_from_bridge│ │+bridge      │  │ +bridge         │
     └────────┬────────┘ └─────┬──────┘  └────────┬────────┘
              │                │                   │
              │         ┌──────▼──────┐            │
              │         │  V1 WEEK    │            │
              │         │  (reads     │            │
              │         │   week_fact)│            │
              │         └─────────────┘            │
              │                                    │
     ┌────────▼────────┐                  ┌────────▼────────┐
     │ SNAPSHOT        │                  │ PLAN_VS_REAL    │
     │ (SNAPSHOT_SHARED)│                 │ (V2 only)       │
     │ Writer: refresh │                  │ reads:          │
     │ _snapshots      │                  │ month_fact      │
     └────────┬────────┘                  │ + plan_trips    │
              │                           └─────────────────┘
     ┌────────▼────────┐
     │ V2 MATRIX       │
     │ V2 SHELL        │
     │ (snapshot-first)│
     └────────┬────────┘
              │
     ┌────────▼────────┐
     │ V2 INSPECTOR    │
     │ (drill endpoint)│
     │ reads: bridge   │
     └─────────────────┘
```

## DEPENDENCY CHAIN

```
If RAW is stale → ALL downstream stale
If BRIDGE is stale → day_fact, week_fact, month_fact, drill stale
If DAY is stale → week_fact, month_fact, snapshots stale
If WEEK is stale → V1 weekly, V2 week grain stale
If MONTH is stale → V2 month grain, Plan vs Real stale
If SNAPSHOT is stale → V2 UI shows old data or MISSING
```

---

*End of Dependency Map*
