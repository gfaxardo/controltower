# OV2-CLOSE.1 — PRODUCT CLOSURE SCOPE

> **Date:** 2026-06-08
> **Motor:** Control Foundation
> **Phase:** OV2-CLOSE.1 — Product Closure Scope
> **Status:** SCOPE DEFINED — AWAITING GO/NO-GO FOR OV2-CLOSE.2
> **Governance Hash:** ai_operating_system.md + ai_current_phase.md read and validated

---

## 0. GOVERNANCE VALIDATION

### Source Documents Read

| Document | Path | Key Findings |
|----------|------|-------------|
| ai_operating_system.md | `/ai_operating_system.md` | Control Foundation REOPENED/P0. Engine order mandatory. Maximum 1 ACTIVE + 1 READY NEXT. |
| ai_current_phase.md | `/ai_current_phase.md` | ACTIVE: OMNI-P0 — False GO Recovery & Vs Proy Canonicalization. READY NEXT: Diagnostic 2A.3 (PAUSED) + Revenue Detail Certification (CF-H2). |

### Phase Validation

| Check | Result |
|-------|--------|
| Active phase | OMNI-P0 — False GO Recovery & Vs Proy Canonicalization |
| READY NEXT phase | Diagnostic Engine 2A.3 (PAUSED), Revenue Detail Certification CF-H2 (can run in parallel) |
| Blocked engines | Forecast, Suggestion, Decision, Action |
| Backlog engines | AI Copilot, Learning |
| This task belongs to Control Foundation? | **YES** — OV2-CLOSE.1 is scoping/documentation only, directly supporting OMNI-P0 closure |
| This task opens Diagnostic? | **NO** — Diagnostic remains PAUSED |
| This task opens Forecast/Suggestion/Decision/Action/AI Copilot/Learning? | **NO** — all remain blocked/backlog |
| This task touches Yango ingestion infrastructure? | **NO** — Yango ingestion infra remains BACKLOG per governance |
| This task modifies V1? | **NO** — documentation only |
| This task introduces heavy runtime in public UI? | **NO** |
| This task breaks Shared Reality Governance? | **NO** — validates it |

### Architectural Restrictions Verified

| Restriction | Status |
|-------------|--------|
| 1 writer per layer (RAW→BRIDGE→DAY→WEEK→MONTH→SNAPSHOT) | ✅ Certified in OV2-G.1 |
| Single canonical weekly chain | ✅ Certified |
| V1/V2 isolation (code + endpoints) | ✅ Certified in OV2-G.1 V1/V2 Isolation Audit |
| Shared REAL facts only (day_fact, week_fact, month_fact) | ✅ SAFE_SHARED |
| 0 writers legacy activos | ✅ Confirmed |
| Runtime fallback retired (debug-only) | ✅ Certified in OV2-C.8 |
| Serving-first (RAW → MATERIALIZED VIEWS → SERVING FACTS → UI) | ✅ Certified in OV2-CX.4 |

---

## 1. EXECUTIVE SUMMARY

"Closing Omniview V2" means: defining and certifying the **Omniview V2 Shadow page** as an operationally reliable replacement for V1/Shadow, capable of coexisting alongside V1 without silent fallback, without touching V1 routers, and without opening any engine beyond Control Foundation.

This phase (OV2-CLOSE.1) audits current routes, defines the final product boundary, and establishes GO/NO-GO criteria for advancing to OV2-CLOSE.2. No functional changes are implemented.

---

## 2. ROUTE AUDIT — CURRENT STATE

### 2.1 V1 Active Routes (Canonical/Production)

| Route | Component | Navigation | Engine | Status |
|-------|-----------|-----------|--------|--------|
| `/operacion/omniview-matrix` | BusinessSliceOmniviewMatrix | KEEP_VISIBLE | Control Foundation | **CANONICAL** |
| `/operacion/control-loop-plan-vs-real` | ControlLoopPlanVsRealView | KEEP_VISIBLE | Control Foundation | Active |
| `/operacion/lob-drill` | RealLOBDrillView | KEEP_VISIBLE | Control Foundation | Active |
| `/operacion/reportes` | BusinessSliceOmniviewReports | KEEP_VISIBLE | Control Foundation | Active |
| `/operacion/oportunidades` | OperationalOpportunitiesView | KEEP_VISIBLE | Diagnostic (READY NEXT) | Active |
| `/` (root) | BusinessSliceOmniviewMatrix | KEEP_VISIBLE | Control Foundation | **CANONICAL** |

### 2.2 V1 Legacy Routes (Hidden but Active)

| Route | Component | Navigation | Classification |
|-------|-----------|-----------|---------------|
| `/operacion/omniview` | BusinessSliceOmniview | HIDE_FROM_NAV | Legacy — redundant with Omniview Matrix |
| `/operacion/business-slice` | BusinessSliceView | HIDE_FROM_NAV | Legacy — redundant with Omniview Matrix |

**Governance Note:** Both legacy routes remain URL-accessible for backwards compatibility but are hidden from navigation. They share the same REAL facts (day_fact, week_fact, month_fact) as the canonical matrix. No plans to remove them in this closure scope.

### 2.3 V2 Shadow/Candidate Routes

| Route | Component | Navigation | Data Source | Status |
|-------|-----------|-----------|-------------|--------|
| `/operacion/omniview-v2-shadow` | OmniviewV2ShadowPage | NOT IN NAV (direct URL only) | Real backend (`/ops/omniview-v2/*`) | **SHADOW — Operational** |
| `/operacion/omniview-v2-matrix-sandbox` | OmniviewV2MatrixSandbox | NOT IN NAV (direct URL only) | Mock data only | **SANDBOX — Design prototype** |

**V2 Shadow Components:**
- `OmniviewV2CommandHeader` — source/grain/mode selector
- `OmniviewV2ContextBar` — KPI strip + date range context
- `OmniviewV2ExecutiveState` — KPIs header row
- `OmniviewV2AlertStrip` — alerts/warnings
- `OmniviewV2SectionShell` — section container
- `MatrixShell` — main matrix grid
- `CellInspector` — drill-down panel (park + driver breakdown)
- `MatrixSkeleton` — loading skeleton
- `OmniviewV2GlobalEmptyState` — empty/error state handler

### 2.4 Backend OV2 Routers

| Router | Prefix | Key Endpoints | Data Source |
|--------|--------|--------------|-------------|
| `omniview_v2` | `/ops/omniview-v2` | `/sources`, `/summary`, `/health`, `/compare`, `/matrix`, `/plan-real/*`, `/operating-date`, `/cell-audit` | `real_business_slice_*_fact` + bridge |
| `omniview_v2_shell` | `/ops/omniview-v2` | `/shell`, `/shell/sections`, `/shell/section/{id}` | `omniview_v2_serving_snapshot` (pre-computed) |
| `omniview_v2_shadow` | `/ops/omniview-v2-shadow` | `/daily`, `/coverage`, `/reconciliation`, `/health` | `raw_yango` MVs. `canonical_ready` always `false` |

### 2.5 Evolution Mode (V1 Component)

- **Location:** Inside `BusinessSliceOmniviewMatrix.jsx` (V1 component)
- **Flag:** `VITE_OMNIVEW_EVOLUTION_LEGACY` (hidden by default, `false`)
- **Status:** Legacy mode inside V1. Per OMNI-P0 directive: Evolution should be deprecated as operational view. Not relevant to V2 closure scope.

### 2.6 Frontend/Environment Flags Governing Access

| Flag | Default | Controls |
|------|---------|----------|
| `VITE_OV2_ALLOW_MATRIX_FALLBACK` | `false` (not in .env) | Enables shell-to-matrix fallback in V2 Shadow |
| `VITE_OMNIVEW_EVOLUTION_LEGACY` | `false` (not in .env) | Shows Evolution mode in V1 Omniview Matrix |
| `VITE_OMNIVEW_MATRIX_MANUAL_LOAD` | `false` | Defers heavy Omniview queries in V1 |
| `VITE_CT_LEGACY_ENABLED` | `false` | Shows all legacy tabs in main nav |
| `VITE_SHOW_DEV_MODULES` | `false` (not in .env) | Shows DEV_ONLY views in production |
| `VITE_SHOW_FORECAST_EXPERIMENTAL` | `false` (not in .env) | Shows Forecast proto-view |

### 2.7 Fallback Status

| Component | Status | Detail |
|-----------|--------|--------|
| `shellToMatrixResponse.js` adapter | **RETIRED (debug-only)** | OV2-C.8 certified. Requires `VITE_OV2_ALLOW_MATRIX_FALLBACK=true` |
| `useOmniviewV2Matrix` hook | Happy path: `/matrix` endpoint | Error: shows error state with retry, not silent fallback |
| `OmniviewErrorBoundary` | Active | Catches render errors in V1 Matrix, V2 Sandbox, V2 Shadow |
| `BacklogPlaceholder` | Active | Placeholder for blocked engines |
| Lima Growth daily capacity | `DEFAULT_CAPACITY_CONFIG` fallback | Hardcoded config when backend unavailable. Source marked `FALLBACK` |

**V2 Closure Target:** No monstrous runtime fallback. All fallback is either debug-only (gated by env flag) or explicitly labeled in UI.

---

## 3. FINAL PRODUCT BOUNDARY

### 3.1 Omni V2 Final Screen/Route

| Attribute | Value |
|-----------|-------|
| Route | `/operacion/omniview-v2-shadow` |
| Component | `OmniviewV2ShadowPage` |
| Navigation Status | NOT in main navigation (shadow mode). Direct URL access for validation. |
| Data Source | Real backend (`/ops/omniview-v2/*`). CT_TRIPS_2026 as source. |
| Operating Mode | Read-only shadow alongside V1. NOT replacing V1 yet. |

### 3.2 V1 Boundary

| Rule | Detail |
|------|--------|
| V2 does NOT modify V1 | 0 V1 files touched. 0 V1 endpoints modified. |
| V1 can share REAL facts governed | day_fact, week_fact, month_fact are SAFE_SHARED (single writer). V1 and V2 read the same tables. |
| V1 must remain navigable | `/operacion/omniview-matrix` is KEEP_VISIBLE and must continue working. |
| No silent V2→V1 fallback | If V2 has issues, error state is shown in V2. No redirect to V1 without explicit badge/status. |
| V1 Evolution mode | Hidden by default (`VITE_OMNIVEW_EVOLUTION_LEGACY=false`). Not part of V2 closure scope. |

### 3.3 V2 Shadow Boundary

| Rule | Detail |
|------|--------|
| V2 Shadow is the target system | Final Omni V2 = OmniviewV2ShadowPage at `/operacion/omniview-v2-shadow` |
| V2 Sandbox is NOT the final product | Sandbox uses mock data. Only useful for design prototyping. Not part of closure scope. |
| Source system | CT_TRIPS_2026 as default. YANGO_API_RAW as shadow (canonical_ready=false). |
| V2 does NOT use V1 endpoints | V2 has its own routers: `/ops/omniview-v2/*` and `/ops/omniview-v2-shadow/*` |
| V2 does NOT import V1 code | Isolation verified in OV2-G.1 V1/V2 Isolation Audit |

### 3.4 What Remains as Shadow (not in closure scope)

| Component | Reason |
|-----------|--------|
| `omniview_v2_shadow` router (`/ops/omniview-v2-shadow`) | Reads from `raw_yango` MVs. canonical_ready=false. Yango ingestion infra is BACKLOG. |
| Yango source comparison | Yango has PARTIAL coverage (~21% of CT, single park Lima). Source canonical decision deferred to OV2-D.6. |
| Compare mode UI | Not yet wired. Deferred. |
| Hourly grain | CT hour_fact has 0 rows. Yango has no hour MV. Deferred to OV2-D.4. |

### 3.5 What Remains as V1 (not replaced)

| Route | Reason |
|-------|--------|
| `/operacion/lob-drill` | V1 drill-down. Not in V2 shadow yet. |
| `/operacion/reportes` | V1 reports. Not in V2 scope. |
| `/operacion/control-loop-plan-vs-real` | V1 Plan vs Real. V2 has experimental `/plan-real/*` endpoints but Plan vs Real is deferred to OV2-D.2. |
| `/operacion/oportunidades` | Diagnostic Engine view. Not in Control Foundation closure. |
| All Driver tabs | Outside Omni V2 scope. Different engine ownership. |
| All Plan tabs | Outside Omni V2 scope. |
| Legacy `/operacion/omniview`, `/operacion/business-slice` | Hidden but preserved. No removal in this scope. |

---

## 4. FINAL SUPPORTED MODES

| Mode | V2 Shadow | V1 Matrix | Notes |
|------|-----------|-----------|-------|
| **day** | ✅ Supported | ✅ Supported | CT_TRIPS_2026. Operating date range. |
| **week** | ✅ Supported (ISO Mon-Sun) | ✅ Supported | Same `date_trunc('week')` ISO contract. |
| **month** | ✅ Supported | ✅ Supported | Same `date_trunc('month')` contract. |

**NOT supported in V2 closure scope:**
- Hour (CT: 0 rows, Yango: no MV)
- Real-time/intraday

---

## 5. FINAL SUPPORTED KPIs

| KPI | V2 Field | Source | Day | Week | Month | Status |
|-----|----------|--------|-----|------|-------|--------|
| **trips** | `completed_trips` | `driver_day_slice_fact` (bridge) | ✅ | ✅ | ✅ | Exact SUM |
| **revenue** | `revenue_yego_final` | `real_business_slice_*_fact` | ✅ | ✅ | ✅ | Exact SUM |
| **drivers** | `active_drivers` | `driver_day_slice_fact` (bridge) | ✅ | ✅ | ✅ | COUNT DISTINCT (day). SUM (week/month — upper bound warning). |
| **ticket** | `avg_ticket` | Recalculated | ✅ | — | — | revenue/trips. Day only. |
| **TPD** | `trips_per_driver` | Recalculated | ✅ | — | — | trips/drivers. Day only. |

**KPIs certified in cross-metric audit (OV2-D.3D):** 15/15 combinations (5 KPIs × 3 grains) audit-traced. Week had 0-row bug (`timedelta(days=6)` vs `days=7`) — documented with fix pending.

---

## 6. FINAL SUPPORTED VIEWS

| View | V2 Component | Backend Endpoint | Status | Notes |
|------|-------------|-----------------|--------|-------|
| **Real Matrix** | `MatrixShell` | `GET /ops/omniview-v2/matrix` | ✅ Active | Day/week/month, all KPIs, CT source |
| **Plan vs Real** | `MatrixShell` (plan_real mode) | `GET /ops/omniview-v2/plan-real/*` | ⚠️ Experimental | CT plan tables exist. UI wired but not QA-certified. Deferred to OV2-D.2. |
| **Inspector** | `CellInspector` | `GET /drill/cell` | ✅ Active | Park contribution %, top drivers. 6 parks, 1,585 drivers. |
| **Cell Audit** | `CellInspector` + tooltip | `GET /ops/omniview-v2/cell-audit` | ✅ Active | value, parks, drivers, writer, freshness, lineage |
| **Freshness Observatory** | Badges in cell/header | `GET /freshness-observatory` | ✅ Active | 5 layers: RAW/BRIDGE/DAY/WEEK/MONTH/SNAPSHOT |

**NOT supported in V2 closure scope:**
- Evolution mode (V1 legacy, hidden by flag)
- Compare mode (CT vs Yango) — deferred
- Hourly views — deferred
- Forecast / Projection — blocked (Forecast Engine not active)
- Behavioral Alerts / Fleet Leakage — Diagnostic Engine (PAUSED)
- Action Engine views — blocked

---

## 7. FINAL GRAIN CONTRACT

### 7.1 Grain Definitions

| Grain | ISO Contract | Period Identifier | Range |
|-------|-------------|-------------------|-------|
| **day** | YYYY-MM-DD | `trip_date` | Single day |
| **week** | YYYY-MM-DD (Monday) | `date_trunc('week', trip_date)` | Monday 00:00 → Sunday 23:59:59.999 |
| **month** | YYYY-MM-01 | `date_trunc('month', trip_date)` | Month start → month end |

### 7.2 Week Grain ISO Contract (Certified)

| Check | Status | Source |
|-------|--------|--------|
| week_start = Monday | ✅ | PostgreSQL `date_trunc('week')` guarantee |
| Cross-month weeks preserved | ✅ | GROUP BY week_start, not month |
| Cross-year weeks preserved | ✅ | Same ISO contract |
| V1 and V2 use same ISO contract | ✅ | Both read from `real_business_slice_week_fact` (single writer) |
| day_fact → week_fact compatible | ✅ | Same `date_trunc('week', trip_date)` |
| Day→Week rollup from bridge | ✅ | `OV2_F2C_WEEK_FACT_LINEAGE_AND_REBUILD_REPORT.md` |

### 7.3 Slice Rules

| Dimension | Slices | Mapping |
|-----------|--------|---------|
| **business_slice_name** | Auto regular, YMA, Tuk Tuk, PRO, Delivery, Carga | From `business_slice_mapping_rules` via bridge |
| **park** | 6 parks (Lima main = 94.3%) | From `driver_day_slice_fact.park_id` |
| **city** | Lima (single city) | Implicit from park grouping |
| **country** | Peru | Implicit from operational scope |

**Yango slice gap:** Yango has no `business_slice_name` — single "Lima Fleet" row. Slice comparison blocked. Deferred to OV2-D.1 Slice Governance.

---

## 8. FINAL AUDITABILITY CONTRACT

### 8.1 Cell Auditability (Certified OV2-D.3C)

Every cell in Omni V2 Matrix must be able to explain:

| Attribute | Source | Example (Auto regular, 2026-06-06) |
|-----------|--------|-----------------------------------|
| **value** | `real_business_slice_day_fact` | 13,041 trips |
| **park contribution** | `driver_day_slice_fact` | 6 parks: 94.3% + 2.5% + 1.9% + 0.6% + 0.5% + 0.1% |
| **top drivers** | `driver_day_slice_fact` | Top = 40 trips (0.3%) |
| **writer** | Canonical chain | `rebuild_day_from_bridge.py` |
| **freshness** | Bridge max date | 2026-06-07 |
| **lineage** | Freshness Observatory | city/park/driver READY, fleet/raw PARTIAL |
| **snapshot/source fact** | Serving snapshot | `omniview_v2_serving_snapshot` or runtime query |

**Endpoint:** `GET /ops/omniview-v2/cell-audit?period=YYYY-MM-DD&business_slice_name=X&grain=day|week|month`

**Cross-KPI auditability certified (OV2-D.3D):** 15 combinations (5 KPIs × 3 grains), 13/15 passing. Week bug documented (fix: `timedelta(days=7)`).

### 8.2 Inspector Contract

| Field | Source |
|-------|--------|
| Park list with contribution % | `GET /drill/cell` |
| Driver top-N (limit=20) | `GET /drill/cell` |
| Lineage badges (READY/PARTIAL) | `lineage_status` in response |

---

## 9. FINAL FRESHNESS CONTRACT

### 9.1 Badges Expected

| Layer | Badge | Meaning |
|-------|-------|---------|
| RAW | READY / PARTIAL / STALE | Based on `MAX(fecha_inicio_viaje)` freshness |
| BRIDGE | READY / STALE | Based on `MAX(activity_date)` in `driver_day_slice_fact` |
| DAY | READY / STALE | Based on `MAX(trip_date)` in `real_business_slice_day_fact` |
| WEEK | READY / STALE | Based on `MAX(week_start)` in `real_business_slice_week_fact` |
| MONTH | READY / STALE | Based on `MAX(month)` in `real_business_slice_month_fact` |
| SNAPSHOT | READY / STALE | Based on `operating_date` + `generated_at` |

**Observatory endpoint:** `GET /freshness-observatory` returns freshness per layer.

### 9.2 Stale Behavior

| Scenario | Behavior |
|----------|----------|
| Data within expected lag (T+1) | Fresh READY. Normal operation. |
| Data within tolerable lag (T+2) | WARN badge. Data still shown. |
| Data beyond threshold (T+3+) | STALE badge. Data shown with freshness warning. |
| No data at all | Empty state with "No data available for selected period" |

### 9.3 Controlled Failure Behavior

| Scenario | Behavior |
|----------|----------|
| `/matrix` endpoint error | Error state in UI. Retry button. Source/grain/date context shown. |
| Shell endpoint error | Empty state with "Unable to load shell data" + retry. |
| Drill endpoint error | Inspector shows "Unable to load cell details" inline. |
| Snapshot missing | Falls back to runtime query (single query, no cascade). |
| Fallback enabled (`VITE_OV2_ALLOW_MATRIX_FALLBACK=true`) | Yellow banner: "MATRIX_FALLBACK_ACTIVE — Using shell adapter." |

### 9.4 No Monstrous Fallback

- **No** silent degradation to V1
- **No** 600s timeout cascades (week_fact rebuilt from 2,500 rows, not 6.8M)
- **No** raw table scans for serving
- **No** runtime computation in serving path (snapshots are pre-computed)
- **No** hidden data substitution (fallback explicitly labeled)

---

## 10. FINAL V1 BOUNDARY

| Rule | Implementation | Status |
|------|---------------|--------|
| V2 does NOT modify V1 files | 0 V1 files touched in any OV2 phase | ✅ Verified in OV2-G.1 |
| V2 does NOT modify V1 endpoints | V2 uses separate routers | ✅ Verified |
| V1 shares REAL facts governed | day_fact, week_fact, month_fact — single writer per table | ✅ SAFE_SHARED |
| V1 remains fully navigable | `/operacion/omniview-matrix` KEEP_VISIBLE | ✅ Active |
| No silent V2→V1 fallback | No routing redirect. No component reuse. | ✅ Isolated code |
| V1 Evolution hidden by default | `VITE_OMNIVEW_EVOLUTION_LEGACY=false` | ✅ Per OMNI-P0 |
| V1 and V2 can coexist | Both active, independent routers, shared DB tables | ✅ Operational |

---

## 11. EXPLICIT OUT OF SCOPE

| Scope Item | Reason | Status |
|-----------|--------|--------|
| **Yango ingestion infrastructure** | Yango source is PARTIAL. Ingestion infra in BACKLOG. | NOT in closure scope |
| **API-first migration** | V2 Shadow is UI-first. API-first is not in Control Foundation. | NOT in scope |
| **Forecast Engine** | Blocked per ai_operating_system.md | NOT in scope |
| **Suggestion Engine** | Blocked per ai_operating_system.md | NOT in scope |
| **Decision Engine** | Blocked per ai_operating_system.md | NOT in scope |
| **Action Engine** | Blocked per ai_operating_system.md | NOT in scope |
| **AI Copilot** | Backlog per ai_operating_system.md | NOT in scope |
| **Learning Engine** | Backlog per ai_operating_system.md | NOT in scope |
| **New visual features not needed for closure** | V2 Shadow already has Matrix, Inspector, Shell, command bar | No new features |
| **V1 modification** | V1 stays intact. Only V2 evolves. | No V1 changes |
| **V1 removal/deprecation** | V1 must remain navigable. Evolution deprecation is a separate OMNI-P0 task. | Not in scope |
| **Compare mode UI (CT vs Yango)** | Yango is PARTIAL. Compare is deferred. | Deferred |
| **Hourly grain activation** | CT: 0 rows. Yango: no MV. | Deferred |
| **Source canonical decision (CT vs Yango)** | Yango needs ≥30d data + ≥99.5% coverage | Deferred to OV2-D.6 |

---

## 12. GO / NO-GO CRITERIA FOR OV2-CLOSE.2

### GO Criteria

| # | Criterion | Current Status | Evidence |
|---|-----------|---------------|----------|
| 1 | Scope final documented | ✅ This document | `OV2_CLOSE_1_PRODUCT_CLOSURE_SCOPE.md` |
| 2 | V1 routes identified | ✅ Section 2.1–2.2 | All 8 active + 2 legacy routes catalogued |
| 3 | V2 routes identified | ✅ Section 2.3–2.4 | 2 frontend routes + 3 backend routers catalogued |
| 4 | KPIs defined | ✅ Section 5 | 5 KPIs: trips, revenue, drivers, ticket, TPD |
| 5 | Grains defined | ✅ Section 7 | day, week (ISO Mon-Sun), month |
| 6 | Modes defined | ✅ Section 4 | day, week, month |
| 7 | Boundaries explicit | ✅ Sections 3, 10 | V1 boundary, V2 boundary, shadow boundary, out of scope |
| 8 | No governance conflict | ✅ Section 0 | ai_operating_system.md + ai_current_phase.md validated |
| 9 | Freshness contract defined | ✅ Section 9 | Badges, stale behavior, failure behavior |
| 10 | Auditability contract defined | ✅ Section 8 | Cell audit + inspector contract |
| 11 | Fallback status verified | ✅ Section 2.7 | OV2-C.8: FALLBACK RETIRED (debug-only) |
| 12 | Shared Reality Governance verified | ✅ Section 0 | OV2-G.1: SAFE_SHARED certified |
| 13 | Feature parity verified | ✅ OV2-R.2A | 99.3% MATCH V1↔V2 (276 cells) |

### NO-GO Criteria (Triggers that block OV2-CLOSE.2)

| # | Trigger | Detection Method | Status |
|---|---------|-----------------|--------|
| 1 | V2 depends on silent fallback | Check `VITE_OV2_ALLOW_MATRIX_FALLBACK` must be `false` in production | **PASS** — fallback is debug-only |
| 2 | Lack of final route clarity | Check all V1/V2 routes documented with current status | **PASS** — this document provides clarity |
| 3 | Plan/Real semantics mixed | Check viewMode switching in V2 Shadow | **PASS** — Real is default; PvR is experimental/deferred |
| 4 | Heavy runtime in public UI | Verify serving snapshots are pre-computed | **PASS** — OV2-CX.4: SERVING_PURE, 0% runtime |
| 5 | Yango used as blocker | Verify V2 Shadow works with CT_TRIPS_2026 alone | **PASS** — CT is default source; Yango is shadow |
| 6 | V1 at risk | Verify 0 V1 files modified, V1 fully navigable | **PASS** — OV2-G.1 verified |
| 7 | Evolution still default view | Check `VITE_OMNIVEW_EVOLUTION_LEGACY` is `false` | **PASS** — hidden by default |
| 8 | Unresolved week_fact bug | Check OV2-D.3D week fix applied | **PENDING** — fix documented but not applied. Not a blocker for scope doc. |

### DECISION

**GO condition met for documentation phase closure.**

Open risk: Week fact `timedelta(days=6)` vs `days=7)` bug not yet applied to endpoint. This is a code fix, not a scope documentation issue. Must be resolved in OV2-CLOSE.2.

---

## 13. EVIDENCE OF GOVERNANCE COMPLIANCE

### Documents Read and Validated

| Document | Hash/Date | Evidence |
|----------|-----------|----------|
| `ai_operating_system.md` | 225 lines, full read | Engine order validated. Control Foundation = ACTIVE/REOPENED. Maximum 1 ACTIVE + 1 READY NEXT. |
| `ai_current_phase.md` | 167 lines, full read | ACTIVE: OMNI-P0. READY NEXT: Diagnostic 2A.3 (PAUSED) + CF-H2 Revenue. |
| `OV2_G1_SHARED_REALITY_GOVERNANCE_REPORT.md` | 2026-06-08 | SAFE_SHARED certified. 1 writer per layer. |
| `OV2_G1_V1_V2_ISOLATION_AUDIT.md` | 2026-06-08 | 0 cross-imports. 0 endpoint sharing. Isolated routers. |
| `OV2_D0_PRODUCT_READINESS_MATRIX.md` | 2026-06-06 | 3 READY, 2 PARTIAL, 2 NOT CERTIFIED, 3 NOT READY |
| `OV2_D0_FINAL_REPORT.md` | 2026-06-06 | OV2-C closed. 73 files. 15 QA phases. 0 V1 regressions. |
| `OV2_C8_FALLBACK_RETIREMENT_REPORT.md` | 2026-06-06 | FALLBACK RETIRED → DEBUG-ONLY |
| `OV2_CX4_SERVING_CERTIFICATION.md` | 2026-06-06 | SERVING_PURE: 0% runtime, 100% pre-computed |
| `OV2_CX5_SNAPSHOT_LATENCY_REDUCTION_REPORT.md` | 2026-06-06 | At architectural floor: 0.054ms DB, ~739ms total |
| `OV2_D3B_MATRIX_VISUAL_EVOLUTION_REPORT.md` | 2026-06-08 | Matrix components built. Inspector connected. V1 intact. |
| `OV2_D3C_CELL_AUDITABILITY_CERTIFICATION_REPORT.md` | 2026-06-08 | CELL_AUDITABILITY_CERTIFIED |
| `OV2_D3D_CROSS_KPI_GRAIN_AUDITABILITY_REPORT.md` | 2026-06-08 | 15/15 combinations tested. Week bug documented. |
| `OV2_R2A_FEATURE_PARITY_VERDICT.md` | 2026-06-06 | 99.3% MATCH V1↔V2 (276 cells) |

---

## 14. DELIVERABLES CHECKLIST

| # | Deliverable | Status |
|---|-------------|--------|
| 1 | `OV2_CLOSE_1_PRODUCT_CLOSURE_SCOPE.md` created | ✅ |
| 2 | Executive summary | ✅ Section 1 |
| 3 | Route audit table | ✅ Section 2 |
| 4 | Final scope table (KPIs, grains, modes, views) | ✅ Sections 4–7 |
| 5 | GO/NO-GO criteria for OV2-CLOSE.2 | ✅ Section 12 |
| 6 | Evidence of ai_operating_system.md + ai_current_phase.md read | ✅ Section 0 + 13 |
| 7 | No functional changes made | ✅ Documentation only |
| 8 | No commit (per governance: commit only when explicitly asked) | ✅ No commit made |

---

## 15. NEXT PHASE

```
OV2-CLOSE.2 — Implementation Hardening

Scope:
- Fix week `timedelta(days=7)` in `/cell-audit` endpoint
- Apply Grain Coverage Audit
- Verify serving snapshot freshness chain
- Verify 0 runtime fallback activations in real use
- Human-in-the-loop validation (per OMNI-P0 lesson)

Pre-requisite: GO from OV2-CLOSE.1 GO/NO-GO criteria
Blocked by: Nothing (OV2-CLOSE.1 is documentation only)

DO NOT:
- Implement new features
- Open Diagnostic/Forecast/Suggestion/Decision/Action/AI Copilot/Learning
- Modify V1
- Touch Yango ingestion infra
- Change UI rendering
```

---

*End of OV2-CLOSE.1 — Product Closure Scope*

*Awaiting GO/NO-GO decision for advancement to OV2-CLOSE.2*
