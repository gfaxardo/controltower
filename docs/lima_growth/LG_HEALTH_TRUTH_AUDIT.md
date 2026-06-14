# LG_HEALTH_TRUTH_AUDIT

**Phase:** LG-CF-RECOVERY-2B — Control Foundation Operational Closure  
**Generated:** 2026-06-12T23:28  

---

## THE QUESTION

**¿Cuál es hoy la señal más cercana a la verdad operacional?**

---

## THE FOUR SIGNALS

### Signal A: `/growth/health` (SLA compliance)

| Attribute | Value |
|-----------|-------|
| **Current status** | CRITICAL |
| **Source** | `growth.yego_lima_serving_freshness_fact` |
| **What it says** | 4 broken assets, 3 degraded, 6 healthy |
| **What it means** | SLA refresh intervals are violated for 4 assets |
| **Is it true?** | **YES** — the SLAs ARE violated. `activity_daily` has not been refreshed. `explorer_fact` doesn't exist. |
| **Is it useful?** | **PARTIALLY** — correct about SLA compliance, but misleading about data availability. `driver_state_snapshot` has 06-12 data but is marked BROKEN because its SLA (5h) is violated. |
| **Closest to truth?** | **NO** — measures governance (SLA), not data (freshness). |

### Signal B: `operational-date` (snapshot freshness)

| Attribute | Value |
|-----------|-------|
| **Current status** | `is_fresh: true` |
| **Source** | `detect_latest_closed_data_date()` → checks `MAX(snapshot_date)` from `driver_state_snapshot` |
| **What it says** | The system is caught up and data is fresh |
| **What it means** | `driver_state_snapshot` and `program_eligibility_daily` have data for the operational date |
| **Is it true?** | **PARTIALLY** — those two tables ARE fresh. But it ignores lifecycle/taxonomy/movement. |
| **Is it useful?** | **NO** — false positive for overall system health. Led to 2-day gap being undetected in LG-CF-RECOVERY-1. |
| **Closest to truth?** | **NO** — too narrow. Only checks 2 of 10 tables. |

### Signal C: V2 Freshness Registry

| Attribute | Value |
|-----------|-------|
| **Current status** | 6 FRESH, 3 STALE |
| **Source** | `growth.yego_lima_v2_freshness_registry` |
| **What it says** | lifecycle_daily, taxonomy_v2, program_v2, movement_fact, observability_fact, activity_monthly are FRESH. activity_daily, activity_weekly, effectiveness_fact are STALE (0 rows). |
| **What it means** | 6 of 9 V2 pipeline steps produced data. 3 skipped (no new data). |
| **Is it true?** | **YES** — pipeline step log confirms exactly this. |
| **Is it useful?** | **YES** — accurate step-by-step pipeline health. |
| **Closest to truth?** | **PARTIALLY** — accurate for V2 pipeline but ignores operational tables and orphan tables. |

### Signal D: Real DB Query (ground truth)

| Table | Rows 06-12 | Status |
|-------|-----------|--------|
| `driver_state_snapshot` | 18,545 | FRESH |
| `program_eligibility_daily` | 28,128 | FRESH |
| `driver_lifecycle_daily` | 68,506 | FRESH |
| `v2_taxonomy_daily` | 68,506 | FRESH |
| `v2_program_daily` | 68,506 | FRESH |
| `v2_movement_fact` | 466 | FRESH |
| `rna_priority_fact` | 888 | FRESH |
| `program_effectiveness_fact` | 34 | FRESH |
| `driver_explorer_fact` | 0 | MISSING |
| `driver_movement_fact` (orphan) | 68,473 (06-10 only) | STALE |

| What it says | 9/10 tables have fresh 06-12 data. 1 table doesn't exist. |
| **Closest to truth?** | **YES** — this is the absolute ground truth. |

---

## THE ANSWER

**La señal más cercana a la verdad operacional es la consulta directa a la base de datos (Signal D).**

De las señales automatizadas:

| Rank | Signal | Accuracy | Why |
|------|--------|----------|-----|
| **1** | **V2 Freshness Registry** | Most accurate automated signal | 6/9 correct. Tracks actual pipeline output. Only misses operational layer. |
| 2 | `/growth/health` | Accurate about SLA, misleading about data | Correctly identifies violations but wrong severity (CRITICAL when data exists). |
| 3 | `operational-date` | Too narrow | Only checks 2 tables. False positive for overall health. |

### The Single Best Automated Health Signal Today

**V2 Freshness Registry** is the best automated signal because:
1. It tracks actual pipeline step output (rows produced per step)
2. It correctly identifies which steps produced data and which skipped
3. It doesn't conflate SLA compliance with data availability
4. It's updated every time the pipeline runs

### What's Missing

No automated signal today queries `SELECT COUNT(*) WHERE date = target_date` for all tables. This is what LG_GOV_2A_HEALTH_CONTRACT_V2 proposes as DATA HEALTH — the simplest and most honest signal.

---

## RECOMMENDATION

**Implement DATA HEALTH as the primary operational health signal.** It requires zero new tables, zero new writers, just a read-only endpoint that does:

```sql
SELECT COUNT(*) FROM each_table WHERE date_col = target_date
```

This is:
- **Simple** — one query per table
- **Honest** — no interpretation, just facts
- **Non-blocking** — read-only, no locks
- **Low-effort** — ~50 lines of code

**Until DATA HEALTH exists, the V2 Freshness Registry is the best available automated signal.** For absolute truth, query the DB directly.
