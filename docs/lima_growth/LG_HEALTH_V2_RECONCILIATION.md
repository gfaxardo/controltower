# LG_HEALTH_V2_RECONCILIATION

**Phase:** LG-CF-RECOVERY-2A — Control Foundation Closure  
**Generated:** 2026-06-12  
**Purpose:** Compare 4 health signals, identify contradictions, define survivors

---

## SIGNAL INVENTORY

### Signal 1: `/growth/health`

| Attribute | Value |
|-----------|-------|
| **Source** | `growth.yego_lima_serving_freshness_fact` → `serving_freshness_audit_service.py` |
| **What it measures** | SLA compliance (refresh interval) for 13 serving assets |
| **Current status** | **CRITICAL** (4 broken, 3 degraded, 6 healthy) |
| **Broken assets** | `program_assignment`, `driver_state_snapshot`, `RNA_serving`, `serving_driver_explorer` |
| **Problem** | Reports CRITICAL for tables that HAVE fresh data. SLA compliance ≠ data absence. |

### Signal 2: `operational-date` (embedded in serving facts)

| Attribute | Value |
|-----------|-------|
| **Source** | `detect_latest_closed_data_date()` → checks `MAX(snapshot_date)` from `driver_state_snapshot` |
| **What it measures** | Whether the operational date has data |
| **Current status** | `is_fresh: true` |
| **Problem** | Only checks `driver_state_snapshot` and `program_eligibility`. Ignores intelligence layer. **False positive.** |

### Signal 3: V2 Freshness Registry

| Attribute | Value |
|-----------|-------|
| **Source** | `growth.yego_lima_v2_freshness_registry` → `_update_freshness_registry()` in V2 pipeline |
| **What it measures** | Step-by-step freshness of the 9 V2 pipeline steps |
| **Current status** | **6 FRESH, 3 STALE** (activity_daily, activity_weekly, effectiveness_fact = 0 rows) |
| **Problem** | Only tracks V2 shadow pipeline. Does not track operational tables. Ignores orphan tables. |

### Signal 4: `growth.yego_lima_freshness_registry` (V1 governance)

| Attribute | Value |
|-----------|-------|
| **Source** | `_refresh_freshness_registry()` in `yego_lima_scheduler_service.py` |
| **What it measures** | Governance operability: `raw_orders`, `driver_state`, `eligibility`, `prioritized`, `queue` |
| **Current status** | Updated every 5 min by autonomous_tick |
| **Problem** | Governance-focused, not data-freshness-focused. Tracks process health, not data age. |

---

## CONTRADICTION MATRIX

| Table | `/growth/health` | V2 Registry | Real DB | Contradiction? |
|-------|-----------------|------------|---------|---------------|
| `driver_state_snapshot` | **BROKEN** (SLA 5h violated) | Not tracked | **FRESH** (06-12, 18,545 rows) | **YES** — health says BROKEN, data says FRESH |
| `program_assignment` | **BROKEN** (SLA 5h violated) | Not tracked | **FRESH** (06-12, 28,128 rows) | **YES** — health says BROKEN, data says FRESH |
| `lifecycle_daily` | **DEGRADED** | **FRESH** | **FRESH** (06-12, 68,506 rows) | **YES** — health severity inflated |
| `taxonomy_v2` | **DEGRADED** | **FRESH** | **FRESH** (06-12, 68,506 rows) | **YES** — health severity inflated |
| `program_v2` | **DEGRADED** | **FRESH** | **FRESH** (06-12, 68,506 rows) | **YES** — health severity inflated |
| `movement_fact` | **CRITICAL** | **FRESH** | **FRESH** (06-12, 466 rows) | **YES** — health says CRITICAL, data says FRESH |
| `activity_daily` | **CRITICAL** | STALE (0 rows) | 0 rows for 06-12 | **NO** — correctly detected |
| `effectiveness_fact` | **CRITICAL** | STALE (0 rows) | 0 rows for 06-12 | **NO** — correctly detected |
| `serving_driver_explorer` | **CRITICAL** | Not tracked | Table does not exist | **NO** — correctly detected |
| `RNA_serving` | **CRITICAL** | Not tracked | 888 rows exist | **YES** — health says CRITICAL, data exists |

**7 of 11 tracked assets have contradictions between health signal and actual data state.**

---

## ROOT CAUSE

The serving freshness audit (`serving_freshness_audit_service.py`) checks `freshness_age_hours` against SLAs stored in `growth.yego_lima_serving_freshness_fact`. The `last_refresh_at` timestamps in that table are not being updated frequently enough, even though the underlying data IS fresh.

**The freshness fact lags behind the data.** The data is refreshed by autonomous_tick/V2 pipeline. The freshness audit runs separately. When the audit runs, it computes age from `last_refresh_at`, which may be hours old even though the data was refreshed minutes ago.

---

## SIGNALS TO KEEP vs DEPRECATE

| Signal | Verdict | Rationale |
|--------|---------|-----------|
| `/growth/health` | **KEEP but add context** | Currently the only SLA compliance signal. Add `data_health` field to distinguish SLA issues from data issues. |
| `operational-date` / freshness check | **EXTEND** | Must check intelligence tables (lifecycle, taxonomy, movement) in addition to operational tables. |
| V2 Freshness Registry | **KEEP** | Correctly tracks V2 pipeline step results. Should be extended to operational tables or merged with V1 registry. |
| V1 Freshness Registry | **KEEP** | Governance operability tracking is valuable. Different purpose from data freshness. |

### New Signals (Additive, from LG_GOV_2A_HEALTH_CONTRACT_V2)

| Signal | What It Measures | How |
|--------|-----------------|-----|
| **DATA HEALTH** | Row counts per target_date for all source tables | `GET /growth/data-health` — simple COUNT(*) per table |
| **SLA HEALTH** | Refresh interval compliance (existing, with better labels) | `GET /growth/sla-health` — existing freshness audit with corrected categories |
| **SYSTEM HEALTH** | Combined signal: DATA + SLA | `GET /growth/system-health` — matrix combination |

---

## RECOMMENDED ARCHITECTURE

```
Data Sources (tables) ──→ DATA HEALTH check ──→ GET /growth/data-health
                              (COUNT(*) per target_date)
                              
Refresh Timestamps ──→ SLA HEALTH check ──→ GET /growth/sla-health
 (freshness_registry)    (age vs SLA thresholds)
 
DATA HEALTH ──┬──→ SYSTEM HEALTH ──→ GET /growth/system-health
SLA HEALTH  ──┘    (matrix combination)

EXISTING: /growth/health ──→ PRESERVED (backward compat)
EXISTING: /growth/freshness ──→ PRESERVED
EXISTING: /growth/operability ──→ PRESERVED
```

### Transition Plan

| Phase | Action |
|-------|--------|
| LG-CF-RECOVERY-2A (current) | Document contradictions. Design DATA HEALTH signal. |
| LG-CF-RECOVERY-2 | Implement DATA HEALTH endpoint (read-only, additive). |
| LG-CF-RECOVERY-3 | Add SLA HEALTH + SYSTEM HEALTH endpoints. |
| Post-closure | Evaluate deprecating `/growth/health` in favor of V2 endpoints. |

---

## CURRENT HONEST SIGNAL

**If Control Foundation had a single honest health signal today, it would be:**

```json
{
  "system_health": "DEGRADED",
  "data_health": "HEALTHY",
  "data_health_detail": "9/10 tables have fresh 06-12 data. 1 table missing (explorer_fact).",
  "sla_health": "DEGRADED",
  "sla_health_detail": "4 assets exceed SLA thresholds (activity_daily, effectiveness, serving_explorer, program_assignment).",
  "summary": "Data is operationally complete. Pipeline governance has SLA violations but does not impact data availability."
}
```

**This is the truth.** CRITICAL is too strong (data exists). HEALTHY would be dishonest (governance broken). DEGRADED is correct.
