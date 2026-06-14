# OMNIVIEW V2 — UI P1F PLAN VS REAL VISUALIZATION REPORT

**Version:** 1.0.0
**Date:** 2026-06-13
**Status:** COMPLETED — Plan vs Real visualization implemented
**Phase:** OV2-UI-P1F

---

## 0. Executive Decision

**GO: PLAN VS REAL VISUALIZATION COMPLETE**

Plan vs Real cell display enhanced. Each cell in `plan_real` mode shows plan value, attainment %, behind/ahead label, and semantic tone. Uses existing endpoint (`/ops/omniview-v2/plan-real/monthly`). No forecast. No diagnostic.

---

## 1. Scope

Enhance `plan_real` view mode in Omniview V2 matrix cells with richer Plan vs Real comparison display. Derive real value, attainment %, and status from existing payload fields.

---

## 2. Payload Audit

**Endpoint:** `/ops/omniview-v2/plan-real/monthly`

| Field | Available | Meaning |
|-------|-----------|---------|
| `value` | YES | Plan value (projected) |
| `delta_value` | YES | Real - Plan absolute |
| `delta_pct` | YES | (Real - Plan) / Plan * 100 |
| `comparison_status` | YES | OFF_TRACK, ON_TRACK, etc. |
| `lineage_refs.plan_table` | YES | `ops.plan_trips_monthly` |
| `lineage_refs.real_table` | YES | `ops.real_business_slice_month_fact` |
| `period_status` | YES | CLOSED, PARTIAL, FUTURE |
| `cell_status` | YES | BLOCKED, OK, WARNING |

**Derived:**
- `real_value` = `plan_value + delta_value`
- `attainment_pct` = `real / plan * 100`

---

## 3. UI Contract

Created: `omniviewV2PlanReal.js` → `getPlanRealDisplay(cell, metricId)`

Returns: `{ planValue, realValue, deltaValue, deltaPct, attainmentPct, status, tone, planFormatted, realFormatted, attainmentFormatted, isFuture, isMissing }`

Status handling:
- `comparable`: both plan and real exist
- `no_plan`: plan is null → neutral N/A
- `no_real`: real can't be derived → neutral N/A
- `not_comparable`: COMPARISON_STATUS → neutral gray
- `future`: period_status=FUTURE → neutral disabled
- `missing`: both null → N/A

Tone: uses `getDeltaTone` from color semantics engine. Respects metric polarity (`cancel_rate_pct` inverted).

---

## 4. Components Updated

| File | Change |
|------|--------|
| `omniviewV2PlanReal.js` | **CREATED** — Plan vs Real display engine |
| `MatrixCell.jsx` | **MODIFIED** — Shows attainment % + ahead/behind label in plan_real mode |
| `MatrixRow.jsx` | `viewMode` prop propagated |
| `MatrixShell.jsx` | `viewMode` prop propagated |
| `OmniviewV2ShadowPage.jsx` | `viewMode` passed to MatrixShell |

---

## 5. Validation

| Scenario | Result |
|----------|--------|
| real + plan (comparable) | attainment visible, tone correct |
| no plan | N/A neutral |
| no real | N/A neutral |
| future | neutral disabled |
| not comparable | neutral gray |
| cancel_rate_pct lower-is-better | tone inverted (negative delta = green) |
| metric change | PvR updates |
| sort change | stable |
| period preset change | PvR updates |
| `npm run build` | PASS (8.87s) |

---

## 6. Remaining Gaps

| # | Gap | Status |
|---|-----|--------|
| P0-1 | Multi-metric selector | COMPLETE |
| P0-2 | CSV export | COMPLETE |
| P0-3 | Color semantics | COMPLETE |
| P0-4 | Sort controls | COMPLETE |
| P0-5 | Plan vs Real visualization | **COMPLETE** |
| P0-6 | Period presets | COMPLETE |

**ALL P0 GAPS CLOSED.**

---

## 7. Next Phase

**OV2-UI-P2: Drilldown & Freshness Transparency.** Enhance inspector with richer data, add trust scoring visibility, improve freshness display. Or final smoke validation for production readiness.

---

*Plan vs Real visualization complete. All 6 P0 gaps closed.*