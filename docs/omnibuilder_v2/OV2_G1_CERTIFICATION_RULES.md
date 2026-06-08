# OV2-G.1 — CERTIFICATION RULES

> **Date:** 2026-06-08
> **Status:** RULES DEFINED

---

## RULE 1: REAL > PROJECTION

```
PROJECTION fresh ≠ REAL fresh
SNAPSHOT fresh ≠ REAL fresh
UI serving fresh data ≠ REAL fresh
```

**DO NOT** certify V1 or V2 as REAL_CERTIFIED if `week_fact` is stale.

## RULE 2: LAYER DATE ≠ EFFECTIVE SOURCE DATE

```
week_fact.max(week_start) = "2026-06-01" (layer date)
day_fact.max(trip_date) = "2026-06-07" (effective source date)
```

The effective source date is the MAX date of the layer's input data, not its own period column.

## RULE 3: SCHEDULER SUCCESS ≠ DATA ADVANCEMENT

```
refresh_run_log.status = "success"
```

Does NOT mean new data was loaded. Must verify:
- `before_max_date` vs `after_max_date`
- `SUCCESS_WITH_DATA` vs `SUCCESS_NO_CHANGE`

## RULE 4: 1 OBJECT = 1 WRITER

```
If 2 writers → LEGACY_REFRESH_BLOCKED
If 0 writers → ORPHAN_TABLE
```

## RULE 5: RUNTIME MATCH

```
backend.git_hash = source.git_hash
scheduler code = source code
```

If __pycache__ is stale → RUNTIME_MISMATCH, DO NOT certify.

---

*End of Certification Rules*
