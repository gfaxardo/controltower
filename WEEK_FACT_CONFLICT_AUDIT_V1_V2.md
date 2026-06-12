# WEEK FACT CONFLICT AUDIT — V1 / V2 SERVING COLLISION CHECK

**Date**: 2026-06-08  
**Git Hash**: 938c047  
**Classification**: `MULTIPLE_WEEK_OBJECTS_NO_COLLISION`  
**Related**: OMNI-V1 HARDENING CERTIFICATION REPORT (V1_AT_RISK)

---

## 0. GOVERNANCE

| Field | Value |
|-------|-------|
| ACTIVE Motor | Control Foundation (REOPENED / P0) |
| ACTIVE Phase | OMNI-P0 — False GO Recovery & Vs Proy Canonicalization |
| This audit falls under | Control Foundation + Serving Governance + Runtime Governance |
| Conflict with active phase | NONE (audit-only, no data modification) |

---

## 1. THE CONTRADICTION — RESOLVED

**V1 says weekly stale. V2 says weekly fresh. Both are right — they're measuring different objects.**

| Question | Answer |
|----------|--------|
| What V1 measures as "weekly" | `ops.real_business_slice_week_fact` — REAL aggregated business slice data at ISO week grain |
| What V2 measures as "weekly fresh" | `serving.omniview_projection_daily_fact WHERE grain='weekly'` — PROJECTION/PLAN serving layer |
| Is V1 correctly detecting staleness? | **YES** — week_fact max=2026-04-20, 49 days stale |
| Is V2 correctly claiming freshness? | **YES** — projection serving refreshed daily at 05:00 UTC, generated_at=2026-06-07 |
| Are these the same object? | **NO** — completely different schemas, purposes, and lineage |
| Is there a collision? | **NO** — they serve different purposes (real vs plan/projection) |
| Is the lineage confusing? | **YES** — "weekly" is overloaded across 10+ tables/MVs/views |

---

## 2. INVENTORY OF WEEKLY OBJECTS

### 2.1 Primary Weekly Objects (Real Data)

| Object | Schema | Type | Max Week | Rows | Distinct Weeks | V1/V2/Shared | Purpose |
|--------|--------|------|----------|------|---------------|-------------|---------|
| `real_business_slice_week_fact` | ops | TABLE | **2026-04-20** | 24 | 4 | **Shared (V1+V2 read)** | Canonical business slice facts: trips, revenue, drivers per (week, country, city, business_slice, fleet). **THIS is what V1 reads for weekly data.** |
| `mv_real_lob_week_v3` | ops | MV | **2026-05-04** | 2,248 | 18 | V2 pipeline | LOB drill aggragetion from hourly-first chain. 3 weeks FRESHER than week_fact. |
| `mv_real_trips_weekly` | ops | MV | **2026-01-26** | 742 | 57 | Phase 2B | Real trips weekly aggregation (legacy lineage). Older than week_fact. |
| `mv_real_trips_by_lob_week` | ops | MV | — | 1,988 | — | Legacy | LOB split (superseded by _v3). |
| `mv_real_lob_week_v2` | ops | MV | — | 2,129 | — | Legacy | v2 LOB (superseded by _v3). |

### 2.2 Projection/Plan Weekly Objects

| Object | Schema | Type | Max Week | Rows | Distinct Weeks | V1/V2/Shared | Purpose |
|--------|--------|------|----------|------|---------------|-------------|---------|
| `omniview_projection_daily_fact` (grain=weekly) | serving | TABLE | **2026-12-28** | 1,495 | 53 | **V2 (Vs Proy)** | Plan vs Real projection data. Contains FUTURE weeks (plan). Refreshed DAILY at 05:00 UTC. **THIS is where V2's "weekly freshness" claim comes from.** |
| `v_plan_trips_weekly_from_monthly` | ops | VIEW | — | — | — | Phase 2B | Distributed plan (monthly / weeks_in_month). |
| `v_plan_vs_real_weekly` | ops | VIEW | — | — | — | Phase 2B | Plan vs Real join at week grain. |

### 2.3 Driver Weekly Objects

| Object | Schema | Type | Max Week | Rows | Purpose |
|--------|--------|------|----------|------|---------|
| `driver_supply_overview_weekly_fact` | ops | MV | **2026-05-18** | 299 | Weekly supply KPIs — FRESHEST weekly real data |
| `driver_weekly_segment_fact` | ops | MV | — | 87,880 | Driver-week segment classification |
| `mv_driver_weekly_stats` | ops | MV | — | 375,844 | Driver-week stats by park |
| `mv_driver_lifecycle_weekly_kpis` | ops | MV | — | 73 | Aggregated lifecycle KPIs |
| `mv_supply_segments_weekly` | ops | MV | — | 5,538 | Supply segmentation |

### 2.4 Yego Pro Weekly Objects

| Object | Schema | Type | Purpose |
|--------|--------|------|---------|
| `mv_yego_pro_profitability_week` | ops | MV | Weekly billing |
| `mv_yego_pro_driver_profitability_week` | ops | MV | Driver profitability |
| `mv_yego_pro_vehicle_profitability_week` | ops | MV | Vehicle profitability |
| `mv_yego_pro_shift_profitability_week` | ops | MV | Shift profitability |
| `mv_yego_pro_driver_close_week` | ops | MV | Driver close |
| `mv_yego_pro_weekly_financial_truth` | ops | MV | Weekly P&L truth |

### 2.5 Growth Weekly Objects

| Object | Schema | Type | Max Week | Purpose |
|--------|--------|------|----------|---------|
| `yango_lima_driver_history_weekly` | growth | TABLE | **2026-06-01** | Lima growth driver history |

---

## 3. READERS AUDIT — V1 vs V2

### 3.1 V1 (Evolution) Weekly Readers

| Endpoint | Service Function | SQL Table | Date Column |
|----------|-----------------|-----------|-------------|
| `GET /ops/business-slice/weekly` | `get_business_slice_weekly()` → `_weekly_from_fact()` | `ops.real_business_slice_week_fact` | `week_start` |
| `GET /ops/business-slice/omniview?grain=weekly` | `_fetch_fact_slice_rows(grain='weekly')` | `ops.real_business_slice_week_fact` | `week_start` (ISO Monday) |
| `GET /ops/business-slice/real-freshness` | `_collect_aggregated_slice_metrics()` | `ops.real_business_slice_week_fact` | `week_start` (metadata only) |

**V1 Evolution reads EXCLUSIVELY from `ops.real_business_slice_week_fact` for weekly data.**

### 3.2 V2 (Vs Proy) Weekly Readers

| Endpoint | Service Function | SQL Table | Date Column |
|----------|-----------------|-----------|-------------|
| `GET /ops/business-slice/omniview-projection` | `_load_real_weekly()` | `ops.real_business_slice_week_fact` | `week_start` |
| `GET /ops/omniview-v2/matrix?grain=week` | `CT_GRAIN_TABLES["week"]` | `ops.real_business_slice_week_fact` | `week_start` |
| `GET /ops/omniview/weekly-serving-guardrails` | `reconcile_weekly_fact_vs_serving()` | `FACT_WEEKLY` + `serving.omniview_projection_daily_fact` | `week_start` + `period_key` |

**V2 Vs Proy reads REAL data from the SAME `ops.real_business_slice_week_fact` as V1, AND reads PLAN/PROJECTION data from `serving.omniview_projection_daily_fact`.**

### 3.3 Conclusion on Readers

**YES — V1 and V2 use the same `ops.real_business_slice_week_fact` for real weekly data.**

The difference is:
- V1: reads ONLY the real fact table. No projection layer available. Weekly view = EMPTY when fact is stale.
- V2: reads the real fact table (for real baseline) AND the projection serving table (for plan/projection). Weekly Vs Proy view may appear "working" because the projection layer IS fresh even though the real fact IS stale.

---

## 4. WRITERS AUDIT

### 4.1 Writers to `ops.real_business_slice_week_fact`

| # | Writer | Path | Schedule | Safe? | Driver Logic | Status |
|---|--------|------|----------|-------|-------------|--------|
| **W1** | `rebuild_week_from_day_and_bridge.py` | `backend/scripts/` | **CLI only (manual)** | **SAFE** | COUNT(DISTINCT) from driver bridge — exact | **CANONICAL** |
| W2 | `_populate_staging_week()` + `_swap_staging_to_production()` | `business_slice_incremental_load.py` | **CLI only** (`--legacy` flag) | SAFE (atomic staging) | COUNT(DISTINCT) from enriched — exact | V2 default path |
| W3 | `load_business_slice_week_for_month()` | `business_slice_incremental_load.py` | CLI only (refresh_business_slice_mvs.py) | SAFE (staged) | COUNT(DISTINCT) from enriched — exact | **DEPRECATED** |
| W4 | `refresh_business_slice_week_range()` | `business_slice_incremental_load.py` | CLI only (`--legacy`) | PARTIAL (no atomicity) | COUNT(DISTINCT) from enriched — exact | Legacy |
| **W5** | `rebuild_week_fact_from_day_fact.py` | `backend/scripts/` | **CLI only** | **UNSAFE** | **SUM(daily distincts) = BROKEN** | DANGEROUS — NO SAFETY GUARD |
| W6 | `recover_week_fact_batched.py` | `backend/scripts/` | CLI only | SAFE (batched W1) | Delegates to W1 | Recovery wrapper |
| N1 | `run_business_slice_real_refresh_job()` | `business_slice_real_refresh_job.py` | **APScheduler 04:00** | **N/A (NO-OP)** | Sets nw=0, writes nothing | False-positive CRITICAL error |

### 4.2 Writers to `serving.omniview_projection_daily_fact` (grain=weekly)

| # | Writer | Path | Schedule | Safe? | Driver Logic |
|---|--------|------|----------|-------|-------------|
| **W7** | `refresh_omniview_projection_facts.py` | `backend/scripts/` | **APScheduler 05:00 DAILY** | **SAFE** | Projection computation (plan vs real) |

### 4.3 Writer to `ops.mv_real_lob_week_v3`

| # | Writer | Path | Schedule | Safe? |
|---|--------|------|----------|-------|
| **W8** | `refresh_hourly_first_chain.py` | `backend/scripts/` | CLI (pipeline) | SAFE (CONCURRENTLY) |

### 4.4 Critical Writer Findings

1. **NO automatic scheduler writes to `ops.real_business_slice_week_fact`** — the scheduled job is a NO-OP. All writers (W1-W6) are CLI-only.

2. **The ONLY scheduled writer (W7) writes to `serving.omniview_projection_daily_fact`**, which contains PLAN/PROJECTION weekly data, NOT aggregated REAL data.

3. **`rebuild_week_fact_from_day_fact.py` (W5) is DANGEROUS and UNBLOCKED** — no safety guard. Running it with `--confirm` will write BROKEN driver counts (SUM of daily distincts ≠ weekly distinct).

4. **`run_ov2_refresh_cascade.py` step `week_rebuild` delegates to W1** (bridge cascade, canonical). But the cascade is CLI-only, not scheduled.

5. **`mv_real_lob_week_v3` has 3 weeks FRESHER data (max=2026-05-04) than `week_fact` (max=2026-04-20)** — the hourly-first chain MV refresh has run more recently than the business slice week rebuild.

6. **The NO-OP scheduler job (`omniview_business_slice_real_refresh`) runs at 04:00 and ALWAYS triggers a false-positive CRITICAL error** because nd=0, nw=0 is hardcoded. This pollutes logs and trust signals.

---

## 5. TRUST SENSOR CROSS-CHECK

### 5.1 Sensors That Query `ops.real_business_slice_week_fact`

| Sensor | Endpoint | Query | Threshold |
|--------|----------|-------|-----------|
| V1 Trust Sensor | `GET /ops/v1-trust-sensor` | `MAX(week_start)` | WARN >7d, FAIL >14d (blocking) |
| Freshness Governance | `GET /ops/omniview/freshness` | `MAX(week_start)` | WARN 8-10d, BLOCK >10d |
| Real Freshness | `GET /ops/business-slice/real-freshness` | `MAX(week_start)` + `MAX(loaded_at)` | Metadata only (no own threshold) |
| Fact Status | `GET /ops/business-slice/fact-status` | Aggregated by month | Informational only |
| Matrix Integrity | Internal | `COUNT(*)` | EMPTY if 0, THIN if <3 |
| Waterfall Validation | `GET /ops/v1-waterfall-validation` | `MAX(week_start)` + `COUNT(*)` | WARN if behind day by >14d |

### 5.2 Sensor That Queries `serving.omniview_projection_daily_fact`

| Sensor | Endpoint | Query | Threshold |
|--------|----------|-------|-----------|
| Freshness Governance (serving weekly) | `GET /ops/omniview/freshness` | `MAX(period_key)` WHERE grain='weekly' | WARN 8-10d, BLOCK >10d |
| Serving Guardrails | `GET /ops/omniview/weekly-serving-guardrails` | Cross-validates fact vs serving | BREACH / WARNING / OK |

### 5.3 Cross-Validation Results (Live)

| Metric | fact-weekly | serving-weekly | mv_real_lob_week_v3 | driver_supply_weekly |
|--------|------------|----------------|--------------------|---------------------|
| Max date | 2026-04-20 | 2026-12-28 (projection) | 2026-05-04 | 2026-05-18 |
| Rows | 24 | 1,495 | 2,248 | 299 |
| Distinct weeks | 4 | 53 | 18 | — |
| Freshness status | **STALE (49d)** | **FRESH** (generated 2026-06-07) | **STALE (5 weeks)** | **FRESH** |
| Type | REAL aggregated | PROJECTION/PLAN | REAL LOB drill | REAL driver supply |

**Key cross-validation finding**: `serving_weekly > week_fact` — this triggers a **BREACH** in the freshness governance cross-validation because the serving projection table has weeks beyond what the canonical fact table provides. This is EXPECTED for projection data but generates a false-positive breach alarm.

---

## 6. CONCLUSIONS

### 6.1 Explicit Answers

| # | Question | Answer |
|---|----------|--------|
| 1 | ¿V1 y V2 usan el mismo `week_fact`? | **YES** for real data — both read from `ops.real_business_slice_week_fact`. But V2 ALSO reads from `serving.omniview_projection_daily_fact` for plan/projection. |
| 2 | ¿Hay más de una rutina actualizando weekly? | **YES** — 6 write paths to week_fact (all CLI), + 1 scheduled writer to projection serving + 1 MV refresh for LOB. |
| 3 | ¿Hay más de un objeto weekly con freshness distinta? | **YES** — 4 distinct real-world freshness levels: week_fact (Apr 20, STALE), mv_real_lob_week_v3 (May 4, STALE), driver_supply_weekly (May 18, FRESH), serving_projection (Dec 2026, FRESH but projection). |
| 4 | ¿El Trust Sensor V1 está midiendo el objeto correcto? | **YES** — it correctly measures `ops.real_business_slice_week_fact`, which IS the table V1's Evolution view consumes. |
| 5 | ¿V2 está realmente fresh o solo otro objeto está fresh? | **PARTIAL** — The PROJECTION serving layer is fresh (daily refresh). The REAL fact layer is stale (same as V1). V2's Vs Proy view can show projections even when the real baseline is stale. |
| 6 | ¿Existe riesgo de que un writer legacy pise datos fresh? | **YES** — `rebuild_week_fact_from_day_fact.py` (W5) is unblocked and would write BROKEN driver counts if executed. Any manual CLI execution of a legacy writer could overwrite data from the canonical bridge cascade. |
| 7 | ¿Cuál es el writer canónico recomendado? | `run_ov2_refresh_cascade.py` → `rebuild_week_from_day_and_bridge.py` (W1). Uses exact driver bridge, atomic staging, ISO Monday validation. |
| 8 | ¿Qué writer debe bloquearse/deprecarse? | `rebuild_week_fact_from_day_fact.py` (W5) — add `--allow-dangerous` guard. `refresh_business_slice_mvs.py` (W3/W4) — block week writes. NO-OP scheduler job (N1) — fix or remove. |
| 9 | ¿Se debe hacer recovery o primero corregir lineage? | **RECOVERY → CORRECT LINEAGE** — Execute W1 canonical rebuild to restore week_fact freshness. Then block dangerous paths, schedule W1 in APScheduler. |

### 6.2 Classification

```
MULTIPLE_WEEK_OBJECTS_NO_COLLISION
```

**Rationale:**

- V1 and V2 DO share the same canonical week_fact table — no collision
- The "freshness contradiction" is explained by V2 having additional projection/serving data that V1 does not access
- The serving projection table (scheduled daily) gives V2 fresh plan-vs-real data even when the underlying real fact is stale
- No writer collision exists because NO scheduled writer produces real data — the canonical writer (W1) is CLI-only
- The lineage IS confusing: "weekly" is overloaded across 16+ objects in 4 different schemas

---

## 7. GO / NO-GO FOR RECOVERY

### **GO — Execute canonical weekly rebuild immediately**

**Prerequisites**:
1. `ops.real_business_slice_day_fact` is fresh (max=2026-06-07) ✓ — confirmed
2. `ops.driver_day_slice_fact` (bridge) has data — to verify before execution
3. No conflicting refresh in progress

**Recommended command**:
```bash
python backend/scripts/rebuild_week_from_day_and_bridge.py --confirm
```

**Expected result**: week_fact populated with ~2 months of fresh weekly data using exact driver bridge.

**Post-recovery actions (P1)**:
1. Schedule `run_ov2_refresh_cascade.py` (or at minimum the week step) in APScheduler
2. Add safety guard (`--allow-dangerous`) to `rebuild_week_fact_from_day_fact.py`
3. Block week writes from `refresh_business_slice_mvs.py`
4. Fix or remove NO-OP scheduler job emitting false CRITICAL errors

---

## 8. NEXT RECOMMENDED PROMPT

```
Execute OMNI-V1 HARDENING — WEEK FACT RECOVERY

Confirmed: week_fact stale, canonical writer is rebuild_week_from_day_and_bridge.py.
Day fact is fresh (2026-06-07). Driver bridge needs verification.

TASK:
1. Verify driver_day_slice_fact has data for the period
2. DRY-RUN rebuild_week_from_day_and_bridge.py --dry-run to preview affected weeks
3. If safe, execute rebuild_week_from_day_and_bridge.py --confirm
4. Re-run V1 Trust Sensor to verify WEEK_FACT_STALE is cleared
5. Document recovery evidence
```

---

**END OF AUDIT**

_Audit conducted 2026-06-08. Git: 938c047. Classification: MULTIPLE_WEEK_OBJECTS_NO_COLLISION._
