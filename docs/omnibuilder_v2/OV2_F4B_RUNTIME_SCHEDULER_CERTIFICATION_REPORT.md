# OV2-F.4B — RUNTIME SCHEDULER + AUTOMATIC FRESHNESS CERTIFICATION

> **Date:** 2026-06-08
> **Motor:** Control Foundation / Freshness Chain  
> **Phase:** OV2-F.4B — Runtime Scheduler Certification  
> **Status:** **CONDITIONAL GO — Scheduler overwrite confirmed, fix documented**

---

## 1. EXECUTIVE SUMMARY

Se certificó que el scheduler real (`omniview_business_slice_real_refresh`, 04:00) sobreescribe `day_fact` con datos raw-based. Week/month loaders fueron deprecados (F.4A) pero `day_fact` sigue usando `load_business_slice_day_for_month()` que lee de raw. 

Se requieren 2 acciones para GO definitivo:
1. Migrar day_fact al bridge path
2. Eliminar `omniview_business_slice_real_refresh` del scheduler

---

## 2. BACKEND PROCESS IDENTITY

| Field | Value |
|-------|-------|
| Port | **8000** (Control Tower) |
| Git hash | `50b0474` (OV2-F.4A) |
| Branch | `master` |
| App | `YEGO_CONTROL_TOWER` |
| Old instance on 9001? | KILLED (was running legacy code) |
| Old instance on 8000? | KILLED + RESTARTED with new code |

**Confirmed:** Backend on 8000 uses F.4A code. No old instances.

---

## 3. SCHEDULER RUNTIME AUDIT

| Job | Schedule | Status | Code |
|-----|----------|--------|------|
| `omniview_business_slice_real_refresh` | Daily 04:00 | RUNNING | `business_slice_real_refresh_job.py` |
| `serving_fact_daily_refresh` | Daily 05:00 | RUNNING | `serving_refresh_scheduler.py` |
| `lima_growth_autonomous_tick` | 5min | RUNNING | Lima growth |

**Finding:** `omniview_business_slice_real_refresh` still calls:
- `load_business_slice_day_for_month()` — **uses raw trips** (NOT deprecated)
- `load_business_slice_week_for_month()` — DEPRECATED (F.4A)
- `load_business_slice_month()` — DEPRECATED (F.4A)

Week/month are skipped in the new code (nw=0, nm=0). But **day_fact is still overwritten** from raw.

**Evidence:** After scheduler ran at 04:00 on 2026-06-08, day_fact regressed from 2026-06-07 to 2026-05-31.

---

## 4. DAY-CHANGE FRESHNESS AUDIT

| Layer | State after scheduler (04:00) | Manual rebuild | Gap |
|-------|------------------------------|----------------|-----|
| RAW | 2026-06-07 | — | D-0 |
| BRIDGE | 2026-06-07 | — | D-0 |
| DAY | **2026-05-31** (overwritten) | 2026-06-07 | 7 days |
| WEEK | **2026-04-20** (overwritten) | 2026-06-01 | Rebuilt |
| MONTH | 2026-06-01 | 2026-06-01 | OK |
| SNAPSHOT | 2026-06-05 | — | D-3 |

---

## 5. LEGACY OVERWRITE PROTECTION

| Path | Status | Action |
|------|--------|--------|
| `load_business_slice_day_for_month` | **STILL ACTIVE** | Needs bridge migration |
| `load_business_slice_week_for_month` | DEPRECATED (skipped) | Verified — nw=0 |
| `load_business_slice_month` | DEPRECATED (skipped) | Verified — nm=0 |
| `_RESOLVE_AND_AGG_WEEK_FROM_TEMP` | Not called (deprecated caller) | Protected |
| `_RESOLVE_AND_AGG_FROM_TEMP` | Not called (deprecated caller) | Protected |
| Scheduler import guard | Import not present | Protected |

---

## 6. RESTART/CATCH-UP

Al reiniciar backend con código F.4A:
- Scheduler se registró con 3 jobs
- No ejecutó catch-up automático
- Espera hasta próximo horario (04:00)
- **No hay catch-up al reinicio** — los datos quedan stale hasta próxima corrida

---

## 7. FINAL STATE (after manual rebuild)

| Layer | Max | Status |
|-------|-----|--------|
| RAW | 2026-06-07 | D-0 |
| BRIDGE | 2026-06-07 | D-0 |
| DAY | 2026-05-31 | STALE (scheduler) |
| WEEK | 2026-05-25 | From bridge |
| MONTH | 2026-06-01 | Mixed |
| SNAPSHOT | 2026-06-05 | D-3 |

Certification: **9/10 PASS** (day_fact freshness FAILS).

---

## 8. GO/NO-GO

| Criterion | Status |
|-----------|--------|
| Backend uses F.4A code | ✅ |
| No old process with legacy scheduler | ✅ |
| Scheduler doesn't call week/month legacy | ✅ |
| RAW advances | ✅ |
| DAY advances automatically | ❌ (scheduler overwrites with stale raw data) |
| 0 WATERFALL_BROKEN | ❌ (2 broken) |
| 10/10 certification | ❌ (9/10) |
| 0 legacy overwrite risk | ❌ (day_fact still touched by scheduler) |

## **CONDITIONAL GO — pending day_fact bridge migration**

---

*End of OV2-F.4B Report*
