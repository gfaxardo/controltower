# CF-H2H.0 — ROLLBACK TEST PLAN

> **Fase:** CF-H2H.0 — Promotion Readiness Audit
> **Motor:** Control Foundation
> **Fecha:** 2026-06-11
> **Park:** `08e20910d81d42658d4334d3f6d10ac0` (Lima)
> **Status:** DESIGN ONLY — NO PROMOTION EXECUTED

---

## 1. PURPOSE

Define how to roll back any promoted KPI from YANGO_API to CT_BRIDGE without data loss or UI disruption. This plan is a prerequisite for CF-H2H Source Promotion.

---

## 2. ROLLBACK CONTROL POINT

### 2.1 Single Source of Truth

```
ops.omniview_metric_source_registry.current_owner
```

The `current_owner` field controls which source Omniview reads for each KPI. Changing it from `YANGO` to `CT_BRIDGE` immediately switches the data source for all consumers.

### 2.2 Rollback Mechanism

```sql
-- Rollback a single KPI
UPDATE ops.omniview_metric_source_registry
SET current_owner = rollback_source,
    source_badge = rollback_source,
    promotion_status = 'ROLLED_BACK',
    rollback_reason = '<REASON>',
    rollback_at = now(),
    rollback_count = rollback_count + 1
WHERE metric_name = '<KPI_NAME>'
  AND current_owner = 'YANGO'
RETURNING metric_name, current_owner, promotion_status;
```

### 2.3 Rollback Verification

```sql
-- Verify rollback took effect
SELECT metric_name, current_owner, source_badge, promotion_status
FROM ops.omniview_metric_source_registry
WHERE metric_name = '<KPI_NAME>';
```

---

## 3. ROLLBACK TYPES

### 3.1 Automatic Rollback (System-Triggered)

| Condition | KPIs Affected | Action |
|-----------|--------------|--------|
| Coverage < 90% for 3+ consecutive days | All promoted YANGO KPIs | Auto-rollback to CT_BRIDGE |
| Delta > 20% for 3+ consecutive days | completed_trips, active_drivers, revenue_yego | Auto-rollback |
| Freshness > 30 min for 6+ consecutive cycles | All YANGO_API KPIs | Flag DEGRADED, keep source with warning |
| API credentials fail (401/403) | All YANGO_API KPIs | Immediate auto-rollback |
| Scheduler fails for 10+ consecutive cycles | All YANGO_API KPIs | Auto-rollback |

### 3.2 Manual Rollback (Operator-Triggered)

| Condition | Action |
|-----------|--------|
| Operator detects semantic delta | Manual rollback with reason code |
| Business decision to revert | Manual rollback, documented |
| Pre-planned maintenance | Manual rollback, temporary |

---

## 4. ROLLBACK BY KPI

### 4.1 `completed_trips` — AUTO + MANUAL

| Aspect | Detail |
|--------|--------|
| Rollback source | CT trips_completed from ops.real_business_slice_day_fact |
| Auto trigger | Delta > 1% for 5+ days |
| Manual trigger | Operator discretion |
| Impact on dependent KPIs | avg_ticket, trips_per_driver, revenue_per_order, cancel_rate_pct also affected |

### 4.2 `active_drivers` — AUTO + MANUAL

| Aspect | Detail |
|--------|--------|
| Rollback source | CT active_drivers from ops.real_business_slice_day_fact |
| Auto trigger | Delta > 5% for 5+ days |
| Manual trigger | Operator discretion |
| Impact | trips_per_driver affected |

### 4.3 `revenue_yego` — AUTO + MANUAL

| Aspect | Detail |
|--------|--------|
| Rollback source | CT revenue_yego_final from ops.real_business_slice_day_fact |
| Auto trigger | Per-trip delta > 5% for 5+ days |
| Manual trigger | Operator discretion |
| Impact | revenue_per_order, commission_rate affected |

### 4.4 `gmv` — MANUAL ONLY

| Aspect | Detail |
|--------|--------|
| Rollback source | MISSING (CT = 0 for Lima) |
| Auto trigger | None (no CT comparison) |
| Manual trigger | Yango API failure |
| Impact | avg_ticket, commission_rate affected |

### 4.5 Derived KPIs — CASCADE

`avg_ticket`, `trips_per_driver`, `revenue_per_order`, `commission_rate` are derived from core KPIs. If any source KPI rollbacks, the derived KPIs automatically switch to their CT equivalents.

---

## 5. FAILURE SCENARIOS

### 5.1 Yango API Timeout

```
Detection:  scheduler_tick_log.tick_status = 'FAILED' with timeout error
Severity:   WARNING (first occurrence) → CRITICAL (3+ consecutive)
User sees:  Data timestamp stalled, freshness badge turns yellow
Fallback:   After 3 failed cycles → auto-rollback to CT_BRIDGE
Remediation: Check Yango API health, restart scheduler
```

### 5.2 Yango API Credentials (401/403)

```
Detection:  HTTP 401/403 in scheduler log
Severity:   CRITICAL
User sees:  Immediate rollback to CT_BRIDGE, banner: "Yango API unavailable"
Fallback:   Immediate auto-rollback
Remediation: Rotate credentials, update api_park_credentials_registry
```

### 5.3 Zero Orders (coverage collapse)

```
Detection:  COUNT(DISTINCT order_id) = 0 for a date
Severity:   CRITICAL after 3 days
User sees:  0 for completed_trips, MISSING badge
Fallback:   Auto-rollback after 3 days at 0
Remediation: Check Yango API endpoint, verify watermark, re-ingest
```

### 5.4 CT Fallback Missing

```
Detection:  CT fact table has no data for rollback date
Severity:   CRITICAL (double failure — both sources missing)
User sees:  — (dash) with explanation "No data available"
Fallback:   MISSING badge, no proxy calculation
Remediation: Investigate CT pipeline, rebuild day facts
```

---

## 6. ROLLBACK PROCEDURE (Step by Step)

### Execute Promotion Rollback

```bash
# Step 1: Identify KPIs to roll back
SELECT metric_name, current_owner, promotion_status
FROM ops.omniview_metric_source_registry
WHERE current_owner = 'YANGO' AND promotion_status = 'PROMOTED';

# Step 2: Execute rollback (manual example)
UPDATE ops.omniview_metric_source_registry
SET current_owner = 'CT_BRIDGE',
    source_badge = 'CT_BRIDGE',
    promotion_status = 'ROLLED_BACK',
    rollback_reason = 'Operator-initiated rollback: Yango delta spike detected',
    rollback_at = now(),
    rollback_count = rollback_count + 1
WHERE metric_name IN ('completed_trips', 'active_drivers', 'revenue_yego');

# Step 3: Verify Omniview reads CT
# Omniview canonical mapper reads current_owner from registry
# No code change needed — mapper auto-switches source

# Step 4: Verify data integrity
SELECT source_date, completed_trips_value, completed_trips_source_badge
FROM ops.omniview_canonical_day_fact_shadow
ORDER BY source_date DESC LIMIT 5;
```

---

## 7. ROLLBACK THROTTLING

To prevent thrashing (promote → rollback → re-promote → rollback):

```
IF rollback_count >= 3:
    promotion_status = 'BLOCKED'
    Notes: "KPI rolled back 3 times. Manual investigation required."
    Alert to operations
```

A BLOCKED KPI requires explicit unblocking after root cause fix:

```sql
UPDATE ops.omniview_metric_source_registry
SET promotion_status = 'SHADOW_ACCUMULATING',
    rollback_count = 0
WHERE metric_name = '<KPI>'
  AND promotion_status = 'BLOCKED'
  AND rollback_count >= 3;
```

---

## 8. TEST PLAN (Dry Run Before Promotion)

Before promoting any KPI, execute a dry-run rollback:

1. **Shadow promotion:** Set current_owner = 'YANGO' in shadow registry, generate day facts
2. **Compare 7 days:** Yango shadow vs CT production
3. **Simulate rollback:** Set current_owner = 'CT_BRIDGE', regenerate
4. **Verify:** Both directions produce deterministic results
5. **Sign-off:** Operator confirms rollback works

---

*Rollback plan complete. No rollback executed yet. Awaiting 30-day shadow window.*
