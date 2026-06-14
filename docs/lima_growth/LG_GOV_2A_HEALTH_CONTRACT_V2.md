# LG_GOV_2A_HEALTH_CONTRACT_V2

**Phase:** LG-CF-GOV-2A — Governance Hardening  
**Generated:** 2026-06-12  
**Status:** SPECIFICATION — not implemented

---

## PROBLEM STATEMENT

### Current State: Two Conflicting Health Signals

**Signal 1: `/growth/health` → CRITICAL**
- Source: `growth.yego_lima_serving_freshness_fact`
- Based on: SLA compliance (refresh intervals)
- Reports: `program_assignment`, `driver_state_snapshot`, `RNA_serving`, `serving_driver_explorer` as **broken**
- Reality: These tables HAVE fresh data (06-12). The SLA freshness fact just hasn't been updated in time.

**Signal 2: `operational-date` API → `is_fresh: true`**
- Source: `detect_latest_closed_data_date()`
- Based on: `MAX(snapshot_date)` from `driver_state_snapshot` only
- Reports: System is caught up and healthy
- Reality: Ignores lifecycle/taxonomy/movement staleness. False positive.

**The contradiction:** One system says CRITICAL because SLAs are violated. Another says HEALTHY because snapshots are fresh. Both are technically correct within their narrow definitions. Neither gives a complete picture.

---

## SPECIFICATION: DATA HEALTH vs SLA HEALTH

### DATA HEALTH — "Is the data usable?"

| Level | Definition | Condition |
|-------|-----------|-----------|
| **HEALTHY** | All source tables have data for target_date | All checked tables: `COUNT(*) > 0 WHERE date = target_date` |
| **DEGRADED** | 1+ tables stale but core operational tables OK | Core tables healthy, 1+ intelligence tables stale |
| **BROKEN** | Core operational tables have no data for target_date | `driver_state_snapshot` has 0 rows for target_date |

**Checked tables for DATA HEALTH:**

| Layer | Tables | Weight |
|-------|--------|--------|
| Core (must pass) | `driver_state_snapshot`, `program_eligibility_daily` | CRITICAL |
| Intelligence (should pass) | `driver_lifecycle_daily`, `v2_taxonomy_daily`, `v2_program_daily`, `v2_movement_fact` | HIGH |
| Specialized (nice to pass) | `rna_priority_fact`, `program_effectiveness_fact`, `loopcontrol_result_sync`, `impact_tracking` | MEDIUM |
| Serving (nice to pass) | `driver_explorer_fact`, `serving_fact` | LOW |

**DATA HEALTH endpoint:** `GET /growth/data-health`

```json
{
  "data_health": "HEALTHY",
  "target_date": "2026-06-12",
  "tables": {
    "driver_state_snapshot": {"status": "HEALTHY", "rows": 18545, "max_date": "2026-06-12"},
    "driver_lifecycle_daily": {"status": "HEALTHY", "rows": 68506, "max_date": "2026-06-12"},
    "v2_taxonomy_daily": {"status": "HEALTHY", "rows": 68506, "max_date": "2026-06-12"},
    "v2_movement_fact": {"status": "HEALTHY", "rows": 466, "max_date": "2026-06-12"},
    "rna_priority_fact": {"status": "HEALTHY", "rows": 888, "max_date": null},
    "driver_explorer_fact": {"status": "MISSING", "rows": 0, "max_date": null}
  },
  "degraded_tables": [],
  "missing_tables": ["driver_explorer_fact"],
  "checked_at": "2026-06-12T23:00:00Z"
}
```

---

### SLA HEALTH — "Are refresh intervals being met?"

| Level | Definition | Condition |
|-------|-----------|-----------|
| **COMPLIANT** | All SLAs met | All assets: `freshness_age_hours <= sla_hours` |
| **DEGRADED** | 1+ SLAs exceeded but ≤ 2x SLA | Any asset: `sla_hours < freshness_age_hours <= sla_hours * 2` |
| **VIOLATED** | 1+ SLAs exceeded > 2x SLA | Any asset: `freshness_age_hours > sla_hours * 2` |

**SLA thresholds per asset type:**

| Asset Type | SLA | Rationale |
|-----------|-----|-----------|
| Operational (snapshot, eligibility) | **5 hours** | These are built every 5 min by autonomous_tick |
| Intelligence (lifecycle, taxonomy, program, movement) | **25 hours** | Built daily by V2 pipeline |
| Specialized (RNA, effectiveness, impact) | **48 hours** | Built on-demand or weekly |
| Serving (explorer_fact, serving_fact) | **25 hours** | Built after intelligence pipeline |
| Contact (loopcontrol, assignment) | **12 hours** | Synced on export cycles |

**SLA HEALTH endpoint:** `GET /growth/sla-health`

```json
{
  "sla_health": "DEGRADED",
  "violations": [
    {"asset": "activity_daily", "sla_hours": 25, "age_hours": 72, "severity": "VIOLATED"},
    {"asset": "serving_driver_explorer", "sla_hours": 25, "age_hours": null, "severity": "VIOLATED"}
  ],
  "degraded": [
    {"asset": "program_assignment", "sla_hours": 5, "age_hours": 8, "severity": "DEGRADED"}
  ],
  "compliant_count": 11,
  "degraded_count": 1,
  "violated_count": 2,
  "checked_at": "2026-06-12T23:00:00Z"
}
```

---

### SYSTEM HEALTH — Combined Signal

| DATA HEALTH | SLA HEALTH | SYSTEM HEALTH | Meaning |
|------------|-----------|---------------|---------|
| HEALTHY | COMPLIANT | **HEALTHY** | Data fresh AND SLAs met. Perfect. |
| HEALTHY | DEGRADED | **DEGRADED** | Data is good but monitoring lagging. |
| HEALTHY | VIOLATED | **DEGRADED** | Data is good but pipeline governance broken. |
| DEGRADED | COMPLIANT | **DEGRADED** | Pipelines running but data incomplete. |
| DEGRADED | DEGRADED | **DEGRADED** | Multiple issues. |
| DEGRADED | VIOLATED | **CRITICAL** | Data AND governance both degraded. |
| BROKEN | * | **CRITICAL** | Core data missing. Emergency. |

**Current state (2026-06-12):**
- DATA HEALTH = HEALTHY (all core + intelligence tables have 06-12 data)
- SLA HEALTH = DEGRADED (SLA violations in activity_daily, serving_driver_explorer)
- **SYSTEM HEALTH = DEGRADED**

**This is the correct, honest signal.** Not CRITICAL (data exists). Not HEALTHY (governance broken).

---

### SYSTEM HEALTH endpoint: `GET /growth/system-health`

```json
{
  "system_health": "DEGRADED",
  "data_health": "HEALTHY",
  "sla_health": "DEGRADED",
  "summary": "Data is operationally fresh (06-12). Pipeline governance has SLA violations (activity_daily, explorer_fact).",
  "action_required": "Run V2 pipeline to refresh activity_daily. Apply migration 220 and populate explorer_fact.",
  "checked_at": "2026-06-12T23:00:00Z"
}
```

---

## IMPLEMENTATION NOTES (not implemented)

### What Changes

1. **New service:** `growth_health_v2_service.py` — 3 functions: `get_data_health()`, `get_sla_health()`, `get_system_health()`
2. **New endpoints:** `GET /growth/data-health`, `GET /growth/sla-health`, `GET /growth/system-health`
3. **Existing endpoints preserved:** `/growth/health`, `/growth/freshness`, `/growth/operability` continue to work
4. **`detect_latest_closed_data_date()`** — extend to check intelligence tables, not just operational

### Data Sources

| Health Type | Queries |
|------------|---------|
| DATA HEALTH | `SELECT COUNT(*) FROM each_table WHERE date_col = target_date` |
| SLA HEALTH | `SELECT * FROM growth.yego_lima_serving_freshness_fact` (existing) |
| SYSTEM HEALTH | Combination of above two |

### Migration Impact

None. This is a read-only contract change. Existing tables, endpoints, and health signals are preserved. New endpoints are additive.
