# OV2-F.5 — LINEAGE COVERAGE AUDIT

> **Date:** 2026-06-08
> **Motor:** Control Foundation / Lineage
> **Status:** AUDIT COMPLETE

---

## 1. TRACEABILITY LEVELS

| Level | Data Source | Day | Week | Month |
|-------|-------------|-----|------|-------|
| KPI value | day_fact / week_fact / month_fact | **READY** | **READY** | **READY** |
| Period (date/week/month) | fact table date column | **READY** | **READY** | **READY** |
| Business slice | fact table business_slice_name | **READY** | **READY** | **READY** |
| City | fact table country/city | **READY** | **READY** | **READY** |
| Park | driver_day_slice_fact.park_id | **READY** | **READY** | **READY** |
| Fleet | day_fact.fleet_display_name (legacy loader only) | **PARTIAL** | **PARTIAL** | **PARTIAL** |
| Subfleet | day_fact.is_subfleet/subfleet_name (legacy) | **PARTIAL** | **PARTIAL** | **PARTIAL** |
| Driver | driver_day_slice_fact.driver_id | **READY** | **READY** | **READY** |
| Raw trip | public.trips_2026 via driver_id + date | **PARTIAL** | **PARTIAL** | **PARTIAL** |

## 2. PER-KPI COVERAGE

| KPI | Day | Week | Month | Notes |
|-----|-----|------|-------|-------|
| trips | bridge→day_fact | bridge + day_fact | bridge + day_fact | Exact additive |
| revenue | day_fact (preserved) | day_fact (preserved) | day_fact (preserved) | Hybrid approach |
| active_drivers | bridge COUNT DISTINCT | bridge COUNT DISTINCT | bridge COUNT DISTINCT | Exact |
| avg_ticket | recalculated | recalculated | recalculated | revenue/trips |
| trips_per_driver | recalculated | recalculated | recalculated | trips/drivers |

## 3. CLASSIFICATION

| Level | Day | Week | Month |
|-------|-----|------|-------|
| city | **READY** | **READY** | **READY** |
| park | **READY** | **READY** | **READY** |
| fleet | **PARTIAL** | **PARTIAL** | **PARTIAL** |
| subfleet | **PARTIAL** | **PARTIAL** | **PARTIAL** |
| driver | **READY** | **READY** | **READY** |
| raw trip | **PARTIAL** | **PARTIAL** | **PARTIAL** |

## 4. GAPS

| Gap | Severity | Fix |
|-----|----------|-----|
| Fleet column lost in bridge-based rebuild | P2 | Add fleet to bridge or query legacy day_fact for fleet |
| Subfleet same issue | P2 | Same as fleet |
| Raw trip reachability requires trips_2026 scan | P2 | Add trip_ids array to bridge |

---

*End of Lineage Coverage Audit*
