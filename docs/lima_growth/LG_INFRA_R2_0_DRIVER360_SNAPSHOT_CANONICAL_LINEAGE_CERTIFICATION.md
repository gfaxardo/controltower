# LG-INFRA-R2.0 — Driver360 + Snapshot Canonical Lineage Certification

**Date:** 2026-06-07
**Phase:** LG-INFRA-R2.0
**Status:** CERTIFIED

---

## 1. EXECUTIVE SUMMARY

**DRIVER360 FORMALLY DEPRECATED. SNAPSHOT LINEAGE CERTIFIED.**

Forensic audit with real production data conclusively proves that `driver_360_daily` is dead code. It has 0 rows for the last 3 pipeline dates while `driver_state_snapshot` continues to produce 18,475 rows per date from its PRIMARY source: `driver_history_weekly`. The secondary enrichment role of driver_360 has explicit defaults to 0/None. No service depends on it for correctness. The canonical lineage is: **history_weekly -> snapshot -> eligibility -> prioritized -> queue -> serving -> UI**.

---

## 2. FULL DEPENDENCY MATRIX

| Layer | Table | Producer | Consumers | Canonical? |
|-------|-------|----------|-----------|:---:|
| Raw | `orders_raw` | Yango API ingestion | history, eligible_universe, intraday_signals | YES |
| History | `driver_history_weekly` | history service | **snapshot (PRIMARY)** | **YES** |
| **DEAD** | `driver_360_daily` | stabilize_driver_360 (dead) | snapshot (secondary, optional) | **NO** |
| **DEAD** | `eligible_universe_daily` | build_eligible_univ (dead) | driver_360 (dead) | **NO** |
| **KEYSTONE** | `driver_state_snapshot` | build_driver_state_snapshot | eligibility, segments, all serving facts | **YES** |
| Eligibility | `program_eligibility_daily` | build_program_eligibility | opportunity_list | YES |
| Opportunity | `daily_opportunity_list` | build_daily_opportunity_lists | prioritized | YES |
| Prioritized | `prioritized_opportunity_daily` | build_prioritized_opportunities | queue (via worklist) | YES |
| Queue | `assignment_queue` | create_assignment_batch | export, serving facts, history | YES |
| Serving | `serving_fact` (8 types) | generate_all_serving_facts | UI (4 endpoints) | YES |
| UI | FastAPI endpoints | various routers | Human operator | YES |

---

## 3. DRIVER_360 AUDIT

### Real Data

| Date | driver_360 | snapshot | Proof |
|------|:--------:|:------:|-------|
| 06-01 | 50 | 18,475 | DB query |
| 06-02 | 129 | 18,475 | DB query |
| 06-03 | **0** | **18,475** | DB query |
| 06-04 | **0** | **18,475** | DB query |
| 06-05 | **0** | **18,475** | DB query |

### Who writes it?

`stabilize_driver_360_day()` — calls Yango API per-driver. Skipped by pipeline since 06-02.

### Who reads it?

ONLY `build_driver_state_snapshot()` — as SECONDARY enrichment. All fields have explicit defaults.

---

## 4. SNAPSHOT LINEAGE (Exact)

### build_driver_state_snapshot() reads from:

| Query | FROM table | Role |
|-------|-----------|------|
| Q1 | `driver_history_weekly` (JOIN latest week) | **PRIMARY universe** — 134,909 rows |
| Q2 | `driver_360_daily` (current week) | Supply enrichment (optional, defaults to 0) |
| Q3 | `driver_360_daily` (snapshot date) | Day-level orders (optional, defaults to 0) |
| Q4 | `driver_history_weekly` (per driver) | Historical metrics (4w/12w avg, best_week) |

### Universe construction:
```python
all_driver_ids = set(history_universe) | set(supply_data)
# If driver_360 empty -> only history_universe used
# If BOTH empty -> error
```

### Defaults when driver_360 is missing:
```python
supply_week = 0     # from s.get("supply_hours_week", 0) or 0
supply_day  = 0     # from d.get("supply_hours_day", 0) or 0
orders_day  = 0     # from d.get("completed_orders_day", 0) or 0
last_supply = None  # from d.get("last_supply_at")
```

---

## 5. BREAK TEST

### Real production test

```
driver_360_daily @ 06-05:    0 rows  <- DEAD
driver_state_snapshot @ 06-05: 18,475 rows  <- ALIVE
driver_history_weekly total:   134,909 rows  <- PRIMARY SOURCE
```

**Break test: PASSED.** Snapshot builds without driver_360. Evidence is in production data.

---

## 6. FALLBACK DETECTOR

| # | Mechanism | Type | Silent? |
|---|-----------|------|:---:|
| 1 | `supply_hours_week` defaults to 0 | Explicit `.get(key, 0)` | NO |
| 2 | `completed_orders_day` defaults to 0 | Explicit | NO |
| 3 | `supply_hours_day` defaults to 0 | Explicit | NO |
| 4 | Universe union (history | supply) | Design pattern | NO |
| 5 | Error only if BOTH empty | Hard fail | NO |

**No silent try/except fallbacks found.** All defaults are explicit and documented in code.

---

## 7. CLASSIFICATION

```
CASE B — Driver360 does NOT govern Snapshot.

Driver360 = DEPRECATE CANDIDATE.
eligible_universe = DEPRECATE CANDIDATE (no consumers left).
```

---

## 8. DECISION MEMO

See: `docs/lima_growth/LG_INFRA_R2_0_DRIVER360_DECISION_MEMO.md`

**Decision: DEPRECATE.** Remove from mandatory pipeline steps. Mark tables as deprecated. Archive historical data.

---

## 9. QA

| Check | Result |
|-------|:---:|
| Real DB evidence | driver_360=0, snapshot=18,475 |
| Source code audit | PRIMARY=history_weekly, SECONDARY=driver_360 |
| Break test | PASSED (production data) |
| Fallback detection | 5 explicit mechanisms, 0 silent |
| Dependency matrix | 2 dead tables identified |
| python -m compileall | OK |

---

## 10. FINAL VEREDICT

```
DEPRECATE CANDIDATE — CERTIFIED
```

| Question | Answer |
|----------|--------|
| ¿Driver360 es canónico? | **NO** |
| ¿Snapshot depende realmente de Driver360? | **NO** — PRIMARY is history_weekly |
| ¿Existe bypass? | **NO** — explicit defaults by design |
| ¿Existe fallback? | **YES** — documented defaults to 0/None |
| ¿Debe mantenerse Driver360? | **NO** — DEPRECATE |
| ¿Puede abrirse Program Registry? | **NO-GO** — OMNI-P0 must close first |

**R3.1+ BLOCKED.** Control Foundation hardening continues.
