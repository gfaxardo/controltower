# OV2-H.1 — POOL CONFIGURATION AUDIT

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Infrastructure Health
> **Status:** AUDIT COMPLETE

---

## 1. POOL LOCATION

**File:** `backend/app/db/connection.py:105-107`

```python
connection_pool = psycopg2.pool.ThreadedConnectionPool(
    minconn=1, maxconn=10, **params
)
```

## 2. POOL PARAMETERS

| Parameter | Value | Assessment |
|-----------|-------|------------|
| Pool type | `ThreadedConnectionPool` | OK — thread-safe for FastAPI thread pool |
| minconn | 1 | OK for dev/single-instance. For production with multiple workers, 2-4 min would reduce cold-start latency |
| maxconn | **10** | **CRITICAL** — shared across ALL endpoints, all workers, all background jobs. See analysis below |
| statement_timeout (per conn) | 180000ms (3 min) | OK — prevents runaway queries |

## 3. maxconn=10 ANALYSIS

### What shares this pool?

| Consumer | Type | 
|----------|------|
| All FastAPI endpoints via `get_db()` | Request-scoped |
| All FastAPI endpoints via `get_db_quick()` | Request-scoped, same pool |
| All service-layer calls | Request-scoped |
| Refresh scripts (`refresh_omniview_v2_snapshots.py`) | Script-scoped |
| Background jobs (APScheduler) | Scheduled |
| All `_query()` / `_exec()` / `_query_one()` helpers in repositories | Indirect via routes |

### Risk: If 10 uvicorn workers each take 1 persistent connection → pool exhausted

- Default FastAPI can spin up N workers (often = CPU count)
- Each worker may hold 1-2 pool connections concurrently
- With 5 uvicorn workers + 2 parallel requests each = 10 connections → pool FULL
- Any additional request → `PoolError: connection pool exhausted`

### PostgreSQL side

- `max_connections` on PostgreSQL (168.119.226.236) is likely 100 (default)
- If multiple services/tools/users connect to same DB, they compete for PG connections
- The "FATAL: sorry, too many clients already" error confirms external connection saturation

## 4. CONNECTION RESET BEHAVIOR

`get_db()` line 127: `conn.reset()` is called on every connection checkout.
- **Impact:** ~200ms overhead per connection checkout (documented in CX5 report)
- **Root cause:** This is PostgreSQL discarding session state
- **Mitigation possible?** Only if we move to `psycopg2.pool.SimpleConnectionPool` (no thread safety) or configure `reset=False` (dangerous — could leak session state between requests)

## 5. get_db() RELEASE BEHAVIOR

`get_db()` context manager (lines 113-158) guarantees release:
```python
finally:
    if conn:
        unregister_active_pg_connection(conn)
        connection_pool.putconn(conn)
```

**Verdict: CORRECT** — connection ALWAYS returned to pool, even on exception.

## 6. get_db_quick() RELEASE BEHAVIOR

`get_db_quick()` (lines 245-279) also guarantees release via `finally`:
```python
finally:
    if conn:
        unregister_active_pg_connection(conn)
        connection_pool.putconn(conn)
```

**Verdict: CORRECT** — same pattern as `get_db()`.

## 7. get_db_audit() — DEDICATED CONNECTION (outside pool)

`get_db_audit()` (lines 174-194) creates a **new, fresh connection** outside the pool:
```python
def _get_connection_with_timeout(timeout_ms: int):
    params = _get_connection_params()
    params["options"] = f"-c statement_timeout={timeout_ms}"
    return psycopg2.connect(**params)
```

It properly closes in `finally`:
```python
finally:
    if conn:
        conn.close()
```

**Verdict: CORRECT** — but each audit script that uses `get_db_audit()` consumes 1 PostgreSQL connection from the shared `max_connections` pool on the server. If many audit scripts run simultaneously, they compete with application connections.

## 8. get_db_drill() — DEDICATED CONNECTION

`get_db_drill()` (lines 197-243) also creates a new connection. Same pattern as audit. Closes in `finally`.

**Verdict: CORRECT** but shares PostgreSQL connection limit with everything else.

## 9. POTENTIAL LEAK VECTORS

### 9.1 Connection Pool Exhaustion (NOT a leak, but saturation)
- If 10+ concurrent requests hit the pool, they will block waiting for `getconn()`
- The pool has no timeout on `getconn()` — it blocks indefinitely
- This manifests as API timeouts (not "too many clients" but "pool exhausted")

### 9.2 Dedicated Connections Outside Pool
- `get_db_audit()` and `get_db_drill()` open connections directly via `psycopg2.connect()`
- If these fail to close (bug, exception in specific code path), connections leak
- Current implementation closes in `finally` → safe

### 9.3 Scripts That Open Connections and Don't Close
Audited in TASK 5 — see `OV2_H1_CONNECTION_LEAK_AUDIT.md`

## 10. CHANGES TO POOL CONFIGURATION

**NEITHER RECOMMENDED NOR APPLIED** (per rules: NO cambiar max_connections, NO tocar infraestructura DB global)

| Proposed change | Risk | Recommendation |
|-----------------|------|----------------|
| Increase maxconn from 10 → 20 | Could exhaust PostgreSQL `max_connections` if other services also connect | **NOT APPLIED** — requires PostgreSQL-side verification first |
| Add pool connection timeout | Low risk — prevents indefinite blocking | BACKLOG for OV2-H.2 |
| Add `application_name` to pool connections | Zero risk — helps tracing | **APPLIED** (see TASK 7) |

## 11. SUMMARY

| Check | Status |
|-------|--------|
| Pool type correct for workload | OK |
| Release guaranteed in `get_db()` | OK |
| Release guaranteed in `get_db_quick()` | OK |
| Release guaranteed in `get_db_audit()` | OK |
| Release guaranteed in `get_db_drill()` | OK |
| maxconn appropriate for current load | AT RISK (10 connections shared) |
| Connection reset overhead acceptable | OK (documented floor) |
| No pool connection timeout | WARNING |
| No application_name set on pool connections | FIXED (TASK 7) |
| No minconn warmup | MINOR (1 cold connection on first request) |

## 12. RISK ASSESSMENT

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| Pool exhaustion under concurrent load | HIGH | MEDIUM | maxconn=10 shared; increase in OV2-H.2 after PostgreSQL-side audit |
| PostgreSQL "too many clients" | CRITICAL | CONFIRMED | Root cause is external connection saturation; pool cannot mitigate this alone |
| `get_db_audit` parallel runs exhaust PG | LOW | LOW | Audit scripts run sequentially/ad-hoc |
| Unclosed cursors in scripts | LOW | LOW | 2 scripts have minor cursor hygiene issues (fixed in TASK 7) |
