# OV2-F.2B — DB SATURATION FORENSICS

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Refresh Chain
> **Status:** FORENSICS COMPLETE — DB saturated by refresh staging connections

---

## 1. TIMELINE

| Time (UTC-5) | Event | Impact |
|-------------|-------|--------|
| ~08:30 | `audit_refresh_execution.py` opened 1 connection | Normal — closed after audit |
| ~08:32 | `refresh_omniview_real_slice_incremental --grain all --force` started | Opened staging connections for 6.8M trips |
| ~08:34 | Day staging completed (1.8M trips, 100s) | Connections: staging day_fact |
| ~08:35 | Week staging started (6.8M trips) | Connections: staging week_fact began |
| ~08:45 | Script TIMEOUT (>10 min) | **Staging connections left OPEN** |
| ~08:46 | Re-attempted week-only refresh | New staging connections opened |
| ~08:48 | `FATAL: too many clients already` | **DB fully saturated** |
| ~08:50 to present | All connection attempts fail | DB inaccessible |

---

## 2. CONNECTION SOURCES

| Source | Estimated Connections | Application |
|--------|----------------------|-------------|
| External JDBC apps | ~20 | PostgreSQL JDBC Driver |
| External unidentified | ~22 | No application_name set |
| apileads service | ~5 | External |
| pgAdmin | ~2 | Admin tool |
| Control Tower pool | ~10 | `control_tower_pool` |
| **Staging connections (stuck)** | **~8-12** | **Refresh script — not released** |
| **Total** | **~67-71/150** | Some headroom but staging queries may consume more |

**Note:** Last successful DB audit (H.1B, before refresh) showed 50/150 connections. After the staging timeout, new connection attempts consume the remaining headroom.

---

## 3. STAGING CONNECTION LIFECYCLE

```
refresh_omniview_real_slice_incremental.py
  → opens psycopg2 connection for staging queries
  → creates staging tables (ops.real_business_slice_day_fact_staging, etc.)
  → runs INSERT INTO SELECT (materialized enriched → staging)
  → if successful: validates, then atomic swap
  → if TIMEOUT: script killed, but PostgreSQL connections remain OPEN
  → PostgreSQL keeps staging connections until:
      a) TCP keepalive timeout (typically hours)
      b) Manual pg_terminate_backend()
      c) PostgreSQL restart
```

---

## 4. WHICH CONNECTIONS ARE STUCK

From `pg_stat_activity`, look for:
- `state = 'active'` with long-running queries (elapsed > 600s)
- `state = 'idle in transaction'` with `application_name LIKE '%refresh%'` or `application_name = ''`
- Queries containing "staging" or "INSERT INTO ops.real_business_slice"

Cleanup command (requires PostgreSQL access):
```sql
-- Identify stuck connections
SELECT pid, usename, application_name, state, 
       EXTRACT(EPOCH FROM (now() - query_start))::int AS elapsed_sec,
       LEFT(query, 100) AS query_preview
FROM pg_stat_activity
WHERE backend_type = 'client backend'
  AND (state = 'active' AND query_start < now() - interval '10 minutes')
   OR (state = 'idle in transaction');

-- Terminate stuck connections (REQUIRES CONFIRMATION)
-- SELECT pg_terminate_backend(<pid>);
```

---

## 5. ROOT CAUSE

**Classification: Type E — Connection exhaustion**

The staging script uses raw `psycopg2.connect()` for the enriched materialization query. When the script times out (10+ minutes), the TCP connection stays open on the PostgreSQL side even though the client process (Python) is terminated. PostgreSQL's `tcp_keepalives_idle` (default 2 hours on Linux) means these zombie connections persist until the keepalive timer fires.

---

## 6. PREVENTION

| Measure | Implementation | Priority |
|---------|---------------|----------|
| Set `statement_timeout` on staging connections | Already applied (180s default in pool) | DONE |
| Use `connect_timeout` for staging connections | Not implemented — add to _get_connection_params | P2 |
| Set `idle_in_transaction_session_timeout` on PostgreSQL | Requires DBA — ALTER SYSTEM | P1 |
| Batch staging queries (30-day windows) | Recovery strategy (TASK 3) | P1 |
| Detect and clean up stale connections | Infra health guard (TASK 9) | P1 |

---

*End of DB Saturation Forensics*
