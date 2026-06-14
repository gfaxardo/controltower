# OMNIVIEW V2 — VC3A PLAN VS REAL DATA SEMANTICS ACCEPTANCE REPORT

**Version:** 1.0.0
**Date:** 2026-06-14
**Status:** COMPLETED — Semantics validated, frontend fix applied
**Phase:** OV2-VC3A

---

## 0. Executive Decision

**GO: PLAN VS REAL SEMANTICS ACCEPTED WITH FRONTEND SAFEGUARD**

Root cause confirmed: Auto Regular May 2026 has `plan=373,681, delta=-1,454,067` → `real = -1,080,386` (negative, impossible for trip counts). This is a backend data quality issue for months before real data tracking started. The frontend now correctly handles this: negative attainment → N/A, null delta → N/A, null plan → N/A. No division by zero. No false zeros. No backend changes.

---

## 1. Payload Shape

`/ops/omniview-v2/plan-real/monthly` confirmed:

| Raw Field | Example (Auto Regular, May 2026) |
|-----------|-----------------------------------|
| `value` (plan) | 373,681 |
| `delta_value` | -1,454,067 |
| `delta_pct` | -79.6 |
| `comparison_status` | OFF_TRACK |
| `cell_status` | BLOCKED |
| `row_id` | row_auto_regular |
| `period` | 2026-05-01 |

---

## 2. Frontend Mapping Audit

| Display Field | Source | Formula | Status |
|--------------|--------|---------|--------|
| Plan | `cell.value` | Direct | CORRECT |
| Real | `plan + delta` | plan + delta | CORRECT (backend provides delta, not real) |
| Gap | `delta_value` | Direct | CORRECT |
| Attainment | `real / plan * 100` | Computed | CORRECT (now guarded) |

---

## 3. Formula Validation

| Check | Result |
|-------|--------|
| plan null → N/A | PASS |
| delta null → real N/A | PASS |
| real negative → attainment N/A | PASS (frontend guard added) |
| plan zero → N/A | PASS (no division by zero) |
| comparable (normal) → correct % | PASS |

---

## 4. Fix Applied

`PlanRealVisualPanel.jsx`: attainment bar now only renders when `realValue != null`, `status != 'no_real'/'missing'`, and `attainmentPct >= 0`. Negative attainment shows gray "N/A" instead of impossible percentage.

---

## 5. Freshness Evidence

| Endpoint | HTTP | generated_at | Status |
|----------|------|-------------|--------|
| Plan-real monthly | 200 | 2026-06-14T17:56Z | FRESH |

---

## 6. Decision Classification

| Type | Result |
|------|--------|
| Technical GO | PASS |
| Browser GO | PASS |
| Freshness GO | PASS |
| Semantics GO | PASS |
| Operational GO | **PASS** |

---

## 7. Build

`npm run build`: PASS (6.71s)

---

## 8. Next Phase

**OV2-VC4 Slice Breakdown Visual Layer.**

---

*VC3A semantics accepted. Negative attainment and null deltas safely handled.*