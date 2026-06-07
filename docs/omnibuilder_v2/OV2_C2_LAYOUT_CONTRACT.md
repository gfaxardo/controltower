# OV2-C.2 — LAYOUT CONTRACT

> **Date:** 2026-06-06
> **Motor:** Control Foundation / UX Architecture
> **Status:** CONTRACT DEFINED

---

## 1. LAYOUT ZONES

```
┌─────────────────────────────────────────────────────────────┐
│ 1. COMMAND HEADER (fixed, top)                              │
│    source | grain | period | canonical | freshness | cov    │
├─────────────────────────────────────────────────────────────┤
│ 2. EXECUTIVE STATE (3-5 cards, connected to filters)        │
│    [Orders] [Revenue] [Drivers] [Rev/Order] [Growth]        │
├─────────────────────────────────────────────────────────────┤
│ 3. WARNING / ALERT STRIP (context-scoped)                   │
│    [⚠ Revenue delta 5% → Auto regular slice]               │
├─────────────────────────────────────────────────────────────┤
│ 4. SECTION SHELL (collapsible cards)                        │
│    [OK Source Health] [WARN Revenue] [BLOCKED PlanVsReal]    │
├─────────────────────────────────────────────────────────────┤
│ 5. MATRIX ZONE (fixed height, inner scroll)                  │
│    ┌──────────┬──────┬──────┬──────┬──────┐                │
│    │ (sticky) │ day1 │ day2 │ day3 │ day4 │                │
│    │ slice1   │ 142  │ 156  │ 134  │ 167  │                │
│    │ slice2   │ 89   │ 92   │ 87   │ 95   │                │
│    └──────────┴──────┴──────┴──────┴──────┘                │
├─────────────────────────────────────────────────────────────┤
│ 6. CELL INSPECTOR (slide-out drawer, right side)            │
│    metric | value | source | lineage | freshness | warnings │
├─────────────────────────────────────────────────────────────┤
│ 7. COMPARE PANEL (modal or split view)                      │
│    CT_TRIPS_2026  |  YANGO_API_RAW                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. ZONE SPECIFICATIONS

### 2.1 Command Header
| Attribute | Spec |
|-----------|------|
| Position | Fixed top, z-index highest |
| Height | 48-56px |
| Contents | Source selector > Grain selector > Period picker > Canonical badge > Freshness indicator > Coverage % |
| Source selector | Dropdown: CT_TRIPS_2026 (default), YANGO_API_RAW (shadow) |
| Canonical badge | Green "CANONICAL" or amber "SHADOW — NOT CANONICAL" |
| Freshness | Relative time: "Updated 5m ago" or "Stale since 2h" |
| Coverage | Percentage badge with color: green ≥95%, amber 50-95%, red <50% |

### 2.2 Executive State
| Attribute | Spec |
|-----------|------|
| Max cards | 5 |
| Card content | metric_id, value, unit, delta indicator (↑↓→), period |
| Layout | Horizontal flex, wrap allowed but prefer single row |
| Connection | Cards reflect currently selected source/grain/period filters |
| Click behavior | Opens inspector with detailed lineage for that metric |

### 2.3 Warning / Alert Strip
| Attribute | Spec |
|-----------|------|
| Visibility | Hidden if 0 warnings. Slides in with animation if warnings exist. |
| Max visible | 3 alerts. "Show all (N)" link if more. |
| Each alert | Icon + severity color + message + target link |
| Target link | Click scrolls to or opens the relevant section/cell |
| Severities | critical (red), warning (amber), info (blue) |

### 2.4 Section Shell
| Attribute | Spec |
|-----------|------|
| Display | Horizontal or grid of cards, 2-3 per row |
| Each card | section_id, title, status badge, summary, next_action |
| Status colors | OK=green, WARNING=amber, BLOCKED=red, NOT_READY=gray |
| Collapse | Sections can collapse to title-only |
| Actions | VIEW_DETAIL only. No real mutations. |

### 2.5 Matrix Zone
| Attribute | Spec |
|-----------|------|
| Height | Fixed: calc(100vh - header - executive - alerts - sections) |
| Min height | 300px |
| Max height | Not constrained by viewport — uses remaining space |
| Scroll | Vertical: inner only. No page-level scroll when matrix is visible. |
| Columns | Sticky header row. Sticky first column (slice/metric name). |
| Virtualization | Enable when rows >100 |
| Row height | 36-40px |
| Cell width | 80-100px for daily, wider for weekly/monthly |
| Loading | Skeleton rows, not spinner over blank |

### 2.6 Cell Inspector
| Attribute | Spec |
|-----------|------|
| Trigger | Click any matrix cell |
| Position | Right-side drawer, width 320-400px |
| Overlay | Semi-transparent backdrop. Click backdrop to close. |
| Contents | metric_id, value, formatted_value, unit, source_system, source_table, grain, period, period_status, canonical_ready, coverage_pct, freshness, confidence, is_estimated, warning_codes, lineage_refs, comparison_status, delta_value, delta_pct, cell_status |
| Close | X button, backdrop click, Escape key |

### 2.7 Compare Panel
| Attribute | Spec |
|-----------|------|
| Trigger | Compare button in command header |
| Display | Split view or modal. Side-by-side KPIs. |
| Label | Source name prominently displayed above each column |
| Delta column | Only where both sources have same metric_id |
| canonical_ready | Visible per source |
| Close | X button, Escape key |

---

## 3. LAYOUT RULES

| Rule | Enforcement |
|------|------------|
| No double vertical scroll | Matrix has `overflow-y: auto` on fixed-height container. Page has `overflow: hidden` when matrix visible. |
| Header always visible | `position: sticky; top: 0; z-index: 100` |
| First column always visible | `position: sticky; left: 0; z-index: 50; background: white` |
| Source always visible | In header, in inspector, on every cell tooltip |
| canonical_ready always visible | Badge in header, badge on every section card |
| No more than 5 executive KPIs | Enforced by component — renders max 5, truncates rest |
| Colors consistent | OK=#22c55e, WARNING=#f59e0b, BLOCKED=#ef4444, NOT_READY=#9ca3af, SHADOW=#6366f1 |
