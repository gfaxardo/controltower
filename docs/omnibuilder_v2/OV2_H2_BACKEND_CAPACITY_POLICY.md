# OV2-H.2 — BACKEND CAPACITY POLICY

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Backend Capacity
> **Status:** POLICY DOCUMENTED — NOT YET APPLIED (OV2-H.2 scope)

---

## 1. CURRENT STATE

| Parameter | Current | Risk |
|-----------|---------|------|
| uvicorn workers | **1** (default) | Single worker blocks all requests |
| Pool maxconn | **10** | Shared 1 worker; heavy queries exhaust pool |
| Pool minconn | **1** | Cold start penalty ~200ms |
| Pool getconn timeout | **None** | Blocks indefinitely if pool full |
| `allow_runtime` default | `False` | Safe — no accidental runtime builds |

## 2. RECOMMENDED VALUES

| Parameter | Current | Recommended | Rationale |
|-----------|---------|-------------|-----------|
| uvicorn `--workers` | 1 | **2-4** | Prevents single request from blocking all others |
| Pool maxconn | 10 | **workers × 5** (10-20) | Each worker may hold multiple concurrent DB connections |
| Pool minconn | 1 | **workers** (2-4) | Eliminates cold start penalty per worker |
| Pool getconn timeout | None | **10s** | Fails fast instead of hanging |
| `allow_runtime` | `False` | **KEEP** `False` | Runtime shell/matrix crash under concurrency |

## 3. PRODUCTION START COMMAND

```bash
# Current (dev)
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Recommended (production)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## 4. POOL CONFIGURATION (Production)

```python
# backend/app/db/connection.py
connection_pool = psycopg2.pool.ThreadedConnectionPool(
    minconn=4,      # 1 per worker
    maxconn=20,     # 5 per worker
    **params
)
```

**Note:** These changes require verifying PostgreSQL `max_connections` headroom (currently 150, 50 in use — 100 available for scaling).

## 5. POOL GETCONN TIMEOUT (Backlog)

Currently `getconn()` blocks indefinitely. Recommended:

```python
# connection_pool.getconn() does NOT support timeout in psycopg2.pool
# Mitigation: wrapper with threading timeout
def _getconn_with_timeout(pool, timeout=10):
    conn = [None]
    def _acquire():
        conn[0] = pool.getconn()
    t = threading.Thread(target=_acquire, daemon=True)
    t.start()
    t.join(timeout)
    if conn[0] is None:
        raise PoolTimeoutError(f"Could not acquire connection within {timeout}s")
    return conn[0]
```

**Backlog for OV2-H.3.**

## 6. SERVING PATH ENFORCEMENT MATRIX

| Endpoint | Default Behavior | Runtime Allowed? |
|----------|-----------------|-----------------|
| `/shell` | Snapshot → MISSING if absent | Only with `allow_runtime=true` (debug) |
| `/matrix` single-day | Snapshot → MISSING if absent | Only with `allow_runtime=true` (debug) |
| `/matrix` multi-day | Runtime (fast ~750ms) | Yes — explicit range query |
| `/operating-date` | Runtime (fast ~2s remote, <500ms local) | Always — single row MAX() |

## 7. CAPACITY TEST RESULTS (H.1B)

| Endpoint | c=1 | c=3 | c=5 | Note |
|----------|-----|-----|-----|------|
| operating-date | PASS | PASS | PASS | Consistent ~2050ms |
| matrix runtime | PASS | PASS | **FAIL** (conn refused) | c=5 exhausts worker+pool |
| shell runtime | **FAIL** | **FAIL** | **FAIL** | Too heavy for 1 worker |

## 8. CRITICAL RULE

**RUNTIME SHELL IS NOT PRODUCTION-SAFE WITH 1 WORKER.**

Always serve shell from snapshots. Runtime path is debug-only.

## 9. ACTION LOG

| # | Action | Applied? | Status |
|---|--------|----------|--------|
| 1 | Workers 2-4 | NO | Backlog H.3 |
| 2 | Pool maxconn 20 | NO | Backlog H.3 |
| 3 | Pool getconn timeout | NO | Backlog H.3 |
| 4 | allow_runtime default False | YES | Already enforced |
| 5 | Shell snapshot-first | YES | Already enforced |
| 6 | Matrix snapshot-first (single-day) | YES | Already enforced |
| 7 | backend-identity endpoint | YES | Created in H.2 |

## 10. DEPENDENCIES

Before increasing maxconn:
1. Verify PostgreSQL `max_connections` headroom (requires DB audit re-run)
2. Confirm no other services are saturating PG (47/50 current connections are external)
3. Coordinate with DBA if external connections are controlled

---

*Policy documented. Implementation deferred to OV2-H.3.*
