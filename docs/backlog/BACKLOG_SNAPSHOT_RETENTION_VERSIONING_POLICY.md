# BACKLOG — Snapshot Retention & Versioning Policy

**Date:** 2026-06-07
**Phase:** BACKLOG (GOVERNANCE)
**Registry:** LG-INFRA-R1.6

---

## OBJECTIVE

Definir política formal de retención y versionado de snapshots operativos:
- Cuánto tiempo se retienen
- Cómo se versionan
- Cómo se auditan cambios
- Cómo se recuperan versiones anteriores

---

## CURRENT STATE

| Snapshot | Retention | Versioned | Recovery |
|----------|:---------:|:---------:|:--------:|
| driver_state_snapshot | Per-date (indefinido) | NO | Re-run pipeline |
| program_eligibility_daily | Per-date (indefinido) | NO | Re-run pipeline |
| prioritized_opportunity_daily | Per-date (indefinido) | YES (policy_id) | UPSERT |
| assignment_queue | Indefinido (never deleted) | YES (batch_id) | Status transitions |
| driver_list_history | Indefinido (immutable) | YES (run_id) | Read-only |
| serving_fact | Per-date (indefinido) | YES (run_id) | UPSERT |

---

## PROPOSED POLICY

| Rule | Value |
|------|-------|
| Snapshot retention | 90 days online, archive after |
| Version tracking | run_id + policy_id on every row |
| Audit trail | pipeline_run_log + refresh_run_log |
| Recovery | Re-run pipeline for any historical date |
| Data loss protection | Never DELETE, only UPSERT or INSERT new |

---

## IMPLEMENTATION NOTES

- Migration to add `run_id` column to snapshot tables not yet versioned
- Archive job for snapshots > 90 days
- Recovery script for historical date rebuild

---

## STATUS: BACKLOG

No urgency. Current indefinite retention is acceptable for operational scale.

---

## FIRMA

```
BACKLOG REGISTRY ENTRY
Snapshot Retention & Versioning Policy
Registered: 2026-06-07
Phase: LG-INFRA-R1.6
Status: BACKLOG — PENDING
```
