# OV2-C.2 — UX ACCEPTANCE CHECKLIST

> **Date:** 2026-06-06
> **Motor:** Control Foundation / UX Architecture
> **For:** OV2-C.3 UI Shadow Implementation validation

---

## 1. LAYOUT ACCEPTANCE

| # | Check | Criterion |
|---|-------|-----------|
| L1 | Header fixed | Header stays at top when scrolling matrix |
| L2 | No double scroll | Exactly one vertical scroll context when matrix visible |
| L3 | Header/columns aligned | Column headers synchronized with data columns on horizontal scroll |
| L4 | Sticky first column | Row labels (slice/metric names) remain visible when scrolling horizontally |
| L5 | Matrix height | Matrix uses remaining viewport height. No page-level scrollbar when matrix has data. |
| L6 | Cards above matrix | Executive cards are above matrix, not side-by-side |
| L7 | Inspector drawer | Inspector opens on right. Does not overlap header. Backdrop closes on click. |
| L8 | Min width | Layout functional at 1024px. Below 1024px shows "Desktop required". |

---

## 2. SOURCE VISIBILITY

| # | Check | Criterion |
|---|-------|-----------|
| S1 | Source in header | Current source_system visible in Command Header at all times |
| S2 | Canonical badge | Header shows CANONICAL (green) or SHADOW — NOT CANONICAL (indigo) |
| S3 | Canonical on sections | Each section card shows canonical_ready status |
| S4 | Yango shadow mode | When YANGO_API_RAW selected: all applicable badges show SHADOW/NOT CANONICAL |
| S5 | Source in inspector | Cell inspector shows source_system and source_table |

---

## 3. GRAIN & PERIOD VISIBILITY

| # | Check | Criterion |
|---|-------|-----------|
| G1 | Grain in header | Current grain visible in Command Header |
| G2 | Period in header | Current date range visible in Command Header |
| G3 | Grain filtering | Only supported grains appear in selector for active source |
| G4 | Period status on cells | Each matrix cell shows period_status badge (CLOSED/PARTIAL/CURRENT/FUTURE) |

---

## 4. CELL INTERACTION

| # | Check | Criterion |
|---|-------|-----------|
| C1 | Cell clickable | Clicking any matrix cell opens Cell Inspector |
| C2 | Inspector content | Inspector shows: metric_id, value, source, lineage, freshness, warnings |
| C3 | Cell status color | Cell background reflects cell_status (OK=white, WARNING=amber, BLOCKED=red) |
| C4 | Cell tooltip | Hover shows metric_id + period_status |
| C5 | Inspector close | X button, backdrop click, Escape key all close inspector |
| C6 | Single inspector | Opening new cell replaces inspector content. No multiple inspectors. |

---

## 5. ALERT INTERACTION

| # | Check | Criterion |
|---|-------|-----------|
| A1 | Alert visibility | Alert strip shows when warnings exist. Hidden when 0 warnings. |
| A2 | Alert severity | Critical=red, Warning=amber, Info=blue |
| A3 | Alert target | Clicking alert scrolls to or highlights the target section/cell |
| A4 | Max visible | At most 3 alerts visible. "Show all (N)" link for overflow. |

---

## 6. SECTION SHELL

| # | Check | Criterion |
|---|-------|-----------|
| SS1 | 10 sections | All 10 sections present in section shell |
| SS2 | Status badges | Each section card shows OK/WARNING/BLOCKED status with correct color |
| SS3 | Source-specific | Plan vs Real and Slice Readiness show BLOCKED for Yango source |
| SS4 | Collapse | Section cards can collapse to title-only |

---

## 7. COMPARE MODE

| # | Check | Criterion |
|---|-------|-----------|
| CP1 | Side-by-side | CT_TRIPS_2026 left, YANGO_API_RAW right |
| CP2 | Source labels | Each column clearly labeled with source name |
| CP3 | Canonical per source | CT shows CANONICAL, Yango shows SHADOW |
| CP4 | Delta column | Middle column shows delta_value and delta_pct for shared metrics |
| CP5 | Compare close | X button and Escape close compare mode |

---

## 8. NO REAL ACTIONS

| # | Check | Criterion |
|---|-------|-----------|
| NA1 | Read-only | No buttons that trigger writes, updates, deletes |
| NA2 | Actions limited | Only VIEW_DETAIL, VIEW_LINEAGE, VIEW_COVERAGE, VIEW_RECONCILIATION |
| NA3 | No execution | No ACTION_ENGINE, DECISION, FORECAST, SUGGESTION actions or buttons |
| NA4 | No exports | No CSV/PDF/Excel export buttons in OV2-C.2 |

---

## 9. V1 INTEGRITY

| # | Check | Criterion |
|---|-------|-----------|
| V1a | V1 routes intact | All V1 endpoints respond normally |
| V1b | V1 UI intact | Omniview V1 page loads without errors |
| V1c | No V1 imports broken | No OV2 imports affect V1 module loading |
| V1d | Build unaffected | `npm run build` succeeds for frontend |

---

## 10. ERROR & EDGE STATES

| # | Check | Criterion |
|---|-------|-----------|
| E1 | Loading skeleton | Matrix shows skeleton rows during data fetch |
| E2 | Error boundary | Component error shows fallback UI, not white screen |
| E3 | No data | Empty state message when no data for selected period |
| E4 | Grain not supported | Clear message when grain not available for source |
| E5 | Unknown source | Error message when invalid source_system requested |
| E6 | Revenue unavailable | Revenue cells show "—" with REVENUE_UNAVAILABLE tooltip |

---

## 11. VISUAL CONSISTENCY (OV2-C.2B Matrix System)

| # | Check | Criterion |
|---|-------|-----------|
| VC1 | Cross-KPI colors | All KPIs (Drivers, Trips, Revenue, TPD) use identical OK/WARNING/BLOCKED colors |
| VC2 | Cross-grain hover | Daily, weekly, and monthly matrices share identical hover behavior |
| VC3 | Cross-grain selected | Same ring-2-blue-500 selected style across all grains |
| VC4 | Cross-grain muted | Same gray muted style for null cells across all grains |
| VC5 | Delta uniformity | All deltas rendered by CellDelta component. Same format for all KPIs. |
| VC6 | Badge uniformity | All badges rendered by CellBadge component. Same position, size, tooltip format. |
| VC7 | Tooltip uniformity | All cell tooltips follow CellContract structure. No per-KPI custom tooltip. |
| VC8 | CSS variables only | No hardcoded hex colors. All colors via `var(--ov2-*)` |
| VC9 | Single CSS file | All matrix styles in one `MatrixVisualSystem.css`. No per-component CSS files. |
| VC10 | No KPI overrides | Code audit: zero `.revenue-cell`, `.trips-cell`, `.drivers-cell` selectors |
| VC11 | No grain overrides | Code audit: zero `.daily-cell`, `.weekly-cell`, `.monthly-cell` selectors |
| VC12 | Column width consistency | Same grain = same column width, regardless of KPI |
| VC13 | Row height consistency | All rows 40px regardless of KPI or grain |
| VC14 | MatrixShell exclusive | Only MatrixShell component wraps matrices. No standalone matrix containers. |
| VC15 | Matrix source-agnostic | MatrixZone has zero references to CT_TRIPS_2026, YANGO_API_RAW, or any physical source |
| VC16 | No SQL assumptions | MatrixZone contains no table names, field names, or SQL fragments |
| VC17 | Cross-source uniformity | Matrix renders identically for CT and Yango data. Only source badge differs. |
| VC18 | Cross-grain uniformity | Matrix renders identically for hour/day/week/month. Only column width differs. |
| VC19 | No business logic | MatrixZone contains zero arithmetic beyond rendering formatted_value |
| VC20 | Single MatrixResponse | All data comes from one MatrixResponse object. No per-KPI fetches. |
| VC21 | Inspector no re-fetch | Cell inspector reuses cellData from MatrixResponse. No API call on cell click. |
| VC22 | No metric_id styles | Code audit: zero CSS selectors containing metric_id values |
| VC23 | No grain styles | Code audit: zero CSS selectors targeting hour/day/week/month |
| VC24 | Performance measured | Initial render <1.5s, cell click <150ms, source switch <2.5s validated |

---

## 12. ACCEPTANCE STATUS

| Phase | Status | Notes |
|-------|--------|-------|
| Layout acceptance | PENDING | Validate in OV2-C.3 |
| Source visibility | PENDING | Validate in OV2-C.3 |
| Grain & period | PENDING | Validate in OV2-C.3 |
| Cell interaction | PENDING | Validate in OV2-C.3 |
| Alert interaction | PENDING | Validate in OV2-C.3 |
| Section shell | PENDING | Validate in OV2-C.3 |
| Compare mode | PENDING | Validate in OV2-C.3 |
| No real actions | PENDING | Validate in OV2-C.3 |
| V1 integrity | PENDING | Validate in OV2-C.3 |
| Error & edge states | PENDING | Validate in OV2-C.3 |
| Visual consistency | PENDING | Validate in OV2-C.3 (OV2-C.2B) |

**GO conditions for OV2-C.3:**
- All layout checks pass (L1-L8)
- All source checks pass (S1-S5)
- All cell checks pass (C1-C6)
- No V1 integrity broken (V1a-V1d)
- No real actions present (NA1-NA4)
- Visual consistency verified (VC1-VC14)
- Matrix contract verified (VC15-VC24)
