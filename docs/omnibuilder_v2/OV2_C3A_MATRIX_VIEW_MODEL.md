# OV2-C.3A — MATRIX VIEW MODEL

> **Date:** 2026-06-06
> **Motor:** Control Foundation / Matrix Data Contract
> **Applies to:** All Omniview V2 matrices — any source, any KPI, any grain

---

## 1. PURPOSE

The MatrixResponse is the **single data contract** for every matrix in Omniview V2. It is source-agnostic: the MatrixZone component never knows whether data came from CT, Yango, or a hybrid source. It only receives MatrixResponse.

This contract builds on OV2-C.2 Cell Contract and OV2-C.2B Matrix Visual System.

---

## 2. MATRIX RESPONSE

```json
{
  "matrix_id": "ov2_main",
  "source_system": "CT_TRIPS_2026",
  "canonical_ready": true,
  "grain": "day",
  "period_range": { "from": "2026-06-01", "to": "2026-06-05" },
  "filters": { "country": "peru", "city": "lima" },
  "metadata": { "..."
  },
  "columns": [ "..."
  ],
  "rows": [ "..."
  ],
  "cells": [ "..."
  ],
  "warnings": [ "..."
  ],
  "lineage": [ "..."
  ]
}
```

### 2.1 Top-Level Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| matrix_id | string | YES | Unique identifier for this matrix instance |
| source_system | string | YES | CT_TRIPS_2026 or YANGO_API_RAW |
| canonical_ready | boolean | YES | Is source certified for operational decisions? |
| grain | string | YES | hour, day, week, month |
| period_range | object | YES | { from, to } ISO dates |
| filters | object | YES | Active filters applied |
| metadata | object | YES | Matrix metadata (see 2.2) |
| columns | array | YES | Ordered column definitions (see 3) |
| rows | array | YES | Ordered row definitions (see 4) |
| cells | array | YES | Flat array of cell data (see 5) |
| warnings | array | YES | Matrix-level warnings |
| lineage | array | YES | Lineage entries for traceability |

---

## 2.2 MatrixMetadata

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| source_status | string | YES | CURRENT_BASELINE, FUTURE_CANDIDATE, DEPRECATED |
| source_table | string | YES | Source table/view name |
| coverage_pct | number | YES | Overall coverage percentage |
| freshness | string | YES | "5m ago", "stale 2h" |
| data_date | string | YES | Max data date in this matrix |
| refreshed_at | string | YES | ISO timestamp of last refresh |
| row_count | number | YES | Total rows |
| column_count | number | YES | Total data columns |
| cell_count | number | YES | Total cells (rows × columns) |
| comparable | boolean | NO | Whether a second source exists for comparison |
| comparison_basis | string | NO | Basis for comparison (if applicable) |

---

## 3. COLUMN

```json
{
  "id": "col_2026-06-03",
  "label": "Jun 3",
  "grain": "day",
  "period": "2026-06-03",
  "period_status": "CLOSED",
  "sort_key": "2026-06-03",
  "width": 90,
  "is_current": false,
  "is_future": false
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | YES | Unique column identifier |
| label | string | YES | Display label (e.g. "Jun 3", "W23", "Jun 2026") |
| grain | string | YES | Grain of this column |
| period | string | YES | Period identifier |
| period_status | string | YES | CLOSED, PARTIAL, CURRENT, FUTURE, NO_PLAN, NO_REAL |
| sort_key | string | YES | Sort ordering (ISO date or numeric) |
| width | number | NO | Recommended pixel width (default: grain default) |
| is_current | boolean | YES | Is this the current period? (for highlight) |
| is_future | boolean | YES | Is this a future period? (for muted style) |

---

## 4. ROW

```json
{
  "id": "row_auto_regular",
  "label": "Auto regular",
  "row_type": "slice",
  "row_status": "OK",
  "parent_id": null,
  "depth": 0,
  "sort_key": "01_auto_regular",
  "is_expandable": false,
  "is_expanded": true
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | YES | Unique row identifier |
| label | string | YES | Display label (slice name or metric name) |
| row_type | string | YES | "slice", "metric", "total", "header" |
| row_status | string | YES | OK, WARNING, BLOCKED — aggregate status for the row |
| parent_id | string\|null | NO | Parent row ID for hierarchical rows |
| depth | number | YES | Indentation level (0 = root) |
| sort_key | string | YES | Sort ordering |
| is_expandable | boolean | YES | Can this row expand/collapse? |
| is_expanded | boolean | YES | Currently expanded? |

---

## 5. CELL

Extends OV2-C.2 Cell Contract. Adds coordinate fields.

```json
{
  "row_id": "row_auto_regular",
  "column_id": "col_2026-06-03",
  "... all OV2-C.2 CellContract fields ..."
}
```

### Additional fields (not in OV2-C.2 Cell Contract):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| row_id | string | YES | Links cell to its row |
| column_id | string | YES | Links cell to its column |

### Full cell contract fields (from OV2-C.2 + coordinates):

| Group | Fields |
|-------|--------|
| Coordinates | row_id, column_id |
| Identity | metric_id, label, slice_id, slice_label |
| Value | value, formatted_value, unit |
| Source | source_system, source_table, grain |
| Period | period, period_status |
| Trust | canonical_ready, coverage_pct, freshness, confidence, is_estimated |
| Warnings | warning_codes[] |
| Lineage | lineage_refs |
| Comparison | comparison_status, delta_value, delta_pct |
| Status | cell_status |

---

## 6. MATRIX WARNINGS

```json
{
  "code": "PARTIAL_COVERAGE",
  "message": "Coverage at 87% for this period range.",
  "severity": "warning",
  "target_row_id": null,
  "target_column_id": "col_2026-06-04",
  "affected_cell_count": 3
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| code | string | YES | Warning code |
| message | string | YES | Human-readable message |
| severity | string | YES | info, warning, critical |
| target_row_id | string\|null | NO | Specific row affected |
| target_column_id | string\|null | NO | Specific column affected |
| affected_cell_count | number | NO | How many cells affected |

---

## 7. MATRIX LINEAGE

```json
{
  "metric_id": "orders",
  "origin_table": "ops.real_business_slice_day_fact",
  "origin_field": "trips_completed",
  "aggregation": "SUM",
  "filters_applied": { "country": "peru", "city": "lima" }
}
```

---

## 8. CELL LOOKUP

Cells are a flat array. To find a specific cell:

```
cell = cells.find(c => c.row_id === rowId && c.column_id === columnId)
```

Alternative: backend may provide a lookup map:

```json
{
  "cells_flat": [ "..."
  ],
  "cells_by_row_col": {
    "row_auto_regular": {
      "col_2026-06-03": { "..."
      },
      "col_2026-06-04": { "..."
      }
    }
  }
}
```

Frontend chooses flat array for virtualization performance. Backend provides both formats at its discretion.

---

## 9. EMPTY MATRIX

When no data:

```json
{
  "matrix_id": "ov2_main",
  "source_system": "CT_TRIPS_2026",
  "canonical_ready": true,
  "grain": "day",
  "period_range": { "from": "2026-06-04", "to": "2026-06-04" },
  "filters": {},
  "metadata": {
    "source_status": "CURRENT_BASELINE",
    "coverage_pct": 0,
    "row_count": 0,
    "column_count": 0,
    "cell_count": 0
  },
  "columns": [],
  "rows": [],
  "cells": [],
  "warnings": [{
    "code": "NO_DATA",
    "message": "No data available for the selected period.",
    "severity": "warning"
  }],
  "lineage": []
}
```

MatrixZone renders OmniviewV2EmptyState when row_count === 0.
