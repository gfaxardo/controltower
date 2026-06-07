# OV2-CX.1B — GLOBAL VIEW STATUS CONTRACT

> **Date:** 2026-06-06
> **Motor:** Control Foundation / Empty State Fix

---

## VIEW STATUSES

| Status | Condition | Example |
|--------|-----------|---------|
| **READY** | matrix.cells > 0 AND at least one core KPI has value AND coverage > 0 | 2026-06-05: 6 slices, all KPIs populated |
| **EMPTY** | matrix.cells = 0 OR all KPI values are null AND no source error | 2026-06-06: no data yet ingested |
| **PARTIAL** | some values present, some missing, coverage < 95% | Partial ingestion mid-day |
| **BLOCKED** | source error, invalid matrix contract, required source unavailable | Backend 500 |
| **ERROR** | endpoint error, invalid source, unsupported grain unhandled | Network failure |

---

## EMPTY STATE RULES

When `view_status = EMPTY`:

### Frontend must:
- Show dominant empty state banner below command header
- Display: source_system, grain, date range, latest_available_date
- Show "Go to latest available date" CTA button
- Collapse or reduce KPI cards (they show null/--)
- Keep alerts visible (NO_DATA warning, etc.)
- Keep section shell visible but sections reflect correct status

### Backend must:
- Return correct section statuses (no false OK when data is missing)
- Return matrix with 0 rows, NO_DATA warning
- Return coverage_pct = 0.0 (not None)
- Expose `data_availability_status = NO_DATA_PERIOD`
- Expose `latest_available_date`

### Must NOT:
- Invent data
- Show 0 when value is null
- Show OK status for data-dependent sections
- Activate fallback adapter
- Hide the fact that data is missing

---

## SECTION STATUS RULES

### Data-dependent sections (must check if real data exists):
| Section | Must check | No data → |
|---------|-----------|-----------|
| growth_movement | days_with_data > 0 for requested period | BLOCKED |
| revenue_integrity | revenue value is not null | BLOCKED |
| operational_coverage | coverage_pct > 0 for requested period | BLOCKED |
| plan_vs_real | real data exists for period | WARNING |
| slice_readiness | real data rows > 0 for period | WARNING |

### Infrastructure-only sections (OK to show OK even without data):
| Section | Justification |
|---------|--------------|
| source_health | Source is healthy, data just hasn't been ingested yet |
| lineage_audit | Lineage metadata exists regardless of data |
| kpi_strip | Correctly shows BLOCKED when all KPIs are null |
| alerts_warnings | Correctly aggregates warnings from other sections |
