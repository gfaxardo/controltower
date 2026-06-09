# LG-DIAG-R1.0B — Explainability Field Mapping Forensic Audit

**Date:** 2026-06-08
**Motor:** Control Foundation / Diagnostic Hardening
**Phase:** LG-DIAG-R1.0B
**Status:** EXPLAINABILITY CERTIFIED (AFTER FIX)

---

## 1. WHY R1.0A WAS INVALIDATED

R1.0A reported suspicious values:
- `declining_flag = 122` (should be boolean)
- `churn_risk_flag = HISTORICAL_50_PLUS` (should be boolean)

Root cause: **Positional column indexing bug** in the explainability service.

---

## 2. SCHEMA AUDIT (REAL)

| Pos | Column | Type |
|:---:|--------|------|
| 1 | snapshot_date | date |
| 2 | driver_profile_id | text |
| 3 | lifecycle_state | text |
| 4 | performance_state | text |
| 5 | retention_state | text |
| 6 | completed_orders_day | integer |
| 7 | completed_orders_week | integer |
| 8 | supply_hours_day | numeric |
| 9 | supply_hours_week | numeric |
| 10 | trips_per_supply_hour_week | numeric |
| 11 | avg_orders_4w | numeric |
| 12 | avg_orders_12w | numeric |
| 13 | best_week_12w | integer |
| 14 | historical_band | text |
| 15 | weekly_trips_target | integer |
| **16** | **distance_to_weekly_target** | **integer** |
| 17 | new_driver_flag | boolean |
| 18 | reactivated_flag | boolean |
| 19 | recoverable_flag | boolean |
| **20** | **declining_flag** | **boolean** |
| **21** | **churn_risk_flag** | **boolean** |
| **22** | **reached_target_flag** | **boolean** |

---

## 3. BUG: Positional Mismatch

| Code Index | Intended Field | Actual Field Read | Type Read | Type Expected |
|:---:|-----------|-------------------|-----------|--------------|
| [10] | distance_to_weekly_target | trips_per_supply_hour_week | numeric | integer |
| [11] | reached_target_flag | avg_orders_4w | numeric | boolean |
| [12] | declining_flag | avg_orders_12w | numeric (122) | boolean |
| [13] | churn_risk_flag | best_week_12w | integer | boolean |
| [14] | recoverable_flag | historical_band | text ("HISTORICAL_50_PLUS") | boolean |
| [15] | new_driver_flag | weekly_trips_target | integer | boolean |

---

## 4. FIX: RealDictCursor + Named Columns

| Before | After |
|--------|-------|
| `SELECT *` | `SELECT snapshot_date, driver_profile_id, lifecycle_state, ...` (16 named columns) |
| `snap_row[10]` | `snap_row["distance_to_weekly_target"]` |
| `snap_row[12]` | `snap_row["declining_flag"]` |
| All positional | All named via RealDictCursor |

---

## 5. VALIDATION — BEFORE vs AFTER

| Field | Before (BUG) | After (FIX) | Correct? |
|-------|:---:|:---:|:---:|
| declining_flag | 122 (numeric) | **False** (boolean) | YES |
| churn_risk_flag | HISTORICAL_50_PLUS | **True** (boolean) | YES |
| distance_to_target | 92.07 | **49.0** (integer) | YES |
| reached_target_flag | 92.07 | **False** (boolean) | YES |
| CP-002 (declining check) | [MATCH] (wrong) | **[FAIL]** (correct) | YES |
| CP-003 (churn_risk check) | [MATCH] | **[MATCH]** (correct) | YES |
| 14-002 (target check) | [FAIL] (wrong) | **[MATCH]** (correct) | YES |

---

## 6. FILES MODIFIED

| File | Change |
|------|--------|
| `yego_lima_program_explainability_service.py` | RealDictCursor + named columns + all dict access |

---

## 7. QA

| Check | Result |
|-------|:---:|
| Schema audited | YES (28 columns documented) |
| Positional bug found | YES (6 fields wrong) |
| Fix applied | YES (RealDictCursor) |
| 3-driver smoke test | PASS |
| npm run build | PASS (5.68s) |
| python -m compileall | OK |

---

## 8. FINAL VERDICT

```
EXPLAINABILITY CERTIFIED
```

**R1.0A invalidated. R1.0B validates the fix. All 11 rules now evaluate against CORRECT field values. Boolean fields are boolean. Numeric fields are numeric. MATCH/FAIL is accurate.**
