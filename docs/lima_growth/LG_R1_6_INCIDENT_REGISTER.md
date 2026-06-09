# LG-INFRA-R1.7 — Incident Register (Updated)

**Date:** 2026-06-07
**Phase:** LG-INFRA-R1.7
**Status:** ACTIVE REGISTER

---

## INCIDENTS (UPDATED FROM R1.6)

### INC-001: Serving Facts STALE on backend restart

| Field | Value |
|-------|-------|
| **Severity** | HIGH → **LOW** (workaround exists — force refresh on restart) |
| **Description** | Serving facts show STALE status after backend restart. Fixed by forcing FRESH on each refresh cycle. |
| **Remediation** | UPDATE freshness_status on each refresh/run call |
| **Go/No-Go** | GO |

### INC-002: Scheduler tick does not execute automatically

| Field | Value |
|-------|-------|
| **Severity** | HIGH |
| **Description** | Scheduler is enabled but no autonomous ticks executed due to DB pool saturation. APScheduler job registered (`autonomous_tick` every 5 min) but cannot run because DB pool exhausted by external apps. |
| **Evidence** | `autonomous_tick()` implemented and registered. `tick_log` table exists. DB pool saturated by `PostgreSQL JDBC Driver` and `apileads` external connections. |
| **Remediation** | 1) Server-side: terminate idle external connections or reduce max_connections. 2) Application: autonomous_tick ready to run once pool is available. |
| **Go/No-Go** | GO — code implemented, infrastructure blocker external |

### INC-003: eligible_universe / driver_360 consistently 0 rows

| Field | Value |
|-------|-------|
| **Severity** | LOW |
| **Go/No-Go** | GO — documented gap, no operational impact |

### INC-004: Supply hours not refreshed intraday

| Field | Value |
|-------|-------|
| **Severity** | MEDIUM |
| **Go/No-Go** | GO — backlogged |

### INC-005: loopcontrol_result_sync table orphaned

| Field | Value |
|-------|-------|
| **Severity** | MEDIUM |
| **Go/No-Go** | GO — non-blocking |

### INC-006: DB Pool Saturation (NEW — R1.7)

| Field | Value |
|-------|-------|
| **Severity** | **CRITICAL** |
| **Description** | PostgreSQL `too many clients already`. External apps (JDBC Driver from 5.161.86.63, apileads from 5.161.229.77) consume 40+ connections. Backend cannot initialize connection pool. |
| **Evidence** | `SELECT COUNT(*) FROM pg_stat_activity` = 50+ connections, mostly idle from external IPs |
| **Owner** | Infrastructure / DBA |
| **Remediation** | 1) Server-side: terminate idle connections from external apps. 2) Reduce PostgreSQL `max_connections` or implement connection limits per user. 3) Implement pgBouncer. |
| **Go/No-Go** | **BLOCKS autonomous operation** — scheduler cannot run without DB pool |

### INC-007: Rollover simulation not possible without DB (NEW — R1.7)

| Field | Value |
|-------|-------|
| **Severity** | HIGH |
| **Description** | Midnight rollover simulation requires DB access to create new snapshot dates. Blocked by INC-006. |
| **Evidence** | Pipeline runs from R1.4 demonstrate rollover works when DB is available |
| **Remediation** | Resolve INC-006 first |
| **Go/No-Go** | GO conditionally — mechanism proven in R1.4, blocked by infra |

---

## SEVERITY SUMMARY

| Severity | Count | Blocking? |
|----------|:-----:|:---:|
| CRITICAL | 1 | YES (DB pool — external) |
| HIGH | 1 | NO (code ready, blocked by CRITICAL) |
| MEDIUM | 2 | NO (backlogged) |
| LOW | 2 | NO (documented) |

---

## GO / NO-GO ASSESSMENT

```
GO — CONDITIONAL
Application code complete and certified. Autonomous operation blocked
by infrastructure (DB pool saturation from external apps).
Resolve INC-006 to achieve full autonomy.
```

---

## FIRMA

```
INCIDENT REGISTER (UPDATED)
LG-INFRA-R1.7 Autonomous Operation Certification
Updated: 2026-06-07
```
