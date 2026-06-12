# OV2-MVP.4A — FEATURE DEPRECATION MATRIX

> **Fase:** OV2-MVP.4A — Deprecation Preparation
> **Sub-document:** Feature Deprecation Matrix
> **Fecha:** 2026-06-12

---

## V1 FEATURES → CLASSIFICATION

### KEEP (same engine, same scope)

| Feature | Reason |
|---------|--------|
| Core matrix (KPI × slice × grain) | Core operational view |
| Day/Week/Month grain | Standard temporal aggregation |
| Country/City filters | Standard operational filters |
| Business slice dimension | Core metric dimension |
| Commission KPI | Core business metric |
| Revenue KPI | Core financial metric |
| Trips/Drivers KPIs | Core operational metrics |
| Date range selection | Standard filter |
| Plan vs Real (monthly) | Core operational comparison |

### REPLACE (V2 equivalent, better)

| V1 Feature | V2 Replacement |
|------------|---------------|
| BusinessSliceOmniviewMatrix (4K lines) | MatrixShell + hooks (modular) |
| BusinessSliceOmniview (legacy flat view) | V2 matrix (business_slice rows) |
| OmniviewCommandHeader (V1) | OmniviewV2CommandHeader (source + 6 filters) |
| OmniviewInspector (904 lines) | CellInspector (structured sections) |
| OperationalStatusBar | V2 status bar (collapsible + extended) |
| DataTrustBadge | CellBadge (CT/YAN/FALLBACK) |
| GlobalFreshnessBanner | FreshnessBadge + status bar |
| KPI cards strip (BusinessSliceOmniviewKpis) | OmniviewV2ExecutiveState |
| Mom/WoW/DoD calculation (V1) | CellDelta (▲▼→ arrows + %) |
| Filter primitives (YearSelect, MonthSelect) | V2 date inputs + selects |

### MERGE (combine V1 + V2)

| V1 Feature | V2 Feature | Result |
|------------|-----------|--------|
| Insight engine (thresholds) | Signal contract (colors) | Signal colors on V2 cells |
| Freshness governance chain | V2 status bar | Extended freshness in status bar |
| FactStatusPanel (backfill) | No V2 equivalent | Backfill controls in V2 (P2) |

### REMOVE (no longer needed)

| Feature | Reason |
|---------|--------|
| EVOLUTION_LEGACY flag + Evolution view | Deprecated in V1 already |
| BusinessSliceOmniview (flat view) | Redundant — matrix covers it |
| OmniviewTopDeviations | Replaced by priority/alert strip |
| Legacy MVs (mv_real_trips_monthly) | Canonical chain replaces them |
| Omniview projection mode (separate) | Replaced by Execution Context |
| RealVsProjectionView | Moved to Forecast Engine |

### FUTURE_ENGINE (moved out of Control Foundation)

| Feature | Engine |
|---------|--------|
| Root cause analysis | Diagnostic |
| Momentum drill (ECharts trend) | Diagnostic |
| Behavioral alerts | Diagnostic |
| Expected progress (projection) | Forecast |
| Real vs Projection | Forecast |
| Action handoff | Action |
| AI recommendations | AI Copilot |

---

## SUMMARY

| Classification | Count | Action |
|----------------|-------|--------|
| KEEP | 9 | No change — core CF |
| REPLACE | 10 | Already replaced by V2 |
| MERGE | 3 | Combine V1+V2 |
| REMOVE | 6 | Deprecate without replacement |
| FUTURE_ENGINE | 7 | Move to their engines |
| **TOTAL** | **35** | |

---

## DEPRECATION SAFETY

| Risk | Mitigation |
|------|------------|
| Removing feature still used | V1 stays available during trial + grace period |
| Wrong classification | Each feature audited against V2 parity matrix (OV2-MVP.0) |
| Engine boundary violation | FUTURE_ENGINE items explicitly moved to correct engine |
