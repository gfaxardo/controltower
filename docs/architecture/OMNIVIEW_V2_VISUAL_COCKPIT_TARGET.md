# OMNIVIEW V2 — VISUAL COCKPIT TARGET ARCHITECTURE

**Version:** 1.0.0
**Date:** 2026-06-13
**Status:** DEFINITIVE — Target architecture for executive visual cockpit
**North Star:** v3.0 — Visual Decision Cockpit
**Preceded by:** Professional UI rebuild (R1-R6), V1 parity (P0)

---

## 0. Executive Decision

**GO: MATRIX-SECONDARY, VISUAL-FIRST TARGET DEFINED**

The current matrix-first UI is functionally complete but cognitively heavy. The target architecture transforms Omniview V2 into an executive visual cockpit where charts and summaries are primary and the matrix is secondary (detail/audit/export). All backend data governance remains certified. No new endpoints needed.

---

## 1. Executive Summary Layer

### Purpose
Operator sees KPI health in one glance.

### Content
- 4-5 KPI cards: Trips, Revenue, Active Drivers, Cancel Rate
- Each card: value + delta vs previous period + trend arrow
- Color semantics per metric polarity
- Freshness dot + coverage % in header

### Data Source
Existing shell endpoint (`/ops/omniview-v2/shell`) with 7 KPIs already available.

### Reuse
`omniviewV2Metrics.js`, `omniviewV2ColorSemantics.js`, existing KPI strip from V2 shadow.

---

## 2. Trend Layer

### Purpose
Visualize evolution over time. DoD (daily), WoW (weekly), MoM (monthly).

### Content
- Line chart showing selected metric over periods
- Grain-aware (day shows ~7-14 days, week shows ~12 weeks, month shows ~12 months)
- Current period marker
- Plan vs Real overlay when in plan_real mode

### Data Source
Matrix endpoint (`/ops/omniview-v2/matrix`) already returns cells with values per period. Aggregate into series.

### Implementation
Client-side chart library (ECharts already in bundle from V1). Lightweight aggregation from matrix cells. No backend changes.

---

## 3. Plan vs Real Layer

### Purpose
Compare actual performance against plan.

### Content
- Horizontal attainment bars per slice
- Plan value (gray) vs Real value (colored)
- Attainment % + gap absolute/gap %
- Color: green >= 100%, amber 80-99%, red < 80%

### Data Source
Plan vs Real endpoint (`/ops/omniview-v2/plan-real/monthly`). Already returns plan_value, real_value, delta, attainment.

### Reuse
`omniviewV2PlanReal.js` — `getPlanRealDisplay()` already computes attainment and tone.

---

## 4. Slice Breakdown Layer

### Purpose
Show contribution and ranking by business slice.

### Content
- Horizontal bars ranking slices by selected metric
- Contribution % label
- Status indicator (OK/WARNING/BLOCKED)
- Click to drill into matrix detail for that slice

### Data Source
Matrix cells already have row labels and values. Aggregate by row_id.

---

## 5. Detail Layer (Matrix — Secondary)

### Purpose
Deep inspection, audit, export.

### Content
- Full matrix table (current implementation)
- Cell-level color semantics and Plan vs Real
- Export CSV

### Accessibility
- Accessible via "Detail" tab or drill from visual layers
- NOT the landing experience
- Preserved for power users and audit

---

## 6. UX Principles

| Principle | Implementation |
|-----------|---------------|
| At-a-glance | KPI cards + trend chart visible without scrolling |
| Visual hierarchy | KPI → Trend → PvR → Breakdown → Detail |
| Progressive disclosure | Executive cockpit first, detail on click |
| Low cognitive load | Charts communicate trends faster than tables |
| Certified data only | All data from certified V2 endpoints |
| Freshness always visible | Status bar in header, never hidden |

---

## 7. What NOT to Build

- No Diagnostic Engine (no anomaly detection, no root cause)
- No Forecast Engine (no projections, no predictions)
- No AI Copilot (no chat, no recommendations)
- No runtime-heavy chart computations
- No custom chart library — reuse ECharts already in bundle
- No new backend endpoints — reuse existing V2 endpoints

---

## 8. Layout Architecture

```
┌─────────────────────────────────────────────────────┐
│ HEADER: Omniview V2 [Default] · FRESH · 98% coverage │
├─────────┬─────────┬─────────┬─────────┬─────────────┤
│  KPI 1  │  KPI 2  │  KPI 3  │  KPI 4  │  [Grain]   │
│  Trips  │ Revenue │ Drivers │ Cancel% │  [Metric]   │
│  12.3K▲ │ S/45K▲  │  1.2K▲  │  2.1%▼  │  [Presets]  │
├─────────┴─────────┴─────────┴─────────┴─────────────┤
│ TREND (line chart — DoD/WoW/MoM)                    │
│ ▓▓▓▓▓▓▓░░░░░░░░░░░░░ ▓▓▓▓▓▓▓▓▓▓░░░░░░             │
├───────────────────────┬─────────────────────────────┤
│ PLAN VS REAL          │ SLICE BREAKDOWN             │
│ Auto:     ██████ 82%  │ Auto        ████████ 62%    │
│ Delivery: ████   95%  │ Delivery    ███ 12%         │
│ PRO:      █████  78%  │ Tuk Tuk     ██ 10%          │
│ YMA:      ███    88%  │ PRO         ██ 8%           │
│                       │ Carga       █ 5%            │
│                       │ DeliveryM   █ 3%            │
├───────────────────────┴─────────────────────────────┤
│ [Matrix Detail]  [Export CSV]  [Sort]  [Debug]     │
└─────────────────────────────────────────────────────┘
```

---

*Target architecture defined. All data from certified V2 endpoints. No new backend. Matrix secondary.*