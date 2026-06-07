# OV2-C.1 — PRODUCT SHELL ARCHITECTURE

> **Date:** 2026-06-06
> **Motor:** Control Foundation / Omniview V2 Product Shell
> **Status:** ARCHITECTURE DEFINED

---

## 1. PURPOSE

The OV2 Product Shell is a **logical-product layer** that sits atop the source-agnostic core (OV2-C.0). It defines 10 internal sections that structure operational intelligence without building final UI. Each section is a self-contained block with explicit status, source, KPIs, and allowed navigation actions.

The shell does NOT render pages. It exposes structured data that a future UX layer consumes.

---

## 2. SECTION ARCHITECTURE

```
┌─────────────────────────────────────────────────────────┐
│ 1. EXECUTIVE STATE          [OK|WARNING|BLOCKED]        │
│    ─ Source status + overall health pulse               │
├─────────────────────────────────────────────────────────┤
│ 2. SOURCE HEALTH            [OK|WARNING|BLOCKED]        │
│    ─ Coverage, freshness, ingestion status per source   │
├─────────────────────────────────────────────────────────┤
│ 3. KPI STRIP                [OK|WARNING|BLOCKED]        │
│    ─ orders | revenue | drivers | rev_per_order         │
├─────────────────────────────────────────────────────────┤
│ 4. PLAN VS REAL READINESS   [OK|WARNING|BLOCKED]        │
│    ─ Plan data available? Delta within threshold?       │
├─────────────────────────────────────────────────────────┤
│ 5. GROWTH MOVEMENT          [OK|WARNING|BLOCKED]        │
│    ─ Trips growth vs prior period, WoW/MoM indicators   │
├─────────────────────────────────────────────────────────┤
│ 6. OPERATIONAL COVERAGE     [OK|WARNING|BLOCKED]        │
│    ─ Days with data, gaps, missing periods              │
├─────────────────────────────────────────────────────────┤
│ 7. REVENUE INTEGRITY        [OK|WARNING|BLOCKED]        │
│    ─ Revenue > 0, delta vs CT, reconciliation status    │
├─────────────────────────────────────────────────────────┤
│ 8. SLICE READINESS          [OK|WARNING|BLOCKED]        │
│    ─ Business slices present, slice-level KPIs, gaps    │
├─────────────────────────────────────────────────────────┤
│ 9. ALERTS / WARNINGS        [OK|WARNING|BLOCKED]        │
│    ─ Active warnings, severity distribution, trends     │
├─────────────────────────────────────────────────────────┤
│ 10. LINEAGE / AUDIT         [OK|WARNING|BLOCKED]        │
│    ─ Traceability: source → table → field → value       │
└─────────────────────────────────────────────────────────┘
```

---

## 3. SECTION DEFINITIONS

### 3.1 Executive State
| Attribute | Value |
|-----------|-------|
| Purpose | Overall operational pulse — is the data trustworthy right now? |
| Source | All registered sources |
| Input | Source health + KPI strip + warnings |
| Output | overall_status, source_list, active_warnings_count, last_refreshed |
| Status | OK: all sources healthy, WARNING: ≥1 source has warnings, BLOCKED: no source available |
| What NOT to do | No forecasting, no AI summary generation |

### 3.2 Source Health
| Attribute | Value |
|-----------|-------|
| Purpose | Per-source coverage, freshness, ingestion pipeline status |
| Source | Source registry + coverage/freshness queries |
| Input | coverage_pct, days_with_data, last_refreshed_at, ingestion_runs |
| Output | per-source health block with coverage %, freshness, status |
| Status | OK: coverage≥95%, WARNING: coverage<95% or stale, BLOCKED: no data |
| What NOT to do | No automatic re-ingestion triggers |

### 3.3 KPI Strip
| Attribute | Value |
|-----------|-------|
| Purpose | Top-level numeric KPIs: orders, revenue, drivers, rev_per_order |
| Source | Selected source_system (CT_TRIPS_2026 or YANGO_API_RAW) |
| Input | get_omniview_v2_summary() from core service |
| Output | 4-7 KPI values with unit, period, delta indicator |
| Status | OK: all KPIs have values, WARNING: ≥1 KPI missing, BLOCKED: no KPIs |
| What NOT to do | No plan comparison, no WoW/MoM (those are other sections) |

### 3.4 Plan vs Real Readiness
| Attribute | Value |
|-----------|-------|
| Purpose | Is plan data available for comparison? |
| Source | CT_TRIPS_2026 only (plan infrastructure is CT-native) |
| Input | Plan tables existence check |
| Output | readiness flag, plan_periods_available, source_note |
| Status | OK: plan data exists, WARNING: partial, BLOCKED: no plan data (Yango source) |
| What NOT to do | No actual plan vs real calculation (that's OV2-D.x) |

### 3.5 Growth Movement
| Attribute | Value |
|-----------|-------|
| Purpose | Directional indicators: is the metric growing or shrinking? |
| Source | Selected source, prior period comparison |
| Input | KPI values from current and prior period |
| Output | direction (+/-), magnitude_pct, prior_period |
| Status | OK: computable, WARNING: short series (<7d), BLOCKED: no prior period |
| What NOT to do | No forecast, no suggestion, no root cause analysis |

### 3.6 Operational Coverage
| Attribute | Value |
|-----------|-------|
| Purpose | How complete is the data? Days, parks, slices covered. |
| Source | Source registry coverage queries |
| Input | days_with_data, expected_days, coverage_pct, missing_dates |
| Output | coverage_pct, gap_list, coverage_status |
| Status | OK: ≥95%, WARNING: 50-95%, BLOCKED: <50% or no data |
| What NOT to do | No data repair, no backfill |

### 3.7 Revenue Integrity
| Attribute | Value |
|-----------|-------|
| Purpose | Is revenue data complete and reconcilable? |
| Source | Selected source + CT reconciliation |
| Input | revenue value, revenue_per_order, CT delta, coverage |
| Output | revenue > 0, delta_vs_ct_pct, reconciliation_status |
| Status | OK: revenue>0 and delta<5%, WARNING: delta>5%, BLOCKED: revenue=0 or unavailable |
| What NOT to do | No revenue forecasting, no driver wallet analysis |

### 3.8 Slice Readiness
| Attribute | Value |
|-----------|-------|
| Purpose | Are business slices properly segmented? |
| Source | CT_TRIPS_2026 only (slice infrastructure is CT-native) |
| Input | Slice count, slice KPIs, slice gaps |
| Output | slice_count, slice_list, slice_gaps |
| Status | OK: slices populated, WARNING: some slices missing, BLOCKED: Yango source (no slice data) |
| What NOT to do | No slice definition changes, no slice rebalancing |

### 3.9 Alerts / Warnings
| Attribute | Value |
|-----------|-------|
| Purpose | Aggregated view of all operational warnings |
| Source | All section warnings |
| Input | warnings from all sections |
| Output | warning_list, severity_counts, most_critical |
| Status | OK: 0 warnings, WARNING: ≥1 warning, BLOCKED: critical warnings |
| What NOT to do | No automated alert actions, no escalation |

### 3.10 Lineage / Audit
| Attribute | Value |
|-----------|-------|
| Purpose | Traceability from value back to source table/field |
| Source | Lineage endpoint from core service |
| Input | metric_id → source_table → origin_field → aggregation |
| Output | lineage graph per metric |
| Status | OK: lineage complete, WARNING: partial lineage, BLOCKED: no lineage |
| What NOT to do | No data mutation, no audit trail insertion |

---

## 4. ALLOWED ACTIONS

Each section can expose navigation actions. ONLY these are allowed:

| Action | Description |
|--------|-------------|
| VIEW_DETAIL | Navigate to detailed view of this section |
| VIEW_LINEAGE | Show full lineage trace |
| VIEW_COVERAGE | Show coverage breakdown |
| VIEW_RECONCILIATION | Show reconciliation vs CT |

**NO Action Engine actions. NO Decision. NO Execution.**

---

## 5. SOURCE SYSTEM BEHAVIOR

| Feature | CT_TRIPS_2026 | YANGO_API_RAW |
|---------|--------------|---------------|
| canonical_ready | true | false |
| Plan vs Real | READY | BLOCKED (no plan data) |
| Slice Readiness | READY | BLOCKED (no slice data) |
| Revenue Integrity | OK (self-consistent) | WARNING (delta vs CT) |
| Growth Movement | OK (≥7d data) | WARNING (short series) |

---

## 6. GOVERNANCE

| Rule | Status |
|------|--------|
| No UI touched | PASS (backend only) |
| No Omniview V1 touched | PASS |
| No serving productivo replaced | PASS |
| Allowed actions limited to VIEW_* | PASS |
| canonical_ready explicit per source | PASS |
| No Forecast/Suggestion/Decision/Action | PASS |
