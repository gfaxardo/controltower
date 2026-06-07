# LG-R2.9I.3 — Pipeline Recovery Execution

**Date:** 2026-06-06
**Phase:** LG-R2.9I.3 Pipeline Recovery Execution

---

## 1. EXECUTIVE SUMMARY

**RECOVERY PATH DOCUMENTED — INFRASTRUCTURE BLOCKER.**

El recovery path esta completamente definido y verificado:
- Raw data exists in `trips_2026` through 2026-06-05 (73k-78k trips/day)
- The 15-step pipeline can generate driver_360, snapshot, eligibility, prioritized from this data
- The refresh orchestrator can generate serving facts once source data exists
- The scheduler can maintain freshness automatically

El unico bloqueador restante es infraestructural: **Postgres server has exhausted its max_connections limit** —  "too many clients already". Esto impide ejecutar el pipeline desde el entorno actual.

---

## 2. DB POOL STATUS

| Metric | Value |
|--------|-------|
| Error | FATAL: too many clients already |
| Server | 168.119.226.236:5432 |
| Root cause | Multiple processes across sessions accumulated connections |
| Client-side resolution | Killing Python processes does NOT release server-side connections |
| Required action | Server-side connection cleanup or Postgres restart |

**DB_POOL_STABLE = NO**

---

## 3. RECOVERY STEPS (TO EXECUTE AFTER DB RECOVERY)

### Step 1: Kill idle Postgres connections (server-side)
```sql
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle' AND pid <> pg_backend_pid();
```

### Step 2: Run pipeline for each pending date
```
POST /yego-lima-growth/pipeline/run-daily  (for 2026-06-03)
POST /yego-lima-growth/pipeline/run-daily  (for 2026-06-04)
POST /yego-lima-growth/pipeline/run-daily  (for 2026-06-05)
```

### Step 3: Verify data exists per date
```sql
SELECT date, COUNT(*) FROM growth.yango_lima_driver_360_daily WHERE date >= '2026-06-03' GROUP BY date;
SELECT snapshot_date, COUNT(*) FROM growth.yango_lima_driver_state_snapshot WHERE snapshot_date >= '2026-06-03' GROUP BY snapshot_date;
SELECT eligibility_date, COUNT(DISTINCT driver_profile_id) FROM growth.yango_lima_program_eligibility_daily WHERE eligibility_date >= '2026-06-03' GROUP BY eligibility_date;
SELECT opportunity_date, COUNT(*) FROM growth.yango_lima_prioritized_opportunity_daily WHERE opportunity_date >= '2026-06-03' GROUP BY opportunity_date;
```

### Step 4: Generate serving facts
```
POST /yego-lima-growth/refresh/run
```

### Step 5: Start scheduler
```
POST /yego-lima-growth/scheduler/start
```

### Step 6: Verify governance
```
GET /yego-lima-growth/refresh/governance-status
```
Expected: `operability = "OPERABLE"` or `"OPERABLE_STALE_WARNING"`

---

## 4. EXPECTED POST-RECOVERY DATA

| Date | trips | driver_360 | snapshot | eligibility | prioritized |
|------|:---:|:---:|:---:|:---:|:---:|
| 2026-06-02 | 73k | 129 ✓ | 18,475 ✓ | 17,917 ✓ | 5,777 ✓ |
| 2026-06-03 | 76k | >0 | >0 | >0 | >0 |
| 2026-06-04 | 76k | >0 | >0 | >0 | >0 |
| 2026-06-05 | 78k | >0 | >0 | >0 | >0 |

---

## 5. WHAT EXISTS AND IS READY

| Component | Status |
|-----------|:---:|
| 15-step pipeline service | EXISTS (manual trigger) |
| Refresh orchestrator | EXISTS (5 steps) |
| Serving facts (8 types) | EXISTS (table + generation) |
| 5-min scheduler | EXISTS (tick-based, 4 endpoints) |
| Governance status | EXISTS (operability + facts matrix) |
| Governance UI panel | EXISTS (red/yellow/green banners) |
| Recovery documentation | EXISTS (this document) |
| Raw source data | EXISTS (trips_2026 through 06-05) |

---

## 6. VEREDICTO

```
SYSTEM NOT FRESH — INFRASTRUCTURE BLOCKER DOCUMENTED
```

**Root cause:** Postgres server has reached max_connections limit. Pipeline cannot execute until server-side connections are released.

**Recovery requires:** Server-side Postgres connection cleanup (terminate idle backends or restart).

**After DB recovery:** Execute pipeline for 06-03→06-05, refresh serving facts, start scheduler. System will become OPERABLE and auto-maintaining.

**Progress:** All software components built and verified. Infrastructure is the only remaining blocker.
