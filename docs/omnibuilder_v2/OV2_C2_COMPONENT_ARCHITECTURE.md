# OV2-C.2 — COMPONENT ARCHITECTURE

> **Date:** 2026-06-06
> **Motor:** Control Foundation / UX Architecture

---

## 1. COMPONENT TREE

```
OmniviewV2ShadowPage
├── OmniviewV2ErrorBoundary
│   ├── OmniviewV2CommandHeader
│   │   ├── SourceSelector
│   │   ├── GrainSelector
│   │   ├── PeriodSelector
│   │   ├── CanonicalBadge
│   │   ├── FreshnessIndicator
│   │   └── CoverageBadge
│   ├── OmniviewV2ContextBar
│   │   └── Breadcrumb trail (Source > Grain > Period > Section)
│   ├── OmniviewV2ExecutiveState
│   │   └── KpiCard (×3-5)
│   ├── OmniviewV2AlertStrip
│   │   └── AlertItem (×0-3 visible)
│   ├── OmniviewV2SectionShell
│   │   └── SectionCard (×10)
│   ├── OmniviewV2MatrixZone
│   │   ├── OmniviewV2MatrixHeader
│   │   │   └── HeaderCell (sticky)
│   │   ├── OmniviewV2MatrixRow (×N, virtualized)
│   │   │   ├── RowLabel (sticky first column)
│   │   │   └── OmniviewV2MatrixCell (×M columns)
│   │   └── OmniviewV2EmptyState (if no data)
│   ├── OmniviewV2CellInspector (drawer, conditional)
│   ├── OmniviewV2LineageDrawer (conditional)
│   ├── OmniviewV2ComparePanel (modal, conditional)
│   └── OmniviewV2EmptyState (page-level fallback)
```

---

## 2. COMPONENT SPECIFICATIONS

### 2.1 OmniviewV2ShadowPage
| Attribute | Spec |
|-----------|------|
| Responsibility | Top-level page container. Manages source/grain/period state. Fetches shell data. |
| State | source_system, grain, period, filters, shellData, loading, error |
| Data fetching | Calls /ops/omniview-v2/shell on mount and on filter change |
| No business logic | Pure orchestration: fetch → pass to children |
| Error handling | OmniviewV2ErrorBoundary wraps entire tree |

### 2.2 OmniviewV2CommandHeader
| Attribute | Spec |
|-----------|------|
| Props | source_system, grain, period, canonical_ready, freshness, coverage_pct, onSourceChange, onGrainChange, onPeriodChange |
| Fixed position | Yes. Always visible. |
| Source options | CT_TRIPS_2026 (default, canonical), YANGO_API_RAW (shadow) |
| Grain options | hour, day, week, month (filtered by source support) |

### 2.3 OmniviewV2ContextBar
| Attribute | Spec |
|-----------|------|
| Props | source_system, grain, period, selected_section, selected_cell |
| Content | Breadcrumb: Omniview V2 > {source} > {grain} > {period} > {section?} > {cell?} |
| Update | Automatically on any state change |

### 2.4 OmniviewV2ExecutiveState
| Attribute | Spec |
|-----------|------|
| Props | kpis (from shell response), loading |
| Max items | 5 |
| Card layout | Horizontal flex, gap 16px, responsive wrap |
| Click handler | onMetricClick(metric_id) → opens inspector or scrolls to matrix |

### 2.5 OmniviewV2AlertStrip
| Attribute | Spec |
|-----------|------|
| Props | warnings (from shell response) |
| Visibility | Hidden if warnings.length === 0 |
| Max visible | 3 |
| Severity sort | critical > warning > info |
| Click handler | onAlertClick(warning) → scrolls to target section/cell |

### 2.6 OmniviewV2SectionShell
| Attribute | Spec |
|-----------|------|
| Props | sections (from shell response) |
| Layout | Grid, 2 columns, gap 16px |
| Sort | OK first, then WARNING, then BLOCKED |
| Collapse | Each section card collapsible |
| Status badge | Color per status: OK/WARNING/BLOCKED/NOT_READY |

### 2.7 OmniviewV2MatrixZone
| Attribute | Spec |
|-----------|------|
| Props | kpis, grain, date_from, date_to |
| Height | Fixed, calc(100vh - header - executive - alerts - sections) |
| Scroll | Inner vertical scroll only. Page overflow hidden when matrix has data. |
| Empty state | If no data: OmniviewV2EmptyState with message |
| Loading | Skeleton grid: 10 rows × 7 columns placeholder |

### 2.8 OmniviewV2MatrixCell
| Attribute | Spec |
|-----------|------|
| Props | All fields from Cell Contract |
| Rendering | value → formatted_value + unit. cell_status → color. badges → overlay. |
| Click | onClick → set selectedCell → open inspector |
| Tooltip | metric_id + period_status badge on hover |
| States | loading (skeleton), empty ("—"), OK, WARNING, BLOCKED |

### 2.9 OmniviewV2CellInspector
| Attribute | Spec |
|-----------|------|
| Props | cell (all cell contract fields), isOpen, onClose |
| Position | Right drawer, width 360px |
| Sections | Value, Source, Period, Trust, Warnings, Lineage, Comparison |
| Close | X button, backdrop click, Escape |

### 2.10 OmniviewV2LineageDrawer
| Attribute | Spec |
|-----------|------|
| Trigger | "View Lineage" button in inspector or section card |
| Content | origin_table → origin_field → aggregation → filters_applied |
| Visual | Stacked flow diagram or indented list |

### 2.11 OmniviewV2ComparePanel
| Attribute | Spec |
|-----------|------|
| Trigger | Compare button in command header |
| Content | Side-by-side KPIs: CT_TRIPS_2026 left, YANGO_API_RAW right |
| Delta column | Middle column showing delta_value + delta_pct for shared metrics |
| canonical_ready | Visible per source |

### 2.12 OmniviewV2EmptyState
| Attribute | Spec |
|-----------|------|
| Props | message, icon (optional), action (optional) |
| States | No data, No source selected, Grain not supported, Error |
| Action | Optional retry button |

### 2.13 OmniviewV2ErrorBoundary
| Attribute | Spec |
|-----------|------|
| Catches | Render errors in any child component |
| Fallback | OmniviewV2EmptyState with error message + retry |
| Reset | Retry button re-mounts children |

---

## 3. SEPARATION OF CONCERNS

| Layer | Responsibility | Example |
|-------|---------------|---------|
| Page | Data fetching, state management | OmniviewV2ShadowPage |
| Layout | Positioning, scrolling, zones | CommandHeader, MatrixZone |
| Data display | Render values, apply status colors | MatrixCell, KpiCard, SectionCard |
| Interaction | Click handlers, inspector, drawers | CellInspector, LineageDrawer |
| Feedback | Alerts, loading, empty, error states | AlertStrip, EmptyState, ErrorBoundary |

---

## 4. FILE STRUCTURE

```
frontend/src/pages/omniview-v2-shadow/
├── OmniviewV2ShadowPage.jsx          # Page container, data fetching
├── OmniviewV2CommandHeader.jsx       # Fixed top command bar
├── OmniviewV2ContextBar.jsx          # Breadcrumb trail
├── OmniviewV2ExecutiveState.jsx      # Top KPI cards
│   └── KpiCard.jsx
├── OmniviewV2AlertStrip.jsx          # Warning alert strip
│   └── AlertItem.jsx
├── OmniviewV2SectionShell.jsx        # Section cards grid
│   └── SectionCard.jsx
├── OmniviewV2MatrixZone.jsx          # Matrix container
│   ├── OmniviewV2MatrixHeader.jsx
│   ├── OmniviewV2MatrixRow.jsx
│   └── OmniviewV2MatrixCell.jsx
├── OmniviewV2CellInspector.jsx       # Right drawer
├── OmniviewV2LineageDrawer.jsx       # Lineage overlay
├── OmniviewV2ComparePanel.jsx        # Compare modal
├── OmniviewV2EmptyState.jsx          # Reusable empty/error state
├── OmniviewV2ErrorBoundary.jsx       # Error boundary wrapper
├── hooks/
│   └── useOmniviewV2Shell.js         # Data fetching hook
└── constants.js                      # Colors, thresholds, labels
```
