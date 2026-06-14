# OMNIVIEW V2 — VISUAL REDESIGN GAP REPORT v3.0

**Version:** 1.0.0
**Date:** 2026-06-13
**Status:** GAP ANALYSIS — Target vs Current State
**North Star:** v3.0 — Visual Decision Cockpit
**Reference:** `OMNIVIEW_V2_VISUAL_COCKPIT_TARGET.md`

---

## 0. Executive Decision

**GO FOR OV2-VC1: EXECUTIVE COCKPIT ARCHITECTURE**

Current state is matrix-first with professional shell. Target is visual-first cockpit with matrix as secondary detail. Gap is significant in visual layers (trend, PvR bars, breakdown) but minimal in data infrastructure (all endpoints certified, all helpers reusable).

---

## 1. Already Available (Reuse)

| Capability | Source | Status |
|-----------|--------|--------|
| 7 KPI definitions + formatters | `omniviewV2Metrics.js` | DONE |
| Color semantics engine | `omniviewV2ColorSemantics.js` | DONE |
| Plan vs Real display logic | `omniviewV2PlanReal.js` | DONE |
| CSV export | `omniviewV2Export.js` | DONE |
| Sort engine | `omniviewV2Sort.js` | DONE |
| Period presets | `omniviewV2PeriodPresets.js` | DONE |
| Route status badges | `RouteStatusBadge.jsx` | DONE |
| 4 data hooks (shell, matrix, planReal, drill) | V2 hooks | DONE |
| 6 backend endpoints | V2 endpoints | DONE |
| Professional shell | `OmniviewV2ProfessionalPage.jsx` | DONE |
| Navigation clarity | `App.jsx` + registry | DONE |
| V1 fallback | URL-only | DONE |
| ECharts (already in bundle) | From V1 | AVAILABLE |

---

## 2. Partial (Needs Enhancement)

| Capability | Current State | Target State | Priority |
|-----------|--------------|-------------|----------|
| KPI summary | Text cards in toolbar | Visual cards with delta arrows | P0 |
| Plan vs Real | Cell-level attainment | Horizontal attainment bars per slice | P0 |
| Status communication | Amber/red dots in header | Color-coded bars + labels | P1 |
| Freshness visibility | Dot + text in header | Prominent status bar | P1 |

---

## 3. Missing (New Build)

| Capability | Priority | Data Source | Effort |
|-----------|----------|------------|--------|
| Trend charts (DoD/WoW/MoM) | P0_VISUAL_CORE | Matrix endpoint cells → aggregate into series | MEDIUM |
| Slice breakdown bars | P1_VISUAL_ENHANCEMENT | Matrix endpoint cells → group by row_id | LOW |
| Executive KPI cards with deltas | P0_VISUAL_CORE | Shell endpoint KPIs | LOW |
| Plan vs Real bars | P0_VISUAL_CORE | Plan-real endpoint | LOW |
| Matrix as secondary detail tab | P1_VISUAL_ENHANCEMENT | Current matrix component | LOW |
| Dashboard storytelling layout | P1_VISUAL_ENHANCEMENT | CSS grid/flex layout | MEDIUM |

---

## 4. Priority Summary

| Priority | Count | Items |
|----------|-------|-------|
| P0_VISUAL_CORE | 4 | Trend charts, PvR bars, KPI cards, Executive layout |
| P1_VISUAL_ENHANCEMENT | 3 | Breakdown bars, matrix secondary, layout polish |
| P2_POLISH | 5 | Coverage display, status labels, global elements, density, console noise |

---

## 5. Phased Roadmap

### OV2-VC1: Executive Cockpit Architecture
- Define new page layout (KPI row + trend area + PvR+breakdown columns + detail tab)
- Reuse all existing hooks and helpers
- No new endpoints
- **Deliverable**: Shell renders with placeholders, real data in KPI cards

### OV2-VC2: Trend Layer
- Line chart for DoD/WoW/MoM
- Grain-aware period selection
- Plan vs Real overlay
- **Deliverable**: Operator sees metric evolution over time

### OV2-VC3: Plan vs Real Visual Layer
- Attainment bars per slice
- Gap display
- Color coding per attainment threshold
- **Deliverable**: Operator sees plan vs actual at a glance

### OV2-VC4: Slice Breakdown
- Ranking bars by contribution
- Status indicators
- Click to drill into matrix detail
- **Deliverable**: Operator sees which slices drive performance

### OV2-VC5: Matrix as Secondary Detail
- Move matrix to detail tab
- Preserve all matrix functionality
- Add drill links from visual layers
- **Deliverable**: Matrix accessible but not primary

### OV2-VC6: Final Polish + Acceptance
- Browser smoke on all routes
- Visual regression check
- Update docs
- **Deliverable**: Visual cockpit certified

---

## 6. What NOT to Do

- No new backend endpoints
- No new data hooks (reuse existing)
- No Diagnostic/Forecast/AI features
- No runtime-heavy chart library
- No V1 chart migration without audit
- No removal of matrix export

---

*Gap analysis complete. 4 P0 visual core items. 3 P1 enhancements. Phased roadmap defined.*