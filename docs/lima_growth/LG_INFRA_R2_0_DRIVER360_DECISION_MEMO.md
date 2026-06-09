# LG-INFRA-R2.0 — Driver360 Decision Memo

**Date:** 2026-06-07
**Phase:** LG-INFRA-R2.0
**Status:** DECISION RENDERED

---

## QUESTION

¿Es driver_360 canónico o debe deprecarse?

---

## EVIDENCE

### 1. Real Data

| Date | driver_360 rows | snapshot rows |
|------|:--------------:|:------------:|
| 2026-06-01 | 50 | 18,475 |
| 2026-06-02 | 129 | 18,475 |
| **2026-06-03** | **0** | **18,475** |
| **2026-06-04** | **0** | **18,475** |
| **2026-06-05** | **0** | **18,475** |

**Finding:** driver_360 has been dead since 2026-06-03. Snapshot continues to produce 18,475 rows per date regardless.

### 2. Source Code (R1.8 forensic audit)

File: `yego_lima_driver_state_service.py`, function `build_driver_state_snapshot()`

```python
# Line 80: PRIMARY UNIVERSE
FROM growth.yango_lima_driver_history_weekly hw

# Line 98: SECONDARY enrichment
FROM growth.yango_lima_driver_360_daily

# Line 126: Universe = UNION of both
all_driver_ids = set(history_universe.keys()) | set(supply_data.keys())

# Lines 167-179: Explicit defaults when 360 is empty
supply_week = float(s.get("supply_hours_week", 0) or 0)     # -> 0
supply_day  = float(d.get("supply_hours_day", 0) or 0)       # -> 0
orders_day  = int(d.get("completed_orders_day", 0) or 0)     # -> 0
```

### 3. Who writes driver_360?

`stabilize_driver_360_day()` in `yego_lima_driver_360_service.py`

This function:
- Reads from `eligible_universe_daily` (which also has 0 rows for 06-03/04)
- Calls Yango API per-driver for supply_hours
- Is marked as "async_in_event_loop" skip in pipeline step 3
- Has NOT successfully run since 2026-06-02

### 4. Who reads driver_360?

ONLY `build_driver_state_snapshot()` — and only as SECONDARY enrichment.

No other service reads from driver_360_daily:
- `build_program_eligibility()` reads from `driver_state_snapshot`, not driver_360
- `build_daily_opportunity_lists()` reads from `program_eligibility`, not driver_360
- `build_prioritized_opportunities()` reads from `daily_opportunity_list`, not driver_360
- `create_assignment_batch()` reads from `prioritized`, not driver_360
- All serving facts read from snapshot/eligibility/prioritized/queue, not driver_360

### 5. Impact of removing driver_360

| What breaks? | Impact |
|-------------|--------|
| `supply_hours_week` in snapshot | Already 0 (because driver_360 is 0) |
| `supply_hours_day` in snapshot | Already 0 |
| `completed_orders_day` in snapshot | Already 0 |
| `last_supply_at` in snapshot | Already NULL |
| Lifecycle classification | Slightly less accurate (minor factor) |
| Everything downstream | NO IMPACT — snapshot builds from history_weekly |

---

## CLASSIFICATION

```
CASE B — Driver360 does NOT govern Snapshot.

Driver360 is SECONDARY ENRICHMENT only.
Snapshot PRIMARY source is driver_history_weekly.
Driver360 has been dead since 2026-06-02.
System operates correctly without it.
```

---

## DECISION

```
DEPRECATE CANDIDATE
```

**Justification:**
1. 0 rows for 3+ consecutive pipeline dates
2. Only consumer uses it as optional enrichment with explicit defaults
3. Removal has zero impact on downstream layers
4. Contains supply_hours data that is already 0
5. Pipeline already skips it successfully
6. No service depends on it for correctness

---

## ACTION ITEMS

| # | Action | Priority |
|---|--------|:---:|
| 1 | Remove `stabilize_driver_360_day` from mandatory pipeline steps | HIGH |
| 2 | Mark `growth.yango_lima_driver_360_daily` as DEPRECATED in schema | HIGH |
| 3 | Mark `growth.yango_lima_eligible_universe_daily` as DEPRECATED (no consumers) | HIGH |
| 4 | Update `LG_SOURCE_LINEAGE_CANONICAL_MAP.md` to reflect deprecation | MEDIUM |
| 5 | Archive historical driver_360 data (06-01, 06-02) | LOW |

---

## ANSWER TO KEY QUESTIONS

| Question | Answer |
|----------|--------|
| ¿Driver360 es canónico? | **NO** |
| ¿Snapshot depende realmente de Driver360? | **NO** — PRIMARY source is history_weekly |
| ¿Existe bypass? | **NO** — explicit defaults by design |
| ¿Existe fallback? | **YES** — documented defaults to 0/None |
| ¿Debe mantenerse Driver360? | **NO** — DEPRECATE |
| ¿Puede abrirse Program Registry? | **NO-GO** — OMNI-P0 must close first |

---

## FIRMA

```
DRIVER360 DECISION MEMO
LG-INFRA-R2.0 Driver360 + Snapshot Canonical Lineage Certification
Date: 2026-06-07
Decision: DEPRECATE CANDIDATE
Status: FINAL
```
