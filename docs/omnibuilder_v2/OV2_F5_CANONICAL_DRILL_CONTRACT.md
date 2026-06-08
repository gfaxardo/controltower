# OV2-F.5 — CANONICAL DRILL CONTRACT

> **Date:** 2026-06-08
> **Status:** DEFINED

---

## 1. INPUT

```json
{
  "source_system": "CT_TRIPS_2026",
  "grain": "month",
  "period": "2026-05-01",
  "metric_id": "trips",
  "business_slice": "Auto regular"
}
```

## 2. OUTPUT

```json
{
  "total_value": 373681,
  "unit": "count",
  "breakdowns": {
    "by_park": [
      {"park_id": "08e20910d81d42658d4334d3f6d10ac0", "value": 373681}
    ],
    "by_driver": [
      {"driver_id": "abc123", "trips": 150, "revenue": 3500.0, "completed_at": "2026-05-15T10:30:00Z"}
    ]
  },
  "metadata": {
    "source_table": "ops.real_business_slice_month_fact",
    "lineage_confidence": "HIGH",
    "freshness": "2026-06-07T04:00:00Z",
    "warnings": []
  }
}
```

## 3. DRILL DEPTHS

| Depth | Endpoint | Status |
|-------|----------|--------|
| 1 — Park | `GET /ops/omniview-v2/drill/park` | READY (bridge.park_id) |
| 2 — Fleet | `GET /ops/omniview-v2/drill/fleet` | PARTIAL |
| 3 — Subfleet | `GET /ops/omniview-v2/drill/subfleet` | PARTIAL |
| 4 — Driver | `GET /ops/omniview-v2/drill/driver` | READY (bridge.driver_id) |
| 5 — Raw trip | `GET /ops/omniview-v2/drill/raw-trip` | PARTIAL |

## 4. NOT YET IMPLEMENTED

Endpoints are defined but not built. Backlog for drill serving architecture.

---

*End of Drill Contract*
