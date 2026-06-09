# CT-GOV-043 — Fail Fast Registry

**Date:** 2026-06-08
**Motor:** Control Foundation / Global Freshness Governance
**Status:** CANONICAL

---

## 1. UNIFIED ERROR CODES

| Code | Name | Severity | Description |
|------|------|:---:|-------------|
| **FF-001** | RAW_STALE | **CRITICAL** | Raw source data > 48h behind. All downstream is stale. |
| **FF-002** | FACT_STALE | HIGH | Fact table not refreshed within SLA. |
| **FF-003** | SNAPSHOT_STALE | HIGH | Snapshot date < latest operational date. |
| **FF-004** | FALSE_FRESHNESS | **CRITICAL** | layer_date > effective_source_date. System reports FRESH but data is old. |
| **FF-005** | WATERFALL_BROKEN | **CRITICAL** | A layer in the waterfall chain is missing or empty. |
| **FF-006** | DOUBLE_WRITER | HIGH | More than one writer for the same table. |
| **FF-007** | ORPHAN_LAYER | MEDIUM | Table has data but no writer or consumer. |
| **FF-008** | SERVING_MISSING | HIGH | Serving fact exists but has MISSING status. |
| **FF-009** | STALE_PROPAGATED | HIGH | Child layer fresh but built from stale parent data. |
| **FF-010** | SOURCE_UNKNOWN | MEDIUM | Layer exists but its source lineage is not documented. |

---

## 2. DETECTION MECHANISMS

| Code | Detection | Where |
|------|-----------|-------|
| FF-001 | MAX(raw_date) < today - 2 | Freshness chain check |
| FF-002 | MAX(fact_date) < today - 1 | SLA registry scan |
| FF-003 | MAX(snapshot_date) < latest_operational_date | validate_source_readiness() |
| FF-004 | layer_date > effective_source_date | False Freshness Detector |
| FF-005 | COUNT(*) = 0 for any waterfall layer | Freshness chain check |
| FF-006 | COUNT(DISTINCT writer) > 1 per table | Ownership registry |
| FF-007 | table has rows but no writer in registry | Ownership audit |
| FF-008 | serving_fact.freshness_status = 'MISSING' | Serving fact check |
| FF-009 | child.layer_date > parent.effective_source_date | Effective freshness check |
| FF-010 | layer not in lineage map | Source lineage audit |

---

## 3. RESPONSE MATRIX

| Severity | Action | Response Time | Blocks GO? |
|:---:|--------|:---:|:---:|
| **CRITICAL** | Stop pipeline. Alert. Remediate immediately. | < 1 hour | **YES** |
| HIGH | Alert. Schedule remediation. | < 24 hours | YES (if > 3 days) |
| MEDIUM | Log. Schedule review. | < 7 days | NO |
| LOW | Log. Backlog. | Next sprint | NO |

---

## 4. ACTIVE INCIDENTS

| Code | Domain | Description | Date | Status |
|------|--------|-------------|------|:---:|
| FF-001 | Lima Growth | RAW_STALE: orders_raw 06-04 (resolved R3.0F) | 06-07 | RESOLVED |
| FF-004 | Lima Growth | FALSE_FRESHNESS: 6 layers STALE_PROPAGATED (resolved R3.0E) | 06-07 | RESOLVED |
| FF-002 | Omniview | FACT_STALE: week_fact 48 days behind | 06-08 | **ACTIVE** |
| FF-007 | Lima Growth | ORPHAN_LAYER: driver_360, eligible_universe | 06-07 | DOCUMENTED |
| FF-007 | Lima Growth | ORPHAN_LAYER: loopcontrol_result_sync | 06-06 | DOCUMENTED |

---

## 5. AUTO-REMEDIATION RULES

| Condition | Auto-Action |
|-----------|-------------|
| FF-001 (RAW_STALE) | Trigger Yango API ingestion retry |
| FF-003 (SNAPSHOT_STALE) | Auto-trigger catch_up_on_startup() |
| FF-005 (WATERFALL_BROKEN) | HALT. Do not auto-remediate. Requires investigation. |
| FF-008 (SERVING_MISSING) | Auto-trigger generate_all_serving_facts() |

---

## FIRMA

```
CT-GOV-043 FAIL FAST REGISTRY
Date: 2026-06-08
Status: CANONICAL
```
