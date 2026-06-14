# OMNIVIEW V2 — VC4A SLICE BREAKDOWN ACCEPTANCE REPORT

**Version:** 1.0.0
**Date:** 2026-06-14
**Status:** COMPLETED — VC4 accepted, park attribution gap registered
**Phase:** OV2-VC4A

---

## 0. Executive Decision

**GO: VC4 SLICE BREAKDOWN OPERATIONALLY ACCEPTED WITH PARK ATTRIBUTION GAP**

Slice breakdown visual layer renders correctly. Contribution % sums to ~100% for additive metrics. Ratio metrics correctly handled (no blind SUM). Monthly audit confirms all 3 grains populated. Park attribution gap registered for VC5 drill validation.

---

## 1. Browser Acceptance

| Check | Result |
|-------|--------|
| Cockpit + breakdown renders | PASS |
| Metric trips (additive SUM) | PASS |
| Metric revenue (additive SUM) | PASS |
| Metric active_drivers | PASS |
| trips_per_driver (latest period) | PASS — no blind SUM |
| cancel_rate_pct (latest period) | PASS — no blind SUM |
| Grain day/week/month | PASS |
| Matrix toggle | PASS |
| Export CSV | PASS |

---

## 2. Freshness Evidence

| Endpoint | HTTP | Grain | Cells | Status |
|----------|------|-------|-------|--------|
| Matrix day | 200 | day | 49 | FRESH |
| Matrix week | 200 | week | 42 | FRESH |
| Matrix month | 200 | month | 42 | FRESH (YYYY-MM-DD) |
| Health v2 | 200 | — | CT canonical | FRESH |
| Sources | 200 | — | 2 | — |

---

## 3. Real Numbers Observed

| Rank | Slice | Trips May 2026 | Contribution % |
|------|-------|---------------:|---------------:|
| 1 | Auto regular | 373,681 | 82.0% |
| 2 | Tuk Tuk | 31,836 | 7.0% |
| 3 | YMA | 24,755 | 5.4% |
| 4 | PRO | 14,484 | 3.2% |
| 5 | Delivery | 10,114 | 2.2% |
| 6 | Carga | 799 | 0.2% |
| 7 | unmapped | 241 | <0.1% |
| **Total** | | **~455,910** | **~100%** |

Contribution % validates — slices sum approximately to 100%. No negative impossible values in additive metrics.

---

## 4. Monthly Audit Reference

From `OMNIVIEW_V2_REAL_MONTHLY_PARK_SLICE_AUDIT.md`:
- Monthly fact: 285 rows (2025-01 to 2026-06-01)
- Day fact: 8,734 rows 
- Week fact: 120 rows
- Matrix month: 42 cells with `YYYY-MM-DD` format
- Root cause of previous 0 cells: `YYYY-MM` format returns empty

---

## 5. Park Attribution Status

**PARK_ATTRIBUTION_REQUIRES_DRILL_VALIDATION**

Monthly fact does not expose `park_id` column directly. Park attribution uses `fleet_display_name` via bridge (`rebuild_month_from_day_and_bridge.py`). Slice breakdown works at slice level. Park-level drill requires VC5 validation.

Classification: **P1 for park drill certification. Not blocker for slice breakdown.**

---

## 6. Monthly Format Contract

- `YYYY-MM` → 0 cells (incorrect)
- `YYYY-MM-DD` → 42 cells (correct)
- Frontend uses correct format from `operatingDate.default_date`
- Added to `KNOWN_CONSTRAINTS.md`

---

## 7. Defect Registry

| ID | Severity | Area | Status |
|----|----------|------|--------|
| D1 | P1 | Park attribution monthly | To be validated in VC5 drill |
| D2 | P2 | Monthly format awareness | Documented — frontend correct |

---

## 8. Decision Classification

| Type | Result |
|------|--------|
| VC4 Technical GO | PASS |
| VC4 Browser GO | PASS |
| VC4 Freshness GO | PASS |
| VC4 Semantics GO | PASS |
| Monthly Real GO | PASS |
| Park Attribution GO | CONDITIONAL (pending VC5) |
| Operational GO | **PASS** |

---

## 9. Next Step

**OV2-VC5 Matrix as Secondary Detail / Drill Layer with Park Attribution Validation.**

---

*VC4A acceptance complete. Park attribution gap registered.*