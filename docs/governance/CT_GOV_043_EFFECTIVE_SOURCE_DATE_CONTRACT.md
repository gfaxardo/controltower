# CT-GOV-043 — Effective Source Date Contract

**Date:** 2026-06-08
**Motor:** Control Foundation / Global Freshness Governance
**Status:** CANONICAL

---

## 1. DEFINITION

Every serving layer MUST expose two dates:

| Field | Definition |
|-------|-----------|
| **layer_date** | When this specific layer was generated/refreshed |
| **effective_source_date** | The MAX date of the upstream data that feeds this layer |

### Why

Discovered in R3.0E: Lima Growth snapshot showed `layer_date=06-05` but `effective_source_date=06-01`. The layer was freshly generated from stale data. This is FALSE FRESHNESS.

---

## 2. RULES

### Rule 1: Effective Source Date

```
effective_source_date = MAX(date_column) OF upstream source table
```

For each layer, trace ONE level up in the lineage chain and take the max date.

### Rule 2: Freshness Status

| Condition | Status |
|-----------|--------|
| effective_source_date >= today - 1 | **FRESH** |
| effective_source_date >= today - 3 | **OK** |
| effective_source_date >= today - 7 | **STALE** |
| effective_source_date > 7 days ago | **CRITICAL** |
| layer_date > effective_source_date | **STALE_PROPAGATED** (false freshness) |

### Rule 3: Propagation

```
If parent_layer.effective_source_date < child_layer.layer_date:
    child_layer.status = STALE_PROPAGATED
```

Staleness propagates downstream. A child cannot be fresher than its parent.

### Rule 4: Gap Calculation

```
freshness_gap_days = today - effective_source_date
```

---

## 3. CONTRACT FIELDS

Every layer in the freshness chain MUST return:

```json
{
  "layer": "snapshot",
  "layer_date": "2026-06-05",
  "effective_source_date": "2026-06-04",
  "freshness_gap_days": 4,
  "freshness_status": "OK",
  "propagated": false,
  "source_layer": "history_weekly",
  "source_table": "growth.yango_lima_driver_history_weekly"
}
```

---

## 4. VIOLATIONS

| Violation | Severity | Detection |
|-----------|:---:|-----------|
| layer_date > effective_source_date | HIGH | STALE_PROPAGATED status |
| effective_source_date missing | CRITICAL | Cannot compute freshness |
| source_layer undefined | MEDIUM | Lineage broken |
| gap > 7 days without warning | HIGH | False GREEN in UI |

---

## 5. IMPLEMENTATION

- Lima Growth: `GET /yego-lima-growth/freshness-chain/status` returns this contract
- Omniview: `GET /ops/omniview-v2/freshness-chain` (to be created)
- Global: `GET /governance/freshness-chain` aggregates all domains

---

## FIRMA

```
CT-GOV-043 EFFECTIVE SOURCE DATE CONTRACT
Date: 2026-06-08
Status: CANONICAL
```
