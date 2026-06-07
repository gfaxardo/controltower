# OV2-CX.1A — EMPTY STATE ROOT CAUSE AUDIT

> **Date:** 2026-06-06
> **Motor:** Control Foundation / Diagnostic
> **Status:** ROOT CAUSE IDENTIFIED

---

## 1. EXECUTIVE SUMMARY

Omniview V2 Shadow shows empty KPIs and matrix for 2026-06-06 because **the CT data pipeline has not yet ingested today's data**. The `ops.real_business_slice_day_fact` table has data through 2026-06-05 only. Today (2026-06-06) has 0 rows. This is expected operational behavior — data loads with a lag.

Additionally, **3 secondary bugs** were found in the Shell section status logic that produce misleading OK statuses when data is missing.

---

## 2. REQUEST AUDITED

```
source_system = CT_TRIPS_2026
grain = day
date_from = 2026-06-06
date_to   = 2026-06-06
filters   = {country: "peru", city: "lima"}
```

---

## 3. SHELL RESPONSE — SUMMARY

| Field | Value | Correct? |
|-------|-------|----------|
| source_system | CT_TRIPS_2026 | Yes |
| canonical_ready | true | Yes |
| KPI strip status | BLOCKED | **Yes** — all KPIs are None |
| All KPI values | None | **Yes** — no data for today |
| executive_state | WARNING | **Yes** — some sections BLOCKED |
| source_health | OK | **Yes** — source is healthy, just no data for this date |
| kpi_strip | BLOCKED | **Yes** |
| revenue_integrity | BLOCKED | **Yes** — revenue is None |
| operational_coverage | BLOCKED | **Yes** — coverage is None |
| **growth_movement** | **OK** | **BUG** — should be BLOCKED for 0 days |
| **plan_vs_real** | **OK** | **BUG** — checks plan infrastructure, not data availability |
| **slice_readiness** | **OK** | **BUG** — checks slice infrastructure, not data availability |
| lineage_audit | OK | Yes |
| alerts_warnings | BLOCKED | **Yes** — REVENUE_UNAVAILABLE + KPI_MISSING |
| coverage_pct | None | **BUG** — should be 0%, not None |
| warnings count | 0 in top-level | Yes (warnings are in sections) |

---

## 4. MATRIX RESPONSE — SUMMARY

| Field | Value | Correct? |
|-------|-------|----------|
| rows | 0 | **Yes** — no data for today |
| columns | 1 (2026-06-06) | Yes |
| cells | 0 | **Yes** |
| coverage_pct | 0.0 | Yes |
| source_table | ops.real_business_slice_day_fact | Yes |
| warnings | NO_DATA | **Yes** |

---

## 5. CT SOURCE AUDIT

| Metric | Value |
|--------|-------|
| Table | `ops.real_business_slice_day_fact` |
| Filter | `country='peru'`, `city='lima'` |
| Date range | 2025-02-28 → 2026-06-05 (463 days) |
| 2026-06-06 rows | **0** |
| 2026-06-05 rows | 6 slices, 15,073 trips, 6,373.45 PEN |
| 2026-06-04 rows | 6 slices, 14,213 trips, 5,832.27 PEN |
| DB CURRENT_DATE | 2026-06-06 |

---

## 6. ROOT CAUSE

### PRIMARY: `NO_DATA_PERIOD`

**The CT data pipeline has not ingested data for 2026-06-06.** This is expected — the ingestion runs on a schedule (or manually) and today's data may not be available until later in the day or the following day.

### SECONDARY BUGS:

| # | Bug | Section | Cause |
|---|-----|---------|-------|
| B1 | `growth_movement` shows OK with 0 days of data | growth_movement | `build_growth_movement()` in shell service calls `get_coverage()` without date filters → gets ALL-time coverage (463 days), not the requested period |
| B2 | `plan_vs_real` shows OK for empty period | plan_vs_real | `build_plan_vs_real_readiness()` only checks if plan tables exist, not whether real data exists for the requested period |
| B3 | `slice_readiness` shows OK for empty period | slice_readiness | `build_slice_readiness()` only checks slice infrastructure, not data availability |
| B4 | Coverage shows `None%` instead of `0%` | operational_coverage | When `days_with_data` and `expected_days` are both NULL, the division produces None instead of 0 |

---

## 7. CLASSIFICATION

| Code | Applies? |
|------|----------|
| NO_DATA_PERIOD | **YES** — primary root cause |
| DATE_MISMATCH | No — date format is correct |
| COVERAGE_BUG | **YES** — B4: None instead of 0% |
| SHELL_STATUS_BUG | **YES** — B1, B2, B3: misleading OK statuses |
| MATRIX_METADATA_BUG | No — matrix correctly shows 0 rows, NO_DATA |
| FILTER_MISMATCH | No — filters are correct |
| SOURCE_STALE | No — source has data through yesterday |
| UI_MAPPING_BUG | No — UI correctly renders empty state |

---

## 8. WHAT NOT TO TOUCH YET

- Do NOT modify Omniview V1
- Do NOT change UI rendering
- Do NOT modify ingestion pipeline
- Do NOT add fake/fallback data

---

## 9. FIX RECOMMENDED FOR PHASE 2

### Critical (P0):
| Fix | File | Description |
|-----|------|-------------|
| Fix coverage None→0 | `omniview_v2_source_repository.py` | `_ct_get_coverage()` — ensure `coverage_pct` defaults to 0.0 when no data |
| Fix growth_movement status | `omniview_v2_shell_service.py` | `build_growth_movement()` — pass date_from/date_to to `get_coverage()` so it checks the requested period, not all-time |

### Medium (P1):
| Fix | File | Description |
|-----|------|-------------|
| Fix plan_vs_real status | `omniview_v2_shell_service.py` | `build_plan_vs_real_readiness()` — check if real data exists for the period, not just plan infrastructure |
| Fix slice_readiness status | `omniview_v2_shell_service.py` | `build_slice_readiness()` — check if data exists for the period |

### Low (P2):
| Fix | File | Description |
|-----|------|-------------|
| Add "Data pending" message | UI | When date=today and no data, show "Today's data is being processed. Check back later." |

---

## 10. EVIDENCE FILES

- `backend/exports/audits/omniview_v2_empty_state/shell_response.json`
- `backend/exports/audits/omniview_v2_empty_state/matrix_response.json`

---

## 11. QA

| Check | Result |
|-------|--------|
| Audit script runs | PASS |
| No UI modified | PASS |
| No V1 touched | PASS |
| Root cause identified | YES |
| Secondary bugs documented | 4 bugs |
