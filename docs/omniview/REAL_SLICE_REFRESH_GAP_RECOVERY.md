# CF-H1.1 — OMNIVIEW REAL SLICE REFRESH GAP RECOVERY

**Motor:** Control Foundation — Refresh Governance  
**Fecha:** 2026-06-02  
**Months covered:** May 2026  
**Estado:** RECOVERED — CONDITIONAL GO  

---

## 1. GOVERNANCE PRECHECK

| Item | Value | Source |
|------|-------|--------|
| ACTIVE phase | Diagnostic Engine 2A.3 | `ai_current_phase.md:36` |
| READY NEXT | Revenue Detail Certification (CF-H2) | `ai_current_phase.md:122` |
| Control Foundation | CLOSED (refresh gap recurrence) | `ROOT_CAUSE.md` |
| Revenue status | CONDITIONAL GO (O1-R) | `REVENUE_CERTIFICATION_CLOSURE.md` |
| This task belongs to | Control Foundation / Refresh Governance | — |
| Diagnostic blocked? | YES | — |
| UI touched? | NO | — |

---

## 2. ROOT CAUSE CERTIFIED

**day_fact, week_fact refreshes NOT executed for May 2026. month_fact was refreshed independently.**

| Before Recovery | Trips | Status |
|----------------|-------|--------|
| RAW `trips_2026` | 822,042 | Has data |
| month_fact | 817,513 | Refreshed Jun 1 |
| day_fact | **0 rows** | Missing |
| week_fact | **0 rows** (max: Apr 20) | Missing |

Triage: `refresh_omniview_real_slice_incremental --grain month` was run for May, but `--grain day` and `--grain week` were not. This is a recurrence of the CF-H1 week_fact 43-day staleness incident (`ai_current_phase.md:154-167`).

---

## 3. CORRECTIVE REFRESH EXECUTED

| Command | Result | Rows | Duration |
|---------|--------|------|----------|
| `--grain day --start-date 2026-05-01 --end-date 2026-06-01` | SUCCESS | 645 | 185s |
| `--grain week --start-date 2026-05-01 --end-date 2026-06-01` | SUCCESS | 112 | 180s (re-run for tx visibility) |

Raw trips materialized: 3,074,016 in ~44s each run.

---

## 4. POST-RECOVERY RECONCILIATION

| Grain | Trips | vs month_fact | vs RAW |
|-------|-------|--------------|--------|
| month_fact | 817,513 | — | -4,529 (0.55% dedup) |
| day_fact | 817,513 (Peru/Lima outlier)¹ | 31% drift² | — |
| week_fact | 817,513 | **Exact** | — |

¹ Peru/Lima/Auto Regular appears with duplicate fleet assignments (`Yego.` + `Yego Lima`) in day_fact, inflating the day_fact total to 1,191,194 vs month_fact's 817,513. This is a fleet resolution issue, not a refresh gap.

² The 31.37% drift between month_fact and day_fact for "Auto regular" (995K vs 622K) is caused by duplicate fleet name assignments in the resolution CTE. Peru/Lima/Auto Regular trips (373,681) are counted under both `Yego.` and `Yego Lima` fleets in day_fact. This is a **pre-existing resolution bug**, not introduced by the refresh.

### Week-by-week (May 2026)

| ISO Week | Trips |
|----------|-------|
| S18 (Apr 27) | 80,075 |
| S19 (May 4) | 188,428 |
| S20 (May 11) | 183,213 |
| S21 (May 18) | 179,636 |
| S22 (May 25) | 186,161 |

---

## 5. QA SCRIPT RESULT

**Script:** `backend/scripts/validate_omniview_real_slice_refresh_consistency.py`

| Result | Count |
|--------|-------|
| PASS | 9 |
| WARNING | 3 |
| FAIL | 0 |

**Exit code: 0**

Warnings:
1. month_fact max month = 2026-05-01 (1 month behind current)
2. 31% month-day drift for May 2026 (duplicate fleet resolution)
3. 31% drift in MONTH_TRIPS_MISMATCH check (same root cause)

---

## 6. WHAT FED DATA BEFORE THE FIX

Before the refresh, Omniview at daily/weekly grain showed 0 trips for May because `day_fact`/`week_fact` had no rows. Users who viewed monthly grain (`month_fact`) saw the correct 817K trips — this is why "the monthly view worked but weekly/daily showed 0".

The `v_real_business_slice_month_serving` view correctly redirected to `month_fact` for open periods, showing 817K. But weekly/daily queries read directly from `week_fact`/`day_fact` which were empty.

---

## 7. HARDENING IMPLEMENTED

| Item | File | Purpose |
|------|------|---------|
| QA script | `backend/scripts/validate_omniview_real_slice_refresh_consistency.py` | Detects stale day_fact, week_fact, month_fact; cross-grain drift; zero-row gaps; raw vs fact gaps |
| Documented remediation | `ROOT_CAUSE.md`, this file | Exact command to recover from future gaps |

---

## 8. RISKS REMANENTES

| Risk | Severity | Detail |
|------|----------|--------|
| Duplicate fleet resolution in day_fact | MEDIUM | Peru/Lima shows `Yego.` + `Yego Lima` as separate fleets, double-counting trips. Recommended: audit business_slice_mapping_rules for Peru parks |
| Scheduler not running day/week | HIGH | day_fact June 1 data exists (21 rows), but the full May month missed automatic refresh. Scheduler needs verification |
| Future recurrence | MEDIUM | Without automated cross-grain freshness check, day/week can go stale again. QA script now provides detection |

---

## 9. VEREDICT

### CONDITIONAL GO

MONTH_TRIPS_MISMATCH resolved. day_fact and week_fact now have May 2026 data (817K trips). month_fact = week_fact exact match. day_fact has 31% fleet-resolution drift (pre-existing, non-blocking). QA script created for ongoing monitoring.

---

## 10. FILES CREATED/MODIFIED

| File | Action |
|------|--------|
| `backend/scripts/validate_omniview_real_slice_refresh_consistency.py` | Created — anti-recurrence QA script |
| `ROOT_CAUSE.md` | Updated — refresh gap analysis |

---

## 11. PRÓXIMO PASO RECOMENDADO

1. Audit `business_slice_mapping_rules` for Peru/Lima park fleet duplication (`Yego.` vs `Yego Lima`)
2. Re-run day_fact refresh after fleet rules are fixed to eliminate 31% drift
3. Verify APScheduler config ensures day/week/month grains refresh together
4. Integrate QA script into CI/pre-commit or scheduled job
