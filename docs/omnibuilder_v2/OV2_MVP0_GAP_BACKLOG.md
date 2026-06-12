# OV2-MVP.0 — GAP BACKLOG (PRIORITIZED)

> **Fase:** OV2-MVP.0 — Feature Parity Audit
> **Sub-document:** Gap Backlog
> **Fecha:** 2026-06-12

---

## P0 — BLOCKS DAILY USE (MVP cannot function without these)

| # | Gap | Area | Detail | Estimated Effort |
|---|-----|------|--------|-----------------|
| P0-1 | **Business Slice dimension** | Backend + Frontend | V2 matrix doesn't show KPI × business_slice grid. Missing query, missing dimension in MatrixResponse, missing frontend rendering. | LARGE |
| P0-2 | **Signal colors in matrix cells** | Frontend | No green/amber/red threshold coloring. Must port insight thresholds from `insightConfig.js` to V2 design tokens. | MEDIUM |
| P0-3 | **City + Country filters** | Frontend + Backend | V2 CommandHeader only has date + grain. Missing city/country dropdowns. Backend queries need filter params. | MEDIUM |
| P0-4 | **Business Slice filter** | Frontend + Backend | Filter by business_slice (regular, delivery, etc.). Depends on P0-1. | MEDIUM |
| P0-5 | **Commission rate KPI** | Backend + Frontend | Add commission_pct to MatrixResponse + frontend KPI selector + executive state. | SMALL |
| P0-6 | **No double-scroll verification + hardening** | Frontend | MatrixShell must be verified for no double-scroll issue that plagued V1. Add `overflow` containment + test. | SMALL |
| P0-7 | **Operational status bar** | Frontend | Collapsible bar showing: max date, coverage %, unmapped trips, period state, trust status, KPI summary. | MEDIUM |
| P0-8 | **KPI delta arrows + direction** | Frontend | `DeltaValue` needs direction indicator (↑ green / ↓ red) and comparison context. | SMALL |
| P0-9 | **V2 route in production nav registry** | Config | Add `omniview-v2-shadow` to `controlTowerNavigationRegistry.js` as `productionReady: false` (MVP mode) with `engine: Control Foundation`. | TINY |
| P0-10 | **Cell inspector: Evolution/Momentum drill** | Frontend + Backend | Port Evolution drill (current vs previous) and Momentum drill (ECharts trend) from V1 inspector. | LARGE |

---

## P1 — AFFECTS OPERATION (usable but degraded)

| # | Gap | Area | Detail | Estimated Effort |
|---|-----|------|--------|-----------------|
| P1-1 | **Plan vs Real daily + weekly** | Backend + Frontend | V2 PvR is monthly-only. Add daily/weekly grains to plan-real endpoint + frontend toggle. | MEDIUM |
| P1-2 | **Cancel rate KPI** | Backend + Frontend | Add cancel_rate_pct to matrix (CT-only, since Yango doesn't ingest cancellations). | SMALL |
| P1-3 | **Subfleet filter** | Frontend + Backend | Toggle to show/hide subfleets in matrix. | SMALL |
| P1-4 | **Sticky column headers** | Frontend | Verify and implement `position: sticky` on matrix column headers. | SMALL |
| P1-5 | **Virtual scroll / large dataset performance** | Frontend | Profile MatrixShell with 100+ business_slices × 7 KPIs × 30 days. | MEDIUM |
| P1-6 | **Projection mode (full)** | Backend + Frontend | Port projection drill with plan attainment analysis, root cause engine, alert handoff. | LARGE |
| P1-7 | **Freshness governance chain visualization** | Frontend | Port RAW → day → week → month chain visualization from `OmniviewFreshnessGovernanceCard`. | MEDIUM |
| P1-8 | **Error boundary wrapper** | Frontend | Wrap V2 page in error boundary for graceful failure. | SMALL |
| P1-9 | **Trust badges in matrix cells** | Frontend | Show trust status (ok/warning/blocked) directly in cells, not just inspector. | SMALL |
| P1-10 | **Health state visualization** | Frontend | Show infra-health and backend-identity in UI (not just endpoints). | SMALL |

---

## P2 — UX IMPROVEMENT (nice to have for daily use)

| # | Gap | Area | Detail | Estimated Effort |
|---|-----|------|--------|-----------------|
| P2-1 | **ECharts-based reports view** | Frontend | Port ECharts bar/line/heatmap reports from `BusinessSliceOmniviewReports`. | LARGE |
| P2-2 | **Fullscreen toggle** | Frontend | F11 button on matrix. | SMALL |
| P2-3 | **Control Loop PvR view** | Frontend | Port standalone control loop PvR table with signal colors. | MEDIUM |
| P2-4 | **Park filter** | Frontend + Backend | Filter matrix by park (multipark support). | MEDIUM |
| P2-5 | **Backfill controls** | Frontend | Backfill trigger + progress panel (dev-ops concern, not daily-user). | MEDIUM |
| P2-6 | **LOB drill PRO** | Frontend + Backend | Port dimensional drill (country → city → park → LOB) from V1. | LARGE |
| P2-7 | **Executive banner** | Frontend | Port `MatrixExecutiveBanner` with KPI executive summary. | SMALL |
| P2-8 | **Snapshot auto-expiry** | Backend | Prune old `omniview_v2_serving_snapshot` rows (>30 days). | SMALL |

---

## P3 — NICE TO HAVE (future)

| # | Gap | Area | Detail |
|---|-----|------|--------|
| P3-1 | **Zoom control** | Frontend | Zoom in/out on matrix |
| P3-2 | **Dark mode** | Frontend | Theme toggle (light/dark) |
| P3-3 | **Export to CSV/PDF** | Frontend | Export matrix as CSV or PDF |
| P3-4 | **Real Operational snapshot** | Frontend | Port today/yesterday snapshot view |
| P3-5 | **Hardcoded values cleanup** | Backend | Replace hardcoded park_id, country, city with registry lookups |
| P3-6 | **Print-friendly layout** | Frontend | @media print styles |
| P3-7 | **Keyboard navigation** | Frontend | Arrow keys to navigate matrix cells |
| P3-8 | **Cell comments / annotations** | Frontend + Backend | Add notes to cells |

---

## SUMMARY BY AREA

| Area | P0 | P1 | P2 | P3 | Total |
|------|----|----|----|----|-------|
| Backend | 4 | 4 | 4 | 1 | 13 |
| Frontend | 9 | 10 | 7 | 5 | 31 |
| UX | 5 | 3 | 3 | 2 | 13 |
| Data Governance | 1 | 0 | 1 | 0 | 2 |
| Performance | 1 | 1 | 0 | 0 | 2 |
| Config | 1 | 0 | 0 | 0 | 1 |

**Total gaps: 10 P0 + 10 P1 + 8 P2 + 8 P3 = 36 items**

---

## EFFORT ESTIMATE

| Priority | Count | Total Est. Effort | Timeline |
|----------|-------|-------------------|----------|
| P0 | 10 | ~15-20 story points | 1-2 weeks |
| P1 | 10 | ~12-18 story points | 2-3 weeks |
| P2 | 8 | ~10-14 story points | 1-2 weeks |
| P3 | 8 | ~8-12 story points | Backlog |
| **TOTAL** | **36** | **~45-64 story points** | **4-7 weeks to P1** |
