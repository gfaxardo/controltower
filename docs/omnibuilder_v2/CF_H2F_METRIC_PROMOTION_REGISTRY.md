# CF-H2F — METRIC PROMOTION REGISTRY

> **Fase:** CF-H2F — Metric Ownership Matrix
> **Motor:** Control Foundation
> **Fecha:** 2026-06-11
> **Park:** `08e20910d81d42658d4334d3f6d10ac0` (Lima)
> **Clasificación:** `CF_H2F_PROMOTION_REGISTRY_DESIGN`

---

## 1. PURPOSE

Diseño de la tabla `ops.metric_promotion_registry` que gobierna la promoción y rollback de fuentes de KPIs. **NO se promueve nada todavía.** Solo diseño y workflows.

---

## 2. TABLE: `ops.metric_promotion_registry`

### 2.1 DDL

```sql
CREATE SCHEMA IF NOT EXISTS ops;

CREATE TABLE ops.metric_promotion_registry (
    -- Identity
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    -- KPI Identity
    metric_name         text NOT NULL UNIQUE,          -- ej. 'completed_trips'
    metric_label        text,                          -- ej. 'Trips Completados'
    metric_tier         text NOT NULL DEFAULT 'core',  -- core | derived | lifecycle | dimensional | program

    -- Ownership
    current_owner       text NOT NULL,                 -- YANGO | CT_BRIDGE | SHARED | HYBRID | BLOCKED
    candidate_owner     text,                          -- proposed canonical owner (null if already promoted)
    source_badge        text NOT NULL,                 -- YANGO_API | CT_BRIDGE | SHARED | HYBRID | PROXY | MISSING | BLOCKED

    -- Shadow / Promotion Metrics
    shadow_days         integer DEFAULT 0,             -- consecutive days in shadow mode
    coverage_pct        numeric(5,2),                  -- coverage vs shadow validator (0-100)
    delta_pct           numeric(8,4),                  -- max daily delta vs validator
    freshness_pct       numeric(5,2),                  -- freshness SLA compliance % (0-100)
    freshness_target_min integer,                      -- target freshness in minutes
    coverage_requirement_pct numeric(5,2),             -- required coverage % for promotion
    promotion_threshold_delta numeric(8,4),            -- max allowed delta for promotion

    -- Promotion State
    promotion_status    text NOT NULL DEFAULT 'NOT_CERTIFIED',
    -- NOT_CERTIFIED | SHADOW_ONLY | SHADOW_ACCUMULATING | READY | APPROVED | PROMOTED | ROLLED_BACK

    -- Rollback
    rollback_source     text,                          -- fallback source if rolled back
    rollback_reason     text,                          -- reason for last rollback
    rollback_at         timestamptz,                   -- when rollback occurred
    rollback_count      integer DEFAULT 0,             -- number of rollbacks (prevent thrashing)

    -- Approval
    approved_at         timestamptz,
    approved_by         text,                          -- operator or system identity
    approval_notes      text,

    -- Shadow Validator Config
    shadow_validator    text,                          -- CT metric/query used for validation
    validator_query     text,                          -- reference SQL or endpoint for validator
    validator_threshold numeric(8,4),                  -- acceptable delta for validator comparison

    -- Audit
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    last_shadow_check_at timestamptz,                  -- last automated shadow comparison
    last_promotion_event_at timestamptz                -- last status change (promote/rollback)
);

-- Seed: insert all 21 KPIs with current state
COMMENT ON TABLE ops.metric_promotion_registry IS
'Governs KPI source promotion from shadow to canonical. Tracks coverage, delta, freshness, and approval chain.';
```

### 2.2 Seed Data (Initial State)

```sql
-- Core KPIs
INSERT INTO ops.metric_promotion_registry (metric_name, metric_label, metric_tier, current_owner, candidate_owner, source_badge, promotion_status, rollback_source, shadow_validator)
VALUES
('completed_trips',       'Trips Completados',     'core',   'CT_BRIDGE', 'YANGO', 'CT_BRIDGE', 'SHADOW_ACCUMULATING', 'CT_BRIDGE', 'ops.real_business_slice_day_fact.trips_completed'),
('cancelled_trips',       'Trips Cancelados',      'core',   'CT_BRIDGE', NULL,     'CT_BRIDGE', 'NOT_CERTIFIED',       NULL,         NULL),
('total_orders',          'Total Órdenes',         'core',   'HYBRID',    NULL,     'HYBRID',    'NOT_CERTIFIED',       NULL,         NULL),
('active_drivers',        'Conductores Activos',   'core',   'CT_BRIDGE', 'YANGO', 'CT_BRIDGE', 'SHADOW_ACCUMULATING', 'CT_BRIDGE', 'ops.real_business_slice_day_fact.active_drivers'),
('revenue_yego',          'Revenue YEGO',          'core',   'CT_BRIDGE', 'YANGO', 'CT_BRIDGE', 'SHADOW_ACCUMULATING', 'CT_BRIDGE', 'ops.real_business_slice_day_fact.revenue_yego_final'),
('gmv',                   'GMV',                   'core',   'CT_BRIDGE', 'YANGO', 'CT_BRIDGE', 'SHADOW_ACCUMULATING', 'MISSING',    NULL),

-- Derived KPIs
('avg_ticket',            'Ticket Promedio',       'derived','CT_BRIDGE', 'YANGO', 'CT_BRIDGE', 'SHADOW_ACCUMULATING', 'CT_BRIDGE', 'ops.real_business_slice_day_fact.avg_ticket'),
('trips_per_driver',      'Viajes por Conductor',  'derived','CT_BRIDGE', 'YANGO', 'CT_BRIDGE', 'SHADOW_ACCUMULATING', 'CT_BRIDGE', 'ops.real_business_slice_day_fact.trips_per_driver'),
('revenue_per_order',     'Revenue por Orden',     'derived','CT_BRIDGE', 'YANGO', 'CT_BRIDGE', 'SHADOW_ACCUMULATING', 'CT_BRIDGE', NULL),
('commission_pct',        'Tasa de Comisión',      'derived','CT_BRIDGE', 'YANGO', 'CT_BRIDGE', 'SHADOW_ACCUMULATING', 'CT_BRIDGE', 'ops.real_business_slice_day_fact.commission_pct'),
('cancel_rate_pct',       'Tasa de Cancelación',   'derived','HYBRID',    NULL,     'HYBRID',    'NOT_CERTIFIED',       NULL,         NULL),

-- Identity & Lifecycle
('driver_identity',       'Identidad Conductor',   'identity','SHARED',   NULL,     'SHARED',    'READY',               NULL,         NULL),
('new_drivers',           'Nuevos Conductores',    'lifecycle','CT_BRIDGE',NULL,     'CT_BRIDGE', 'SHADOW_ONLY',         NULL,         NULL),
('reactivated_drivers',   'Reactivados',           'lifecycle','CT_BRIDGE',NULL,     'CT_BRIDGE', 'BLOCKED',             NULL,         NULL),
('churned_drivers',       'Churn',                 'lifecycle','CT_BRIDGE',NULL,     'CT_BRIDGE', 'BLOCKED',             NULL,         NULL),
('supply_hours',          'Horas Online',          'lifecycle','BLOCKED',   NULL,     'BLOCKED',   'BLOCKED',             NULL,         NULL),

-- Dimensional
('business_slice',        'Segmento de Negocio',   'dimensional','REQUIRES_MAPPING','YANGO','CT_BRIDGE','BLOCKED',        'CT_BRIDGE', NULL),
('park',                  'Park',                  'dimensional','SHARED',  NULL,     'SHARED',    'READY',               NULL,         NULL),
('city',                  'City',                  'dimensional','SHARED',  NULL,     'SHARED',    'READY',               NULL,         NULL),
('country',               'Country',               'dimensional','SHARED',  NULL,     'SHARED',    'READY',               NULL,         NULL),

-- Programs
('scout_cohorts_programs','Scout/Cohortes/Programs','program','CT_BRIDGE', NULL,     'CT_BRIDGE', 'SHADOW_ONLY',         NULL,         NULL);
```

---

## 3. PROMOTION WORKFLOW

### 3.1 State Machine

```
                    ┌─────────────────┐
                    │  NOT_CERTIFIED  │  ← Initial state
                    └────────┬────────┘
                             │ source candidate identified
                             ▼
                    ┌─────────────────┐
                    │  SHADOW_ONLY    │  ← Reading from candidate, not comparing yet
                    └────────┬────────┘
                             │ validator configured, data flowing
                             ▼
                    ┌──────────────────────┐
                    │ SHADOW_ACCUMULATING  │  ← Daily shadow comparison running
                    │ (shadow_days += 1)   │     coverage, delta, freshness tracked
                    └────────┬─────────────┘
                             │ shadow_days >= 30
                             │ coverage_pct >= 95%
                             │ delta_pct <= threshold
                             │ freshness_pct >= 95%
                             ▼
                    ┌─────────────────┐
                    │     READY       │  ← Meets all promotion criteria
                    └────────┬────────┘
                             │ approved_by != null
                             ▼
                    ┌─────────────────┐
                    │    APPROVED     │  ← Human or system approval
                    └────────┬────────┘
                             │ migration executed (CF-H2H)
                             ▼
                    ┌─────────────────┐
                    │    PROMOTED     │  ← Canonical source in production
                    │ (current_owner  │
                    │  = candidate)   │
                    └────────┬────────┘
                             │ rollback condition triggered
                             ▼
                    ┌─────────────────┐
                    │  ROLLED_BACK    │  ← Reverted to fallback_source
                    │ (rollback_count │
                    │  += 1)          │
                    └────────┬────────┘
                             │ root cause fixed, re-enters shadow
                             ▼
                    ┌──────────────────────┐
                    │ SHADOW_ACCUMULATING  │  ← Restart shadow days from 0
                    └──────────────────────┘
```

### 3.2 Daily Shadow Check (Automated)

Executed by scheduler after each Yango ingestion cycle:

```
FOR each KPI WHERE promotion_status = 'SHADOW_ACCUMULATING':

  1. Query Yango value (candidate source)
  2. Query CT value (shadow_validator)
  3. Compute delta_pct = ABS(yango - ct) / ct * 100
  4. Compute coverage_pct = (days with yango data / total days) * 100
  5. Compute freshness_pct = (cycles within SLA / total cycles) * 100
  6. shadow_days += 1
  7. UPDATE ops.metric_promotion_registry

  IF shadow_days >= 30
     AND coverage_pct >= coverage_requirement_pct
     AND delta_pct <= promotion_threshold_delta
     AND freshness_pct >= 95:
    → promotion_status = 'READY'
```

### 3.3 Approval Workflow

```
1. KPI reaches READY status
2. System generates promotion report:
   - 30-day coverage chart
   - 30-day delta chart
   - Freshness SLA compliance
   - Rollback plan tested (dry-run)
3. Operator reviews report
4. Operator sets:
   UPDATE ops.metric_promotion_registry
   SET promotion_status = 'APPROVED',
       approved_at = now(),
       approved_by = '<operator_id>',
       approval_notes = '<reason>'
   WHERE metric_name = '<kpi>';
5. CF-H2H migration executes:
   - Omniview source mapper updated to point to Yango source
   - current_owner updated to candidate_owner
   - promotion_status = 'PROMOTED'
```

---

## 4. ROLLBACK WORKFLOW

### 4.1 Automatic Rollback Triggers

| Condition | Action |
|-----------|--------|
| Coverage < 90% for 3+ consecutive days | AUTO: `promotion_status → ROLLED_BACK`, `rollback_source` activated |
| Delta > 20% for 3+ consecutive days | AUTO: `promotion_status → ROLLED_BACK`, alert operator |
| Freshness > 30 min for 6+ consecutive cycles | AUTO: `source_badge → YANGO_API_DEGRADED`, warn, keep source |
| API credentials fail (401/403) | AUTO: immediate `ROLLED_BACK` |
| Scheduler fails for 10+ consecutive cycles | AUTO: `ROLLED_BACK` |

### 4.2 Manual Rollback

```
POST /ops/metrics/{metric_name}/rollback
{
  "reason": "Revenue delta spike detected (manual review)",
  "rollback_to": "CT_BRIDGE"
}

→ UPDATE ops.metric_promotion_registry
  SET promotion_status = 'ROLLED_BACK',
      current_owner = rollback_source,
      rollback_reason = <reason>,
      rollback_at = now(),
      rollback_count = rollback_count + 1
  WHERE metric_name = <metric_name>;
```

### 4.3 Rollback Throttling

```
IF rollback_count >= 3:
  → promotion_status = 'BLOCKED'
  → metric requires manual investigation before re-entering shadow
  → Alert: "KPI {name} has been rolled back 3 times. Manual investigation required."
```

### 4.4 Post-Rollback Recovery

```
1. Root cause identified and fixed
2. shadow_days reset to 0
3. promotion_status → 'SHADOW_ACCUMULATING'
4. Re-accumulate 30 days in shadow
5. Re-enter approval workflow
```

---

## 5. KPI-SPECIFIC PROMOTION THRESHOLDS

| metric_name | freshness_target_min | coverage_requirement_pct | promotion_threshold_delta | validator |
|------------|---------------------|-------------------------|--------------------------|-----------|
| completed_trips | 5 | 95 | 1.0% | CT trips_completed |
| active_drivers | 5 | 95 | 5.0% | CT active_drivers |
| revenue_yego | 5 | 95 | 5.0% | CT revenue_yego_final (per-trip) |
| gmv | 5 | 95 | N/A | N/A (CT=0) |
| avg_ticket | 5 | 95 | 5.0% | CT avg_ticket |
| trips_per_driver | 5 | 95 | 5.0% | CT trips_per_driver |
| revenue_per_order | 5 | 95 | 5.0% | CT derived |
| commission_pct | 5 | 95 | 5.0% | CT commission_pct |

---

## 6. MONITORING QUERIES

### 6.1 KPIs Ready for Approval

```sql
SELECT metric_name, shadow_days, coverage_pct, delta_pct, freshness_pct
FROM ops.metric_promotion_registry
WHERE promotion_status = 'READY'
ORDER BY metric_name;
```

### 6.2 KPIs in Shadow (Accumulating)

```sql
SELECT metric_name, shadow_days, coverage_pct,
       30 - shadow_days AS days_until_ready
FROM ops.metric_promotion_registry
WHERE promotion_status = 'SHADOW_ACCUMULATING'
ORDER BY shadow_days DESC;
```

### 6.3 Blocked / Rolled Back KPIs

```sql
SELECT metric_name, promotion_status, rollback_count, rollback_reason
FROM ops.metric_promotion_registry
WHERE promotion_status IN ('BLOCKED', 'ROLLED_BACK', 'NOT_CERTIFIED')
ORDER BY promotion_status, metric_name;
```

### 6.4 Promotion Audit Trail

```sql
SELECT metric_name, promotion_status, current_owner, candidate_owner,
       approved_at, approved_by, last_promotion_event_at
FROM ops.metric_promotion_registry
WHERE last_promotion_event_at IS NOT NULL
ORDER BY last_promotion_event_at DESC;
```

---

## 7. INTEGRATION WITH CF-H2G (Canonical Mapper)

The Canonical Mapper reads `ops.metric_promotion_registry` to determine:
- Which source to use for each KPI
- Whether to include Yango or CT source
- Whether to show a badge or warning

```python
# Pseudocode for canonical mapper
def get_kpi_source(metric_name: str) -> str:
    row = query("SELECT current_owner, source_badge FROM ops.metric_promotion_registry WHERE metric_name = ?", metric_name)
    if row.promotion_status == 'PROMOTED':
        return row.current_owner  # YANGO
    else:
        return 'CT_BRIDGE'  # fallback
```

---

## 8. FIRMA

| Campo | Valor |
|-------|-------|
| **Diseñado por** | CF-H2F Metric Ownership Matrix |
| **Fecha** | 2026-06-11 |
| **Motor** | Control Foundation |
| **Clasificación** | `CF_H2F_PROMOTION_REGISTRY_DESIGN` |
| **Status** | **DESIGN ONLY — NO PROMOTION EXECUTED** |
| **Dependencia** | CF-H2G (Canonical Mapper) debe leer esta tabla |
