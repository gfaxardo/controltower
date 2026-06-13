# LG-PROGRAM-GOV-1B — Program Assignment Explainability Checkpoint

**Date:** 2026-06-13
**Phase:** Program Assignment Explainability Checkpoint
**Mode:** AUDIT + UI VALIDATION TARGETS — NO IMPLEMENTATION
**Prerequisite:** LG-EXP-GRAIN-1A/1B/1C (Explorer counts corrected)

---

## 1. Pre-Check

| # | Question | Answer |
|---|----------|--------|
| 1 | Motor | Growth Machine / Control Foundation |
| 2 | Fase | Program Assignment Explainability Checkpoint |
| 3 | Contrato | Explorer assigned-program, eligibility-vs-assignment, UI explainability |
| 4 | Tablas (read-only) | explorer_fact, eligibility, state_snapshot, history_weekly |
| 5 | Writer | Ninguno |
| 6 | Freshness | Ninguna |
| 7 | Endpoint/UI | Driver Explorer tab, Programs tab |
| 8 | Legacy | ctrl_bridge_sync.py.legacy.disabled |
| 9 | Riesgos | Confundir eligible vs assigned, abrir rediseño |
| 10 | Rollback | Revertir doc |
| 11 | ACTIVE_SCOPE_CONTRACT | In-scope (Section 4) |
| 12 | Scope Escalation | AUDIT ONLY |

## 2. Active Scope Contract Result

**IN SCOPE. AUDIT ONLY.** Program assignment/explainability audit is in-scope. No implementation.

## 3. Clean Count Baseline (Post 1B/1C Fix)

Explorer latest `target_date`: **2026-06-12**. Eligibility today: **2026-06-13**.

| Program | Explorer Assigned (latest date) | Correct? |
|---------|--------------------------------|----------|
| PROGRAM_ACTIVE_GROWTH | **15,054** | YES (was 30,108 pre-fix) |
| PROGRAM_14_90 | **2,669** | YES (was 5,338 pre-fix) |
| PROGRAM_CHURN_PREVENTION | **317** | YES (was 634 pre-fix) |
| NONE | **504** | YES (was 1,008 pre-fix) |
| NEW_DRIVER_ONBOARDING | 1 | — |

All counts are single-date, correctly deduped. No duplication.

## 4. Eligible vs Assigned Reconciliation

### Data Sources and Their Meaning

| Source | Table | Grain | Updated | Semantic |
|--------|-------|-------|---------|----------|
| **Explorer Assigned** | `yego_lima_driver_explorer_fact` | Per `target_date` + `driver_profile_id` | Built per run (06-11, 06-12) | Shows the program each driver was assigned to on that target_date. Cumulative — assignment persists across dates. |
| **Daily Eligibility** | `yango_lima_program_eligibility_daily` | Per `eligibility_date` + `driver_profile_id` + `program_code` | Every 5 min via autonomous tick | Shows which programs a driver qualifies for TODAY. Recalculated daily. |

### Why Numbers Differ (Now with Correct Counts)

| Program | Explorer Assigned | Eligible Today | Gap Analysis |
|---------|------------------|----------------|-------------|
| ACTIVE_GROWTH | 15,054 | 17,685 | -2,631: Fewer assigned than eligible. Some eligible drivers have stale CHURN/14_90 labels, others are newly eligible. |
| 14_90 | 2,669 | 2,669 | 0: Exact match by coincidence. Explorer is cumulative; eligibility is daily. |
| CHURN_PREVENTION | 317 | 7,774 | -7,457: Massive gap. Most CHURN-eligible drivers are still labeled ACTIVE_GROWTH (stale assignment). |
| NONE | 504 | — | Drivers with no program assigned. |

### Key Insight

The Explorer `target_date=2026-06-12` reflects the driver state from June 12. The eligibility table for `2026-06-13` reflects state from today. When a driver's state changes between these dates (e.g., churn_risk_flag flips to true), the Explorer label is stale for one day until the next rebuild.

This is **expected behavior** for a daily pipeline, not a bug. But it needs a UI explainability layer.

### From LG-PROGRAM-GOV-1A (Re-confirmed with Correct Counts)

| Program | Explorer Drivers (1A, before fix) | Explorer Drivers (1B, after fix) | Correct? |
|---------|----------------------------------|--------------------------------|----------|
| ACTIVE_GROWTH | 30,108 (2 dates aggregated) | **15,054** (latest date only) | YES |
| CHURN_PREVENTION | 634 (2 dates aggregated) | **317** (latest date only) | YES |
| 14_90 | 5,338 (2 dates aggregated) | **2,669** (latest date only) | YES |

## 5. Confusion Types (Quantified)

From the 30-driver sample in 1A + corrected Explorer data:

| Confusion Type | Count in Sample | Operator Risk | Root Cause |
|---------------|-----------------|---------------|------------|
| A) Assigned ACTIVE_GROWTH, eligible CHURN today | 4/30 | HIGH — operator targets wrong program | Explorer label stale by 1 day. Flags changed between target_date and today. |
| B) Assigned CHURN with HIGH/ELITE performance | 6/30 | HIGH — operator questions program logic | churn_risk_flag or declining_flag triggers CHURN regardless of performance. Correct behavior, confusing presentation. |
| C) Assigned 14_90 with ESTABLISHED lifecycle | 5/30 | MEDIUM — veteran driver in new-driver program | 14_90 label persists after driver ages out. Explorer not rebuilt with new state. |
| D) Multi-eligible with lower-priority assignment | 3/30 | MEDIUM — driver should be in higher-priority program | Explorer label from prior run, not updated to reflect today's higher-priority eligibility. |
| E) Assigned NONE but high value | Not sampled | LOW | Drivers without program assignment — need investigation if they should be eligible. |
| F) Assigned program not eligible today | ~15/30 | HIGH — all stale assignments fall here | Same as A/C. Explorer label from prior target_date, eligibility recalculated today. |

## 6. Explanation Samples

### Example 1: Assigned ACTIVE_GROWTH, Eligible CHURN_PREVENTION
```
Driver: e7738562...
Explorer (target_date=2026-06-12): ACTIVE_GROWTH, priority=30
Eligibility today: CHURN_PREVENTION, priority=100
Why: churn_risk_flag=true, retention_state=CHURN_RISK, orders_wk=4
Diagnosis: Stale assignment. Flags changed between June 12 and June 13.
Operator action: Treat as CHURN_PREVENTION. Explorer label will update on next rebuild.
```

### Example 2: Assigned CHURN_PREVENTION with HIGH Performance
```
Driver: ac15adf0...
Explorer (target_date=2026-06-12): CHURN_PREVENTION, priority=120
Metrics: orders_wk=81, avg4w=112, HISTORICAL_50_PLUS, reached_target=true
Why: declining_flag=true, retention_state=AT_RISK
Diagnosis: Correct but confusing. CHURN_PREVENTION triggered by declining_flag.
Operator may question why a top performer is in churn prevention.
The flag indicates the driver is declining relative to their own baseline, not absolute performance.
```

### Example 3: Assigned 14_90 with ESTABLISHED Lifecycle
```
Driver: 974da485...
Explorer (target_date=2026-06-12): PROGRAM_14_90, priority=3
Metrics: best_week_12w=36, HISTORICAL_30_49, churn_risk_flag=true
Eligibility today: CHURN_PREVENTION, priority=100
Why: Driver aged out of 14_90 (activated → ESTABLISHED) but Explorer label not updated.
Diagnosis: Stale assignment. Explorer shows 14_90 from prior run; today eligible for CHURN.
```

## 7. Why Explorer Can Differ from Programs Summary

| View | Source | What It Shows | Refresh |
|------|--------|---------------|---------|
| **Driver Explorer** | `driver_explorer_fact` (target_date=06-12) | Which program each driver IS CURRENTLY IN (persistent assignment) | Manual rebuild |
| **Programs Summary** | `serving_fact` → `programs_summary` | Aggregated eligible counts for today | Every 5 min via tick |
| **Eligibility Table** | `program_eligibility_daily` (date=06-13) | Which programs each driver QUALIFIES FOR today | Every 5 min via tick |

The gap exists because:
1. Explorer shows a snapshot from the last rebuild date (06-12)
2. Programs Summary shows today's eligibility (06-13)
3. Driver states change daily — what was true on 06-12 may differ on 06-13
4. Explorer assignment is not automatically synced to new eligibility

**This is CORRECT but CONFUSING.** The UI needs to make this distinction visible to operators.

## 8. UI Validation Checkpoint

| # | Route | Tab | Filter/Search | Expected | PASS Criteria |
|---|-------|-----|---------------|----------|---------------|
| 1 | `/lima-growth/intelligence` | Driver Explorer | Program=ACTIVE_GROWTH | 15,054 drivers | Count matches |
| 2 | `/lima-growth/intelligence` | Driver Explorer | Program=CHURN_PREVENTION | 317 drivers | Count matches |
| 3 | `/lima-growth/intelligence` | Driver Explorer | Program=14_90 | 2,669 drivers | Count matches |
| 4 | `/lima-growth/intelligence` | Driver Explorer | Program=None (if filterable) | 504 drivers | Count matches |
| 5 | `/lima-growth/intelligence` | Driver Explorer | Search e7738562 | Shows ACTIVE_GROWTH label | Operator can see assigned program |
| 6 | `/lima-growth/intelligence` | Driver Explorer | Search ac15adf0 | CHURN_PREVENTION, 81 orders/wk | Operator sees confusing high-perf churn case |
| 7 | `/lima-growth/intelligence` | Programs | View all | Eligible counts: 2,669 / 17,685 / 7,774 | Operator sees gap from Explorer |
| 8 | `/lima-growth/intelligence` | Programs vs Explorer | Compare counts | Numbers differ (expected) | Operator understands eligible vs assigned |

### Operator-Side Questions the UI Should Answer

1. **Q: "Why is this driver in CHURN_PREVENTION when they did 81 orders?"**
   A: Because the `declining_flag` or `churn_risk_flag` triggered the CHURN criteria. The driver IS high-performing, but their trend is declining.

2. **Q: "Why does Explorer show 15,054 ACTIVE_GROWTH but Programs says 17,685?"**
   A: Explorer shows drivers CURRENTLY ASSIGNED to ACTIVE_GROWTH (from the last build date). Programs shows drivers ELIGIBLE for ACTIVE_GROWTH today.

3. **Q: "Why does Explorer show 317 CHURN but Programs says 7,774?"**
   A: Most churn-eligible drivers are still labeled as ACTIVE_GROWTH or 14_90 in Explorer from the last build.

## 9. Backlog Items

| Backlog Item | Reason | Blocker? | Recommended Phase |
|-------------|--------|----------|-------------------|
| "Why this program?" tooltip in Explorer | Operators need to see eligibility logic per driver | No | Program Registry V3 |
| Eligibility column in Explorer | Show eligible programs alongside assigned program | No | Program Registry V3 |
| Assigned vs Eligible badge/diff indicator | Stale assignments need visual indication | No | Program Registry V3 |
| Program transition explainability | Why did driver move from ACTIVE to CHURN? | No | Program Registry V3 / State Machine |
| Explorer-to-eligibility sync contract | Define when Explorer should auto-update from new eligibility | No | Program Registry V3 |
| Priority comparison in multi-eligible drivers | Show why one program was chosen over another | No | Program Registry V3 |
| Program count reconciliation doc (operator-facing) | Explain eligible vs assigned gap | No | Program Registry V3 |
| Age-out indicator for 14_90 | 14_90 label on experienced drivers | No | Program Migration Rules |
| High-perf CHURN explanation context | Operator sees top performer in churn list | No | Health Contract V2 |
| NONE-assigned driver investigation | Drivers with no program need review | No | Program Registry V3 |

**None of these are implemented. All deferred to backlog.**

## 10. Verdict

### **LG_PROGRAM_GOV_1B_PASS**

**Evidence:**

1. Clean counts confirmed: Explorer now shows correct single-date program counts after 1B/1C fix
2. Eligible vs assigned semantics documented and explainable
3. The gap between Explorer (assigned) and Programs (eligible) is:
   - Correct behavior (different concepts)
   - Caused by daily state changes between target_date and eligibility_date
   - Not a bug — a pipeline refresh cadence issue
4. Confusion types quantified: stale assignments (A, C, F), high-perf churn (B), priority conflicts (D)
5. Explanation samples generated for 3 representative confusion types
6. 8 UI validation targets defined
7. 10 backlog items documented — none implemented
8. No code, rules, writers, schedulers, UI, or DB changed

**Growth Machine Closure relevance:** Program assignment is explainable. The readability gap requires UI/serving enhancements (backlog items), not Program Engine changes. Growth Machine closure is NOT blocked by program explainability.

---

*Checkpoint complete. No implementation. All findings documented for backlog.*
