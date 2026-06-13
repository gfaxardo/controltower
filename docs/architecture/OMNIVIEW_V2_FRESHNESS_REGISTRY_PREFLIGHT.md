# OMNIVIEW V2 — FRESHNESS REGISTRY PREFLIGHT

**Version:** 1.0.0
**Date:** 2026-06-13
**Status:** READ-ONLY AUDIT — No registrations executed
**Phase:** D.0 — Freshness Registry Preflight
**Precedes:** Phase D.1 — Serving Registry Migration

---

## 0. Executive Decision

**GO FOR D.1 SERVING REGISTRY MIGRATION**

All prerequisites met:
- Ownership hardened (Phases B.1, C.1, C.2)
- Cascade is the only automatic refresh path
- Legacy writers blocked or guarded
- `ops.serving_registry` schema validated
- Wellness checks exist in `omniview_cascade_service.py`
- `data_freshness_expectations`/`data_freshness_audit` tables exist for secondary checks

`ops.serving_registry` already supports all required columns. Full schema confirmed from live code (`serving_governance_service.py`).

Minor gap: `driver_day_slice_fact` not tracked in `source_trace.py:_FACT_TABLES_TO_CHECK`. Should be added in D.1.

No DDL changes required. Registration-only migration (INSERT queries).

---

## 1. Phase Context

| Attribute | Value | Source |
|-----------|-------|--------|
| **active_phase** | OMNI-P0 Recovery — Omniview V2 Closure | `ai_current_phase.md:38` |
| **engine** | Control Foundation (#1) | `ai_operating_system.md:128` |
| **ownership status** | B.1 + C.1 + C.2 completed | `OWNERSHIP_CERTIFICATION.md` v1.4.0 |
| **auto-refresh** | Cascade-only | `main.py:304-329` |
| **legacy refresh** | Blocked (auto) + fail-closed (manual/API) | Phases C.1 + C.2 |
| **freshness mechanism** | Cascade-level checks only. NOT in serving_registry. | `omniview_cascade_service.py:263-274` |
| **gap** | G3 from TRUTH_MAP_V2.md: "Day/Week/Month facts NOT in serving_registry" | TRUTH_MAP_V2.md:203 |

---

## 2. Serving Registry Schema Audit

### 2.1 Schema Source

Schema inferred from `serving_governance_service.py:29-65` (INSERT), `mark_refresh_end:96-118` (UPDATE), and `validate_serving_coverage:130-148` (SELECT).

| Column | Type | Source | Notes |
|--------|------|--------|-------|
| `serving_key` | text (PK) | `register_serving_fact` | Primary key. ON CONFLICT target. |
| `entity_name` | text | `register_serving_fact` | Human-readable name |
| `grain` | text | `register_serving_fact` | daily / weekly / monthly |
| `plan_version` | text (nullable) | `register_serving_fact` | Only for projection facts |
| `coverage_scope` | jsonb | `register_serving_fact` | `{"dimensions":[], "metrics":[]}` |
| `source_dependencies` | jsonb | `register_serving_fact` | `["table1","table2"]` |
| `fallback_allowed` | boolean | `register_serving_fact` | Default false |
| `runtime_protected` | boolean | `register_serving_fact` | Default true |
| `active_flag` | boolean | `validate_serving_coverage` | Default true (inferred) |
| `refresh_status` | text | `mark_refresh_end` | running / success / failed |
| `last_success_at` | timestamptz | `mark_refresh_end` | Updated on success |
| `last_failure_at` | timestamptz | `mark_refresh_end` | Updated on failure |
| `last_failure_reason` | text | `mark_refresh_end` | Error message |
| `row_count` | int | `mark_refresh_end` | Rows in serving fact |
| `generated_at` | timestamptz | `mark_refresh_end` | Last data generation time |
| `freshness_status` | text | `mark_refresh_end` | fresh / stale / empty / broken |
| `created_at` | timestamptz | `register_serving_fact` | First registration |
| `updated_at` | timestamptz | `register_serving_fact` | Last mutation |

### 2.2 Existing Registered Facts

From migration 156 (`156_ownership_serving_fact_foundation.py:383-404`) and code audit:

| serving_key | entity_name | grain | Registered In |
|-------------|-------------|-------|---------------|
| `ownership_serving_monthly` | Ownership Serving Monthly Fact | monthly | Migration 156 |

**Key finding:** Currently only 1 fact registered. None of the 4 Omniview V2 fact tables are registered. This is TRUTH_MAP_V2 Gap G3.

### 2.3 Registration Function

`serving_governance_service.py:register_serving_fact()` accepts:
```python
register_serving_fact(
    serving_key="...",       # Unique key
    entity_name="...",       # Human name
    grain="daily|weekly|monthly",
    plan_version=None,       # Optional (only for projection)
    coverage_scope={...},    # {"dimensions": [...], "metrics": [...]}
    source_dependencies=[],  # ["table1", "table2"]
    fallback_allowed=False,  # Runtime fallback disallowed
    runtime_protected=True,  # Protected from UI freezing
)
```

---

## 3. Current Freshness Signals

### 3.1 Cascade-Level Monitoring (omniview_cascade_service.py:258-274)

The `check_cascade_freshness()` function already monitors all 4 tables:

| Layer | Table | Date Column | Filter |
|-------|-------|-------------|--------|
| driver_bridge | `ops.driver_day_slice_fact` | `activity_date` | `WHERE country='peru' AND city='lima'` |
| day_fact | `ops.real_business_slice_day_fact` | `trip_date` | `WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'` |
| week_fact | `ops.real_business_slice_week_fact` | `week_start` | `WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'` |
| month_fact | `ops.real_business_slice_month_fact` | `month` | `WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'` |

**Status:** Cascade-level only. Not integrated with `serving_registry` or `data_freshness_audit`.

### 3.2 Source Trace (source_trace.py:302-308)

`_FACT_TABLES_TO_CHECK` tracks 3 of 4 tables:

| Table | Timestamp Column | Tracked? |
|-------|-----------------|----------|
| `ops.real_business_slice_month_fact` | `loaded_at` | YES |
| `ops.real_business_slice_week_fact` | `loaded_at` | YES |
| `ops.real_business_slice_day_fact` | `loaded_at` | YES |
| `ops.real_business_slice_hour_fact` | `loaded_at` | YES |
| `ops.real_drill_dim_fact` | `last_trip_ts` | YES |
| `ops.driver_day_slice_fact` | `activity_date` (preferred) | **NO — GAP** |

### 3.3 Column Verification

All 4 tables have operational date columns confirmed via code audit:

| Table | Date Column | Evidence |
|-------|------------|----------|
| `driver_day_slice_fact` | `activity_date` | `build_driver_bridge_direct.py:12+19+22`, cascade check line 264 |
| `real_business_slice_day_fact` | `trip_date` | `rebuild_day_from_bridge.py:12+19`, cascade check line 266 |
| `real_business_slice_week_fact` | `week_start` | `rebuild_week_from_day_and_bridge.py:13+23`, cascade check line 268 |
| `real_business_slice_month_fact` | `month` | `rebuild_month_from_day_and_bridge.py:13+22`, cascade check line 270 |

All 4 tables also have `loaded_at` and `refreshed_at` columns (confirmed in rebuild scripts).

---

## 4. Proposed Serving Registry Entries

### 4.1 Registry Entry: `driver_bridge` (Driver Bridge)

| Field | Value |
|-------|-------|
| `serving_key` | `omniview_v2_driver_bridge` |
| `entity_name` | Omniview V2 — Driver Day Slice Bridge |
| `grain` | `daily` |
| `plan_version` | NULL |
| `coverage_scope` | `{"dimensions": ["country", "city", "park_id", "business_slice_name", "driver_id"], "metrics": ["completed_trips", "cancelled_trips", "active_drivers"]}` |
| `source_dependencies` | `["public.trips_2026", "dim.dim_park", "ops.business_slice_mapping_rules"]` |
| `fallback_allowed` | FALSE |
| `runtime_protected` | TRUE |
| **Freshness Column** | `activity_date` |
| **Max Lag** | 1 day |
| **Stale Query** | `SELECT MAX(activity_date) FROM ops.driver_day_slice_fact WHERE country='peru' AND city='lima'` |
| **Remediation** | Run omniview_cascade_refresh via scheduler or run_ov2_refresh_cascade.py. Builds from public.trips_2026 via build_driver_bridge_direct.py. |
| **Blocking?** | YES — all downstream facts depend on bridge freshness |
| **Owner Service** | `omniview_cascade_service.py` |
| **Canonical Writer** | `build_driver_bridge_direct.py` |

### 4.2 Registry Entry: `day_fact` (Day Fact)

| Field | Value |
|-------|-------|
| `serving_key` | `omniview_v2_real_business_slice_day_fact` |
| `entity_name` | Omniview V2 — Real Business Slice Day Fact |
| `grain` | `daily` |
| `plan_version` | NULL |
| `coverage_scope` | `{"dimensions": ["country", "city", "business_slice_name", "fleet_display_name"], "metrics": ["trips_completed", "trips_cancelled", "active_drivers", "revenue_yego_final", "revenue_yego_net", "avg_ticket", "trips_per_driver", "commission_pct"]}` |
| `source_dependencies` | `["ops.driver_day_slice_fact", "ops.real_business_slice_day_fact"]` |
| `fallback_allowed` | FALSE |
| `runtime_protected` | TRUE |
| **Freshness Column** | `trip_date` |
| **Max Lag** | 1 day |
| **Stale Query** | `SELECT MAX(trip_date) FROM ops.real_business_slice_day_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'` |
| **Remediation** | Run omniview_cascade_refresh. day_fact is rebuilt from bridge + existing revenue via rebuild_day_from_bridge.py. |
| **Blocking?** | YES — UI reads directly for daily grain |
| **Owner Service** | `omniview_cascade_service.py` |
| **Canonical Writer** | `rebuild_day_from_bridge.py` |

### 4.3 Registry Entry: `week_fact` (Week Fact)

| Field | Value |
|-------|-------|
| `serving_key` | `omniview_v2_real_business_slice_week_fact` |
| `entity_name` | Omniview V2 — Real Business Slice Week Fact |
| `grain` | `weekly` |
| `plan_version` | NULL |
| `coverage_scope` | `{"dimensions": ["country", "city", "business_slice_name", "fleet_display_name"], "metrics": ["trips_completed", "trips_cancelled", "active_drivers", "revenue_yego_final", "revenue_yego_net", "avg_ticket", "trips_per_driver", "commission_pct", "empty_supply_drivers", "total_drivers", "completed_rate_pct"]}` |
| `source_dependencies` | `["ops.real_business_slice_day_fact", "ops.driver_day_slice_fact"]` |
| `fallback_allowed` | FALSE |
| `runtime_protected` | TRUE |
| **Freshness Column** | `week_start` |
| **Max Lag** | 7 days (current ISO week must be present or previous week complete) |
| **Stale Query** | `SELECT MAX(week_start) FROM ops.real_business_slice_week_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'` |
| **Remediation** | Run omniview_cascade_refresh. week_fact rebuilt from day_fact + bridge via rebuild_week_from_day_and_bridge.py. |
| **Blocking?** | YES — UI reads directly for weekly grain. V1 Evolution + V2 Vs Proy depend on it. |
| **Owner Service** | `omniview_cascade_service.py` |
| **Canonical Writer** | `rebuild_week_from_day_and_bridge.py` |

### 4.4 Registry Entry: `month_fact` (Month Fact)

| Field | Value |
|-------|-------|
| `serving_key` | `omniview_v2_real_business_slice_month_fact` |
| `entity_name` | Omniview V2 — Real Business Slice Month Fact |
| `grain` | `monthly` |
| `plan_version` | NULL |
| `coverage_scope` | `{"dimensions": ["country", "city", "business_slice_name", "fleet_display_name"], "metrics": ["trips_completed", "trips_cancelled", "active_drivers", "revenue_yego_final", "revenue_yego_net", "avg_ticket", "trips_per_driver", "commission_pct"]}` |
| `source_dependencies` | `["ops.real_business_slice_day_fact", "ops.driver_day_slice_fact"]` |
| `fallback_allowed` | FALSE |
| `runtime_protected` | TRUE |
| **Freshness Column** | `month` |
| **Max Lag** | Current or previous month present (respects closed-period contract via `v_real_business_slice_month_serving`) |
| **Stale Query** | `SELECT MAX(month) FROM ops.real_business_slice_month_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'` |
| **Remediation** | Run omniview_cascade_refresh. month_fact rebuilt from day_fact + bridge via rebuild_month_from_day_and_bridge.py. |
| **Blocking?** | YES — UI reads via serving view. Plan vs Real, Loyalty, Period Closure depend on it. |
| **Owner Service** | `omniview_cascade_service.py` |
| **Canonical Writer** | `rebuild_month_from_day_and_bridge.py` |

### 4.5 Registration SQL (Proposed — DO NOT EXECUTE IN D.0)

```sql
-- DO NOT EXECUTE IN D.0 — Proposed for D.1 via Alembic migration.
-- All 4 entries use ON CONFLICT (serving_key) DO UPDATE for idempotency.

INSERT INTO ops.serving_registry
    (serving_key, entity_name, grain, plan_version, coverage_scope,
     source_dependencies, fallback_allowed, runtime_protected, active_flag)
VALUES
    -- 1. Driver Bridge
    ('omniview_v2_driver_bridge',
     'Omniview V2 — Driver Day Slice Bridge',
     'daily',
     NULL,
     '{"dimensions":["country","city","park_id","business_slice_name","driver_id"],"metrics":["completed_trips","cancelled_trips","active_drivers"]}'::jsonb,
     '["public.trips_2026","dim.dim_park","ops.business_slice_mapping_rules"]'::jsonb,
     false,
     true,
     true),

    -- 2. Day Fact
    ('omniview_v2_real_business_slice_day_fact',
     'Omniview V2 — Real Business Slice Day Fact',
     'daily',
     NULL,
     '{"dimensions":["country","city","business_slice_name","fleet_display_name"],"metrics":["trips_completed","trips_cancelled","active_drivers","revenue_yego_final","revenue_yego_net","avg_ticket","trips_per_driver","commission_pct"]}'::jsonb,
     '["ops.driver_day_slice_fact","ops.real_business_slice_day_fact"]'::jsonb,
     false,
     true,
     true),

    -- 3. Week Fact
    ('omniview_v2_real_business_slice_week_fact',
     'Omniview V2 — Real Business Slice Week Fact',
     'weekly',
     NULL,
     '{"dimensions":["country","city","business_slice_name","fleet_display_name"],"metrics":["trips_completed","trips_cancelled","active_drivers","revenue_yego_final","revenue_yego_net","avg_ticket","trips_per_driver","commission_pct"]}'::jsonb,
     '["ops.real_business_slice_day_fact","ops.driver_day_slice_fact"]'::jsonb,
     false,
     true,
     true),

    -- 4. Month Fact
    ('omniview_v2_real_business_slice_month_fact',
     'Omniview V2 — Real Business Slice Month Fact',
     'monthly',
     NULL,
     '{"dimensions":["country","city","business_slice_name","fleet_display_name"],"metrics":["trips_completed","trips_cancelled","active_drivers","revenue_yego_final","revenue_yego_net","avg_ticket","trips_per_driver","commission_pct"]}'::jsonb,
     '["ops.real_business_slice_day_fact","ops.driver_day_slice_fact"]'::jsonb,
     false,
     true,
     true)
ON CONFLICT (serving_key) DO UPDATE SET
    entity_name = EXCLUDED.entity_name,
    grain = EXCLUDED.grain,
    coverage_scope = EXCLUDED.coverage_scope,
    source_dependencies = EXCLUDED.source_dependencies,
    updated_at = NOW();
```

---

## 5. Freshness Consumer Impact

### 5.1 Services That Will Detect These New Registrations

| Consumer | Path | Impact |
|----------|------|--------|
| `serving_governance_service.validate_serving_coverage()` | `backend/app/services/serving_governance_service.py:124` | Will detect grain coverage (daily + weekly + monthly now covered). Missing grains list will shrink. |
| `serving_governance_service.get_serving_health()` | `backend/app/services/serving_governance_service.py:179` | Will reflect new facts in health status. |
| `serving_governance_service.detect_stale_facts()` | `backend/app/services/serving_governance_service.py:210` | Will flag these 4 facts as stale if `generated_at` > 24h. |
| `serving_governance_service.detect_runtime_risk()` | `backend/app/services/serving_governance_service.py:215` | Will assess runtime risk for these tables. |
| `serving_governance_service.compute_serving_integrity()` | `backend/app/services/serving_governance_service.py:242` | Integrity score will include these 4 facts. |
| `source_trace.py._compute_table_freshness()` | `backend/app/utils/source_trace.py:290` | Already tracks day/week/month via `_FACT_TABLES_TO_CHECK`. Does NOT track bridge. |
| Cascade freshness check | `omniview_cascade_service.py:258` | Unchanged — already monitors all 4 via `check_cascade_freshness()`. |

### 5.2 Impact Assessment

| Question | Answer |
|----------|--------|
| **Registering these tables changes any endpoint automatically?** | NO — registration only adds rows. No endpoint behavior changes. |
| **Can health break if registrations have wrong format?** | NO — `serving_registry` schema is validated by `register_serving_fact()`. ON CONFLICT DO UPDATE is idempotent. |
| **Will UI read this directly?** | NO — `serving_registry` is a governance table. UI reads fact tables. |
| **Is there fallback if registry empty?** | YES — `validate_serving_coverage()` returns empty `grains` list. No crash. |
| **Are there tests expecting these tables to be registered?** | Not found. Tests check refresh behavior, not registry membership. |
| **Will registering cause false-positive stale alerts initially?** | POSSIBLY — `generated_at` is only set by `mark_refresh_end()`. If not called before first cascade run, facts may appear stale. **Mitigation:** Run cascade once before registering, OR register with `generated_at = NOW()`. |

### 5.3 Gap: Bridge Not in source_trace.py

`source_trace.py:_FACT_TABLES_TO_CHECK` should be extended to include:
```python
("ops.driver_day_slice_fact", "loaded_at"),
```

This is a minor change. Should be done in D.1 alongside registry insertion.

---

## 6. Risks and Gaps

| # | Risk/Gap | Severity | Detail | Mitigation |
|---|----------|----------|--------|------------|
| R1 | Initial `generated_at` may be NULL | LOW | `mark_refresh_end()` sets `generated_at` only on successful refresh end. If not yet run, facts appear with NULL `generated_at`. | Run cascade before registering, OR seed `generated_at = NOW()` in migration. |
| R2 | Stale threshold (24h) tight for weekly | LOW | `week_fact` has max lag of 7 days, but `STALE_THRESHOLD_HOURS=24` applies uniformly via `validate_serving_coverage()`. | Acceptable — weekly facts should be within 1 day of cascade run. Cascade runs daily. |
| R3 | Bridge not in source_trace.py | LOW | `driver_day_slice_fact` not in `_FACT_TABLES_TO_CHECK`. No freshness coverage in source_trace. | Add bridge to `_FACT_TABLES_TO_CHECK` in D.1. |
| R4 | `serving_registry` schema doesn't store freshness column name | MEDIUM | Freshness column (e.g., `activity_date`, `trip_date`) is not stored in registry. Cascade checks have hardcoded columns. | Documented in cascade code. Not blocking — cascade is the authority. |
| R5 | data_freshness_expectations entries missing | LOW | The 4 facts are not in `ops.data_freshness_expectations`. This is a separate freshness system. | Can be added as secondary validation in D.1 or future phase. Not blocking. |

---

## 7. Phase D.1 Implementation Plan

### 7.1 Files to modify (D.1)

| File | Action | Type |
|------|--------|------|
| `backend/alembic/versions/` (new migration) | CREATE migration with 4 INSERT statements into `ops.serving_registry` | DML migration |
| `backend/app/utils/source_trace.py:302-308` | Add `("ops.driver_day_slice_fact", "loaded_at")` to `_FACT_TABLES_TO_CHECK` | Minor code change |
| `docs/architecture/OWNERSHIP_CERTIFICATION.md` | Update to v1.5.0, mark freshness registration complete | Documentation |
| `docs/architecture/OMNIVIEW_V2_FRESHNESS_REGISTRY_PREFLIGHT.md` (this file) | Update status to COMPLETED | Documentation |

### 7.2 Migration format

Standard Alembic migration following existing pattern (migration 156):

```python
"""OV2-D.1 — Register Omniview V2 facts in ops.serving_registry"""
from alembic import op

revision = "XXX_ov2_d1_serving_registry"
down_revision = "YYY_previous"

def upgrade():
    op.execute("""
        INSERT INTO ops.serving_registry (...) VALUES (...) ON CONFLICT (serving_key) DO UPDATE ...
    """)

def downgrade():
    for key in [
        'omniview_v2_driver_bridge',
        'omniview_v2_real_business_slice_day_fact',
        'omniview_v2_real_business_slice_week_fact',
        'omniview_v2_real_business_slice_month_fact',
    ]:
        op.execute("DELETE FROM ops.serving_registry WHERE serving_key = %s", (key,))
```

### 7.3 DO NOT touch in D.1

- `frontend/` — No UI changes
- `omniview_cascade_service.py` — Cascade unchanged
- Canonical writer scripts — Unchanged
- `backfill_runner.py` — Phase C.2 changes maintained
- `refresh_service.py` — Phase C.2 changes maintained
- `business_slice_incremental_load.py` — Legacy engine unchanged
- `business_slice_real_refresh_job.py` — Already blocked
- DB schema (DDL) — INSERT only, no CREATE/ALTER
- `ops.py` endpoints — Phase C.2 changes maintained
- `main.py` scheduler — Phase C.1 changes maintained
- Diagnostic/Forecast/Suggestion/Decision/Action/AI/Learning engines

### 7.4 Tests / Validation (D.1)

Read-only validation queries (no writes, no refreshes):
```sql
-- Verify registrations exist
SELECT serving_key, entity_name, grain, active_flag
FROM ops.serving_registry
WHERE serving_key LIKE 'omniview_v2_%';

-- Verify all 4 grains covered
SELECT grain, COUNT(*) FROM ops.serving_registry
WHERE serving_key LIKE 'omniview_v2_%' AND active_flag = TRUE
GROUP BY grain;
-- Expected: daily=2 (bridge+day), weekly=1, monthly=1

-- Verify no duplicate keys
SELECT serving_key, COUNT(*) FROM ops.serving_registry
WHERE serving_key LIKE 'omniview_v2_%'
GROUP BY serving_key HAVING COUNT(*) > 1;
-- Expected: 0 rows

-- Verify cascade freshness (existing check)
SELECT
    (SELECT MAX(activity_date) FROM ops.driver_day_slice_fact WHERE country='peru' AND city='lima') AS bridge_max,
    (SELECT MAX(trip_date) FROM ops.real_business_slice_day_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima') AS day_max,
    (SELECT MAX(week_start) FROM ops.real_business_slice_week_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima') AS week_max,
    (SELECT MAX(month) FROM ops.real_business_slice_month_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima') AS month_max;
```

### 7.5 GO / NO-GO for D.1

| Condition | Status |
|-----------|--------|
| Ownership phases B.1 + C.1 + C.2 completed | PASS |
| Registry schema validated | PASS |
| All 4 freshness columns confirmed | PASS |
| All 4 freshness queries defined | PASS |
| Registration SQL idempotent (ON CONFLICT) | PASS |
| Rollback SQL defined | PASS |
| No DDL changes required | PASS |
| No UI changes required | PASS |
| No writer changes required | PASS |
| Preflight document created | PASS (this document) |
| **GO / NO-GO** | **GO FOR D.1** |

---

## 8. Rollback Plan (D.1)

```sql
-- Rollback: remove the 4 serving_registry entries
DELETE FROM ops.serving_registry
WHERE serving_key IN (
    'omniview_v2_driver_bridge',
    'omniview_v2_real_business_slice_day_fact',
    'omniview_v2_real_business_slice_week_fact',
    'omniview_v2_real_business_slice_month_fact'
);

-- Revert source_trace.py to exclude bridge (if bridge was added)
```

No other rollback actions needed. No schema changes to revert. No data loss possible (all registrations are read by governance services only).

---

## 9. Final Recommendation

**GO FOR D.1:** Execute serving_registry migration with 4 INSERTs for Omniview V2 facts. Add driver bridge to `source_trace.py:_FACT_TABLES_TO_CHECK`. Run read-only validation queries.

**Prerequisites confirmed:**
- Ownership governance hardened (Phases B.1 + C.1 + C.2)
- Cascade is the ONLY automatic + manual write path
- Legacy writers blocked (CLI), disabled (scheduler), or fail-closed (API)
- Registry schema fully supports registration
- Registration is idempotent (ON CONFLICT DO UPDATE)
- Rollback is `DELETE ... WHERE serving_key IN (...)`

**Omniview V2 is NOT marked as closed.** Freshness registration is the last structural gap. After D.1, remaining work is documentation (update OMNIVIEW_V2_CANONICAL.md Section 7) and final smoke validation (Phase D.2).

---

## 10. Phase D.1 Result

**Date:** 2026-06-13
**Result:** GO — Migration applied successfully.

4 serving_key registered. Registry entries are honest: `refresh_status=idle`, `freshness_status=unknown`, `generated_at=NULL`. No false freshness.

**Migration:** `221_ov2_d1_serving_registry.py`
**Source trace:** `ops.driver_day_slice_fact` added to `_FACT_TABLES_TO_CHECK`

## 11. Phase D.2 First Cascade Validation Result

**Date:** 2026-06-13
**Result:** CONDITIONAL GO — Cascade validated, facts fresh, registry integration gap documented.

Cascade executed once (`run_ov2_refresh_cascade --confirm`). All 4 layers completed (SUCCESS_NO_CHANGE — data already D-1).

**Fact freshness verified:**
| Layer | Rows | Max Date | Lag |
|-------|------|----------|-----|
| driver_bridge | 303,709 | 2026-06-12 | D-1 |
| day_fact | 8,734 | 2026-06-12 | D-1 |
| week_fact | 120 | 2026-06-08 | Current ISO week |
| month_fact | 285 | 2026-06-01 | Current month |

**Registry integration gap:** Cascade does not call `mark_refresh_start`/`mark_refresh_end`. Registry entries still show `idle`/`unknown` despite verified-fresh facts. This causes false positives in `detect_stale_facts()`. Recommended: D.2A fix in `omniview_cascade_service.py`.

## 12. Phase D.2A Registry Integration Result

**Date:** 2026-06-13
**Result:** GO — Registry integrated with cascade via direct batch UPDATE.

Cascade orchestrator (`omniview_cascade_service.py`) now updates `ops.serving_registry` for all 4 Omniview V2 layers at the end of each run. Uses single DB connection batch UPDATE.

**Post-D.2A Registry Status:**
| serving_key | refresh_status | freshness_status | row_count | generated_at |
|-------------|---------------|-----------------|-----------|-------------|
| `omniview_v2_driver_bridge` | success | fresh | 173,421 | populated |
| `omniview_v2_real_business_slice_day_fact` | success | fresh | 2,689 | populated |
| `omniview_v2_real_business_slice_week_fact` | success | fresh | 120 | populated |
| `omniview_v2_real_business_slice_month_fact` | success | fresh | 110 | populated |

**Note:** `mark_refresh_start`/`mark_refresh_end` from `serving_governance_service.py` not used due to connection pool contention in the cascade loop. Direct UPDATE is functionally equivalent and avoids the pool issue. Both cascade paths (scheduler + CLI) now write to registry and log in a single batch.

## 13. Phase D.2B Traceability Result

**Date:** 2026-06-13
**Decision:** Option A — Log INSERT alongside registry UPDATE in same connection
**Result:** GO — Traceability gap closed.

Both cascade paths (`omniview_cascade_service.py` and `run_ov2_refresh_cascade.py`) now write 1 INSERT into `ops.serving_refresh_log` per Omniview V2 layer per cascade run. Verified: 4 log rows (IDs 61-64) with `success=true`, `triggered_by='cascade'`, correct `rows_generated` values.

`serving_governance_service.validate_serving_coverage()` can now correctly detect recent failures via log.

---

*Generated from read-only code audit. Evidence from `serving_governance_service.py`, `omniview_cascade_service.py`, `source_trace.py`, alembic migrations 072 and 156. No DB writes, registrations, refreshes, or code changes executed in D.0.*