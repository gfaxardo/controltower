# CF-H2H.0 — PROMOTION WORKFLOW

> **Fase:** CF-H2H.0 — Promotion Readiness Audit
> **Motor:** Control Foundation
> **Fecha:** 2026-06-11
> **Park:** `08e20910d81d42658d4334d3f6d10ac0` (Lima)
> **Status:** DESIGN ONLY — NO PROMOTION EXECUTED

---

## 1. PROMOTION STATE MACHINE

```
 ┌──────────────────┐
 │  NOT_CERTIFIED   │  Initial state. No candidate identified.
 └────────┬─────────┘
          │ Candidate identified + validator configured
          ▼
 ┌──────────────────┐
 │   SHADOW_ONLY    │  Reading from candidate, not comparing.
 └────────┬─────────┘
          │ Shadow comparison active, data flowing daily
          ▼
 ┌──────────────────────┐
 │ SHADOW_ACCUMULATING  │  shadow_days += 1 each day.
 │  (Day N of 30)       │  coverage, delta, freshness tracked.
 └────────┬─────────────┘
          │ shadow_days >= 30 AND coverage >= 95% AND delta <= threshold
          ▼
 ┌──────────────────┐
 │      READY       │  Meets all promotion criteria.
 └────────┬─────────┘
          │ Phase 1 approval (technical sign-off)
          ▼
 ┌──────────────────┐
 │  APPROVED_PH1    │  Technical readiness confirmed.
 └────────┬─────────┘
          │ Phase 2 approval (business/operations sign-off)
          ▼
 ┌──────────────────┐
 │  APPROVED        │  Full approval. Ready to promote.
 └────────┬─────────┘
          │ Promotion executed (update registry + verify)
          ▼
 ┌──────────────────┐
 │   PROMOTED       │  Yango is active canonical source.
 │ (current_owner   │  Omniview reads Yango.
 │   = YANGO)       │
 └────────┬─────────┘
          │ Rollback condition triggered
          ▼
 ┌──────────────────┐
 │  ROLLED_BACK     │  Reverted to CT_BRIDGE.
 │ (rollback_count  │  Requires investigation.
 │    += 1)         │
 └────────┬─────────┘
          │ Root cause fixed, re-enters shadow
          ▼
 ┌──────────────────────┐
 │ SHADOW_ACCUMULATING  │  Restart from day 0.
 └──────────────────────┘
```

---

## 2. PHASE 1: SHADOW OBSERVATION (30 Days)

### 2.1 Daily Metrics Tracked

| Metric | Target | Measured How |
|--------|--------|-------------|
| `shadow_days` | 30 | Incremented each day Yango data exists |
| `coverage_pct` | >= 95% | Yango days with data / total calendar days |
| `delta_pct` | <= threshold | ABS(Yango - CT) / CT * 100 |
| `freshness_pct` | >= 95% | Cycles within SLA / total cycles |
| `zero_gaps` | 0 | Days with no data and no documented reason |

### 2.2 Automated Daily Check

```sql
-- Runs after each Yango ingestion cycle
SELECT
    COUNT(DISTINCT order_ended_at::date) AS days_with_data,
    30 - COUNT(DISTINCT order_ended_at::date) AS days_remaining
FROM raw_yango.orders_raw
WHERE park_id = '08e20910d81d42658d4334d3f6d10ac0'
  AND order_status = 'complete'
  AND order_ended_at::date >= CURRENT_DATE - INTERVAL '30 days';
```

---

## 3. PHASE 2: READINESS VALIDATION

### 3.1 Minimum Evidence Required

| # | Evidence | Source |
|---|----------|--------|
| 1 | 30 consecutive FULL days of Yango orders | raw_yango.orders_raw DISTINCT dates |
| 2 | Coverage >= 95% vs CT for 30 days | Yango vs CT day_fact comparison |
| 3 | Delta <= threshold for all promoted KPIs | reconciliation_status = MATCH or EXPECTED_SEMANTIC_DELTA |
| 4 | Freshness <= 5min in >= 95% of cycles | scheduler_tick_log |
| 5 | 0 unexplained gaps | Per-date audit |
| 6 | Rollback test executed successfully | Dry-run rollback log |
| 7 | Business slice mapping PASS | CF-H2F.1 certification |
| 8 | Canonical mapper shadow stable | CF-H2G 30-day run log |
| 9 | Omniview productivo unchanged | Diff audit |

### 3.2 Validation Query

```sql
-- Promotion readiness for completed_trips
SELECT
    o.dt,
    o.yango_orders,
    ct.ct_trips,
    ROUND(ABS(o.yango_orders - ct.ct_trips)::numeric / NULLIF(ct.ct_trips, 0) * 100, 2) AS delta_pct,
    CASE
        WHEN ABS(o.yango_orders - ct.ct_trips)::numeric / NULLIF(ct.ct_trips, 0) * 100 <= 1.0 THEN 'PASS'
        WHEN ABS(o.yango_orders - ct.ct_trips)::numeric / NULLIF(ct.ct_trips, 0) * 100 <= 5.0 THEN 'WARN'
        ELSE 'FAIL'
    END AS status
FROM (
    SELECT order_ended_at::date AS dt, COUNT(DISTINCT order_id) AS yango_orders
    FROM raw_yango.orders_raw
    WHERE park_id = '08e20910d81d42658d4334d3f6d10ac0'
      AND order_status = 'complete'
      AND order_ended_at::date >= CURRENT_DATE - 30
    GROUP BY 1
) o
JOIN (
    SELECT trip_date AS dt, SUM(trips_completed) AS ct_trips
    FROM ops.real_business_slice_day_fact
    WHERE LOWER(TRIM(country)) = 'peru' AND LOWER(TRIM(city)) = 'lima'
      AND trip_date >= CURRENT_DATE - 30
    GROUP BY 1
) ct ON o.dt = ct.dt
ORDER BY o.dt;
```

---

## 4. PHASE 3: APPROVAL

### 4.1 Two-Phase Approval

**Phase 1 — Technical Approval:**
- Approved by: System/automated (all thresholds met) OR Senior Engineer
- Requirements: All 9 evidence items PASS
- Output: `promotion_status → APPROVED_PH1`

**Phase 2 — Business/Operations Approval:**
- Approved by: Operations Lead or designated approver
- Requirements: PH1 approval + business validation of Yango vs CT semantics
- Output: `promotion_status → APPROVED`, `approved_by`, `approved_at`, `approval_notes`

### 4.2 Approval Record

```sql
UPDATE ops.omniview_metric_source_registry
SET promotion_status = 'APPROVED',
    approved_at = now(),
    approved_by = '<OPERATOR_ID>',
    approval_notes = '30-day shadow complete. Coverage 98%, delta 0.7%, freshness 2.3min. Rollback test PASS.'
WHERE metric_name = '<KPI>';
```

---

## 5. PHASE 4: CONTROLLED PROMOTION

### 5.1 Promotion Execution (Per-KPI)

```sql
-- Promote completed_trips
BEGIN;
    UPDATE ops.omniview_metric_source_registry
    SET current_owner = 'YANGO',
        source_badge = 'YANGO_API',
        promotion_status = 'PROMOTED',
        last_promotion_event_at = now()
    WHERE metric_name = 'completed_trips'
      AND promotion_status = 'APPROVED';

    -- Re-generate canonical day facts for today
    -- (via cf_h2g_canonical_mapper_service)
COMMIT;
```

### 5.2 Promotion Verification

```bash
# Verify Omniview now reads Yango
GET /ops/omniview-v2/summary → completed_trips.source_badge = "YANGO_API"

# Verify data integrity
SELECT source_date, completed_trips_value, completed_trips_source_badge
FROM ops.omniview_canonical_day_fact_shadow
WHERE completed_trips_source_badge = 'YANGO_API'
ORDER BY source_date DESC LIMIT 5;
```

### 5.3 Promotion Order

KPIs must be promoted in dependency order:

```
1. completed_trips    (base)
2. active_drivers     (base)
3. revenue_yego       (base)
4. gmv                (base, no CT comparison)
5. avg_ticket         (derived: 1+4)
6. trips_per_driver   (derived: 1+2)
7. revenue_per_order  (derived: 3+1)
8. commission_rate    (derived: 3+4)
```

Never promote a derived KPI before its source KPIs.

---

## 6. PHASE 5: MONITORING

### 6.1 Post-Promotion Monitoring (First 7 Days)

| Check | Frequency | Action if fail |
|-------|-----------|----------------|
| Yango-Coverage > 90% | Daily | Auto-rollback if < 90% for 3 days |
| Delta < 5% | Daily | Alert if > 5%, investigate |
| Freshness < 5min | Every 5 min | Alert if > 30min for 6 cycles |
| UI rendering correct | Daily | Fix UI if Yango badge not displayed |
| CT not degraded | Daily | Ensure CT fallback still operational |

### 6.2 Monitoring Dashboard

```
GET /growth/operability → shows all KPI statuses
GET /growth/freshness → shows per-asset freshness
GET /growth/health → overall system health
```

---

## 7. PHASE 6: ROLLBACK (if needed)

See `CF_H2H0_ROLLBACK_TEST_PLAN.md` for full rollback procedure.

---

## 8. GOVERNANCE

### 8.1 Who Approves What

| Decision | Approver |
|----------|----------|
| Technical readiness (PH1) | Senior Engineer or automated check |
| Business go-ahead (PH2) | Operations Lead |
| Emergency rollback | Any operator (logged) |
| Unblock after 3 rollbacks | Senior Engineer + Operations Lead |

### 8.2 Approval Evidence Package

Each promotion must include:
1. 30-day coverage chart
2. 30-day delta chart
3. Freshness SLA compliance report
4. Rollback dry-run log
5. Business slice mapping validation
6. Operator sign-off (name, date, reason)

---

*Workflow complete. No promotion executed yet. Blocked by shadow days (4/30).*
