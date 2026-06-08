# OV2-F.1 — CELL LINEAGE CONTRACT

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Refresh Chain
> **Status:** DEFINED — PARTIAL IMPLEMENTATION

---

## 1. CELL LINEAGE SCHEMA

Every cell in Omniview V2 must be traceable to its source with this contract:

```json
{
  "cell_id": "row_auto_regular|col_2026-03",
  "source_system": "CT_TRIPS_2026",
  "raw_source": {
    "table": "public.trips_2026",
    "primary_key": "order_id",
    "date_column": "fecha_inicio_viaje",
    "filters": {
      "country": "peru",
      "city": "lima"
    }
  },
  "fact_table": {
    "name": "ops.real_business_slice_month_fact",
    "type": "monthly_aggregation",
    "from": "ops.real_business_slice_day_fact",
    "aggregation": "SUM() GROUP BY month, business_slice_name"
  },
  "snapshot": {
    "id": "snap_20260605_ct_trips_2026_day_matrix",
    "hash": "a1b2c3d4e5f6a7b8",
    "generated_at": "2026-06-05T04:05:00Z",
    "status": "READY",
    "coverage_pct": 99.6
  },
  "business_slice": {
    "name": "Auto regular",
    "mapped_from": "auto_taxi"
  },
  "metric": {
    "id": "trips",
    "label": "Trips",
    "unit": "count",
    "plan_column": "projected_trips",
    "real_column": "trips_completed"
  },
  "period": {
    "grain": "month",
    "value": "2026-03-01",
    "status": "CLOSED"
  },
  "confidence": "HIGH",
  "warnings": [],
  "last_refreshed_at": "2026-06-07T04:00:00Z"
}
```

## 2. IMPLEMENTATION STATUS

| Field | Status | Location |
|-------|--------|----------|
| `source_system` | ✓ IMPLEMENTED | `OmniviewV2MatrixCell.source_system` |
| `raw_source` | PARTIAL | Not in cell — available in `operations.py` lineage endpoints |
| `fact_table` | ✓ IMPLEMENTED | `OmniviewV2MatrixCell.source_table` + `lineage_refs` |
| `snapshot` | ✓ IMPLEMENTED | `OmniviewV2MatrixResponse.metadata` (when served from snapshot) |
| `business_slice` | ✓ IMPLEMENTED | `OmniviewV2MatrixRow.label` + `OmniviewV2MatrixCell.slice_label` |
| `metric` | ✓ IMPLEMENTED | `OmniviewV2MatrixCell.metric_id`, `label`, `unit` |
| `period` | ✓ IMPLEMENTED | `OmniviewV2MatrixColumn.period` + `period_status` |
| `confidence` | ✓ IMPLEMENTED | `OmniviewV2MatrixCell.confidence` |
| `warnings` | ✓ IMPLEMENTED | `OmniviewV2MatrixCell.warning_codes` |
| `last_refreshed_at` | PARTIAL | In `metadata.refreshed_at` when snapshot-served |

## 3. LINEAGE BY SOURCE SYSTEM

### CT_TRIPS_2026

```
cell → ops.real_business_slice_{grain}_fact
     → public.trips_2026 (raw)
     → Rider app (source of truth)
```

### YANGO_API_RAW

```
cell → raw_yango.mv_orders_day
     → Yango Fleet API GET /v1/parks/orders/list
     → Yango platform (source of truth)
```

## 4. LINEAGE FOR PLAN VS REAL

```
plan column:
  cell → ops.plan_trips_monthly → plan_template_parser → Excel template

real column:
  cell → ops.real_business_slice_month_fact → trips_2026

gap:
  cell.comparison_status ← ABS(real - plan) / plan * 100
```

## 5. LINEAGE IN CELL INSPECTOR (UI)

The `CellInspector.jsx` component already renders:
- `source_system` → "CT_TRIPS_2026"
- `source_table` → "ops.real_business_slice_day_fact"
- `coverage_pct` → 99.6
- `confidence` → "HIGH"
- `lineage_refs.plan_table` → Plan vs Real source
- `lineage_refs.real_table` → Real data source
- `comparison_status` → ON_TRACK/WATCH/OFF_TRACK

## 6. GAPS

| Gap | Severity | Plan |
|-----|----------|------|
| `raw_source` details not in cell inspector | P2 | Add `raw_source_table` + `raw_source_filter` to cell |
| `snapshot_id` / `payload_hash` not shown | P3 | Add to metadata when snapshot-served |
| `owner` not in plan data lineage | P3 | Plan `ownership` table integration pending |
| No drill-down from cell to raw trips | P2 | See `OV2_F1_DRILL_READINESS_AUDIT.md` |
| No Yango reconciliation lineage | P2 | See `OV2_F1_YANGO_RECONCILIATION_DESIGN.md` |

---

*End of Cell Lineage Contract*
