# LG-PROG-EXCL-1A.1 — Operator Decisions + Contract Patch

**Date:** 2026-06-13
**Phase:** LG-PROG-EXCL-1A.1 (Contract Patch)
**Mode:** DOCUMENTATION PATCH + READ-ONLY RECALC
**Predecessor:** `LG_PROG_EXCL_1A_EXCLUSIVE_DYNAMIC_LISTS_CONTRACT_DRY_RUN.md`
**Status:** COMPLETED

---

## 1. Executive Decision

### LG_PROG_EXCL_1A_PASS

All 5 operator decisions approved. All 6 contract corrections applied. Recalculated dry-run yields 12,403 Cemetery (vs 13,292 at 45d), zero collisions. Active Growth productivity bands corrected to use `weekly_trips` (current) instead of `best_week_12w` (historical). Contract is frozen and ready for LG-PROG-EXCL-1B.

---

## 2. Pre-check

| # | Question | Answer |
|---|----------|--------|
| 1 | Motor | Growth Machine / Control Foundation |
| 2 | Fase | LG-PROG-EXCL-1A.1 — Contract Patch |
| 3 | Contrato | LG_PROG_EXCL_1A, North Star, Production Cutover |
| 4 | Tablas | Read-only: driver_state_snapshot, driver_explorer_fact, driver_history_daily |
| 5 | Writer | Ninguno |
| 6 | Freshness | Ninguna nueva |
| 7 | Endpoint/UI | Ninguno |
| 8 | Legacy | No ejecutar |
| 9 | Riesgos | Ninguno — only docs |
| 10 | Rollback | Revertir docs |
| 11 | ACTIVE_SCOPE_CONTRACT | IN SCOPE |
| 12 | North Star Test | PASS |
| 13 | Scope Escalation | DOCUMENTATION PATCH authorized |

---

## 3. Decisions Approved

| # | Decision | Approved V1 | Impact |
|---|----------|------------|--------|
| 1 | Cemetery threshold | **inactivity_days > 60** (was 45) | -889 drivers moved to Recovery (66.9% vs 71.7%) |
| 2 | Recovery threshold | **7 ≤ inactivity ≤ 60** (was 7-45) | +889 drivers from Cemetery window widening |
| 3 | Protection target | **weekly_trips ≥ 100** (unchanged) | 33 drivers protected |
| 4 | first_active_date source | **driver_history_daily.MIN(date)** — canonical V1 proxy | Documented limitation until first_trip_at is populated |
| 5 | Cemetery Control Loop export | **false by default** | 12,403 drivers not exported daily. CSV under demand. |
| 6 | Active Growth band source | **weekly_trips** (current), not best_week_12w | Bands shift downward; 0 drivers in 100+ band in AG |

---

## 4. Active Growth Band Correction

### Problem

LG-PROG-EXCL-1A used `best_week_12w` for productivity bands. This is a historical metric that overstates current performance for declining drivers. A driver who peaked at 80 trips/week 8 weeks ago may currently be doing 5 trips/week — they should be in the 1-10 band, not 76-99.

### Correction

Productivity bands must use **current `weekly_trips`** (completed_orders_week or trips_7d). `best_week_12w` is reserved for:
- `value_tier` classification (HIGH/DEFAULT/LOW)
- Recovery value prioritization
- Historical context

### Impact on Active Growth Bands

| Band | 1A (best_week_12w) | 1A.1 (weekly_trips) |
|------|--------------------|--------------------|
| 100+ | 542 | 0 |
| 76-99 | 213 | 37 |
| 51-75 | 264 | 148 |
| 41-50 | 87 | 95 |
| 31-40 | 110 | 147 |
| 21-30 | 136 | 152 |
| 11-20 | 163 | 269 |
| 1-10 | 123 | 790 |

---

## 5. Updated Contract V1

### 5.1 Universe Priority (Final)

| Priority | Universe | Entry | Source Fields |
|----------|----------|-------|--------------|
| 1 | CEMETERY | inactivity_days > 60 | explorer_fact.days_since_last_trip |
| 2 | RECOVERY_HIGH | 7 ≤ inactivity ≤ 60 AND value_high | same + driver_state_snapshot.historical_band |
| 3 | RECOVERY_LOW | 7 ≤ inactivity ≤ 60 AND NOT value_high | same |
| 4 | NEW_REACTIVATED | age 0-14 AND trips_30d < 50 AND active < 7d | history_daily.MIN(date), explorer_fact.trips_30d |
| 5 | RAMP_UP | age 15-45 AND weekly < 100 AND active < 7d | same, driver_state_snapshot.completed_orders_week |
| 6 | CONSOLIDATION | age 46-90 AND weekly < 100 AND active < 7d | same |
| 7 | ACTIVE_GROWTH | age > 90 AND 1 ≤ weekly < 100 AND active < 7d | same, band from weekly_trips |
| 8 | PROTECTED | weekly ≥ 100 OR (age ≤ 14 AND trips ≥ 50) | same |
| 9 | NO_DATA | None of the above | fallback |

### 5.2 Serving Fact Target

```
growth.yango_lima_exclusive_driver_worklist_daily
```
22 columns. PK: (generated_date, driver_profile_id). UPSERT idempotent.

### 5.3 Export Rules

| Universe | daily_export_to_control_loop |
|----------|----------------------------|
| CEMETERY | false |
| RECOVERY_HIGH/LOW | true |
| NEW_REACTIVATED | true |
| RAMP_UP | true |
| CONSOLIDATION | true |
| ACTIVE_GROWTH | true |
| PROTECTED | true |
| NO_DATA | false |

---

## 6. Recalculated Counts (2026-06-13)

| Universe | Count | % |
|----------|-------|---|
| CEMETERY | 12,403 | 66.9% |
| RECOVERY_HIGH | 877 | 4.7% |
| RECOVERY_LOW | 2,989 | 16.1% |
| NEW_REACTIVATED | 54 | 0.3% |
| RAMP_UP | 210 | 1.1% |
| CONSOLIDATION | 341 | 1.8% |
| ACTIVE_GROWTH | 1,638 | 8.8% |
| PROTECTED | 33 | 0.2% |
| NO_DATA | 0 | 0.0% |

Exclusivity: **18,545 distinct / 18,545 total — PASS (0 duplicates)**

---

## 7. Implementation Implications for LG-PROG-EXCL-1B

### 7.1 Table Creation

- Create `growth.yango_lima_exclusive_driver_worklist_daily` with 22 columns
- PK: (generated_date, driver_profile_id)
- Migration: additive only, no DROP

### 7.2 Writer

- Single canonical writer: `build_exclusive_driver_worklist_daily(target_date)`
- Reads: `driver_state_snapshot` + `drive_explorer_fact` + `driver_history_daily` (for first_active_date)
- UPSERT with `ON CONFLICT (generated_date, driver_profile_id) DO UPDATE`
- Transaction: explicit BEGIN/COMMIT
- Lock: advisory lock or tick-level (autonomous_tick already serializes)

### 7.3 Pipeline Integration

- Insert into `autonomous_tick` cascade AFTER `build_driver_state_snapshot()`
- `check_driver_history_weekly_freshness()` gate already protects upstream

### 7.4 Freshness Registration

- Chain: layer `"exclusive_worklist"` with lineage source `"snapshot"`
- Registry: component `"exclusive_worklist"` in freshness_registry
- Audit: asset `"exclusive_driver_worklist_daily"` in serving_freshness_fact
- SLA: 24h

### 7.5 Export Path

- `export_to_control_loop = true` → sync to `control_loop_state` with NOT EXISTS
- `export_to_control_loop = false` → CSV endpoint only
- CSV: `GET /yego-lima-growth/export/exclusive-worklist?date=YYYY-MM-DD`

---

## 8. Verdict

### LG_PROG_EXCL_1A_PASS

All conditions met:
- [x] 5 operator decisions approved
- [x] 1 contract correction applied (AG band source)
- [x] Recalculated dry-run: 18,545 drivers, 0 collisions
- [x] 4 documents updated (1A report, North Star, GROWTH_MACHINE_CANONICAL, this certification)
- [x] 0 code/DB/scheduler/writer changes
- [x] Serving fact + export contracts defined
- [x] Ready for LG-PROG-EXCL-1B

**Next phase:** LG-PROG-EXCL-1B — Create table + canonical writer.

---

*Patch complete. No implementation. 6 decisions resolved. Contract frozen for production.*
