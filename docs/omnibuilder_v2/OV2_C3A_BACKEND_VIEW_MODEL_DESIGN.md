# OV2-C.3A — BACKEND VIEW MODEL DESIGN

> **Date:** 2026-06-06
> **Motor:** Control Foundation / Matrix Data Contract
> **Status:** DESIGN — Not Implemented

---

## 1. SERVICE DESIGN

### File: `backend/app/services/omniview_v2_matrix_view_model_service.py`

This service transforms source-native data into the unified MatrixResponse contract. It is the **single translation layer** between source repositories and the frontend matrix.

#### Functions

```python
def build_matrix_response(
    source_system: str,
    grain: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    filters: Optional[Dict] = None,
) -> OmniviewV2MatrixResponse:
    """
    Main entry point. Builds complete MatrixResponse for any source/grain.
    
    1. Validate source and grain
    2. Get raw data from source repository
    3. Build columns from period range
    4. Build rows from data grouping
    5. Build cells from pivoted data
    6. Attach metadata, warnings, lineage
    7. Return MatrixResponse
    """

def build_columns(
    grain: str,
    period_from: str,
    period_to: str,
    period_status_map: Dict[str, str] = None,
) -> List[OmniviewV2MatrixColumn]:
    """
    Generate ordered column list for the period range.
    - hour: 24 columns × days in range
    - day: one column per day
    - week: one column per ISO week
    - month: one column per month
    Each column gets period_status (CLOSED/PARTIAL/CURRENT/FUTURE).
    """

def build_rows(
    source_system: str,
    raw_data: List[Dict],
    filters: Dict,
) -> List[OmniviewV2MatrixRow]:
    """
    Extract unique row identifiers from raw data.
    - CT: rows = business_slice_name values
    - Yango: rows = single "Lima fleet" row (or per-park in future)
    Returns sorted rows with row_type, depth, expandability.
    """

def build_cells(
    source_system: str,
    grain: str,
    rows: List[OmniviewV2MatrixRow],
    columns: List[OmniviewV2MatrixColumn],
    raw_data: List[Dict],
    filters: Dict,
) -> List[OmniviewV2MatrixCell]:
    """
    Pivot raw data into (row, column) cells.
    For each (row, column) combination:
    1. Look up raw value
    2. Normalize to CellContract
    3. Attach lineage
    4. Attach warnings
    5. Compute cell_status
    """

def normalize_cell(
    raw_value: Any,
    metric_id: str,
    source_system: str,
    grain: str,
) -> OmniviewV2MatrixCell:
    """
    Convert a raw DB value into a CellContract-compliant cell.
    - Format numeric values
    - Attach unit
    - Set confidence based on metric and source
    - Set is_estimated flag
    """

def attach_lineage(
    cell: OmniviewV2MatrixCell,
    source_system: str,
    grain: str,
    metric_id: str,
) -> OmniviewV2MatrixCell:
    """
    Populate lineage_refs from source registry.
    Uses get_lineage() from omniview_v2_source_repository.
    """

def attach_warnings(
    cell: OmniviewV2MatrixCell,
    source_system: str,
) -> OmniviewV2MatrixCell:
    """
    Attach cell-level warnings:
    - coverage < 95% → PARTIAL_COVERAGE
    - delta > 5% → REVENUE_DELTA
    - period_status = PARTIAL → PARTIAL_PERIOD
    - value is null → VALUE_MISSING
    """

def build_metadata(
    source_system: str,
    grain: str,
    rows_count: int,
    columns_count: int,
    cells_count: int,
    filters: Dict,
) -> OmniviewV2MatrixMetadata:
    """
    Build metadata block from source registry + computed counts.
    """

def get_comparison_matrix(
    source_a: str,
    source_b: str,
    grain: str,
    date_from: str,
    date_to: str,
    filters: Dict,
) -> Dict:
    """
    Build two MatrixResponse objects and merge with delta computation.
    Used by compare mode.
    """
```

---

## 2. REPOSITORY DESIGN

### File: `backend/app/repositories/omniview_v2_matrix_repository.py`

This repository abstracts source-specific queries. Returns raw data dicts that the service transforms into MatrixResponse.

#### Functions

```python
def get_ct_matrix_data(
    grain: str,
    date_from: str,
    date_to: str,
    country: str = "peru",
    city: str = "lima",
) -> List[Dict]:
    """
    Query ops.real_business_slice_{grain}_fact for matrix raw data.
    
    Returns rows with:
    - period_date (grain key)
    - business_slice_name (row key)
    - trips_completed, revenue_yego_final, active_drivers, etc.
    
    SQL pattern:
        SELECT {grain_key} AS period_date,
               business_slice_name,
               SUM(trips_completed) AS trips_completed,
               SUM(revenue_yego_final) AS revenue_yego_final,
               ...
        FROM ops.real_business_slice_{grain}_fact
        WHERE country = %s AND city = %s
          AND {grain_key} BETWEEN %s AND %s
        GROUP BY {grain_key}, business_slice_name
        ORDER BY {grain_key}, business_slice_name
    """

def get_yango_matrix_data(
    date_from: str,
    date_to: str,
    park_id: str = "08e20910...",
) -> List[Dict]:
    """
    Query raw_yango MVs for matrix raw data.
    
    Returns rows with:
    - period_date (order_date)
    - fleet_label = "Lima fleet" (single row for now)
    - orders_completed, revenue_partner_fee_amount, unique_drivers
    
    SQL pattern:
        SELECT o.order_date AS period_date,
               'Lima fleet' AS fleet_label,
               o.orders_completed,
               r.revenue_partner_fee_amount,
               ...
        FROM raw_yango.mv_orders_day o
        LEFT JOIN raw_yango.mv_revenue_day r ON ...
        WHERE o.park_id = %s
          AND o.order_date BETWEEN %s AND %s
        ORDER BY o.order_date
    """

def get_comparison_matrix_data(
    source_a: str,
    source_b: str,
    grain: str,
    date_from: str,
    date_to: str,
    filters: Dict,
) -> Tuple[List[Dict], List[Dict]]:
    """
    Fetch raw data from both sources and return as tuple.
    """
```

---

## 3. MIGRATION STRATEGY

| Phase | Action |
|-------|--------|
| OV2-C.3A | Design only. No implementation. |
| OV2-C.3B | Implement `omniview_v2_matrix_contract.py` (dataclasses) |
| OV2-C.3B | Implement `omniview_v2_matrix_repository.py` (CT source only) |
| OV2-C.3C | Implement `omniview_v2_matrix_view_model_service.py` (MatrixResponse builder) |
| OV2-C.3C | Wire to `/ops/omniview-v2/matrix` endpoint |
| OV2-C.4 | Add Yango source support |
| OV2-C.5 | Add compare mode support |
| OV2-C.6 | Add hybrid source support |

---

## 4. DEPENDENCY MAP

```
omniview_v2_matrix_contract.py          (dataclasses)
    ↓
omniview_v2_matrix_repository.py        (raw data queries)
    ↓
omniview_v2_matrix_view_model_service.py (transformation)
    ↓
omniview_v2 router → /matrix endpoint   (API exposure)
    ↓
MatrixZone React component              (rendering)
```

---

## 5. GOVERNANCE

| Rule | Status |
|------|--------|
| No implementation yet | PASS (design only) |
| No UI touched | PASS |
| No V1 touched | PASS |
| No serving productivo changed | PASS |
| Source-agnostic design | PASS |
| All sources produce same MatrixResponse | PASS |
