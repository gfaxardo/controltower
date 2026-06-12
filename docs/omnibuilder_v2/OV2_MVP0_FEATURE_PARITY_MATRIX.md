# OV2-MVP.0 — FEATURE PARITY MATRIX (V1 vs V2)

> **Fase:** OV2-MVP.0 — Feature Parity Audit
> **Sub-document:** Feature Parity Matrix
> **Fecha:** 2026-06-12

---

## 1. KPIs

| KPI | V1 Status | V2 Status | Parity | Severity | Recommendation |
|-----|----------|----------|--------|----------|----------------|
| `completed_trips` | ✓ day/week/month | ✓ day/week/month (as "orders") | **PARITY** | — | — |
| `active_drivers` | ✓ day/week/month | ✓ day/week/month | **PARITY** | — | — |
| `revenue_yego` | ✓ day/week/month | ✓ day/week/month | **PARITY** | — | — |
| `avg_ticket` | ✓ day/week/month | ✓ day/week/month | **PARITY** | — | — |
| `trips_per_driver` | ✓ day/week/month | ✓ day/week/month | **PARITY** | — | — |
| `commission_pct` | ✓ day/week/month | ✗ | **MISSING** | P0 | Add commission_pct query to matrix view model |
| `cancel_rate_pct` | ✓ day/week/month | ✗ | **MISSING** | P1 | Add cancel_rate_pct (CT-only, Yango doesn't ingest cancellations) |
| `gmv` | ✗ V1 doesn't show | ✓ (raw_yango) | **BETTER_THAN_V1** | — | V2 has GMV, V1 doesn't |
| `business_slice` mapping | ✓ per-KPI | ✗ | **MISSING** | P0 | V2 missing entire business slice dimension |

---

## 2. VIEWS / MODES

| View | V1 Status | V2 Status | Parity | Severity | Recommendation |
|------|----------|----------|--------|----------|----------------|
| Day grain | ✓ | ✓ | **PARITY** | — | — |
| Week grain | ✓ | ✓ | **PARITY** | — | — |
| Month grain | ✓ | ✓ | **PARITY** | — | — |
| Matrix grid | ✓ (4,072 lines) | ✓ (MatrixShell) | **PARTIAL** | P0 | V2 grid functional but lacks signal colors, sticky headers, virtual scroll verification |
| Plan vs Real (monthly) | ✓ | ✓ | **PARITY** | — | — |
| Plan vs Real (daily) | ✓ | ✗ | **MISSING** | P1 | Add daily/weekly PvR to V2 |
| Plan vs Real (weekly) | ✓ | ✗ | **MISSING** | P1 | — |
| Projection mode | ✓ (plan vs real with root cause) | ✗ | **MISSING** | P0 | Projection drill with plan attainment analysis |
| Reports (ECharts) | ✓ (852 lines) | ✗ | **MISSING** | P1 | Add ECharts-based reports view |
| Momentum drill | ✓ (ECharts chart) | ✗ | **MISSING** | P1 | Momentum trend chart in cell inspector |
| Control Loop PvR | ✓ (standalone view) | ✗ | **MISSING** | P2 | Not critical for MVP — standalone view |
| LOB drill (dimensional) | ✓ (4-level drill) | ✗ | **MISSING** | P2 | Park drill in cell inspector is partial equivalent |
| Real Operational snapshot | ✓ | ✗ | **MISSING** | P2 | Today/yesterday/hourly snapshot |
| Shadow comparison (CT vs Yango) | ✗ | ✓ | **BETTER_THAN_V1** | — | V2 has source comparison mode |
| Source system selector | ✗ | ✓ | **BETTER_THAN_V1** | — | V2 has CT_TRIPS_2026 / YANGO_API_RAW toggle |

---

## 3. FILTERS

| Filter | V1 Status | V2 Status | Parity | Severity | Recommendation |
|--------|----------|----------|--------|----------|----------------|
| Date range (from/to) | ✓ (year+month) | ✓ (date inputs) | **PARITY** | — | V2 date inputs are actually more flexible |
| Grain (day/week/month) | ✓ | ✓ | **PARITY** | — | — |
| City | ✓ | ✗ | **MISSING** | P0 | Add city filter to V2 CommandHeader |
| Country | ✓ | ✗ | **MISSING** | P0 | Add country filter to V2 CommandHeader |
| Business Slice | ✓ | ✗ | **MISSING** | P0 | Add business slice filter + dimension |
| KPI selector | ✓ | ✓ | **PARITY** | — | — |
| Subfleet toggle | ✓ | ✗ | **MISSING** | P1 | Add subfleet filter |
| Plan version | ✓ (in projection mode) | ✓ (in PvR mode) | **PARITY** | — | — |
| Source system | ✗ | ✓ | **BETTER_THAN_V1** | — | V2 unique feature |
| Park filter | ✗ | ✗ | **MISSING** | P2 | V2 has park drill but no filter |

---

## 4. UX FEATURES

| Feature | V1 Status | V2 Status | Parity | Severity | Recommendation |
|---------|----------|----------|--------|----------|----------------|
| Signal colors (green/amber/red) | ✓ (insight thresholds) | ✗ | **MISSING** | P0 | Add signal color system to MatrixCell + ExecutiveState |
| KPI delta arrows (↑/↓) | ✓ | ✗ | **MISSING** | P0 | DeltaValue exists but needs direction + color |
| Cell inspector side panel | ✓ (904 lines, Evolution/Momentum) | ✓ (156 lines, structured) | **PARTIAL** | P0 | V2 inspector is better structured but missing Evolution/Momentum drill modes |
| Operational status bar | ✓ (collapsible) | ✗ | **MISSING** | P0 | Add collapsible status bar: freshness, coverage, period state, trust, KPI summary |
| Freshness governance chain | ✓ (RAW → day → week → month) | ✓ (FreshnessBadge only) | **PARTIAL** | P1 | V2 has badge but not governance chain visualization |
| Trust badges | ✓ (DataTrustBadge) | ✓ (StatusBadge) | **PARTIAL** | P1 | V2 trust in cell inspector only, not in matrix cells |
| Backfill controls | ✓ (trigger + progress) | ✗ | **MISSING** | P2 | Not needed for MVP (dev-ops concern) |
| Loading skeleton | ✓ | ✓ | **PARITY** | — | — |
| Empty state | ✓ (SmartEmptyState) | ✓ (GlobalEmptyState + MatrixEmptyState) | **BETTER_THAN_V1** | — | V2 has richer empty states |
| Error boundary | ✓ | ✗ (fallback adapter is partial) | **PARTIAL** | P1 | Add proper error boundary wrapper |
| Fullscreen toggle | ✓ | ✗ | **MISSING** | P2 | Add fullscreen button |
| Zoom control | ✓ | ✗ | **MISSING** | P3 | Low priority |
| Sticky headers | ✓ | ? | **MISSING** | P1 | Verify and implement sticky column headers |
| Virtual scroll | ✓ | ? | **MISSING** | P1 | Verify MatrixShell performance with large datasets |
| No double scroll | ✓ (hardened) | ? | **MISSING** | P0 | Verify no double-scroll in MatrixShell |
| Responsive layout | ✓ | ✓ (Tailwind) | **PARITY** | — | — |
| Dark mode | ✗ | ✗ | **NOT_NEEDED** | — | Not required for MVP |

---

## 5. GOVERNANCE

| Feature | V1 Status | V2 Status | Parity | Severity | Recommendation |
|---------|----------|----------|--------|----------|----------------|
| Freshness badge | ✓ (dot + OperationalStatusBar) | ✓ (FreshnessBadge) | **PARITY** | — | — |
| Source badge | ✗ | ✓ (SourceBadge CANONICAL/SHADOW) | **BETTER_THAN_V1** | — | V2 unique feature |
| Coverage badge | ✓ (OperationalStatusBar) | ✓ (CoverageBadge) | **PARITY** | — | — |
| Lineage visibility | ✗ | ✓ (CellInspector Lineage section) | **BETTER_THAN_V1** | — | V2 shows origin_table, origin_field, aggregation |
| Health state | ✓ (OperationalStatusBar + GlobalFreshnessBanner) | ✓ (AlertStrip + health endpoint) | **PARTIAL** | P1 | V2 health is endpoint-only, not visualized in matrix |
| Fallback visibility | ✗ (implicit) | ✓ (fallback_used flag) | **BETTER_THAN_V1** | — | V2 explicitly shows when using CT fallback |
| Degraded mode | ✓ (partial data handling) | ✓ (emptystate + skeleton + fallback) | **PARITY** | — | — |
| Cross-layer freshness observatory | ✗ | ✓ (RAw → BRIDGE → SNAPSHOT) | **BETTER_THAN_V1** | — | V2 unique endpoint |
| Cell auditability | ✗ | ✓ (/cell-audit endpoint) | **BETTER_THAN_V1** | — | V2 has structured cell audit |
| Reconciliation (CT vs Yango) | ✗ | ✓ (/reconciliation/park) | **BETTER_THAN_V1** | — | V2 unique feature |

---

## 6. PERFORMANCE

| Feature | V1 Status | V2 Status | Parity | Severity | Recommendation |
|---------|----------|----------|--------|----------|----------------|
| Serving facts only (no runtime calcs) | ✓ | ✓ (snapshot-first) | **PARITY** | — | — |
| API latency acceptable | ✓ (mat MVs) | ✓ (snapshot cache) | **BETTER_THAN_V1** | — | V2 snapshot layer reduces DB load |
| Render time acceptable | ✓ (virtual scroll) | ? | **MISSING** | P1 | Measure and profile V2 matrix render |
| No heavy runtime fallback | ✓ (guarded) | ✓ (snapshot → runtime fallback) | **PARITY** | — | — |
| Connection pool | ✓ | ✓ (/infra-health endpoint) | **BETTER_THAN_V1** | — | V2 has explicit pool monitoring |
| Backend identity | ✗ | ✓ (/backend-identity endpoint) | **BETTER_THAN_V1** | — | V2 has git hash + branch verification |

---

## 7. SUMMARY COUNTS

| Category | PARITY | PARTIAL | MISSING | BETTER_THAN_V1 | NOT_NEEDED |
|----------|--------|---------|---------|----------------|------------|
| KPIs (9 items) | 5 | 0 | 2 | 1 | 0 |
| Views (14 items) | 4 | 1 | 7 | 2 | 0 |
| Filters (10 items) | 4 | 0 | 5 | 1 | 0 |
| UX (17 items) | 3 | 4 | 7 | 1 | 1 |
| Governance (10 items) | 1 | 1 | 0 | 5 | 0 |
| Performance (6 items) | 2 | 0 | 1 | 3 | 0 |
| **TOTAL (66 items)** | **19** | **6** | **22** | **13** | **1** |

---

## 8. PARITY HEATMAP

```
KPIs:        ████████░░  (5/7 parity, 2 missing)
Views:       ████░░░░░░  (4/14 parity, 7 missing, 1 partial)
Filters:     ████░░░░░░  (4/10 parity, 5 missing)
UX:          ███░░░░░░░  (3/17 parity, 4 partial, 7 missing)
Governance:  █████████░  (1 parity, 1 partial, 0 missing, 5 better-than-V1!)
Performance: ██████░░░░  (2 parity, 0 partial, 1 missing, 3 better-than-V1!)
```

**Overall: 29% full parity, 20% partial/better, 33% missing, 17% better-than-V1.**

---

## 9. MOST CRITICAL GAPS (Top 10)

| # | Gap | Category | Severity | Reason |
|---|-----|----------|----------|--------|
| 1 | Business Slice dimension missing | KPI | **P0** | Core V1 feature — KPI × business_slice grid |
| 2 | Signal colors missing in matrix cells | UX | **P0** | Operational decision-making requires visual signals |
| 3 | City/Country/Business Slice filters | Filters | **P0** | V2 can't filter by basic operational dimensions |
| 4 | Projection mode (plan vs real root cause) | Views | **P0** | V1 has full projection analysis |
| 5 | Commission rate KPI | KPI | **P0** | Core business metric |
| 6 | No double-scroll verification | UX | **P0** | Critical UX bug from early V1 |
| 7 | Operational status bar | UX | **P0** | Missing freshness/coverage/trust at-a-glance |
| 8 | No Evolution/Momentum drill in cell inspector | Views | **P0** | Inspector is less useful than V1 without trend context |
| 9 | V2 not in production nav registry | Views | **P0** | Can't be used as daily tool if not navigable |
| 10 | Plan vs Real daily/weekly missing | Views | **P1** | Important for granular PvR analysis |
