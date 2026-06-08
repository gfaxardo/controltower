# OV2-H.1 — BACKEND PROCESS AUDIT

> **Date:** 2026-06-07 10:00 UTC-5
> **Motor:** Control Foundation / Infrastructure Health
> **Status:** RUNTIME AUDIT COMPLETE

---

## 1. AUDIT METHOD

Executed on local dev machine (Windows) via PowerShell.

---

## 2. FINDINGS — PYTHON/UVICORN PROCESSES

| PID | Process | Command Line | Start Time | CPU (s) | Mem (MB) | Role |
|-----|---------|-------------|-----------|---------|----------|------|
| 5484 | python (uvicorn) | `uvicorn app.main:app --host 0.0.0.0 --port 8000` | 08:27 | *runtime* | *runtime* | **Control Tower backend** |
| 12460 | python (uvicorn) | `uvicorn app.main:app --host 0.0.0.0 --port 9001 --reload` | 07:08 | 4.2 | 25 | **OTHER APP** (not CT) |
| 17484 | python (spawn) | `spawn_main(parent_pid=12460)` | 07:28 | 7.1 | 107.2 | Reload worker for OTHER APP |

---

## 3. PORT ACTIVITY

| Port | PID | Process | State | Owner |
|------|-----|---------|-------|-------|
| **8000** | 5484 | uvicorn | LISTENING | **Control Tower backend** |
| 9001 | 12460 | uvicorn | LISTENING | OTHER APP (not CT) |
| 5173 | 29280 | node (vite) | LISTENING | Frontend dev server |

---

## 4. DUPLICATE WORKERS

| Finding | Status |
|---------|--------|
| Multiple Control Tower backends | **0** — single instance on port 8000 |
| Multiple backends on same port | **0** |
| Orphaned processes | **0** — all started today |
| Other apps on same machine | 1 (port 9001 — different app) |

---

## 5. CONTROL TOWER BACKEND DETAILS

- **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- **Workers:** 1 (default, no `--workers` flag)
- **Reload:** disabled (production-style, no `--reload`)
- **Working directory:** `C:\cursor\controltower\controltower\backend`
- **Blocking bug fixed:** `yego_lima_scheduler.py` missing `Query` import

---

## 6. CONNECTION-HOLDING PROCESSES

DB audit shows Control Tower holding connections via pool:
- Pool: `ThreadedConnectionPool(minconn=1, maxconn=10)`
- Active connections visible as `application_name=control_tower_pool`

---

## 7. VERDICT

**Status:** PASS — Single Control Tower backend. One worker. Port 8000. No duplicates.

**Risk:** Single worker = limited concurrent request capacity. Under heavy load (5+ concurrent shell builds), server rejects new TCP connections.

**Action recommended for OV2-H.2:** Increase uvicorn workers to 2-4 for production.
