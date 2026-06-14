# LG-PROG-EXCL-1D — Export Preview + CSV/API

**Date:** 2026-06-13
**Phase:** LG-PROG-EXCL-1D (Export Preview + CSV/API)
**Mode:** IMPLEMENTATION — Read-only endpoints + CSV export
**Predecessor:** `LG_PROG_EXCL_1C_MIGRATION_WRITER_FRESHNESS_SMOKE.md`
**Status:** IMPLEMENTED

---

## 1. Executive Decision

### LG_PROG_EXCL_1D_PASS

4 endpoints created. CSV export works. Control Loop preview functional. Cemetery/Protected excluded by default. 6,109 exportable drivers verified. 34/34 tests pass. No Control Loop DB writes.

---

## 2. Pre-check

| # | Question | Answer |
|---|----------|--------|
| 1 | Motor | Growth Machine / Control Foundation |
| 2 | Fase | LG-PROG-EXCL-1D Export Preview |
| 3 | Contrato | Exclusive Dynamic Lists V1, Control Loop export |
| 4 | Tablas | Read-only: exclusive_driver_worklist_daily |
| 5 | Writer | None changed |
| 6 | Freshness | Read-only. No modifications. |
| 7 | Endpoint/UI | 4 new endpoints. No UI. |
| 8 | Legacy | None activated |
| 9 | Riesgos | See Section 9 |
| 10 | Rollback | Remove router + main.py registration |
| 11 | ACTIVE_SCOPE_CONTRACT | IN SCOPE |
| 12 | North Star Test | PASS |
| 13 | Scope Escalation | IMPLEMENTATION AUTHORIZED |

---

## 3. Endpoints Added

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/yego-lima-growth/exclusive-worklist/summary` | Summary counts by universe. Default: latest date. |
| GET | `/yego-lima-growth/exclusive-worklist/rows` | Paginated rows. Filter by universe, exportable_only, search. |
| GET | `/yego-lima-growth/exclusive-worklist/export.csv` | CSV download. Default: exportable_only=true. |
| GET | `/yego-lima-growth/exclusive-worklist/control-loop-preview` | Preview of what would be synced to Control Loop. |

**Router file:** `backend/app/routers/yego_lima_exclusive_worklist.py`
**Registration:** `backend/app/main.py` (after driver_explorer)

---

## 4. Export Contract

### 4.1 CSV Export

| Parameter | Default | Description |
|-----------|---------|-------------|
| generated_date | latest | Date to export |
| assigned_universe_v1 | None | Filter by universe |
| exportable_only | true | Exclude Cemetery + Protected |
| include_cemetery | false | Explicitly include Cemetery |

**By default:** CSV exports 6,109 drivers (excludes Cemetery + Protected). Cemetery requires `include_cemetery=true`.

**Headers (19 fields):** generated_date, driver_profile_id, driver_id, assigned_universe_v1, assigned_program_v1, subsegment, objective, reason_code, priority_rank, operational_age_days, weekly_trips, activation_window_trips, inactivity_days, value_tier, productivity_band, trend, target_metric, baseline_metric, export_to_control_loop.

### 4.2 Control Loop Preview

| Parameter | Default | Description |
|-----------|---------|-------------|
| generated_date | latest | Date |
| assigned_universe_v1 | None | Filter |
| limit | 1000 | Max 10,000 |
| offset | 0 | Pagination |

**Always excludes:** Cemetery, Protected, No Data.

**Fields (12):** driver_profile_id, assigned_universe_v1, assigned_program_v1, objective, reason_code, priority_rank, recommended_action_category, target_metric, baseline_metric, generated_date, would_export_to_control_loop, initial_control_loop_status.

### 4.3 Recommended Action Categories

| Universe | Category |
|----------|----------|
| NEW_REACTIVATED_0_14_TO_50 | ONBOARDING_PUSH |
| RAMP_UP_15_45_TO_100W | PRODUCTIVITY_RAMP |
| CONSOLIDATION_46_90_TO_100W | CONSOLIDATION_PUSH |
| ACTIVE_GROWTH_90_PLUS_BAND_UP | BAND_GROWTH |
| RECOVERY_HIGH_VALUE | HIGH_VALUE_RECOVERY |
| RECOVERY_LOW_VALUE | LOW_VALUE_RECOVERY |
| Cemetery / Protected / No Data | DO_NOT_EXPORT |

---

## 5. Counts Validation

| Metric | Value | Matches Expected? |
|--------|-------|------------------|
| Total drivers | 18,545 | Yes |
| Exportable | 6,109 | Yes |
| Cemetery | 12,403 | Yes |
| Protected | 33 | Yes |
| DO_NOT_EXPORT total | 12,436 | Yes |
| Exportable + Non-exportable = Total | 18,545 | Yes |

---

## 6. CSV Evidence

- CSV endpoint: `GET /yego-lima-growth/exclusive-worklist/export.csv`
- Default exports 6,109 rows (exportable_only=true)
- 19 header columns present
- Cemetery excluded by default
- `include_cemetery=true` adds 12,403 rows (total 18,512 exportable + cemetery)
- Content-Type: `text/csv`
- Content-Disposition: `attachment; filename=exclusive_worklist_2026-06-13.csv`

---

## 7. API Smoke

| Endpoint | Result |
|----------|--------|
| `/summary` | 18,545 total, 6,109 exportable, 8 universes |
| `/rows?limit=3` | 3 rows returned, total 18,545 |
| `/rows?assigned_universe_v1=ACTIVE_GROWTH_90_PLUS_BAND_UP&limit=3` | 3 rows, correct universe |
| `/export.csv` | CSV with 6,109 rows + header |
| `/control-loop-preview?limit=10` | 10 rows, Cemetery/Protected excluded |

---

## 8. Tests

```
34 passed in 0.58s
```
(25 worklist + 9 freshness gate)

---

## 9. Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| CSV endpoint loads all rows for filtering | LOW | 18K rows is small. Row fetch limited to 50K. |
| Control Loop preview is read-only | NONE | No DB writes. Safe. |
| No authentication on endpoints | LOW | Matches existing router pattern. |

---

## 10. Rollback

1. Remove `app.include_router(yego_lima_exclusive_worklist.router)` from main.py
2. Delete `backend/app/routers/yego_lima_exclusive_worklist.py`

No data impact. No DB changes.

---

## 11. Verdict

### LG_PROG_EXCL_1D_PASS

| Criterion | Status |
|-----------|--------|
| Summary endpoint | **PASS** |
| Rows endpoint | **PASS** |
| CSV export | **PASS** (6,109 default, Cemetery excluded) |
| Control Loop preview | **PASS** (DO_NOT_EXPORT excluded) |
| Export counts match DB | **PASS** (18,545 total, 6,109 exportable) |
| Recommended action categories | **PASS** (6 universes mapped) |
| Tests: 34/34 | **PASS** |
| No UI changes | **PASS** |
| No Control Loop DB writes | **PASS** |
| No legacy activation | **PASS** |

**Next phase:** LG-PROG-EXCL-1E — Control Loop sync (write) + E2E validation.
