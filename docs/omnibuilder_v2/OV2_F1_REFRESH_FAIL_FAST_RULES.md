# OV2-F.1 — REFRESH FAIL FAST RULES

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Refresh Chain
> **Status:** DEFINED

---

## 1. ERROR CODES

### RAW / LANDING

| Code | Condition | Severity | UI Impact | Remediation |
|------|-----------|----------|-----------|-------------|
| `RAW_STALE` | `trips_2026` max date > D-3 | **CRITICAL** | Matrix/shell show old data | Check upstream ingestion pipeline |
| `RAW_YANGO_STALE` | Yango raw MVs max date > D-3 | WARNING | Yango source shows STALE | Re-run `refresh_raw_yango_mvs` |
| `RAW_COVERAGE_GAP` | source_coverage missing park_id | WARNING | Coverage badge shows gap | Refresh Yango source coverage |

### BUSINESS SLICE FACTS

| Code | Condition | Severity | UI Impact | Remediation |
|------|-----------|----------|-----------|-------------|
| `DAY_FACT_STALE` | max trip_date > D-2 | **CRITICAL** | Matrix/shell show STALE freshness | Run `refresh_omniview_real_slice_incremental --days 7` |
| `WEEK_FACT_STALE` | max week_start > D-14 | **CRITICAL** | Week grain matrix broken | Re-run week_fact refresh from day_fact |
| `MONTH_FACT_STALE` | current month has 0 rows | WARNING | Month grain shows incomplete | Re-run after week_fact fixed |
| `MONTH_FACT_ZERO_ROWS` | 0 rows for current month | WARNING | Monthly KPI empty | Check day_fact coverage |

### SNAPSHOTS

| Code | Condition | Severity | UI Impact | Remediation |
|------|-----------|----------|-----------|-------------|
| `SNAPSHOT_STALE` | max snapshot date > D-2 | WARNING | Shell/matrix serve stale data | Re-run `refresh_omniview_v2_snapshots` |
| `SNAPSHOT_MISSING` | 0 READY snapshots for date | WARNING | Endpoint shows SERVING_SNAPSHOT_MISSING | Refresh snapshots for needed date |
| `SNAPSHOT_FAILED` | status=FAILED in snapshot table | WARNING | Same as MISSING | Check snapshot build errors, re-run |

### OPERATING DATE

| Code | Condition | Severity | UI Impact | Remediation |
|------|-----------|----------|-----------|-------------|
| `OPERATING_DATE_MISMATCH` | latest_closed_date != day_fact max | WARNING | Confusion in date picker default | Audit day_fact refresh vs operating date query |
| `OPERATING_DATE_STALE` | latest_closed_date > D-2 | **CRITICAL** | UI shows old default date | Run day_fact refresh |

### REVENUE

| Code | Condition | Severity | UI Impact | Remediation |
|------|-----------|----------|-----------|-------------|
| `REVENUE_GAP` | revenue_yego_final fill < 80% in month_fact | WARNING | Plan vs Real revenue shows OFF_TRACK | Re-run month_fact with revenue data |
| `REVENUE_ZERO` | SUM(revenue_yego_final) = 0 for current month | WARNING | Revenue cells show 0 | Check revenue column in month_fact |
| `REVENUE_PLAN_GAP` | Plan version has 0 projected_revenue | WARNING | Plan vs Real shows NO_PLAN for revenue | Use older plan version with revenue data |

### SLICE COVERAGE

| Code | Condition | Severity | UI Impact | Remediation |
|------|-----------|----------|-----------|-------------|
| `SLICE_COVERAGE_GAP` | < 5 unique business slices in day_fact | **CRITICAL** | Incomplete matrix | Check day_fact refresh, business_slice mapping |
| `SLICE_MAPPING_GAP` | LOB in plan not mapped to slice | INFO | Some slices show NO_PLAN | Update `plan_lob_mapping` |

### PLAN VERSION

| Code | Condition | Severity | UI Impact | Remediation |
|------|-----------|----------|-----------|-------------|
| `PLAN_VERSION_MISSING` | 0 plan versions in table | **CRITICAL** | Plan vs Real fails completely | Upload plan template |
| `PLAN_VERSION_STALE` | Latest plan > 90 days old | INFO | Plan may be outdated | Upload new plan version |
| `PLAN_METRIC_GAP` | Plan version has 0 for requested metric | WARNING | NO_PLAN for that metric | Use version with metric data (`get_best_plan_version`) |

---

## 2. SEVERITY DEFINITIONS

| Severity | Action | UI Banner | Alert |
|----------|--------|-----------|-------|
| **CRITICAL** | Block operation, alert ops | RED — "Data Refresh Required" | Yes |
| WARNING | Degraded, continue | YELLOW — "Data may be incomplete" | Optional |
| INFO | Advisory only | BLUE — "Advisory" | No |

---

## 3. IMPLEMENTATION STATUS

| Code | Implemented? | Location |
|------|------------|----------|
| `SNAPSHOT_MISSING` | ✓ | `omniview_v2_shell.py:46-54`, `omniview_v2.py:124-138` |
| `SNAPSHOT_STALE` | ✓ | `get_snapshot_health()` returns stale count |
| `SNAPSHOT_FAILED` | ✓ | `mark_snapshot_failed()` sets FAILED status |
| `REVENUE_PLAN_GAP` | ✓ | `get_best_plan_version()` picks best version |
| `OPERATING_DATE_MISMATCH` | PARTIAL | Freshness check exists, no automated alert |
| `DAY_FACT_STALE` | NOT IMPLEMENTED | Needs freshness sensor |
| `WEEK_FACT_STALE` | NOT IMPLEMENTED | Needs freshness sensor |
| `REVENUE_GAP` | NOT IMPLEMENTED | Detected by audit but no UI alert |

---

*End of Fail Fast Rules*
