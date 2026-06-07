# OV2-C.3A — MATRIX RENDER RULES

> **Date:** 2026-06-06
> **Motor:** Control Foundation / Matrix Data Contract

---

## 1. WHAT MATRIX ZONE CAN DO

### 1.1 Render Columns
- Receive `columns[]` from MatrixResponse
- Render each column header with label, grain indicator, period_status badge
- Apply sticky positioning to header row
- Apply current/future period visual distinction
- Sort columns by `sort_key` (already sorted by backend — frontend renders in order)

### 1.2 Render Rows
- Receive `rows[]` from MatrixResponse
- Render each row with label in sticky first column
- Apply row_status color to row label
- Handle hierarchical rows (parent_id, depth → indentation)
- Handle row expansion (is_expandable, is_expanded)
- Sort rows by `sort_key` (backend-sorted)

### 1.3 Render Cells
- Receive `cells[]` from MatrixResponse
- Look up cell by (row_id, column_id)
- Apply cell_status (from cell contract): OK, WARNING, BLOCKED, NOT_COMPARABLE
- Apply corresponding visual from OV2-C.2B Matrix Visual System
- Render formatted_value and unit
- Render badges: PARTIAL, ESTIMATED, SHADOW, DELTA, FUTURE
- Render delta in compare mode via CellDelta component
- Render "—" for null values (muted style)

### 1.4 Apply Visual States
- **OK:** white background, default text
- **WARNING:** amber-50 background, left amber border, badge
- **BLOCKED:** red-50 background, left red border, muted text
- **SELECTED:** blue ring-2, row left border blue
- **HOVER:** blue-50 background on cell + row
- **MUTED:** gray-100 background, gray-400 text, "—"
- **DISABLED:** gray-200 background, gray-400 text, no interaction
- **PARTIAL:** amber left border, PARTIAL badge
- **ESTIMATED:** purple text, ESTIMATED badge

### 1.5 Scroll Management
- Single vertical scroll container (MatrixShell)
- Synchronized horizontal scroll between header and body
- Sticky header row (position: sticky, top: 0)
- Sticky first column (position: sticky, left: 0)
- Smooth scroll to target on alert click

### 1.6 Cell Interaction
- Click cell → set selected cell → open inspector
- Hover cell → blue-50 background
- Escape → close inspector, clear selection
- Click different cell → replace selection + inspector content

### 1.7 Empty State
- When row_count === 0: render OmniviewV2EmptyState
- Message from first warning message or default "No data available"
- Show filter context to help user understand why empty

### 1.8 Loading State
- When `loading === true`: render skeleton grid
- Skeleton: 10 rows × 7 columns, shimmer animation
- Header still renders with selected grain/period context
- No blank screen at any point

### 1.9 Inspector Trigger
- Cell click → onCellClick(cellData) → open CellInspector
- CellInspector receives full cell contract
- No additional fetch needed — all data is in the cell
- Inspector content: value, source, lineage, trust, warnings

---

## 2. WHAT MATRIX ZONE CANNOT DO

### 2.1 Business Calculations (FORBIDDEN)

| Forbidden | Reason |
|-----------|--------|
| Calculate revenue | Backend computes via revenue_yego_final or revenue_partner_fee_amount |
| Calculate active_drivers | Backend computes from source tables |
| Calculate trips_per_driver | Backend derives |
| Calculate WoW/MoM/DoD | Backend computes deltas, frontend renders CellDelta |
| Calculate pacing | Not in OV2 scope yet |
| Calculate forecast | Not in Control Foundation phase |
| Calculate coverage | Backend computes coverage_pct |
| Calculate confidence | Backend assigns confidence level |

### 2.2 Source Inference (FORBIDDEN)

| Forbidden | Reason |
|-----------|--------|
| Infer source from cell data | source_system is explicit in MatrixResponse |
| Infer slice from row label | row_type and row metadata are explicit |
| Have per-source rendering logic | MatrixResponse is source-agnostic |
| Consult different endpoints per KPI | All data comes in one MatrixResponse |

### 2.3 Styling Violations (FORBIDDEN)

| Forbidden | Reason |
|-----------|--------|
| Styles scoped to metric_id | All KPIs share one visual system (OV2-C.2B) |
| Styles scoped to grain | All grains share same hover/select/muted (OV2-C.2B) |
| Hardcoded hex colors | Use CSS variables only (OV2-C.2B) |
| Per-component CSS files | One MatrixVisualSystem.css (OV2-C.2B) |
| Inline styles on cells | Use CSS classes from visual system |

### 2.4 Data Fetching (FORBIDDEN)

| Forbidden | Reason |
|-----------|--------|
| Fetch data from cell click | All data is pre-loaded in MatrixResponse.cells |
| Fetch coverage separately | coverage_pct is in MatrixResponse.metadata |
| Fetch lineage separately | lineage[] is in MatrixResponse |
| Fetch warnings separately | warnings[] is in MatrixResponse |
| Make per-cell API calls | One request = one MatrixResponse |

---

## 3. MATRIX ZONE CONTRACT

```
MatrixZone receives: MatrixResponse + loading flag + selectedCell state

MatrixZone renders:
  - MatrixHeader (columns from MatrixResponse.columns)
  - Virtualized row list (rows from MatrixResponse.rows)
  - Cells (from MatrixResponse.cells, looked up by row_id + column_id)
  - EmptyState (if row_count === 0)
  - Skeleton (if loading === true)

MatrixZone emits:
  - onCellClick(cellData) → parent opens inspector

MatrixZone does NOT:
  - Fetch data
  - Compute values
  - Know the source system (except to display source_system badge)
  - Have per-KPI branches
```

---

## 4. MATRIX ZONE PROPS

```typescript
interface MatrixZoneProps {
  matrixData: MatrixResponse | null;
  loading: boolean;
  error: Error | null;
  selectedCell: { rowId: string; columnId: string } | null;
  compareMode: boolean;
  onCellClick: (cellData: CellContract) => void;
  onRetry: () => void;
}
```
