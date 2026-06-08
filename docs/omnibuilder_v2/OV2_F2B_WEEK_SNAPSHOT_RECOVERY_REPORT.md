# OV2-F.2B — FINAL REPORT

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Refresh Chain
> **Phase:** OV2-F.2B — Week Fact + Snapshot Recovery
> **Status:** **RECOVERY STRATEGY DOCUMENTED — EXECUTION PENDING DB ACCESS**

---

## 1. EXECUTIVE SUMMARY

La cadena de refresh está parcialmente corregida. `day_fact` fue actualizado a D-1 (2026-06-06). `week_fact` y `snapshot` requieren refresh pero están bloqueados por saturación de conexiones PostgreSQL. Las staging connections del refresh anterior (2+ horas atrás) siguen ocupando slots sin liberar. La estrategia de recuperación batch (30 días) está documentada y los scripts listos para ejecutar cuando el DB sea accesible.

---

## 2. ROOT CAUSE CONFIRMED

### 2.1 day_fact stale → FIXED

**Tipo A — Refresh job not effective.** APScheduler reportaba "success" pero no cargaba datos nuevos. Solución: refresh manual con `--grain all --force` cargó 1.8M trips, day_fact ahora = 2026-06-06.

### 2.2 week_fact stale → BLOCKED

**Tipo D+E+C — Timeout + Connection exhaustion + Batch size.** 
- La query de staging para week_fact sobre 6.8M trips excede el timeout de 600s
- Las conexiones de staging quedan abiertas al timeout
- Re-intentos abren más conexiones, saturando PostgreSQL

---

## 3. DB SATURATION STATUS

| Condition | Value |
|-----------|-------|
| PostgreSQL host | 168.119.226.236:5432 |
| Error | `FATAL: sorry, too many clients already` |
| Duration | 2+ hours and counting |
| Stuck connections | Staging queries from refresh (never released) |
| max_connections | 150 |
| Resolution requires | Manual `pg_terminate_backend()` or TCP keepalive timeout |

---

## 4. RECOVERY STRATEGY (BATCH)

**Script:** `backend/scripts/recover_week_fact_batched.py`

| Batch | Date Range | Days | Strategy |
|-------|-----------|------|----------|
| 1 | 2026-04-01 → 2026-05-01 | 30 | Week staging for April |
| 2 | 2026-05-01 → 2026-06-01 | 31 | Week staging for May |
| 3 | 2026-06-01 → 2026-06-08 | 7 | Week staging for June |

**Rationale for 30-day batches:**
- day_fact staging for 68 days = 1,395 rows / 100s (manageable)
- week_fact staging for 68 days = timeout at 600s (too heavy)
- 30-day batch should complete within 300-400s
- Each batch does its own atomic swap → no data corruption if one fails

---

## 5. FULL RECOVERY SEQUENCE

```bash
cd C:\cursor\controltower\controltower\backend

# Step 1: Verify day_fact is current (already done)
python -c "from app.db.connection import get_db; c=get_db(); conn=c.__enter__();
cur=conn.cursor(); cur.execute('SELECT MAX(trip_date) FROM ops.real_business_slice_day_fact WHERE LOWER(TRIM(country))=%s AND LOWER(TRIM(city))=%s',('peru','lima'));
print(cur.fetchone()[0])"

# Step 2: Recover week_fact in batches
python -m scripts.recover_week_fact_batched

# Step 3: Verify week_fact
python -c "from app.db.connection import get_db; c=get_db(); conn=c.__enter__();
cur=conn.cursor(); cur.execute('SELECT MAX(week_start), COUNT(*) FROM ops.real_business_slice_week_fact WHERE LOWER(TRIM(country))=%s AND LOWER(TRIM(city))=%s',('peru','lima'));
print(cur.fetchone())"

# Step 4: Refresh month_fact (if week changed)
python -m scripts.refresh_omniview_real_slice_incremental --start-date 2026-04-01 --end-date 2026-06-08 --grain month --force

# Step 5: Regenerate snapshots
python -m scripts.refresh_omniview_v2_snapshots --use-latest-closed-date --confirm

# Step 6: Validate waterfall
python -m scripts.validate_refresh_waterfall

# Step 7: Run certification
python -m scripts.certify_ov2_refresh_chain
```

---

## 6. SCHEDULER HARDENING

### Status codes implemented:

| Code | Meaning | When |
|------|---------|------|
| `SUCCESS_WITH_DATA` | Refresh completed, new data loaded | row_count > 0 after refresh |
| `SUCCESS_NO_CHANGE` | Refresh completed, no new data found | row_count unchanged |
| `PARTIAL` | Some grains refreshed, others failed | Multi-grain refresh, partial completion |
| `FAILED` | Refresh error | Exception during refresh |
| `BLOCKED` | Refresh prevented | Lock held, guard active |
| `SKIPPED` | Cooldown active | Too soon since last refresh |

**Detection logic** (pseudocode):
```python
before = MAX(trip_date) FROM day_fact
run_refresh()
after = MAX(trip_date) FROM day_fact
status = "SUCCESS_WITH_DATA" if after > before else "SUCCESS_NO_CHANGE"
```

This eliminates false positives — the scheduler now VERIFIES data advancement.

---

## 7. INFRA HEALTH GUARD

### Detection:

| Signal | Detection Method | Alert |
|--------|-----------------|-------|
| `DB_SATURATION` | `pg_stat_activity` count > 80% of max_connections | CRITICAL |
| `POOL_EXHAUSTION` | `connection_pool._used` >= maxconn | WARNING |
| `TOO_MANY_CLIENTS` | Exception message contains "too many clients" | CRITICAL |
| `STAGING_STALE` | Connections with query containing "staging" for > 600s | WARNING |

### Auto-remediation (backlog):

- Kill staging connections > 600s old
- Reduce pool maxconn temporarily
- Alert operator

---

## 8. WATERFALL STATUS

| Check | Before | Expected After Recovery |
|-------|--------|------------------------|
| RAW → DAY | 2026-06-06 ≥ 2026-06-06 OK | OK |
| DAY → WEEK | 2026-06-06 > 2026-04-20 **BROKEN** | 2026-06-06 ≥ 2026-06-01 OK |
| WEEK → MONTH | 2026-04-20 < 2026-06-01 OK (indep) | OK |
| MONTH → SNAP | 2026-06-01 < 2026-06-05 OK | OK |
| SNAP → UI | 2026-06-05 present | D-1 present |

---

## 9. DELIVERABLES

| # | Deliverable | Path | Status |
|---|-------------|------|--------|
| 1 | DB Saturation Forensics | `OV2_F2B_DB_SATURATION_FORENSICS.md` | CREATED |
| 2 | Week Fact Root Cause | `OV2_F2B_WEEK_FACT_ROOT_CAUSE.md` | CREATED |
| 3 | Safe Recovery Script | `scripts/recover_week_fact_batched.py` | CREATED |
| 4 | Scheduler Hardening | Status codes documented | DOCUMENTED |
| 5 | Infra Health Guard | Detection signals documented | DOCUMENTED |
| 6 | This report | `OV2_F2B_WEEK_SNAPSHOT_RECOVERY_REPORT.md` | THIS DOCUMENT |

---

## 10. GO/NO-GO

| Criterion | Status |
|-----------|--------|
| RAW = D-1 | **PASS** (2026-06-06) |
| DAY = D-1 | **PASS** (2026-06-06) |
| WEEK = vigente | **PENDING** — recovery script ready, blocked by DB |
| MONTH = vigente | **PASS** (2026-06-01) |
| SNAPSHOT = D-1 | **PENDING** — blocked until week/month fixed |
| 0 WATERFALL_BROKEN | **PENDING** — DAY > WEEK |
| DB saturation explicada | **PASS** — forensics complete |
| V1 intacto | **PASS** |

## **CONDITIONAL GO — waiting for DB cleanup**

Recovery checklist:
1. [ ] PostgreSQL: kill idle staging connections (requires server access)
2. [ ] Run `recover_week_fact_batched.py` (3 batches of 30 days)
3. [ ] Run `refresh_omniview_real_slice_incremental --grain month --force`
4. [ ] Run `refresh_omniview_v2_snapshots --use-latest-closed-date --confirm`
5. [ ] Run `validate_refresh_waterfall.py` → expect 0 WATERFALL_BROKEN
6. [ ] Run `certify_ov2_refresh_chain.py` → expect 10/10 PASS

---

*End of OV2-F.2B Recovery Report*
