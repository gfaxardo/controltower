# AUDITORIA FASE 1F-6 — PRECHECK

**Fecha**: 2026-05-20
**Estado**: **GO**

---

## 1. Git

- **Branch**: `master`
- **Working tree**: Modified (12 files fraude + ops), untracked (14 fraude docs + 2 scripts)
- **Fase 1F-5D**: Cerrada GO
- **No cambios sucios ajenos**

## 2. DB State

| Metrica | Valor |
|---|---|
| total risk_cases | 263 |
| open cases | 39 |
| closed cases | 224 |

| Type | Count |
|---|---|
| recalibrated_downgraded (closed) | 223 |
| recalibrated_kept (open) | 33 |
| NULL calibration, closed | 1 (driver003 test) |
| NULL calibration, open | 6 (new calibrated commit cases) |

## 3. Confidence State

| Metrica | Valor |
|---|---|
| confidence=0 | 8 |
| confidence>0 | 0 |
| confidence=NULL | 255 |
| open cases with 0/NULL conf | 39 (100%) |

**Razon**: Los 8 con confidence=0 son casos nuevos de `REPEATED_ROUTE_SIGNATURE` sola. Los otros 255 nunca tuvieron confidence computado (pre-calibration). La logica de confidence es correcta pero nunca se ejecuto sobre los kept cases ni sobre los casos legacy.

## 4. Behavioral Profiles

| Metrica | Valor |
|---|---|
| driver_risk_snapshot rows | 0 |
| with behavioral_profile_class | 0 |

**Razon**: `routine_behavioral_driver_profile` nunca se ejecuto.

## 5. Rutinas

| Rutina | Estado | Signature |
|---|---|---|
| repeated_origin_pattern | OK | `(date_from, date_to, park_id, window_days, dry_run, limit)` |
| repeated_route_signature | OK | Same |
| low_avg_distance_pattern | **BROKEN -> FIXED** | Was `(dry_run, limit)`, now matches others |
| low_avg_duration_pattern | OK | Same |
| extreme_short_trip_ratio | OK | Same |
| low_variance_pattern | OK | Same |
| short_trip_farming | OK | Same |
| long_trip_outlier_v2 | OK | Same |
| route_loop_pattern | OK | Same |
| coordinated_origin_pattern | OK (slow) | Same |
| park_behavior_concentration | OK | `(dry_run)` |
| behavioral_driver_profile | OK (needs run) | Same |

## 6. GO/NO-GO

| Item | Estado |
|---|---|
| low_avg_distance fixed | GO (compila) |
| coordinated_origin needs optimization | TAREA 2 |
| behavioral profiles never run | TAREA 3 |
| confidence=0 cases need review | TAREA 4 |
| 12/12 routines not all executed | TAREA 5 |

**GO para FASE 1F-6.**
