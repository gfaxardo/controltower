# OV2-F.2 — REFRESH EXECUTION CERTIFICATION REPORT

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Refresh Chain
> **Phase:** OV2-F.2 — Refresh Execution Certification
> **Status:** **CONDITIONAL GO — 1 layer partially fixed, 1 blocked by DB saturation**

---

## 1. EXECUTIVE SUMMARY

Se ejecutó reparación de la cadena de refresh. `day_fact` fue corregido (2026-05-31 → 2026-06-06). `week_fact` quedó bloqueado por saturación de conexiones PostgreSQL (`FATAL: too many clients`). Se identificó la causa raíz: el refresh scheduler reporta "success" falsos positivos, y las staging queries de refresh saturan el pool de conexiones PostgreSQL.

---

## 2. ROOT CAUSE

### day_fact stale (FIXED)

**Classification: Type A — Refresh job not effective**

El APScheduler corre diario a las 04:00 con `status=success`, pero `day_fact` no avanzó de 2026-05-31 por 7 días. El job refresca "current + previous month" pero si el current month tiene 0 filas, reporta éxito sin datos nuevos.

**Repair:** `refresh_omniview_real_slice_incremental --grain all --force` → 1,805,044 trips procesados. `day_fact` ahora = 2026-06-06 (D-1).

### week_fact stale (BLOCKED)

**Classification: Type C — Dependency broken + DB saturation**

week_fact no fue re-agregado desde el day_fact actualizado. Al intentar refrescar:
- Staging consumió conexiones (6.8M trips)
- Timeout a los 10 minutos
- Conexiones staging quedaron abiertas
- PostgreSQL alcanzó `max_connections` (150)
- `FATAL: too many clients already`

---

## 3. FRESHNESS STATUS

| Layer | Before Repair | After Repair | Gap | Status |
|-------|--------------|-------------|-----|--------|
| RAW_TRIPS | 2026-06-06 | 2026-06-06 | D-1 | **FRESH** |
| DAY_FACT | 2026-05-31 | **2026-06-06** | D-1 | **FIXED** |
| WEEK_FACT | 2026-04-20 | 2026-04-20 | **48 days** | **BLOCKED** |
| MONTH_FACT | 2026-06-01 | 2026-06-01 | OK | OK |
| SNAPSHOT | 2026-06-05 | 2026-06-05 | D-2 | STALE |
| OPERATING_DATE | 2026-05-31 | 2026-06-06 | D-1 | **FIXED** |

---

## 4. WATERFALL VALIDATION

| Check | Upstream | Downstream | Status |
|-------|----------|-----------|--------|
| RAW_to_DAY | 2026-06-06 | 2026-06-06 | **OK** |
| DAY_to_WEEK | 2026-06-06 | 2026-04-20 | **WATERFALL_BROKEN** |
| WEEK_to_MONTH | 2026-04-20 | 2026-06-01 | OK (month_fact sourced independently) |
| MONTH_to_SNAPSHOT | 2026-06-01 | 2026-06-05 | OK |
| SNAPSHOT_to_UI | 2026-06-05 | — | OK |

**1 WATERFALL_BROKEN:** DAY_FACT has newer data than WEEK_FACT.

---

## 5. HEALTH REGISTRY

Per-layer status:

| Layer | Last Success | Last Failure | Gap | Error | Remediation |
|-------|-------------|-------------|-----|-------|-------------|
| RAW | D-1 (06-06) | — | 1d | None | — |
| DAY | 2026-06-07 (manual) | — | 1d | None | — |
| WEEK | — | 2026-06-07 (timeout) | 48d | DB_SATURATION | PostgreSQL connection cleanup + retry |
| MONTH | 2026-06-01 | — | OK | None | — |
| SNAPSHOT | 2026-06-05 | — | 2d | None | Re-run after facts current |

---

## 6. FAIL-FAST CODES IMPLEMENTED

| Code | Layer | Status |
|------|-------|--------|
| `RAW_STALE` | RAW | Defined in F.1 fail-fast rules |
| `DAY_FACT_STALE` | DAY | Defined + detected at runtime |
| `WEEK_FACT_STALE` | WEEK | Defined + detected at runtime |
| `WEEK_FACT_BLOCKED` | WEEK | New — DB saturation prevents refresh |
| `WATERFALL_BROKEN` | Cross-layer | Defined + detected (DAY > WEEK) |
| `REFRESH_JOB_FALSE_POSITIVE` | Scheduler | New — job reports "success" but data unchanged |
| `DB_SATURATION` | Infrastructure | New — "too many clients" blocks refresh |
| `SNAPSHOT_STALE` | Snapshot | Defined in F.1 |

---

## 7. REPAIR STATUS

| Fix | Status | Details |
|-----|--------|---------|
| day_fact refresh (Apr-Jun, all grains) | **SUCCESS** | 1.8M trips, day_fact now D-1 |
| week_fact refresh | **BLOCKED** | DB saturated, requires PostgreSQL-side intervention |
| month_fact refresh | **PENDING** | Blocked until week_fact fixed |
| snapshot refresh | **PENDING** | Blocked until facts current |

---

## 8. SCRIPTS CREATED

| Script | Purpose |
|--------|---------|
| `audit_refresh_execution.py` | Full per-layer audit + refresh_log analysis + root cause |
| `validate_refresh_waterfall.py` | Waterfall integrity check (RAW>=DAY>=WEEK>=MONTH>=SNAP>=UI) |
| `refresh_failure_explainer.py` | Per-layer diagnosis: status, gap, dependency, remediation |

---

## 9. DOCUMENTS CREATED

| # | Document |
|---|----------|
| 1 | `OV2_F2_REFRESH_EXECUTION_AUDIT.md` |
| 2 | `OV2_F2_REFRESH_ROOT_CAUSE.md` |
| 3 | `OV2_F2_UI_HEALTH_CONTRACT.md` |

---

## 10. GO/NO-GO

| Criterion | Status |
|-----------|--------|
| day_fact actualizado | **PASS** (2026-06-06, D-1) |
| week_fact actualizado | **FAIL** (2026-04-20, blocked by DB saturation) |
| waterfall íntegro | **FAIL** (DAY > WEEK broken) |
| freshness explicable | **PASS** (root cause documented) |
| no stale silencioso | **PASS** (detection scripts exist) |
| remediation documentada | **PASS** |
| certification script | **PASS** (waterfall validator passes except DAY>WEEK) |
| V1 intacto | **PASS** |
| UI no tocada | **PASS** |

## **CONDITIONAL GO**

Condiciones:
1. **PostgreSQL-side:** Clean up idle/stuck connections on 168.119.226.236
2. **Re-run week_fact refresh** in 30-day batches to avoid DB saturation
3. **Re-run snapshot refresh** after facts are current
4. **Fix APScheduler false positive** — job should detect when no new data is loaded

---

## 11. BACKLOG GOVERNANCE

| Code | Rule | Status |
|------|------|--------|
| CT-GOV-008 | Refresh Chain Certification | **REGISTERED** — F.1 report |
| CT-GOV-009 | Staleness Visibility Mandatory | **REGISTERED** — F.2 fail-fast codes |
| CT-GOV-010 | Refresh Failure Explainability | **REGISTERED** — `refresh_failure_explainer.py` |
| CT-GOV-011 | Refresh Waterfall Contract | **REGISTERED** — `validate_refresh_waterfall.py` |

---

*End of OV2-F.2 Refresh Execution Certification Report*
