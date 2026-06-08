# OV2-F.3 — AUTOMATIC FRESHNESS CHAIN CERTIFICATION

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Freshness Chain
> **Phase:** OV2-F.3 — Automatic Freshness Chain Certification
> **Status:** **YELLOW — Manual steps remain for bridge, week, snapshots**

---

## 1. EXECUTIVE SUMMARY

La cadena de refresh funciona pero **no es automática**. Tres de seis capas requieren intervención manual (bridge, week, snapshots). El scheduler diario reporta falsos positivos. month_fact aún usa raw trips para drivers. La certificación waterfall 4/4 PASS (F.2E) pero fue lograda manualmente, no por automatización.

---

## 2. PER-LAYER STATUS

| Layer | Source | Auto-refresh? | Drivers from? | Status |
|-------|--------|--------------|---------------|--------|
| RAW | trips_2026 | ✓ Continuous | N/A | **GREEN** |
| BRIDGE | trips_2026 | ✗ Manual (F.2E build_driver_bridge_direct) | N/A | **YELLOW** |
| DAY | enriched + resolution | ✓ Scheduler 04:00 | COUNT DISTINCT from raw | **YELLOW** |
| WEEK | day_fact + bridge | ✗ Manual (F.2E rebuild) | Bridge (exact) ✓ | **YELLOW** |
| MONTH | enriched + resolution | ✓ Scheduler (raw path) | COUNT DISTINCT from raw ✗ | **RED** |
| SNAPSHOT | day_fact | ✗ Manual (refresh_omniview_v2_snapshots) | N/A | **YELLOW** |

## 3. CRITICAL QUESTIONS

### 1. ¿Monthly drivers ya usa bridge?

**NO.** month_fact.active_drivers = 65,283 (from raw trips). Bridge-based monthly distinct would be different and exact.

### 2. ¿La cadena corre sola?

**NO.** Only RAW and DAY have automatic refresh. Bridge, week, month (bridge path), and snapshots are manual.

### 3. ¿Qué sigue dependiendo de ejecución manual?

- `build_driver_bridge_direct` — bridge backfill + daily
- `rebuild_week_from_day_and_bridge` — week rebuild
- `refresh_omniview_v2_snapshots` — snapshots
- `rebuild_month_from_bridge` (not yet created) — month driver fix

### 4. ¿Qué puede quedarse rancio silenciosamente?

| Layer | Will stale silently? | Detection |
|-------|---------------------|-----------|
| Bridge | **YES** — no auto update | Only manual audit |
| Week | **YES** — no auto update | Waterfall validator (manual) |
| Month drivers | **YES** — uses raw, not bridge | Only explicit audit |
| Snapshots | **YES** — D-2 already | Endpoint returns MISSING |
| Day | **YES** — scheduler false positives | Detection exists (audit script) |

### 5. ¿Estamos listos para cerrar Freshness Chain?

**NO.** Se requiere:

1. [ ] Bridge: schedule daily update (APScheduler job)
2. [ ] Week: schedule auto-rebuild after bridge update
3. [ ] Month: rebuild from bridge, then schedule
4. [ ] Snapshots: schedule after facts refresh
5. [ ] Scheduler: fix false positive reporting (SUCCESS_WITH_DATA vs SUCCESS_NO_CHANGE)
6. [ ] Fail-fast: implement automated staleness detection

---

## 4. CLASSIFICATION

| Layer | Status |
|-------|--------|
| RAW | **GREEN** |
| Bridge | **YELLOW** (exists, manual) |
| Day | **YELLOW** (auto but false positives) |
| Week | **YELLOW** (manual, but correct source) |
| Month | **RED** (uses raw, not bridge) |
| Snapshot | **YELLOW** (manual) |

**Overall: YELLOW** — Chain works when manually executed. Not automatic.

---

## 5. GO/NO-GO FOR CLOSING F PHASE

**NO-GO** until all 6 items in §3.5 are addressed.

Minimal viable automatic chain:
```
APScheduler 04:00 → bridge_daily (D-1)
                → day_fact (from scheduler, verify data loaded)
                → week_fact (from day+bridge)
                → month_fact (from bridge for drivers)
                → snapshots (if facts changed)
                → certification (log result)
```

---

*End of Automatic Freshness Chain Certification*
