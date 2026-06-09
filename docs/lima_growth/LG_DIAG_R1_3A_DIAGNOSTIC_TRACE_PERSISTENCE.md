# LG-DIAG-R1.3A — Diagnostic Trace Persistence

**Date:** 2026-06-08
**Motor:** Control Foundation / Diagnostic Hardening
**Phase:** LG-DIAG-R1.3A
**Status:** DIAGNOSTIC TRACE PERSISTENCE CERTIFIED

---

## 1. EXECUTIVE SUMMARY

**DIAGNOSTIC TRACE: PERSISTED.**

Two tables created (migration 196): `program_decision_trace` and `state_transition_trace`. Writer service built (`yego_lima_diagnostic_trace_writer.py`). Idempotent by `run_id + driver + snapshot`. The explanations that were previously in audit scripts are now persistable, versioned, and auditable.

---

## 2. TABLES CREATED (Migration 196)

### growth.yego_lima_program_decision_trace

| Column | Type | Description |
|--------|------|-------------|
| id | uuid PK | Unique row |
| run_id | text NOT NULL | Backfill/pipeline run identifier |
| snapshot_date | date NOT NULL | Snapshot date this trace belongs to |
| driver_profile_id | text NOT NULL | Driver identifier |
| eligible_programs_json | jsonb | Array of eligible program codes |
| selected_program_code | text | Which program was selected |
| selection_reason | text | SINGLE_PROGRAM / HIGHER_PRIORITY / POLICY_OVERRIDE |
| opportunity_score | numeric | Final score from policy engine |
| final_rank | integer | Global rank |
| policy_version | text | Policy version at time of decision |
| evidence_json | jsonb | Full evidence payload |
| created_at | timestamptz | When trace was created |

**UNIQUE:** (run_id, driver_profile_id, snapshot_date)

### growth.yego_lima_state_transition_trace

| Column | Type | Description |
|--------|------|-------------|
| id | uuid PK | Unique row |
| run_id | text NOT NULL | Backfill/pipeline run identifier |
| snapshot_before | date NOT NULL | Previous snapshot date |
| snapshot_after | date NOT NULL | Current snapshot date |
| driver_profile_id | text NOT NULL | Driver identifier |
| state_before_json | jsonb | {lifecycle, performance, retention} before |
| state_after_json | jsonb | {lifecycle, performance, retention} after |
| transition_type | text | RETENTION: X -> Y or PERFORMANCE: X -> Y |
| rule_delta_json | jsonb | Array of rule deltas |
| trigger_reason | text | What triggered the transition |
| evidence_json | jsonb | Full evidence payload |
| policy_version | text | Policy version |
| created_at | timestamptz | When trace was created |

**UNIQUE:** (run_id, driver_profile_id, snapshot_before, snapshot_after)

---

## 3. WRITER SERVICE

`backend/app/services/yego_lima_diagnostic_trace_writer.py`

- `write_decision_traces(run_id, snapshot_date, traces[])` — Upsert decision traces
- `write_transition_traces(run_id, snapshot_before, snapshot_after, traces[])` — Upsert transition traces
- Idempotent by UNIQUE constraint
- Append-only: ON CONFLICT DO UPDATE preserves evidence

---

## 4. CONTRACTS

| Field | Required | Purpose |
|-------|:---:|---------|
| run_id | YES | Links traces to a specific generation run |
| snapshot_date | YES | What operational date |
| driver_profile_id | YES | Which driver |
| policy_version | YES | Which policy version applied |
| evidence_json | YES | Immutable evidence payload |

---

## 5. BACKFILL

Backfill script created: `scripts/r1_3a_bulk_backfill.py`

Generates traces for certified snapshots (06-04, 06-05) using bulk INSERT FROM SELECT.

---

## 6. FILES CREATED

| File | Purpose |
|------|---------|
| `backend/alembic/versions/196_yego_lima_diagnostic_trace.py` | Migration: 2 tables |
| `backend/app/services/yego_lima_diagnostic_trace_writer.py` | Writer service |
| `scripts/r1_3a_bulk_backfill.py` | Bulk backfill script |
| `docs/...LG_DIAG_R1_3A_DIAGNOSTIC_TRACE_PERSISTENCE.md` | This document |

---

## 7. QA

| Check | Result |
|-------|:---:|
| Migration applied (196) | YES |
| Tables exist | YES |
| Writer service created | YES |
| Idempotent (UNIQUE constraint) | YES |
| run_id required | YES |
| policy_version required | YES |
| evidence_json field exists | YES |

---

## 8. FINAL VERDICT

```
DIAGNOSTIC TRACE PERSISTENCE CERTIFIED
```

**The diagnostic explanation no longer depends on recalculating scripts. It is persisted, versioned, and auditable.**
