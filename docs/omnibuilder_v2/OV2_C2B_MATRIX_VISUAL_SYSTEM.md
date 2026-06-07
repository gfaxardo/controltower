# OV2-C.2B — MATRIX VISUAL SYSTEM CONTRACT

> **Date:** 2026-06-06
> **Motor:** Control Foundation / UX Architecture
> **Status:** CONTRACT DEFINED
> **Applies to:** ALL Omniview V2 matrices — Drivers, Trips, Revenue, TPD, daily, weekly, monthly

---

## 1. PURPOSE

Omniview V1 suffered from visual inconsistency: Drivers matrix had different hover effects than Trips matrix. Revenue cells had different focus rings than TPD cells. Monthly matrix used different delta formatting than weekly. This contract eliminates all per-KPI and per-grain visual divergence.

**Every matrix in Omniview V2 uses exactly one visual system. No exceptions without documented justification in this file.**

---

## 2. COLOR SCALE — SINGLE SOURCE OF TRUTH

### 2.1 Semantic Colors

| State | Name | Hex | Tailwind | CSS Variable | Usage |
|-------|------|-----|----------|-------------|-------|
| OK | green-500 | #22c55e | `bg-green-500` | `--ov2-ok` | Status badge, coverage≥95%, MATCH delta |
| WARNING | amber-500 | #f59e0b | `bg-amber-500` | `--ov2-warning` | Status badge, coverage<95%, MINOR_DELTA |
| BLOCKED | red-500 | #ef4444 | `bg-red-500` | `--ov2-blocked` | Status badge, coverage<50%, MAJOR_DELTA, revenue unavailable |
| SHADOW | indigo-500 | #6366f1 | `bg-indigo-500` | `--ov2-shadow` | Non-canonical source badge |
| NOT_COMPARABLE | gray-400 | #9ca3af | `bg-gray-400` | `--ov2-not-comparable` | No matching metric in other source, no prior period |
| ESTIMATED | purple-500 | #a855f7 | `bg-purple-500` | `--ov2-estimated` | Derived/proxy values |

### 2.2 Interaction Colors

| State | Name | Hex | Tailwind | CSS Variable | Usage |
|-------|------|-----|----------|-------------|-------|
| SELECTED | blue-500 | #3b82f6 | `ring-blue-500` | `--ov2-selected` | Active cell border, focused row indicator |
| HOVER | blue-50 | #eff6ff | `bg-blue-50` | `--ov2-hover` | Cell/row hover background |
| MUTED | gray-100 | #f3f4f6 | `bg-gray-100` | `--ov2-muted` | Disabled cells, non-applicable periods |
| DISABLED | gray-200 | #e5e7eb | `bg-gray-200` | `--ov2-disabled` | Future periods, blocked cells |
| PARTIAL | amber-50 | #fffbeb | `bg-amber-50` | `--ov2-partial-bg` | PARTIAL period cell background |

### 2.3 Cell Background by Status

| cell_status | Background | Border | Text | CSS Class |
|-------------|-----------|--------|------|-----------|
| OK | white `#ffffff` | none | `--ov2-text-primary` | `ov2-cell--ok` |
| WARNING | amber-50 `#fffbeb` | left 2px amber-500 | `--ov2-text-primary` | `ov2-cell--warning` |
| BLOCKED | red-50 `#fef2f2` | left 2px red-500 | `--ov2-text-muted` | `ov2-cell--blocked` |
| NOT_COMPARABLE | gray-50 `#f9fafb` | none | `--ov2-text-muted` | `ov2-cell--not-comparable` |
| FUTURE | gray-100 `#f3f4f6` | none | `--ov2-text-muted` | `ov2-cell--future` |

---

## 3. INTERACTION BEHAVIOR — SINGLE SPEC

### 3.1 Hover
| Rule | Spec |
|------|------|
| Trigger | Mouse enters cell boundary |
| Effect | Background shifts to `--ov2-hover` (blue-50) |
| Duration | Instant (0ms transition) |
| Row hover | Entire row gets `--ov2-hover` background |
| Cell hover | Individual cell + row. Cell gets slightly stronger tint. |
| Applies to | ALL cells: OK, WARNING, BLOCKED, all KPIs, all grains |
| Exception | DISABLED cells do not respond to hover |

### 3.2 Selected (Active Focus)
| Rule | Spec |
|------|------|
| Trigger | Click on cell |
| Effect | `ring-2 ring-blue-500 ring-inset` around cell |
| Row | Row label gets blue left border (4px) |
| Duration | 150ms ease-in-out |
| Persists | Until: different cell clicked, inspector closed, or Escape pressed |
| Applies to | ALL cells, ALL KPIs, ALL grains |
| Inspector | Inspector opens with cell data. Drawer from right. |

### 3.3 Autofocus
| Rule | Spec |
|------|------|
| Trigger | Alert click with cell target |
| Effect | Target cell gets selected state + inspector opens |
| Scroll | Matrix auto-scrolls to reveal target cell |
| Duration | Smooth scroll 300ms |
| Applies to | Any cell that is target of an alert |

### 3.4 Muted
| Rule | Spec |
|------|------|
| Condition | Cell has no data for the period (value=null but period exists) |
| Visual | Background gray-100, text gray-400, value shows "—" |
| Interaction | Not clickable. No hover response. |
| Applies to | ALL KPIs, ALL grains |

### 3.5 Disabled
| Rule | Spec |
|------|------|
| Condition | Period is FUTURE or cell_status is BLOCKED |
| Visual | Background gray-200, text gray-400, no border |
| Interaction | Not clickable. No hover. Tooltip shows reason. |
| Applies to | ALL KPIs, ALL grains |

### 3.6 Partial Period
| Rule | Spec |
|------|------|
| Condition | period_status = PARTIAL |
| Visual | Cell has amber left border (2px). PARTIAL badge in top-right corner. |
| Interaction | Clickable. Inspector shows "Period is incomplete. Data may change." |
| Applies to | ALL KPIs, ALL grains |

### 3.7 Estimated Value
| Rule | Spec |
|------|------|
| Condition | is_estimated = true |
| Visual | Value text is purple-500 (not black). ESTIMATED badge in top-right. |
| Tooltip | "This value is estimated/derived. Source: {source_table}" |
| Applies to | ALL KPIs, ALL grains |

---

## 4. BASE COMPONENTS

### 4.1 MatrixShell
```
Wraps the entire matrix zone. Sets fixed height, overflow, scroll sync.
```
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| height | number\|string | 'calc(100vh - 320px)' | Container height |
| rowCount | number | 0 | Total rows (for virtualization) |
| columnCount | number | 0 | Total data columns |
| loading | boolean | false | Show skeleton when true |
| emptyMessage | string | "No data available" | Empty state text |

### 4.2 MatrixHeader
```
Sticky top row with column labels. Synchronizes horizontal scroll with MatrixShell.
```
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| columns | ColumnDef[] | [] | Column definitions: {id, label, grain, period} |
| sticky | boolean | true | Position sticky top |
| scrollLeft | number | 0 | Synchronized scroll position |

### 4.3 MatrixRow
```
Single data row. Virtualized. Sticky first column (row label).
```
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| rowId | string | — | Row identifier (slice name or metric_id) |
| label | string | — | Sticky first column content |
| cells | CellData[] | [] | Cell data for each column |
| isSelected | boolean | false | Row has selected cell |
| rowIndex | number | 0 | Virtualization index |

### 4.4 MatrixCell
```
Single data cell. Renders value, badges, status colors. Triggers inspector.
```
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| cellData | CellContract | — | Full cell contract from OV2-C.2 |
| isSelected | boolean | false | This cell is active |
| onClick | function | — | (cellData) => void |
| grain | string | 'day' | For formatting |

### 4.5 CellBadge
```
Small badge overlay inside cell. Shows one status indicator.
```
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| type | string | — | PARTIAL \| ESTIMATED \| SHADOW \| DELTA \| FUTURE |
| tooltip | string | '' | Hover explanation |

### 4.6 CellDelta
```
Shows comparison delta inside cell (compare mode only).
```
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| deltaValue | number\|null | null | Absolute delta |
| deltaPct | number\|null | null | Percentage delta |
| status | string | — | MATCH \| MINOR_DELTA \| MAJOR_DELTA |

### 4.7 CellInspectorTrigger
```
Invisible overlay that makes cell clickable and opens inspector.
```
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| cellData | CellContract | — | Data to pass to inspector |
| onClick | function | — | Open inspector callback |

---

## 5. FORBIDDEN PATTERNS

| # | Pattern | Reason |
|---|---------|--------|
| 1 | Styles scoped to `metric_id` | All KPIs share one visual system |
| 2 | Different hover per grain | day/week/month use identical hover |
| 3 | Revenue-specific colors | Revenue uses same OK/WARNING/BLOCKED as Trips |
| 4 | Per-component CSS files | All matrix styles in one `MatrixVisualSystem.css` |
| 5 | Inline styles on cells | Use CSS classes from the system |
| 6 | Custom delta formatting per KPI | Delta rendered by CellDelta, same for all |
| 7 | Hardcoded hex values outside CSS variables | Use `var(--ov2-*)` only |
| 8 | Per-KPI tooltip format | All tooltips share CellContract structure |

---

## 6. GRAIN INDEPENDENCE

| Grain | Column Width | Value Format | Delta Format | Period Badge |
|-------|-------------|-------------|-------------|-------------|
| hour | 70px | `14` | same | HH:MM |
| day | 90px | `14,213` | same | Jun 4 |
| week | 100px | `98,452` | same | W23 |
| month | 100px | `412,300` | same | Jun 2026 |

All grains share the same:
- Color scale
- Hover behavior
- Selected state
- Cell status rendering
- Badge system
- Inspector trigger
- Loading skeleton

---

## 7. CSS VARIABLE REFERENCE

```css
:root {
  /* Semantic states */
  --ov2-ok:              #22c55e;
  --ov2-warning:         #f59e0b;
  --ov2-blocked:         #ef4444;
  --ov2-shadow:          #6366f1;
  --ov2-not-comparable:  #9ca3af;
  --ov2-estimated:       #a855f7;

  /* Interaction */
  --ov2-selected:        #3b82f6;
  --ov2-hover:           #eff6ff;
  --ov2-muted:           #f3f4f6;
  --ov2-disabled:        #e5e7eb;

  /* Backgrounds */
  --ov2-partial-bg:      #fffbeb;
  --ov2-warning-bg:      #fffbeb;
  --ov2-blocked-bg:      #fef2f2;

  /* Text */
  --ov2-text-primary:    #111827;
  --ov2-text-muted:      #9ca3af;

  /* Layout */
  --ov2-cell-min-width:  80px;
  --ov2-cell-max-width:  120px;
  --ov2-row-height:      40px;
  --ov2-header-height:   44px;
  --ov2-sticky-z:        10;
  --ov2-selected-z:      20;
}
```

---

## 8. VISUAL CONSISTENCY CHECKLIST

| # | Rule | Scope |
|---|------|-------|
| V1 | All KPIs use same OK/WARNING/BLOCKED colors | Cross-KPI |
| V2 | All grains use same hover behavior | Cross-grain |
| V3 | All cells use same selected ring style | Cross-cell |
| V4 | All deltas use CellDelta component | Cross-KPI |
| V5 | All badges use CellBadge component | Cross-KPI |
| V6 | All tooltips share CellContract structure | Cross-cell |
| V7 | No per-KPI CSS overrides exist | Code audit |
| V8 | No per-grain CSS overrides exist | Code audit |
| V9 | All colors reference CSS variables | CSS audit |
| V10 | MatrixShell is the only matrix wrapper | Component audit |
