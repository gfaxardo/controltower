# AUDITORIA FASE 1F-7 — DAILY CONTROL HARDENING

**Fecha**: 2026-05-20
**Estado**: **COMPLETO**

---

## 1. fraud_daily_control.py (v2)

**Script**: `backend/scripts/fraud_daily_control.py`

### Parametros

| Param | Default | Descripcion |
|---|---|---|
| `--mode` | daily | daily/weekly/monthly/all |
| `--date` | now | Reference date YYYY-MM-DD |
| `--dry-run` | true | Preview or commit |
| `--config-version` | trip_behavior_v1_calibrated | Threshold version |
| `--max-cases-per-run` | 50 | Guardrail override |

### Modos

| Modo | Window | Routines | Target Runtime |
|---|---|---|---|
| daily | D-1 | 7 rutinas rapidas | < 120s |
| weekly | D-7 | 4 rutinas medias/lentas | < 600s |
| monthly | D-30 | 2 rutinas pesadas | < 900s |
| all | — | 13 combinadas | — |

## 2. routine_schedule_config

**Tabla**: `fraud.routine_schedule_config`

| Frecuencia | Routines |
|---|---|
| daily | 7 (repeated_origin, low_avg_distance, low_avg_duration, extreme_short_trip_ratio, low_variance, short_trip_farming, park_behavior_concentration) |
| weekly | 4 (repeated_route_signature, route_loop, coordinated_origin, long_trip_outlier_v2) |
| monthly | 2 (behavioral_driver_profile, park_behavior_concentration) |

## 3. Hardware

- `routine_run_log.frequency`: registra el modo de ejecucion
- `_compute_daily_operational_status()`: evalua readiness para operacion recurrente
- Fallback schedule si `routine_schedule_config` no esta disponible

## 4. Resultado Daily Dry Run

| Metrica | Valor |
|---|---|
| Routines | 7 |
| Runtime | **15.6s** |
| Signals | 4 |
| Candidates | 0 |
| Cases | 0 |
| Errors | 0 |

## 5. Veredicto

**GO** — Daily control endurecido, schedule-based, 15.6s runtime. Listo para operacion recurrente.
