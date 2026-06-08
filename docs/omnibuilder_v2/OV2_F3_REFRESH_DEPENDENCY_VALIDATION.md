# OV2-F.3 — REFRESH DEPENDENCY VALIDATION

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Freshness Chain
> **Status:** AUDIT COMPLETE

---

## 1. ACTUAL DEPENDENCY DAG

```
RAW (trips_2026)
  ↓  ← driver bridge reads raw (batched, 3-day)
BRIDGE (driver_day_slice_fact)     [MANUAL — not automatic]
  ↓  ← week reads bridge for drivers + day_fact for trips/revenue
WEEK (week_fact)                   [MANUAL — F.2E rebuild]
  ↓  ← month reads... RAW (not week/bridge!)
MONTH (month_fact)                 [AUTOMATIC — raw path, stale logic]
  ↓  ← snapshots read day_fact + shell service (heavy)
SNAPSHOT (serving_snapshot)        [MANUAL — timed out during F.2E]
  ↓
UI (shell, matrix endpoints)       [AUTOMATIC — reads snapshots]
```

## 2. DEPENDENCY GAPS

| Layer | Upstream | Expected Source | Actual Source | Status |
|-------|----------|----------------|---------------|--------|
| Bridge | RAW | trips_2026 | trips_2026 | **OK** (by design) |
| Day | Bridge | bridge aggregation | raw enriched + resolution | **FAIL** (uses raw) |
| Week | Day + Bridge | day_fact + bridge | day_fact + bridge | **OK** (F.2E fix) |
| Month | Week + Bridge | week or bridge | raw enriched | **FAIL** (uses raw) |
| Snapshot | Day | day_fact | day_fact via shell service | **OK** |

## 3. WHAT MUST BE FIXED

1. day_fact must use bridge for drivers (not raw)
2. month_fact must use bridge or week_fact for drivers (not raw)
3. Bridge rebuild must be automatic (not manual F.2E script)

---

*End of Dependency Validation*
