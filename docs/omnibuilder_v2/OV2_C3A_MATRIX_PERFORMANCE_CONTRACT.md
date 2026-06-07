# OV2-C.3A — MATRIX PERFORMANCE CONTRACT

> **Date:** 2026-06-06
> **Motor:** Control Foundation / Matrix Data Contract

---

## 1. VIRTUALIZATION

| Rule | Spec |
|------|------|
| Trigger | Row count > 100 |
| Library | react-window (FixedSizeList) or @tanstack/virtual |
| Row height | Fixed 40px (from OV2-C.2B) |
| Overscan | 5 rows above and below viewport |
| Column virtualization | Not required until column count > 50 |
| Sticky elements | Header and first column rendered outside virtual list, CSS sticky |

### Implementation note:
```
<MatrixShell>
  <MatrixHeader />             {/* outside virtual list, sticky */}
  <VirtualList rowCount={rows.length} rowHeight={40}>
    {({ index, style }) => (
      <MatrixRow style={style}>
        <RowLabel />           {/* sticky first column */}
        {columns.map(col => (
          <MatrixCell />       {/* regular cells */}
        ))}
      </MatrixRow>
    )}
  </VirtualList>
</MatrixShell>
```

---

## 2. MEMOIZATION

### 2.1 Row Memoization
```
MatrixRow: React.memo with comparison on row.id + row.row_status
Re-renders only when:
- Row data changes (row_status, is_expanded)
- Cell data in this row changes (any cell value changes)
- Selected cell is in this row
```

### 2.2 Cell Memoization
```
MatrixCell: React.memo with comparison on cell.value + cell.cell_status
Re-renders only when:
- Cell value changes
- Cell status changes (OK → WARNING)
- Cell becomes selected / deselected
- Badge visibility changes
```

### 2.3 Column Memoization
```
MatrixHeader: React.memo
Re-renders only when columns array changes (grain/period change)
```

---

## 3. SCROLL PERFORMANCE

| Rule | Spec |
|------|------|
| Scroll event handler | Throttled to 16ms (requestAnimationFrame) |
| Scroll sync | Header scrollLeft synchronized with body scrollLeft via ref, not state |
| No state updates on scroll | Use ref for scroll position, not React state |
| Sticky column | CSS `position: sticky` — zero JS cost |
| Sticky header | CSS `position: sticky` — zero JS cost |
| Smooth scroll to target | `element.scrollIntoView({ behavior: 'smooth', block: 'nearest' })` |

---

## 4. RENDER GUARDS

| Rule | Spec |
|------|------|
| Inspector lazy mount | CellInspector component only mounted when inspector_open === true |
| Inspector no re-fetch | Inspector uses cellData passed from click event. No API call. |
| Compare panel lazy mount | ComparePanel only mounted when compare_mode === true |
| Skeleton ceiling | Maximum 10 rows × 7 columns in skeleton. Never render 100+ skeleton rows. |
| Node count limit | Target < 5000 DOM nodes for matrix zone at any time (virtualization achieves this) |

---

## 5. DATA FETCHING

| Rule | Spec |
|------|------|
| Single endpoint | One GET /ops/omniview-v2/shell call. No per-KPI endpoints. |
| Debounce filter changes | 300ms debounce on period/grain/source changes before fetch |
| Abort controller | Previous request aborted on new filter change |
| Cache last response | Keep previous MatrixResponse in memory for instant back-navigation |
| Stale indicator | Show subtle "Refreshing..." badge during fetch, keep old matrix visible |
| Error retry | Show error state with retry button. No auto-retry. |

---

## 6. PERFORMANCE THRESHOLDS

| Metric | Target | Measurement |
|--------|--------|-------------|
| Initial render (page load → matrix visible) | < 1.5s | First paint of MatrixShell |
| Source switch (CT → Yango or reverse) | < 2.5s | From click to new matrix rendered |
| Grain switch (day → week) | < 1.0s | Cached data, just re-layout |
| Period change | < 2.0s | New fetch + render |
| Cell click → inspector open | < 150ms | No fetch needed, just render |
| Horizontal scroll | 60fps | No visible lag, no frame drops |
| Vertical scroll (virtualized) | 60fps | Even with 10,000 rows |
| Memory usage | < 50MB | For matrix zone + inspector |

---

## 7. PERFORMANCE ANTI-PATTERNS

| Anti-pattern | Why bad | Fix |
|-------------|---------|-----|
| Scroll position in React state | Causes re-render on every scroll frame | Use refs |
| Deep equality on cell data in memo | 1000 cells × deep compare = slow | Shallow compare on primitive fields |
| useEffect watching all cell data | Re-runs on any cell change | Listen only to filter changes |
| Re-rendering all cells on hover | Hover change triggers full re-render | CSS :hover pseudo-class, no JS |
| Computing row color in render | Same function called N times per frame | Pre-computed row_status from backend |
| Inline object creation in render | `style={{}}` creates new object each render | Use CSS classes |
| No key on list items | React re-mounts instead of updating | Stable keys: `row.id`, `cell.row_id + cell.column_id` |
