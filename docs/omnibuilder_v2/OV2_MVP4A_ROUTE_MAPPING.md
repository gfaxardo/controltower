# OV2-MVP.4A — V1 → V2 ROUTE MAPPING

> **Fase:** OV2-MVP.4A — Deprecation Preparation
> **Sub-document:** Route Mapping
> **Fecha:** 2026-06-12

---

## PRODUCTION ROUTES (V1 ACTIVE → V2)

| V1 Route | Purpose | V2 Route | Parity | Blocker | Notes |
|----------|---------|----------|--------|---------|-------|
| `/operacion/omniview-matrix` | Core matrix | `/operacion/omniview-v2-shadow` | **FULLY_MAPPED** | — | V2 has same capabilities: KPI × slice × grain |
| `/operacion/omniview` | Legacy flat view | N/A (deprecated) | **NO_EQUIVALENT** | — | V1 hidden. Not needed in V2. |
| `/operacion/reportes` | ECharts reports | N/A | **PARTIALLY_MAPPED** | ECharts not ported | V2 matrix + filters substitute reports. ECharts is P2. |
| `/operacion/control-loop-plan-vs-real` | CL PvR | `/operacion/omniview-v2-shadow` (PvR mode) | **PARTIALLY_MAPPED** | Monthly only | V2 has monthly PvR. Day/week + CL view pending. |
| `/performance/plan-vs-real` | Monthly PvR | `/ops/omniview-v2/plan-real/monthly` | **FULLY_MAPPED** | — | V2 endpoint serves this data |
| `/performance/real` | Real operational | `/operacion/omniview-v2-shadow` (day view) | **FULLY_MAPPED** | — | V2 day grain covers real ops |
| `/operacion/lob-drill` | LOB dimensional drill | V2 cell drill + park filter | **PARTIALLY_MAPPED** | Drill is cell-level, not global | V2 inspector covers park/driver drill. LOB hierarchy pending. |
| `/operacion/business-slice` | Business slice detail | V2 business_slice filter | **FULLY_MAPPED** | — | V2 filter + matrix rows |
| `/plan/acciones` | Plan actions | N/A | **NO_EQUIVALENT** | Plan tab — separate engine | Not Omniview. Plan engine. |
| `/en-revision/real-vs-proyeccion` | Real vs Projection | N/A | **NO_EQUIVALENT** | Forecast Engine (BACKLOG) | Moved to Forecast. Not Control Foundation. |

---

## PERFORMANCE ROUTES

| V1 Route | V2 Equivalent | Parity |
|----------|-------------|--------|
| `/performance/plan-vs-real` | V2 PvR mode | **FULLY_MAPPED** |
| `/performance/real` | V2 day matrix | **FULLY_MAPPED** |

---

## HIDDEN / BACKLOG ROUTES

| V1 Route | Status | V2 Plan |
|----------|--------|---------|
| `/operacion/omniview` | HIDDEN in V1 | Remove (already deprecated in V1) |
| `/operacion/business-slice` | HIDDEN in V1 | Remove (covered by V2 matrix) |
| `/en-revision/real-vs-proyeccion` | BACKLOG | Move to Forecast Engine |

---

## SUMMARY

| Classification | Count | Routes |
|----------------|-------|--------|
| FULLY_MAPPED | 4 | Omniview Matrix, Plan vs Real, Real Ops, Business Slice |
| PARTIALLY_MAPPED | 3 | Reports (ECharts), CL PvR (day/week), LOB Drill |
| NO_EQUIVALENT | 3 | Legacy flat view (deprecated), Plan actions, Real vs Projection |
| **TOTAL** | **10** | |

---

## CUTOVER PLAN

When OV2-MVP.4 executes:
1. `/operacion/omniview-matrix` → redirect to `/operacion/omniview-v2-shadow`
2. `/operacion/reportes` → redirect to V2 with note (ECharts not yet ported)
3. `/operacion/control-loop-plan-vs-real` → redirect to V2 PvR mode
4. HIDDEN routes → no redirect needed (already hidden)
5. Performance routes → redirect to V2 equivalents

---

## REDIRECT READINESS

| Status | Count |
|--------|-------|
| Ready for redirect | 4 routes |
| Needs partial notice | 3 routes |
| Can be removed | 3 routes |
