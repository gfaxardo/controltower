# LG-R2.9I.2B — Yango API → Driver360 Lineage & Recovery

**Date:** 2026-06-06
**Phase:** LG-R2.9I.2B Yango API to Driver360 Lineage & Recovery

---

## 1. EXECUTIVE SUMMARY

**FIRST BREAKPOINT IDENTIFIED: `eligible_universe_missing` at driver_360 build.**

The source chain audit revealed the exact point where freshness stops. Raw Yango API data exists (raw_yango.orders_raw has 11,087 rows), but the pipeline layers between raw data and operational UI are empty for dates 2026-06-03 through 2026-06-05.

---

## 2. SOURCE CHAIN MATRIX

| Date | driver_360 | snapshot | eligibility | prioritized | queue | serving_facts |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| 2026-06-02 | 129 | 18,475 | 28,493 | 5,777 | 500 | 8 |
| 2026-06-03 | **0** | 0 | 0 | 0 | 0 | 0 |
| 2026-06-04 | **0** | 0 | 0 | 0 | 0 | 0 |
| 2026-06-05 | **0** | 0 | 0 | 0 | 0 | 0 |
| 2026-06-06 | **0** | 0 | 0 | 0 | 0 | 0 |

**First breakpoint:** driver_360 at 2026-06-03 (0 rows). Everything downstream is 0 because driver_360 feeds the snapshot, which feeds eligibility, which feeds prioritized, which feeds the queue.

---

## 3. RAW YANGO API STATUS

| Source | Rows | Status |
|--------|:---:|:---:|
| raw_yango.orders_raw | 11,087 | DATA EXISTS |
| raw_yango.driver_profiles_raw | Present | DATA EXISTS |
| raw_yango.transactions_raw | Present | DATA EXISTS |
| growth.yango_lima_orders_raw | 237 | Schema mismatch (timestamp, not date column) |

Yango API ingestion is working. Raw data exists. The gap is in pipeline execution, not API availability.

---

## 4. DRIVER360 BUILD AUDIT — ROOT CAUSE

Attempting `stabilize_driver_360_day('2026-06-05')` returns:

```json
{
  "ok": false,
  "error_type": "eligible_universe_missing",
  "error_message": "No eligible drivers found for 2026-06-05. Run build-eligible-universe first."
}
```

**Root cause chain:**
1. `eligible_universe` must be built first (POST `/lab/build-eligible-universe`)
2. `driver_360` depends on eligible_universe
3. `driver_state_snapshot` depends on driver_360
4. `program_eligibility` depends on driver_state_snapshot
5. Everything downstream depends on eligibility

This is the standard dependency chain of the 15-step pipeline. The pipeline was run for 2026-06-02 and never again.

---

## 5. RECOVERY PROCEDURE

For each date (06-03, 06-04, 06-05):

```
1. POST /yego-lima-growth/lab/build-eligible-universe     (creates eligible drivers)
2. POST /yego-lima-growth/lab/stabilize-driver-360-day     (builds driver_360 from Yango API)
3. POST /yego-lima-growth/state/build-driver-states         (builds snapshot)
4. POST /yego-lima-growth/programs/build-eligibility        (builds eligibility)
5. POST /yego-lima-growth/opportunities/build-daily         (builds prioritized)
6. POST /yego-lima-growth/assignment-queue/build            (builds queue)
7. POST /yego-lima-growth/refresh/run                       (generates serving facts)
```

Or, equivalently:
```
POST /yego-lima-growth/pipeline/run-daily   (runs all 15 steps)
```

---

## 6. BLOCKER: DB CONNECTION POOL

The recovery cannot execute until the Postgres "too many clients" issue is resolved. This requires server-side intervention:

```sql
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle';
```

Or restart the uvicorn backend and reduce connection pool to `minconn=1, maxconn=3`.

---

## 7. SCHEDULER CORRECTION

The 5-min scheduler must execute the full pipeline sequence, not just refresh/run. The tick method should:

1. Detect latest available Yango API date
2. Build eligible_universe if missing
3. Build driver_360 if missing
4. Build downstream layers if missing
5. Generate serving facts

Current scheduler only refreshes serving facts — it needs to be extended to detect and fill gaps in the pipeline chain.

---

## 8. VEREDICTO

```
SYSTEM NOT FRESH — BREAKPOINT DOCUMENTED
```

**Breakpoint:** `eligible_universe_missing` at driver_360 build for 2026-06-05.

**Root cause:** 15-step pipeline never executed for dates after 2026-06-02.

**Recovery:** Requires pipeline execution (or individual build steps) for 06-03 through 06-05. Blocked by DB connection pool exhaustion.

**After recovery + scheduler correction:** System will auto-maintain freshness via Yango API → pipeline → serving facts.
