# OV2-F.5 — DRILL SERVING ARCHITECTURE

> **Date:** 2026-06-08
> **Status:** DESIGNED

---

## 1. ARCHITECTURE

```
RAW (trips_2026)
  ↓
DRIVER DAY SLICE BRIDGE (driver_day_slice_fact)  ← existing
  ↓
DRILL SERVING FACTS (new)
  ├── ops.drill_park_day_fact     (park-level aggregates)
  ├── ops.drill_driver_day_fact   (driver-level aggregates, pre-joined with bridge)
  └── ops.drill_fleet_day_fact    (fleet-level, needs mapping rules)
  ↓
DRILL ENDPOINTS
  ├── GET /ops/omniview-v2/drill/park?period=&slice=
  ├── GET /ops/omniview-v2/drill/driver?period=&slice=
  ├── GET /ops/omniview-v2/drill/fleet?period=&slice=
  └── GET /ops/omniview-v2/drill/raw-trip?driver_id=&date=
  ↓
UI (cell inspector → drill panel)
```

## 2. SERVING FACTS (NOT YET BUILT)

| Table | Grain | Source | Backlog |
|-------|-------|--------|---------|
| `ops.drill_park_day_fact` | park × day × slice | bridge aggregation | P2 |
| `ops.drill_driver_day_fact` | driver × day × slice | bridge (already exists!) | P2 |
| `ops.drill_fleet_day_fact` | fleet × day × slice | business_slice_mapping_rules | P2 |

## 3. RUNTIME RULE

- Park/driver drill: read from bridge (162K rows, fast)
- Fleet drill: read from business_slice_mapping_rules (static)
- Raw trip drill: read from trips_2026 with driver_id + date filter (acceptable)
- NO runtime 6.8M row scans
- NO full rebuild on query

## 4. IMPLEMENTATION STATUS

| Component | Status |
|-----------|--------|
| Bridge exists | ✅ |
| Drill endpoints | ❌ Not built |
| Drill serving facts | ❌ Not built |
| UI drill panel | ❌ Not built |
| Contract defined | ✅ (this document) |

---

*End of Drill Serving Architecture*
