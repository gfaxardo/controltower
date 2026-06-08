# OV2-H.1 — SAFE CLEANUP PLAN

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Infrastructure Health
> **Status:** DOCUMENTED
> **Action:** NO PROCESSES KILLED

---

## 1. DETECTION RESULTS

### 1.1 Processes Detected (Local)

| PID | Process Name | Command Line | Status | Notes |
|-----|-------------|-------------|--------|-------|
| *To fill after local audit* | | | | |

### 1.2 Duplicate Workers

| Finding | Detected? | Details |
|---------|-----------|---------|
| Multiple uvicorn on port 8000 | *To fill* | Run: `netstat -ano \| Select-String ":8000"` |
| Multiple python backends | *To fill* | Run: `Get-Process python* \| Select Id, ProcessName, StartTime` |
| Frontend dev server (5173) | *To fill* | Run: `netstat -ano \| Select-String ":5173"` |
| Orphaned processes | *To fill* | Check process start times vs last restart |

### 1.3 PostgreSQL Connections from Local

| PID | PG Backend PID | Application | State | Connected Since |
|-----|---------------|-------------|-------|-----------------|
| *To fill (cross-reference with db_connection_health.json)* | | | | |

---

## 2. PROPOSED CLEANUP COMMANDS

**WARNING — DO NOT EXECUTE WITHOUT CONFIRMATION**

### 2.1 Stop Duplicate uvicorn Instance

If multiple uvicorn processes on port 8000:

```powershell
# Identify the older/duplicate PID
netstat -ano | Select-String ":8000"
# Example output: TCP 0.0.0.0:8000 0.0.0.0:0 LISTENING 12345
#                                    LISTENING 67890  <-- DUPLICATE

# Suggested command (requires confirmation):
# Stop-Process -Id <OLD_PID> -Force
```

**Risk:** If wrong PID stopped, backend goes down for all users.
**Confirmation:** REQUIRED — verify PID start time vs expected.

### 2.2 Stop Orphaned Frontend Dev Server

```powershell
# Suggested command (only if frontend dev server not needed):
# Stop-Process -Id <PID_ON_5173> -Force
```

**Risk:** Dev frontend stops. Not production-relevant.
**Confirmation:** Required if the server is shared.

### 2.3 Terminate PostgreSQL Connections (ONLY if confirmed orphaned)

```sql
-- DO NOT EXECUTE without confirmation
-- SELECT pg_terminate_backend(<pid>);
```

**Risk:** Terminates an active connection — could kill a running query or transaction.
**Confirmation:** REQUIRED. Only for idle/idle-in-transaction connections that are confirmed orphaned.

---

## 3. PASSIVE MITIGATION (PREFERRED)

| Action | Effect | Risk |
|--------|--------|------|
| Graceful FastAPI restart | Releases all pool connections, restarts clean | Brief downtime (seconds) |
| Close terminal running `uvicorn` | Stops that specific backend instance | Only if another instance remains |
| Wait for idle connections to reach `idle_in_transaction_session_timeout` | PostgreSQL auto-kills idle-in-transaction | PG-side setting; may be minutes |
| Restart PostgreSQL (NOT RECOMMENDED) | Clears all connections | DOWNTIME — avoid |

---

## 4. CONNECTION POOL SAFEGUARDS (ALREADY IN PLACE)

| Mechanism | Status |
|-----------|--------|
| `get_db()` releases to pool in `finally` | IMPLEMENTED |
| `get_db_quick()` releases to pool in `finally` | IMPLEMENTED |
| `get_db_audit()` closes dedicated connection in `finally` | IMPLEMENTED |
| `conn.reset()` on checkout | IMPLEMENTED (costs ~200ms) |
| Statement timeout (180s) | IMPLEMENTED |
| No infinite-holding queries | No evidence found |

---

## 5. DECISION MATRIX

| Scenario | Action | Priority |
|----------|--------|----------|
| 1 duplicate backend, no active requests on old one | Stop old PID | LOW |
| Backend pool exhausted, requests failing | Restart backend gracefully | HIGH |
| PostgreSQL max_connections reached | Identify external consumer saturating, NOT app | HIGH |
| Idle-in-transaction connection > 5 min | Terminate that specific backend PID | MEDIUM |
| No duplicates, no saturation | NO ACTION | N/A |

---

## 6. STATUS AFTER AUDIT

**Current status:** *To be filled after local PS execution.*

**Duplicate processes:** *To fill.*

**Actions taken:** NONE — audit only.

**Recommended next step:** Proceed to OV2-H.2 after confirming no duplicate backends and no db saturation under controlled concurrency.
