# OV2-C.2 — INTERACTION CONTRACT

> **Date:** 2026-06-06
> **Motor:** Control Foundation / UX Architecture

---

## 1. INTERACTION MAP

### 1.1 Change Source
| Trigger | User selects different source in Command Header dropdown |
|---------|----------------------------------------------------------|
| Effect | All sections reload with new source data |
| Visual | Brief skeleton state, then update. Header source badge updates (CANONICAL/SHADOW). |
| Canonical | If YANGO_API_RAW selected: canonical_ready badge changes to "SHADOW — NOT CANONICAL" |
| Sections | Plan vs Real and Slice Readiness → BLOCKED for Yango source |
| URL | Not persisted yet. |

### 1.2 Change Grain
| Trigger | User selects hour/day/week/month in Command Header |
|---------|----------------------------------------------------|
| Effect | Matrix columns change. KPIs re-aggregate. |
| Unsupported | If grain not supported by source → GRAIN_NOT_SUPPORTED warning, matrix shows empty state |
| Visual | Grain badge updates. Matrix column width adjusts. |
| Period | Period selector range updates to match grain. |

### 1.3 Change Period
| Trigger | User selects date range in period picker |
|---------|----------------------------------------|
| Effect | All sections reload for new period |
| Visual | Period displayed in header. Matrix columns update to match range. |
| Short series | If <7 days: Growth Movement → WARNING (short series) |
| No data | If no data for period: Operational Coverage → BLOCKED |

### 1.4 Click on Cell
| Trigger | User clicks any matrix cell |
|---------|---------------------------|
| Effect | Cell Inspector drawer opens on right side |
| Focus | Clicked cell gets border highlight. Row stays highlighted while inspector open. |
| Content | Inspector shows full cell contract: metric, value, source, lineage, freshness, warnings |
| Close | X button, backdrop click, Escape key. Cell highlight removed. |
| Multiple | Opening new cell replaces inspector content. No multiple inspectors. |

### 1.5 Click on Alert
| Trigger | User clicks alert in Warning Strip |
|---------|-----------------------------------|
| Effect | Scrolls to target. If target is a cell: opens inspector. If target is a section: expands section card. If target is a slice: scrolls matrix to that row. |
| Visual | Target element gets highlight animation. Alert in strip dims (seen state). |

### 1.6 Open Lineage
| Trigger | User clicks "View Lineage" in inspector or section card |
|---------|--------------------------------------------------------|
| Effect | Lineage Drawer opens. Shows: source_table → origin_field → aggregation → filters_applied |
| Visual | Slide-out from inspector or modal overlay |
| Close | X button, Escape key |

### 1.7 Blocked Data
| Trigger | Section or cell has status BLOCKED |
|---------|-----------------------------------|
| Effect | Element displays BLOCKED badge. Content shows reason. No action available. |
| Visual | Grayed out with red BLOCKED label. Tooltip explains reason. |
| Example | Yango Plan vs Real: "BLOCKED — no plan infrastructure for Yango API" |

### 1.8 Non-Canonical Source
| Trigger | Source has canonical_ready = false |
|---------|-----------------------------------|
| Effect | Header shows SHADOW badge. All section cards show NOT CANONICAL. Cell inspector shows canonical_ready: false. |
| Visual | Purple SHADOW badge everywhere. Subtle purple tint to background in compare mode. |
| Warning | Permanent warning in alert strip: "Source YANGO_API_RAW is NOT certified for operational decisions." |

### 1.9 Low Coverage
| Trigger | coverage_pct < 95% |
|---------|-------------------|
| Effect | Coverage badge turns amber (<95%) or red (<50%). Operational Coverage section shows WARNING or BLOCKED. |
| Visual | Coverage badge with %. Section card status updates. |
| Warning | Alert strip: "Coverage at {pct}% — below 95% threshold." |

### 1.10 Revenue Unavailable
| Trigger | revenue value is null or 0 |
|---------|--------------------------|
| Effect | Revenue KPIs show "—" or "N/A". Revenue Integrity section → BLOCKED. |
| Visual | Revenue card shows empty state. Revenue cell in matrix shows "—" with REVENUE_UNAVAILABLE tooltip. |
| Warning | Alert strip: "REVENUE_UNAVAILABLE — no revenue data for selected period." |

---

## 2. INTERACTION RULES

| # | Rule |
|---|------|
| 1 | Every click changes visible focus (highlight, border, breadcrumb) |
| 2 | Every focus has breadcrumb: Source > Section > Metric > Period |
| 3 | No multiple modals. Inspector replaces modal. Drawer replaces inspector. |
| 4 | No real actions. VIEW_DETAIL, VIEW_LINEAGE, VIEW_COVERAGE, VIEW_RECONCILIATION only. |
| 5 | No mutations. Read-only UI. |
| 6 | Escape key closes inspector, drawer, modal, compare panel. |
| 7 | Skeleton states for all loading transitions. No blank screens. |
| 8 | Error boundaries catch component failures. Degrade gracefully. |

---

## 3. BREADCRUMB MODEL

```
Omniview V2 > CT_TRIPS_2026 > Day > Jun 4 2026 > Revenue > Auto regular slice
```

Breadcrumb updates on:
- Source change
- Grain change
- Period change
- Cell click (adds metric + slice to trail)
- Section focus

---

## 4. STATE TRANSITIONS

```
[Idle] → click source dropdown → [Loading Source] → [Data Loaded]
[Data Loaded] → click cell → [Inspector Open] → close → [Data Loaded]
[Data Loaded] → click alert → [Scroll to Target] → [Data Loaded]
[Data Loaded] → click Compare → [Compare Mode] → close → [Data Loaded]
[Any] → error → [Error State] → retry → [Loading] → [Data Loaded]
```
