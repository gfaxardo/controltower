# AUDITORIA FASE 1F-7 — PRECHECK

**Fecha**: 2026-05-20
**Estado**: **GO**

---

## 1. Git

- **Branch**: `master`, clean for fraud (modified files are F1F-5/6 + ops files)
- **FASE 1F-6**: Cerrada GO

## 2. DB State

| Metrica | Valor |
|---|---|
| driver_risk_snapshot | 103 |
| behavioral_profiles | 100 (97% normal) |
| null profiles | 3 |
| driver_trust_snapshot | 20,505 |
| routine_run_log | 128 |
| open cases | 43 |

## 3. Profile Coverage Gap

| Metrica | Valor |
|---|---|
| Driver trust snapshots (full universe) | 20,505 |
| Driver risk snapshots | 103 |
| Behavioral profiles | 100 |
| **Coverage** | **0.5%** |

**Severe under-coverage**: `routine_behavioral_driver_profile` solo ejecuto con limit=100. Se necesita ejecutar con batch mode sobre full universe.

## 4. Routine Performance (from F1F-6)

| Rutina | Runtime | Daily-ready |
|---|---|---|
| coordinated_origin | 303.9s | NO |
| repeated_route | 86.9s | NO |
| long_trip_outlier_v2 | 82.3s | NO |
| behavioral_driver_profile | 67.3s | NO |
| repeated_origin | 7.6s | YES |
| low_avg_duration | 3.9s | YES |
| route_loop | 3.3s | YES |
| extreme_short_trip | 3.2s | YES |
| park_concentration | 2.9s | YES |
| low_avg_distance | 2.2s | YES |
| short_trip_farming | 2.2s | YES |
| low_variance | 2.1s | YES |

## 5. GO/NO-GO

| Item | Estado |
|---|---|
| F1F-6 cerrada | GO |
| fraud_daily_control.py exists | GO |
| routine_run_log exists | GO |
| Profile coverage gap identified | TAREA 1 |
| Indexes needed | TAREA 2 |
| Daily schedule hardening needed | TAREA 4-5 |

**GO para FASE 1F-7.**
