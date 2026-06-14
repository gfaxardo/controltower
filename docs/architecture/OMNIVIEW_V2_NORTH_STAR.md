# OMNIVIEW V2 — PRODUCT NORTH STAR

**Version:** 1.0.0
**Date:** 2026-06-13
**Status:** DEFINITIVE — Product Definition for Omniview V2 UI
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