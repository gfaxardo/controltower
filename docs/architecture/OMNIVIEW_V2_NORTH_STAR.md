# OMNIVIEW V2 — VISUAL DECISION COCKPIT NORTH STAR v3.0

**Version:** 3.0.0
**Date:** 2026-06-13
**Status:** REDEFINED — Matrix-secondary, visual-first executive cockpit
**Preceded by:** v2.0.0 (Professional Operational UI) — achieved; v1.0.0 (V1 Parity) — achieved
**Scope:** Functional and visual target for Omniview V2
**Preceded by:** Ownership/Freshness/Traceability Certification (Phase B.1 → E)

---

## 0. Executive Intent

Omniview V2 must equal or exceed the functional and visual utility of Omniview V1, without inheriting its technical debt or data governance risks.

V1 has ~12,000+ lines of UI code across 20 components, with rich operational features (dual modes, charts, export, insights, trust scoring, priority panels, comprehensive drilldown). V2 has clean architecture (30 files, design tokens, unified CSS, multi-source awareness) but lacks ~10 key features needed for production parity.

The North Star defines WHAT V2 must deliver. The Gap Report defines what's missing and at what priority.

---

## 1. What Omniview V2 Is

V2 is the **operational control surface** for Control Foundation:

- **Operating control cockpit** — See what's happening NOW.
- **Plan vs Real comparison matrix** — Compare actuals vs targets.
- **Operational performance matrix** — Multi-metric, multi-grain, multi-slice.
- **Freshness-aware serving UI** — Transparently shows data age and trust.
- **Control Foundation layer** — No speculation, no prediction, no AI.

---

## 2. What Omniview V2 Is Not

V2 does NOT include:

- **Diagnostic Engine** — No root cause analysis, no anomaly detection, no pattern diagnosis.
- **Forecast Engine** — No projections, no seasonality predictions, no trends.
- **Suggestion Engine** — No automated recommendations, no action proposals.
- **Decision Engine** — No automated decisions, no policy evaluation.
- **Action Engine** — No automated execution, no assignment triggers.
- **AI Copilot** — No chat, no natural language, no AI interpretation.
- **Runtime-heavy calculator** — No heavy aggregation in UI. Serving-first.
- **Legacy replica** — No copy-paste of V1 code. No legacy endpoints.

**Any feature belonging to Diagnostic/Forecast/Suggestion/Decision/Action/AI must NOT be built in V2.** It must wait for its respective engine phase.

---

## 3. Minimum Functional Parity with V1

| # | V1 Capability | Required in V2? | Notes |
|---|--------------|-----------------|-------|
| 1 | KPI visibility (7 KPIs) | YES — same 7 KPIs | V2 currently shows only 1 KPI (hardcoded `orders`) |
| 2 | Plan vs Real comparison | YES | V2 has partial toggle but no projection visualization |
| 3 | Color semantics (green/red/amber/gray) | YES | V2 has design tokens; need consistent application |
| 4 | Period navigation (monthly/weekly/daily) | YES | V2 has grain selector + date range |
| 5 | Filter usability (country/city/slice/park) | YES | V2 already has CommandHeader with all filters |
| 6 | Visual hierarchy (sorted, sticky, scannable) | YES | V2 has sticky headers/rows; needs sort controls |
| 7 | Drill / readability (cell inspector) | YES | V2 has CellInspector (solid) |
| 8 | Operational alerts (deterministic only) | YES | V2 has alert strip |
| 9 | Freshness transparency | YES | V2 has freshness badge + operating date |
| 10 | Export (CSV) | YES | V1 has comprehensive CSV; V2 needs same |
| 11 | Empty/loading/error states | YES | V2 has all three (solid) |
| 12 | Charts (trends, evolution, composition) | YES — via ECharts | V2 has none |
| 13 | Sort controls (alpha, impact, volume) | YES | V2 has none |
| 14 | Density toggle (comfortable/compact) | YES | V2 has infrastructure but no UI toggle |
| 15 | Period presets (Today, This Week, etc.) | YES | V2 has smart defaults but no presets |

---

## 4. Certified Data Contract

V2 consumes ONLY:
- Certified serving facts (`ops.real_business_slice_*_fact`, `ops.driver_day_slice_fact`)
- Canonical cascade output (via `omniview_cascade_refresh`)
- Registry/freshness metadata (`ops.serving_registry`, `ops.serving_refresh_log`)
- Read-only endpoints (`/ops/omniview-v2/*`)

V2 does NOT consume:
- Legacy refresh paths (`business_slice_real_refresh_job`, `business_slice_incremental_load`)
- Runtime-heavy fallback
- Ungoverned tables (`v_real_trips_business_slice_resolved`, `v_real_trips_enriched_base`)
- Uncensored writers
- POST endpoints for refresh/backfill

---

## 5. UI/UX Principles

1. **Fewer endpoints, more clarity** — V2 uses 7 endpoints (vs V1's 17). Keep it lean.
2. **Fewer but stronger surfaces** — Matrix is the main surface. Inspector is the detail surface. Don't scatter information.
3. **Sticky context** — Filters, period, grain always visible. No context loss on scroll.
4. **Focus by period** — Anchor on current period. Show context around it.
5. **Color discipline** — Green = good/ahead/fresh. Red = bad/behind/stale. Yellow = warning/partial. Gray = no data/not comparable. Never use color alone (always pair with value/text).
6. **No hidden stale data** — Show data freshness prominently. Show staleness as warning.
7. **No silent empty states** — Every empty state explains WHY and offers CTAs to resolve.
8. **No misleading zero** — Never show 0 when data is simply not yet available.
9. **No heavy recalculation in UI** — All aggregation happens in backend/cascade. UI renders pre-computed values.
10. **No cognitive overload** — Progressive disclosure. Default view is scannable. Details are drillable.
11. **Operator-first reading** — Top-down: status bar → KPI strip → alerts → matrix. Left-right: labels → periods.

---

## 6. Color Semantics Contract

| Color | Meaning | CSS Class | When to use |
|-------|---------|-----------|-------------|
| Green (`#22c55e`) | Ahead / positive / healthy / fresh | `.ok` | Positive delta for higher-better KPIs. Fresh data. |
| Red (`#ef4444`) | Behind / negative / critical / stale | `.blocked` | Negative delta for higher-better KPIs. Stale data. |
| Yellow/Amber (`#f59e0b`) | Warning / partial / at risk | `.warning` | Partial periods. Minor degradation. |
| Gray/Slate (`#9ca3af`) | Not comparable / no data / unknown | `.not-comparable` | Missing reference. Empty cell. |
| Blue (`#3b82f6`) | Informational / current focus / selected | `.selected` | Currently inspected cell. Current period. |

Arrow direction respects KPI polarity (higher_better vs lower_better).

---

## 7. P0 Parity Requirements

| # | Requirement | V1 Source | Why It Matters |
|---|------------|-----------|----------------|
| P0-1 | Multi-metric matrix (7 KPIs) | `BusinessSliceOmniviewMatrix` with MATRIX_KPIS | Operators need to see all KPIs per row, not one at a time. |
| P0-2 | Plan vs Real comparison | `OmniviewProjectionMode` with attainment/gap | Core operational workflow: compare plan vs actual. |
| P0-3 | CSV Export | `omniviewExport.js` (metadata + data + YTD + opportunities) | Operators export data for reports and offline analysis. |
| P0-4 | Color semantics consistent | V1 signal colors (green/red/amber/gray) | Instant visual recognition of status across cells. |
| P0-5 | Period navigation presets | V1 grain + period selectors | Quick access to current/previous periods. |
| P0-6 | Sort controls | V1 sort (alpha, impact, volume, critical) | Operators reorder rows to find issues quickly. |
| P0-7 | Freshness visibility (prominent) | V1 freshness banner + freshness card | Operators must know data age before making decisions. |

---

## 8. Anti-Requirements (Do NOT Port from V1)

| V1 Feature | Why NOT to Port |
|-----------|-----------------|
| Legacy refresh endpoints (`/ops/omniview/refresh`, `/ops/business-slice/backfill`) | Already fail-closed (Phase C.2). Superseded by cascade. |
| Runtime-heavy fallback queries | Against serving-first architecture. Must use serving facts. |
| `business_slice_incremental_load` writer paths | Deprecated and blocked. |
| Duplicated KPI computation across grains | Single canonical computation in cascade. |
| UI-only business logic (insight engine, alerting engine, root cause engine) | Belongs to Diagnostic Engine (blocked). Port only deterministic, control-level checks. |
| Broken active_drivers at week grain (SUM of daily distincts) | Fixed in V2 via bridge cascade (COUNT DISTINCT). |
| Multi-source fallback adapters (shellToMatrixResponse adapter) | V2 matrix endpoint is already implemented. Remove adapter. |
| Hardcoded runtime calculations for projections | Projection engine belongs to Forecast. Keep V2 real-only for now. |
| Unclear color semantics (inconsistent across modes) | V2 must enforce single color contract across all views. |
| Evolution view mode (MoM/WoW/DoD comparison) | Deprecated by OMNI-P0. Vs Proy is canonical. |

---

## 9. Phase Plan

### OV2-UI-P0 — Parity Audit & North Star (THIS PHASE)
- Document V1 inventory. Document V2 inventory.
- Define North Star. Define gaps. Create parity matrix.
- **Deliverable:** `OMNIVIEW_V2_NORTH_STAR.md`, `OMNIVIEW_V2_UI_PARITY_GAP_REPORT.md`

### OV2-UI-P1 — KPI + Color + Export Parity
- Add multi-metric selector (7 KPIs). Apply color semantics consistently.
- Implement CSV export (reuse/extend V1 export engine).
- Add sort controls. Add period presets.
- **Deliverable:** V2 reaches visual parity with V1 on KPIs, colors, export, sort, presets.

### OV2-UI-P2 — Plan vs Real + Charts Parity
- Implement projection visualization (attainment %, gap, curves).
- Add ECharts-based charts (evolution, composition, trends).
- Wire `getOmniviewV2Compare` endpoint for source comparison.
- **Deliverable:** V2 reaches functional parity with V1 on Plan vs Real and charts.

### OV2-UI-P3 — Drilldown + Freshness Transparency
- Enhance CellInspector with trust scoring (port from V1 trust sensor).
- Add root cause display (deterministic only, no Diagnostic Engine).
- Add density toggle. Add keyboard navigation.
- **Deliverable:** V2 inspector reaches parity with V1 inspector.

### OV2-UI-P4 — Final Operational Smoke
- Full end-to-end smoke with backend running.
- Verify all endpoints respond. Verify export works.
- Verify no legacy paths used.
- **Deliverable:** V2 marked as production-ready for operational use.

---

## 10. Mandatory Prompt Precheck

Every future prompt for Omniview V2 UI must:
1. Read this document (`OMNIVIEW_V2_NORTH_STAR.md`)
2. Read `OMNIVIEW_V2_UI_PARITY_GAP_REPORT.md`
3. Read `OMNIVIEW_V2_CANONICAL.md`
4. Read `OWNERSHIP_CERTIFICATION.md`
5. Read `TRUTH_MAP_V2.md`
6. Read `KNOWN_CONSTRAINTS.md`

And must answer:
1. Which North Star capability does this touch?
2. Is this V1 parity, V2 improvement, or blocked engine (Diagnostic/Forecast/etc.)?
3. What data source does it use?
4. Is the data source certified?
5. Does it introduce runtime-heavy UI computation?
6. Does it revive legacy paths?
7. Can it show stale/misleading zero data?
8. What is the rollback?

---

*Defines the product vision for Omniview V2. All UI work must reference this document.*

---

## 11. V1 Parity Milestone Reached (v1.0.0)

P0 parity with Omniview V1 is implemented:
- 7/7 KPIs available via selector
- CSV export functional
- Color semantics consistent per metric polarity
- Sort controls (alpha, volume, impact, critical)
- Period presets (Today, Last 7d, This Week, This Month)
- Plan vs Real visualization
- Freshness visibility

Backend governance (ownership, freshness, traceability) is certified. Endpoint smoke: 7/7 HTTP 200. Build passes.

---

## 12. New North: Professional Operational UI (v2.0.0)

Omniview V2 must now become a **professional operational control UI**:

- Reliable on open — no runtime crashes, no stack traces
- Visually clean — clear hierarchy, no noise
- Executive — operator can scan and understand in seconds
- Fast — no heavy recalculation, no double scroll
- Freshness-visible — data age always known
- Certified-only — no legacy, no ungoverned data
- Empty-state honest — no misleading zeros
- Error-state actionable — tells operator what to do

**What "professional" means:**
1. No runtime crashes. No visible stack traces to end user (except debug mode).
2. Layout balanced. Header clean. Status/freshness visible but not invasive.
3. Matrix legible. KPIs clear. Controls grouped.
4. No UI contradicting certified backend.
5. No features from blocked engines (Diagnostic, Forecast, etc.)

---

## 13. Professionalization Phase Plan

After V1 parity and runtime fix:

- **OV2-UI-R0**: Runtime Reliability Smoke — verify no crashes on open
- **OV2-UI-R1**: Professional Layout Audit — clean up header, status bar, spacing
- **OV2-UI-R2**: Header/Controls Polish — group controls, reduce clutter
- **OV2-UI-R3**: Matrix Readability Polish — font sizes, column widths, density
- **OV2-UI-R4**: Empty/Error/Freshness States — fix all visual edge cases
- **OV2-UI-R5**: Final Professional UI Smoke — verify operational quality

---

## 14. Updated Prompt Precheck

Every future Omniview V2 UI prompt must answer:
1. Does it improve runtime stability?
2. Does it improve professional clarity?
3. Does it respect certified data?
4. Does it reduce cognitive load?
5. Does it avoid legacy?
6. Does it avoid blocked engines?
7. Does it keep freshness visible?
8. Does it have a rollback?
 9. Was it smoke-tested in browser?
10. Would an operator understand it without seeing a stack trace?

---

## 15. Navigation Clarity North Star

Omniview V2 is not operationally validated just by rendering. It must also:
- Orient the operator — which view is the official one?
- Avoid version ambiguity — V1 vs V2 must be unmistakable
- Distinguish default vs legacy vs fallback vs dev
- Use consistent labels and colors per the status taxonomy
- Never expose dev/sandbox routes as operational
- Keep fallback routes accessible but never default
- Avoid duplicate or near-duplicate tab names

Reference: `OMNIVIEW_UI_NAVIGATION_STATUS_TAXONOMY.md`

---

## 16. North Star v3.0: Executive Visual Decision Cockpit

### What Changed

v2.0 was about matching V1 parity with a professional shell. That is achieved. v3.0 shifts the primary experience from matrix-first to visual-first. The matrix becomes a secondary detail/audit view. The primary view becomes an executive cockpit optimized for at-a-glance operational decisions.

### The New Primary Experience

The operator should see, in one screen:
1. **KPI Summary** — 3-5 key metrics with delta vs previous period
2. **Trend Layer** — DoD/WoW/MoM visualization by grain
3. **Plan vs Real** — attainment bars with gap
4. **Slice Breakdown** — ranking by contribution/performance
5. **Freshness & Coverage** — always visible, never invasive

### The Matrix's New Role

The matrix is NOT removed. It becomes:
- **Detail view** — drill into any visual element to see matrix
- **Export source** — CSV export from matrix data
- **Audit tool** — verify specific cells
- **Secondary tab** — accessible but not the landing experience

### Design Principles

- **At-a-glance**: Operator understands state in seconds
- **Visual hierarchy**: KPI → Trend → Plan vs Real → Breakdown
- **Progressive disclosure**: Executive first, detail on demand
- **Low cognitive load**: Charts > tables for comprehension
- **No speculation**: Only deterministic, certified data. No predictions.

### What NOT to Build

- No Diagnostic Engine disguised as charts
- No forecast curves or projections
- No AI insights or recommendations
- No runtime-heavy chart engines
- No legacy V1 chart libraries without audit

### Visual Cockpit Architecture

```
┌─────────────────────────────────────────────┐
│ HEADER: Omniview V2 · Freshness · Coverage   │
├──────────┬──────────┬───────────────────────┤
│ KPI 1    │ KPI 2    │ KPI 3    │ KPI 4     │
│ Trips    │ Revenue  │ Drivers  │ Cancel %  │
│ 12,341 ▲ │ S/ 45K ▲ │ 1,234 ▲  │ 2.1% ▼   │
├──────────┴──────────┴──────────┴────────────┤
│ TREND: Daily/Weekly/Monthly line chart       │
│ ▓▓▓▓▓▓▓░░░░░░░░  ▓▓▓▓▓▓▓▓▓▓░░░░           │
├──────────────────────┬──────────────────────┤
│ PLAN VS REAL         │ SLICE BREAKDOWN      │
│ Auto: ████████ 82%   │ Auto     ████████ 62%│
│ Delivery: ████ 95%   │ Delivery ███ 12%     │
│ PRO: ██████ 78%      │ PRO      ██ 10%      │
├──────────────────────┴──────────────────────┤
│ [Matrix Detail] [Export CSV] [Audit]        │
└─────────────────────────────────────────────┘
```

### Phase Roadmap

- **OV2-VC1**: Executive cockpit architecture + layout shell
- **OV2-VC2**: KPI summary + trend charts (DoD/WoW/MoM)
- **OV2-VC3**: Plan vs Real visual layer (attainment bars, gap)
- **OV2-VC4**: Slice breakdown + composition charts
- **OV2-VC5**: Matrix as secondary detail/audit view
- **OV2-VC6**: Final visual polish + acceptance

### Precheck for Visual Cockpit Prompts

Every future prompt must answer:
1. Is this visual-first or matrix-first?
2. Does it reduce cognitive load?
3. Does it use only certified data?
4. Does it avoid Diagnostic/Forecast engines?
5. Can the operator understand it at a glance?
6. Is the matrix still accessible as detail?
7. Does it preserve freshness/coverage visibility?