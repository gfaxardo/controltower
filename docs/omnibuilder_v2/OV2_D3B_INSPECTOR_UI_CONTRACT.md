# OV2-D.3B — INSPECTOR UI CONTRACT

> **Date:** 2026-06-08
> **Status:** BACKEND READY — UI INTEGRATION DOCUMENTED

## ENDPOINT

```
GET /ops/omniview-v2/drill/cell?period=2026-06-06&business_slice_name=Auto%20regular&grain=day&metric_id=trips
```

## RESPONSE → UI MAPPING

| API Field | Inspector Display |
|-----------|------------------|
| `cell.metric_id` | KPI label |
| `cell.grain` | Grain badge |
| `cell.period` | Period header |
| `cell.business_slice_name` | Slice label |
| `drill.park.data[]` | Park breakdown table (park_id, drivers, trips) |
| `drill.driver.data[]` | Top-N driver list (driver_id, trips) |
| `drill.driver.total_count` | "X drivers total" |
| `lineage_status.city` | ✅ READY badge |
| `lineage_status.park` | ✅ READY badge |
| `lineage_status.driver` | ✅ READY badge |
| `lineage_status.fleet` | ⚠️ PARTIAL badge |
| `lineage_status.raw_trip` | ⚠️ PARTIAL badge |
| `lineage_status.yango` | ⚠️ PARTIAL badge |

## EXISTING FRONTEND

`CellInspector.jsx` already renders cell values, source info, warnings. Integration with `/drill/cell` requires adding park/driver/lineage sections.

## PERFORMANCE

- Response: <500ms (bridge-based, no raw scans)
- Driver limit: 20 (configurable)
- Park limit: unlimited (max ~6 per city)
