# CT-GOV-043 — False Freshness Detector

**Date:** 2026-06-08
**Motor:** Control Foundation / Global Freshness Governance
**Status:** CANONICAL

---

## 1. PROBLEM STATEMENT

A layer can be "freshly generated" (layer_date = today) but built from stale data (effective_source_date = 6 days ago). This is FALSE FRESHNESS.

**Example (Lima Growth R3.0E):**
```
snapshot.layer_date = 2026-06-05
snapshot.effective_source_date = 2026-06-01  <- 4 days behind
Status: STALE_PROPAGATED (previously reported as FRESH)
```

---

## 2. DETECTION RULES

### Rule 1: Layer Date vs Effective Source Date

```python
if layer_date > effective_source_date:
    status = "STALE_PROPAGATED"
    severity = "HIGH"
```

### Rule 2: Staleness Propagation

```python
if parent.status == "STALE" and child.layer_date > parent.effective_source_date:
    child.status = "STALE_PROPAGATED"
```

### Rule 3: Gap Classification

| Gap Size | Classification | Action |
|:--------:|:--------------:|--------|
| 0-1 days | OK | None |
| 2-3 days | WARNING | Monitor |
| 4-7 days | STALE | Remediation required |
| > 7 days | **CRITICAL** | Block GO certification |

### Rule 4: False GREEN Prevention

A serving fact MUST NOT be marked FRESH if:
- `layer_date > effective_source_date`
- Any ancestor in the lineage chain is STALE
- The gap exceeds SLA maximum

---

## 3. DETECTOR IMPLEMENTATION

### Lima Growth

`GET /yego-lima-growth/freshness-chain/status` already implements this:
- Returns `effective_source_date` per layer
- Returns `effective_freshness` with STALE_PROPAGATED status
- Returns `propagated: true` for inherited staleness

### Omniview

Must implement equivalent endpoint:
`GET /ops/omniview-v2/freshness-chain`

### Global Aggregator

`GET /governance/freshness-chain` (to be created) aggregates all domains.

---

## 4. PREVIOUS INCIDENTS

| Date | System | Layer | False Status | Real Status | Root Cause |
|------|--------|-------|:---:|:---:|------------|
| 06-07 | Lima Growth | snapshot through serving | FRESH | STALE_PROPAGATED | layer_date checked, effective_source_date not checked |
| 06-03 | Omniview | week_fact | OK | STALE (48d) | Serving facts not refreshed |
| 06-03 | Omniview | Revenue | WARNING | FAIL (0%) | Wrong revenue column used |

---

## 5. PREVENTION CHECKLIST

Before any GO certification:

- [ ] All layers have `effective_source_date` defined
- [ ] No layer has `layer_date > effective_source_date` without STALE_PROPAGATED status
- [ ] All gaps are within SLA maximums
- [ ] UI shows honest freshness status (not false GREEN)
- [ ] Operational layers exist (>0 rows)
- [ ] Serving facts are generated for latest date

---

## FIRMA

```
CT-GOV-043 FALSE FRESHNESS DETECTOR
Date: 2026-06-08
Status: CANONICAL
```
