# AUDITORIA FASE 1F-5D — DB PRECHECK

**Fecha**: 2026-05-20
**Estado**: **GO**

---

## 1. Git

- **Branch**: `master`
- **Tracking**: up to date with `origin/master`
- **Working tree**: modified (12 files, 10 untracked)
- **Fraud files modified**: fraud.py, fraud_behavioral_routines.py, fraud_case_service.py, fraud_remediate_precalibration_cases.py, fraud_trip_behavior_audit.py, README_FRAUD_RISK_CONTROL.md
- **Fraud files untracked**: migration 149, fraud_confidence_scoring.py, validate script, 4 auditoria docs
- **Non-fraud modified**: ops.py, 5 business_slice/projection services (F1G1 unrelated)
- **Veredicto**: Clean for fraud execution. No fraud files touched by unrelated changes.

## 2. PostgreSQL Connection

- **SELECT 1**: OK
- **Schema fraud**: EXISTS
- **Tables**: All 7 base tables EXIST

## 3. Config Version

| Item | Value |
|---|---|
| `trip_behavior_v1_calibrated` | 12 threshold rows seeded |

## 4. Risk Cases

| Metrica | Valor |
|---|---|
| Total risk_cases | 257 |
| Open cases | 256 |
| Pre-calibration (NULL calib, open) | 256 |
| Already calibrated | 0 |
| Calibration breakdown | None: 257 (100%) |

## 5. Driver Risk Snapshot

| Metrica | Valor |
|---|---|
| Total rows | 0 (empty) |

## 6. Pre-migration Column Check

| Column | Status |
|---|---|
| risk_cases.case_confidence_score | MISSING |
| risk_cases.confidence_reason | MISSING |
| risk_cases.calibration_status | EXISTS (mig 148) |
| risk_cases.calibration_version | EXISTS (mig 148) |
| driver_risk_snapshot.behavioral_profile_class | MISSING |
| driver_risk_snapshot.behavioral_profile_reason | MISSING |
| driver_risk_snapshot.behavioral_confidence_score | MISSING |

## 7. GO/NO-GO

| Item | Estado |
|---|---|
| DB conectada | GO |
| Schema fraud existe | GO |
| Tablas existen | GO |
| Config version existe | GO |
| Migration 149 pendiente | GO (a ejecutar) |
| 256 casos por remediar | GO |
| 0 casos ya calibrados | GO |

**GO para ejecutar TAREA 1 (Migration 149).**
