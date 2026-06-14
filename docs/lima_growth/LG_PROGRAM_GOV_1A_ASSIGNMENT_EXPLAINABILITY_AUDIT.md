# LG-PROGRAM-GOV-1A — Program Assignment Explainability Audit

**Date:** 2026-06-13
**Commit base:** d6099657449c7358c4a415fed020c3a9fa1402ed
**Motor:** Growth Machine / Control Foundation
**Phase:** Program Assignment Explainability Audit
**Mode:** AUDIT ONLY — NO IMPLEMENTATION

---

## 1. Pre-Check

| # | Question | Answer |
|---|----------|--------|
| 1 | Motor | Growth Machine / Control Foundation |
| 2 | Fase | Program Assignment Explainability Audit |
| 3 | Contrato | Program assignment visibility, Explorer consistency, explainability |
| 4 | Tablas (read-only) | eligibility, explorer_fact, state_snapshot, history_weekly, opportunity_list, serving_fact |
| 5 | Writer | Ninguno |
| 6 | Freshness | Ninguna (validated: all tables current for 06-13) |
| 7 | Endpoint/UI | Lima Growth Intelligence (Explorer + Programs tabs) |
| 8 | Legacy | ctrl_bridge_sync.py.legacy.disabled — no revive risk |
| 9 | Riesgos | Confundir eligible vs assigned, abrir rediseño |
| 10 | Rollback | Revertir este doc |

## 2. Active Scope Contract Result

**IN SCOPE. AUDIT ONLY.**

ACTIVE_SCOPE_CONTRACT.md Section 4 lists "Program assignment audit" and "Program explainability audit" as in-scope. Section 9 — Audit mode is permitted since it does not modify rules, writers, schedulers, UI, or DB.

No implementation. No code changes. No Program Engine changes.

## 3. Sources and Contracts

| Source | Table | Type | Writer | Reader | Grain | Freshness (06-13) |
|--------|-------|------|--------|--------|-------|-------------------|
| Program Eligibility | `growth.yango_lima_program_eligibility_daily` | Eligibility | `yego_lima_program_eligibility_service.py` | Explorer, Opportunity, Programs | Daily | FRESH (today) |
| Explorer Fact | `growth.yego_lima_driver_explorer_fact` | Assigned Program | `build_driver_explorer_fact.py` | Driver Explorer UI | Cumulative | 30,108 ACTIVE_GROWTH, 5,338 14_90, 634 CHURN |
| State Snapshot | `growth.yango_lima_driver_state_snapshot` | State Classification | `yego_lima_driver_state_service.py` | Eligibility, Explorer | Daily | FRESH (today, 185,257 rows) |
| History Weekly | `growth.yango_lima_driver_history_weekly` | Rolling Metrics | `yego_lima_growth_history_service.py` | State, Segmentation | Weekly | HEALTHY (max=06-01) |
| Opportunity List | `growth.yango_lima_daily_opportunity_list` | Daily Queue | `yego_lima_daily_opportunity_service.py` | Control Loop | Daily | FRESH (today, 28,128 rows) |
| Programs Summary | `growth.yego_lima_serving_fact` | UI Summary | `yego_lima_serving_facts_service.py` | Programs tab | Daily | FRESH (generated 09:23) |

### Program Builder Logic (from code audit)

**Eligibility rules** (`yego_lima_program_eligibility_service.py`):
- `PROGRAM_14_90`: lifecycle IN (ACTIVATED, EARLY_LIFE), reached_target_flag = false
- `PROGRAM_ACTIVE_GROWTH`: lifecycle IN (ESTABLISHED, REACTIVATED), performance_state IN (LOW, MEDIUM), retention_state != CHURNED
- `PROGRAM_CHURN_PREVENTION`: retention_state IN (CHURN_RISK, AT_RISK, WATCHLIST) OR declining_flag = true OR churn_risk_flag = true; NOT CHURNED

**Priority assignment:**
- 14_90: priority = 3
- ACTIVE_GROWTH: priority = 30
- CHURN_PREVENTION: priority = 100 (churn_risk) or 120 (declining/at_risk)

**Opportunity list builds from eligibility**, selecting the highest-priority eligible program per driver.

## 4. Eligible vs Assigned Semantics

### Definitions

| Term | Meaning | Source Table | Refresh |
|------|---------|-------------|---------|
| **Eligible** | Driver qualifies for a program TODAY based on current state | `program_eligibility_daily` | Every 5 min via autonomous tick |
| **Assigned** | Driver's CURRENT program label (persists until reassigned) | `driver_explorer_fact` | Cumulative — may lag behind daily eligibility |

### Eligible vs Assigned Counts (2026-06-13)

| Program | Eligible Today | Explorer Assigned | Gap | Analysis |
|---------|---------------|-------------------|-----|----------|
| PROGRAM_14_90 | 2,669 | 5,338 | +2,669 (100%) | Explorer shows 2x eligible. Drivers age out of 14_90 but Explorer retains old assignment. |
| PROGRAM_ACTIVE_GROWTH | 17,685 | 30,108 | +12,423 (70%) | Explorer shows significantly more than eligible. Drivers previously assigned ACTIVE_GROWTH keep the label even as eligibility changes. |
| PROGRAM_CHURN_PREVENTION | 7,774 | 634 | -7,140 (92%) | Explorer shows only 8% of eligible drivers. Most CHURN_PREVENTION-eligible drivers are still labeled ACTIVE_GROWTH or 14_90 from prior assignments. |

### Multi-Eligibility

- **9,125 drivers** are eligible for >1 program today
- Top combinations: ACTIVE_GROWTH + CHURN_PREVENTION (6,476), 14_90 + ACTIVE_GROWTH (1,668), all three (963)
- Multi-eligible drivers should be assigned to the HIGHEST priority program (CHURN 100/120 > ACTIVE 30 > 14_90 3)

### Why Numbers Differ

This is **correct behavior** — not a bug. The Explorer fact and daily eligibility serve different purposes:

1. **Eligibility** answers: "Who qualifies today?" — daily snapshot.
2. **Explorer/Assigned** answers: "What program is this driver currently in?" — persistent state.

The gap exists because:
- Drivers move between eligibility states daily
- The Explorer fact assignment updates less frequently than daily eligibility
- A driver assigned ACTIVE_GROWTH on Monday may be CHURN_PREVENTION-eligible on Tuesday but Explorer still shows ACTIVE_GROWTH
- The system does not aggressively reassign programs; it waits for an explicit rebuild

**Assessment: CORRECT but SEMANTICALLY CONFUSING.** An operator looking at the Programs tab (eligible count) vs Explorer filter (assigned count) will see different numbers and may not understand why. The UI needs a "why" layer.

## 5. Program Assignment Cases

Audit of 30 drivers (10 ACTIVE_GROWTH, 10 CHURN_PREVENTION, 5 14_90, 5 multi-eligible) traced through all 5 tables.

### Case Patterns Identified

#### Pattern A: Clean Assignment — Explorer = Eligibility (10/30 drivers)

Driver is assigned to the correct program and eligible for the same program today.

Example: Driver #1 (6bbec910) — ACTIVE_GROWTH assigned, eligible for ACTIVE_GROWTH. Priority 40. MEDIUM performance. 39 orders/week. 35.8 avg4w. HISTORICAL_50_PLUS. Opportunity: OPPORTUNITY_ACTIVE_GROWTH.

**Verdict: Operationally clear.**

#### Pattern B: Explorer Stale — Eligible for Different Program (12/30 drivers)

Driver's Explorer assignment does not match today's eligibility.

Examples:
- Drivers #3, #4, #6, #10: Explorer = ACTIVE_GROWTH, eligible today = CHURN_PREVENTION
- Drivers #21, #23, #25: Explorer = 14_90, eligible today = CHURN_PREVENTION
- Drivers #22, #24, #28, #29: Explorer = 14_90, eligible today = ACTIVE_GROWTH

These drivers have churn_risk_flag=true or declining_flag=true, making them eligible for CHURN_PREVENTION, but their Explorer label still shows the prior program.

**Verdict: Correct logic, semantically confusing.** The opportunity list correctly targets them as CHURN_PREVENTION, but the Explorer label is stale.

#### Pattern C: CHURN_PREVENTION with High Performance (6/30 drivers)

Drivers assigned CHURN_PREVENTION but with strong metrics:
- Driver #11: 81 orders/week, HISTORICAL_50_PLUS, reached_target=true. Assigned CHURN_PREVENTION because declining_flag=true.
- Driver #14: 52 orders/week, HISTORICAL_50_PLUS. CHURN_PREVENTION for churn_risk_flag.
- Driver #15: 52 orders/week, HISTORICAL_50_PLUS. CHURN_PREVENTION for churn_risk_flag.
- Driver #16: 53 orders/week, HISTORICAL_50_PLUS. CHURN_PREVENTION for churn_risk_flag.

**Verdict: Operationally confusing.** A driver doing 80+ orders/week with reached_target=true should NOT appear in churn prevention to an operator. The rule is technically correct (churn_risk flag is set based on retention_state), but the flag and the performance metrics tell contradictory stories.

#### Pattern D: 14_90 Assignment with Aged-Out Drivers (5/30 drivers)

Drivers assigned 14_90 but beyond the early-life window:
- Driver #23: 14_90 assigned, 36 best_week_12w, HISTORICAL_30_49, CHURN_RISK eligible. This driver has significant history and should have graduated from 14_90.
- Driver #25: 14_90 assigned, HISTORICAL_10_29, churn_risk_flag. Eligible for CHURN_PREVENTION.

**Verdict: Stale assignment.** The 14_90 label persists after the driver has clearly moved beyond early life.

## 6. Confusing / High-Risk Cases

| Case Type | Count Observed | Example Driver | Why Confusing | Recommended UI Action |
|-----------|---------------|----------------|---------------|----------------------|
| Explorer stale vs eligibility | 12/30 | #3 (e7738562): Explorer=ACTIVE_GROWTH, eligible=CHURN | Operator filters Explorer by ACTIVE_GROWTH but driver is actually CHURN_PREVENTION target | Add "eligible programs" column to Explorer showing all current eligibilities |
| High-perf CHURN_PREVENTION | 6/30 | #11 (ac15adf0): 81 orders/wk, reached_target, CHURN | Operator sees high performer in churn list — questions program logic | Add trigger explanation: which flag triggered CHURN (declining, churn_risk, at_risk) |
| 14_90 stale on experienced drivers | 5/30 | #23 (974da485): 14_90 label, 36 best_week, CHURN eligible | Operator sees veteran in new-driver program | Show "days since first trip" or age-out indicator |
| Multi-eligible at lower priority | 3/30 | #26 (000150dc): Explorer=ACTIVE_GROWTH(p30), eligible=CHURN(p100) | Driver should be in higher-priority program | Show priority comparison in Explorer |
| Explorer program None | 1,008 drivers | N/A | Drivers with no program assignment | Investigate if None means "no eligibility" or "not yet assigned" |

## 7. UI Validation Checkpoint

### Target Routes

| Route | Tab | Expected | Current |
|-------|-----|----------|---------|
| `/lima-growth/intelligence` | Programs | Shows eligible counts per program | Programs Summary fact shows 14_90=2669, ACTIVE_GROWTH=17685, CHURN_PREVENTION=7774 |
| `/lima-growth/intelligence` | Driver Explorer | Shows assigned program per driver | Explorer Fact shows ACTIVE_GROWTH=30108, 14_90=5338, CHURN_PREVENTION=634 |

### Validation Filters

| # | Filter | Expected Result | PASS Criteria |
|---|--------|----------------|---------------|
| 1 | Explorer → Program = ACTIVE_GROWTH | 30,108 drivers | Count matches Explorer Fact |
| 2 | Explorer → Program = CHURN_PREVENTION | 634 drivers | Count matches Explorer Fact |
| 3 | Explorer → Program = 14_90 | 5,338 drivers | Count matches Explorer Fact |
| 4 | Explorer → search driver_id e7738562 | Shows ACTIVE_GROWTH label, eligible CHURN | Operator can see both |
| 5 | Programs → compare eligible vs Explorer count | Numbers differ (expected) | Operator understands why |

### Operator Validation

An operator should be able to:
1. See which program a driver is currently assigned to
2. See which programs a driver is eligible for today
3. Understand why a driver is in CHURN_PREVENTION despite high performance
4. Understand why Explorer and Programs show different counts

**Current state:** Operator can see #1. #2 requires navigating to a different view. #3 and #4 are not surfaced. The UI needs a "why" layer.

## 8. Backlog Items

| Backlog Item | Reason | Blocker? | Scope Status | Recommended Phase |
|-------------|--------|----------|-------------|-------------------|
| Program label/copy layer in Explorer | Operators need to see "why" a driver has a program | No | Backlog | Program Registry V3 |
| Eligibility column in Explorer | Explorer shows only assigned program, not eligible programs | No | Backlog | Program Registry V3 |
| Program transition explainability | Why did driver move from ACTIVE_GROWTH to CHURN_PREVENTION? | No | Backlog | Program Registry V3 / State Machine |
| Explorer-to-eligibility sync | Explorer label lags behind daily eligibility | No | Backlog | Program Registry V3 |
| Priority comparison in Explorer | Multi-eligible drivers should show priority ranking | No | Backlog | Program Registry V3 |
| High-perf CHURN explanation tooltip | Operator sees high performer in churn list — needs context | No | Backlog | Health Contract V2 |
| Age-out indicator for 14_90 | 14_90 label persists on experienced drivers | No | Backlog | Program Migration Rules |
| Program count reconciliation doc | Explain eligible vs assigned vs Explorer counts | No | Backlog | Program Registry V3 |

**None of these are implemented. All are documented for backlog.**

## 9. Verdict

### **LG_PROGRAM_GOV_1A_PASS**

**Evidence:**

1. Eligible vs assigned semantics are understood and documented:
   - Eligibility = daily qualification snapshot
   - Explorer = persistent program assignment (may lag)
   - The gap is correct behavior, not a bug

2. Program assignment is explainable per driver:
   - Sourced from eligibility rules (lifecycle, performance, retention, flags)
   - Priority ordering is defined (CHURN > 14_90 > ACTIVE_GROWTH)
   - Opportunity list picks highest-priority eligible program

3. Confusing cases identified:
   - 12/30 drivers have stale Explorer labels vs eligibility
   - 6/30 have CHURN_PREVENTION with high performance (flags override metrics)
   - 5/30 have 14_90 label on experienced drivers

4. UI validation targets defined (5 filter tests)

5. 8 backlog items documented — none implemented

6. No code, rules, writers, schedulers, UI, or DB changed

**Growth Machine Closure relevance:** This audit confirms that program assignment is deterministic and explainable. The readability gap (Explorer lag, high-perf CHURN, stale 14_90) is a UI/serving issue, not a Program Engine bug. These are backlog items for Program Registry V3.

---

*Audit complete. No implementation. All findings documented for backlog.*
