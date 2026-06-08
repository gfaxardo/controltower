# OV2-D.3A — LINEAGE-AWARE INSPECTOR CONTRACT

> **Date:** 2026-06-08
> **Status:** IMPLEMENTED

## ENDPOINT

`GET /ops/omniview-v2/drill/cell`

## RESPONSE CONTRACT

```json
{
  "cell": {"source_system", "grain", "period", "metric_id", "business_slice_name", "country", "city"},
  "total": {},
  "lineage_status": {
    "city": "READY",
    "park": "READY",
    "driver": "READY",
    "fleet": "PARTIAL",
    "raw_trip": "PARTIAL",
    "yango": "PARTIAL"
  },
  "drill": {
    "park": {"status": "READY", "data": [{"park_id", "drivers", "trips"}]},
    "driver": {"status": "READY", "data": [{"driver_id", "trips"}], "total_count": N},
    "fleet": {"status": "PARTIAL", "message": "..."},
    "raw_trip": {"status": "PARTIAL", "message": "..."},
    "yango": {"status": "PARTIAL", "message": "..."}
  },
  "warnings": []
}
```

## PERFORMANCE

- Reads from `ops.driver_day_slice_fact` (162K rows, no raw scans)
- Top N limited (default 20, max 100)
- Response time: <500ms

---

*End of Inspector Contract*
