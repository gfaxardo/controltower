# OMNIVIEW V2 — UI PARITY GAP REPORT

**Version:** 1.0.0
**Date:** 2026-06-13
**Status:** COMPLETED — Read-Only UI Audit
**Scope:** V1 vs V2 parity gap analysis
**Preceded by:** OMNIVIEW_V2_NORTH_STAR.md

---

## 0. Executive Decision

**GO FOR OV2-UI-P1 PARITY IMPLEMENTATION**

V2 has 30 well-architected files with clean design tokens, but lacks ~10 critical V1 features. The gap is PRIORITY-ORDERED: start with P0 (multi-metric + colors + export), then P1 (charts + plan-vs-real), then P2 (drilldown enhancements). V1 has `productionReady: true`; V2 has `productionReady: false`.

---

## 1. Scope

| Dimension | V1 | V2 |
|-----------|----|-----|
| Component count | ~20 main files | 30 files (well-organized) |
| Code volume | ~12,000+ lines | ~3,500 lines |
| API endpoints consumed | 17 | 7 (2 unused stubs) |
| Routes | 5 | 2 (shadow + sandbox) |
| KPIs supported | 7 | 1 (hardcoded) |
| Grains | 3 | 3 |
| View modes | 2 (Evolution + Projection) | 2 (real + plan_real toggle) |
| Production readiness | `productionReady: true` | `productionReady: false` |
| Design system | Ad-hoc Tailwind | Unified tokens + CSS custom properties |

---

## 2. V1 Inventory (Summary)

Omniview V1 is the current production matrix at `/operacion/omniview-matrix`. Key components:

| Component | Lines | Purpose |
|-----------|-------|---------|
| `BusinessSliceOmniviewMatrix.jsx` | ~2000+ | Main orchestrator: dual-mode matrix, all state |
| `BusinessSliceOmniviewMatrixTable.jsx` | 696 | Hierarchical table with city/line expand/collapse |
| `BusinessSliceOmniviewMatrixCell.jsx` | 499 | Cell renderer: values, deltas, colors, trust, timeline |
| `BusinessSliceOmniviewMatrixHeader.jsx` | 194 | Column headers with period badges |
| `BusinessSliceOmniviewInspector.jsx` | 904 | Cell drill-down with charts, trust, evidence |
| `BusinessSliceOmniviewReports.jsx` | 852 | ECharts reports: line, bar, heatmap, sparklines |
| `OmniviewPriorityPanel.jsx` | 203 | Priority deviation ranking |
| `omniviewMatrixUtils.js` | 1208 | Core matrix utility: KPIs, deltas, signals, periods |
| `projectionMatrixUtils.js` | 937 | Projection utility: attainment, gap, KPI contracts |
| `omniviewUtils.js` | 158 | Signal colors, formatting, tree building |
| `alertingEngine.js` | 495 | Priority scoring (KPI-weighted) |
| `insightEngine.js` | 292 | Threshold-based insight detection |
| `omniviewExport.js` | 392 | CSV export with metadata, data quality, matrix data |

**17 API endpoints** (14 GET, 3 POST) across evolution, projection, freshness, and plan-vs-real domains.

---

## 3. V2 Inventory (Summary)

Omniview V2 is the shadow-mode matrix at `/operacion/omniview-v2-shadow`. 30 files organized into pages, hooks, components (matrix/layout/base), design tokens, CSS system.

**Strengths:**
- Clean separation of concerns (hooks isolate data fetching, components are pure renderers)
- Unified design token system (117 line JS tokens + 494 line CSS system)
- Multi-source awareness (canonical vs shadow badges, banners, inspector)
- Robust error/empty/loading states (global empty with CTAs, matrix skeleton, error retry)
- Cell inspector with lineage, freshness, trust, drill data
- Sticky headers/rows with horizontal scroll sync
- Filter CommandHeader with all selectors (source, grain, date range, country, city, slice, park)

**Structure:**
```
omniview-v2-shadow/
  OmniviewV2ShadowPage.jsx      — main orchestrator (422 lines)
  OmniviewV2MatrixSandbox.jsx    — dev sandbox (98 lines)
  adapters/shellToMatrixResponse.js — fallback adapter (158 lines)
  design/
    omniviewV2Tokens.js           — design tokens (117 lines)
    MatrixVisualSystem.css        — unified CSS (494 lines)
  hooks/
    useOmniviewV2Shell.js         — shell API hook
    useOmniviewV2Matrix.js        — matrix API hook
    useOmniviewV2PlanReal.js      — plan/real API hook
    useOmniviewV2DrillCell.js     — drill API hook
  components/
    matrix/ (9 files)             — MatrixShell, Header, Row, Cell, Inspector, Delta, Badge, Skeleton, Empty
    layout/ (5 files)             — CommandHeader, ContextBar, ExecutiveState, AlertStrip, SectionShell
    base/ (8 files)               — MetricValue, SourceBadge, StatusBadge, CoverageBadge, FreshnessBadge, PeriodBadge, WarningBadge, DeltaValue
    OmniviewV2GlobalEmptyState.jsx (133 lines)
```

---

## 4. V1 vs V2 Parity Matrix

| Capability | V1 | V2 | Gap | Priority | Phase |
|-----------|----|----|-----|----------|-------|
| **Matrix visualization** | Table-based, KPI columns | Matrix grid, sticky headers/rows | V2 has better architecture | N/A | DONE |
| **Design system** | Ad-hoc Tailwind | Unified tokens + CSS properties | V2 is superior | N/A | DONE |
| **Multi-metric matrix** | 7 KPIs per row | 1 KPI (hardcoded `orders`) | **No KPI selector UI** | P0 | P1 |
| **Plan vs Real** | Full projection with attainment, gap, curves | Primitive plan/real toggle | **No projection visualization** | P0 | P2 |
| **CSV Export** | Comprehensive (metadata + matrix + YTD + opportunities) | None | **No export at all** | P0 | P1 |
| **Color semantics** | Green/red/amber/gray signals | Design tokens exist but not fully applied | GAP | P0 | P1 |
| **Sort controls** | Alpha, impact, volume, critical | None | **No sort UI** | P0 | P1 |
| **Period presets** | None in V1 either | Smart defaults on grain change | Missing quick buttons | P1 | P1 |
| **Charts (ECharts)** | Evolution, composition, bar, line, heatmap, sparklines | None | **No charts at all** | P1 | P2 |
| **Source comparison** | Implicit (same table) | Endpoint exists, not wired | Compare view not built | P1 | P2 |
| **KPI strip** | 5 KPIs with deltas | Up to 5 KPI cards | V2 has cards, V1 has richer deltas | P1 | P2 |
| **Density toggle** | Compact/Comfortable | Infrastructure exists, no UI toggle | Hardcoded to comfortable | P2 | P3 |
| **Keyboard navigation** | Arrow keys for matrix | Only Escape for fullscreen | No cell navigation | P2 | P3 |
| **Filter persistence** | None in V1 either | None | URL params or localStorage | P3 | P3 |
| **Trust scoring** | Composite trust with decision modes | Boolean `canonical_ready` | No trust engine | P2 | P3 |
| **Insight engine** | Threshold-based insights per cell | None | **Belongs to Diagnostic** | DO_NOT_PORT | N/A |
| **Alerting engine** | KPI-weighted priority scoring | Alert strip with severity | **Belongs to Diagnostic** | DO_NOT_PORT | N/A |
| **Root cause engine** | Root cause attribution | None | **Belongs to Diagnostic** | DO_NOT_PORT | N/A |
| **Evolution view** | MoM/WoW/DoD comparison | None | **Deprecated by OMNI-P0** | DO_NOT_PORT | N/A |
| **Drilldown** | Inspector with charts, trust, evidence | Inspector with lineage, parks, drivers | V2 inspector is solid. Charts missing. | P1 | P2 |
| **Error/Loading/Empty states** | Basic error boundary | All three (global empty, skeleton, retry) | V2 is superior | N/A | DONE |
| **Freshness visibility** | Freshness banner + governance card | Freshness badge + operating date | V1 has richer presentation | P1 | P2 |
| **Multi-source awareness** | None | Canonical/shadow badges, banners, inspector | V2 is superior | N/A | DONE |
| **Lineage visualization** | Basic | Origin table, field, aggregation, filters | V2 is superior | N/A | DONE |
| **Responsive/mobile** | Desktop-only | Desktop-only | Out of scope | P3 | N/A |

---

## 5. P0 Gaps (Must-Fix for Production Parity)

| # | Gap | V1 Feature | V2 Status | Required Work |
|---|-----|-----------|-----------|---------------|
| P0-1 | Multi-metric selector | 7 KPIs in MATRIX_KPIS | Hardcoded `orders`, no UI selector | **COMPLETE (7/7)** — selector implemented, all metrics available. See P1A/P1A.1 reports. |
| P0-2 | CSV Export | `omniviewExport.js` (392 lines) | No export functionality | **COMPLETE** — V2 export engine with metadata, wide+long matrix. See P1C report. |
| P0-3 | Color semantics applied | Green/red/amber/gray on all cells | Design tokens exist, not fully applied | **COMPLETE** — Semantic tone per metric polarity. See P1B report. |
| P0-4 | Sort controls | Sort by alpha/impact/volume/critical | No sort controls | **COMPLETE** — 6 modes. Client-side, no refetch. Export respects sort. See P1D report. |
| P0-5 | Plan vs Real visualization | Projection mode with attainment %, gap, curves | Primitive plan/real toggle | **COMPLETE** — attainment + ahead/behind label + semantic tone. See P1F report. |
| P0-6 | Period presets | Implicit (grain defaults) | Smart defaults but no quick buttons | **COMPLETE** — 6 presets in CommandHeader. ISO Monday. See P1E report. |
| P0-7 | Freshness prominence | Banner + governance card | Single badge in header | **COMPLETE** — FreshnessBadge + operational status bar (8 fields) + health endpoint. Export includes freshness metadata. |

---

## 6. P1 Gaps (Important for Daily Operation)

| # | Gap | Required Work |
|---|-----|---------------|
| P1-1 | Charts (ECharts) | Add evolution/trend charts in Inspector. Add composition/bar charts in Reports view. |
| P1-2 | Source comparison view | Wire `getOmniviewV2Compare` endpoint. Build side-by-side matrix view. |
| P1-3 | KPI strip with deltas | Enhance ExecutiveState cards with delta indicators (vs previous period). |
| P1-4 | Drilldown with charts | Add ECharts-based evolution chart in CellInspector (like V1 inspector). |
| P1-5 | Trust scoring | Implement deterministic trust scoring (coverage + freshness + consistency) without insight engine. |

---

## 7. Things NOT To Port from V1

| V1 Feature | Reason |
|-----------|--------|
| Evolution view (MoM/WoW/DoD) | Deprecated by OMNI-P0. Vs Proy is canonical. |
| Insight engine (`insightEngine.js`) | Belongs to Diagnostic Engine (engine #2, BLOCKED). |
| Alerting engine (`alertingEngine.js`) | Priority scoring belongs to Diagnostic. Simple alerts OK. |
| Root cause engine (`rootCauseEngine.js`) | Belongs to Diagnostic Engine. |
| Legacy refresh endpoints | Already fail-closed (Phase C.2). |
| `shellToMatrixResponse` fallback adapter | Matrix endpoint is implemented. Remove adapter. |
| Runtime-heavy aggregation queries | Against serving-first architecture. |
| Broken active_drivers (SUM of daily distincts) | Fixed in V2 bridge cascade. |
| `business_slice_incremental_load` data paths | Deprecated and blocked. |

---

## 8. Data/Endpoint Constraints

| Constraint | Impact |
|-----------|--------|
| 5 serving facts (4 OV2 + 1 driver_bridge) are certified | V2 reads from certified sources only. No fallback to ungoverned tables. |
| `/ops/omniview-v2/matrix` returns 1 metric at a time | Multi-metric matrix requires either backend change or N parallel calls. |
| `getOmniviewV2Compare` endpoint not wired | Source comparison view blocked until wired. |
| `getOmniviewV2Sources` endpoint unused | Can be used for source health display. |
| No projection endpoint in V2 | Plan vs Real uses `getOmniviewV2PlanRealMonthly`. Projection curves not supported yet. |
| Legacy refresh endpoints fail-closed | POST `/ops/omniview/refresh` and `/ops/business-slice/backfill` return HTTP 423. UI must not call them. |

---

## 9. UX Risks

| Risk | Mitigation |
|------|-----------|
| V2 shows misleading zero when data not yet available | Implement check: if `row_count == 0` for current date, show "Data pending" not "0". |
| V2 shows stale data without prominent warning | Freshness must be visible at ALL times. Yellow/red status if lag > threshold. |
| Color semantics inconsistent across views | Enforce single `omniviewV2Tokens.js` color system across ALL components. |
| Multi-metric matrix overloads screen | Start with 3 default KPIs. Allow expand to 7. Compact mode for dense view. |
| Charts make UI feel like Diagnostic Engine | Use charts ONLY for data visualization (trends, composition). No predictions, no recommendations. |
| Export exposes internal implementation details | Use V1's formula injection protection. Sanitize all output. |

---

## 10. Recommended Implementation Phases

| Phase | Content | Files to Touch | Deliverable |
|-------|---------|---------------|-------------|
| **OV2-UI-P1** (P0) | Multi-metric selector, color semantics, CSV export, sort, period presets | `MatrixCell.jsx`, `OmniviewV2ShadowPage.jsx`, new `omniviewV2Export.js`, `OmniviewV2CommandHeader.jsx` | V2 reaches KPI + visual parity |
| **OV2-UI-P2** (P0+P1) | Plan vs Real visualization, ECharts, source comparison | `OmniviewV2ShadowPage.jsx`, new chart components, wire compare endpoint | V2 reaches functional parity |
| **OV2-UI-P3** (P2) | Density toggle, keyboard nav, trust scoring, filter persistence | `MatrixShell.jsx`, `MatrixCell.jsx`, `OmniviewV2ShadowPage.jsx` | V2 UX polish |
| **OV2-UI-P4** (Validation) | End-to-end smoke, export verification, mark productionReady=true | Smoke report, `controlTowerNavigationRegistry.js` | V2 production-ready |

---

## 11. Prompt Precheck Addendum

Every future prompt for Omniview V2 UI must answer these questions BEFORE implementation:

1. Which North Star capability does this touch? (Reference section number from `OMNIVIEW_V2_NORTH_STAR.md`)
2. Is this V1 parity, V2 improvement, or blocked engine (Diagnostic/Forecast/etc.)?
3. What data source does it use? (Must be certified — see Section 4 of North Star)
4. Is the data source certified? (Check `OWNERSHIP_CERTIFICATION.md`)
5. Does it introduce runtime-heavy UI computation? (Must be "NO" for V2)
6. Does it revive legacy paths? (Must be "NO" — check `KNOWN_CONSTRAINTS.md`)
7. Can it show stale/misleading zero data? (Must handle these cases)
8. What is the rollback? (Must be documented)

---

*Generated from exhaustive frontend audit of V1 (20 components, ~12K lines) and V2 (30 files, ~3.5K lines). No code changes executed.*