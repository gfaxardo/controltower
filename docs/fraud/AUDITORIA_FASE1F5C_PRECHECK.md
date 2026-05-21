# AUDITORIA FASE 1F-5C — PRECHECK

**Fecha**: 2026-05-20
**Estado**: **GO**

---

## 1. Rama

- **Branch**: `master`
- **Tracking**: up to date with `origin/master`

## 2. Working Tree

- **Status**: Dirty (6 modified files, 3 untracked)
- **Modified files**: All belong to Fase 1G1 UI Regression Recovery — **no fraud files touched**
  - `backend/app/routers/ops.py`
  - `backend/app/services/business_slice_omniview_service.py`
  - `backend/app/services/business_slice_real_freshness_service.py`
  - `backend/app/services/business_slice_service.py`
  - `backend/app/services/data_trust_service.py`
  - `backend/app/services/projection_expected_progress_service.py`
- **Untracked files**:
  - `AUDITORIA_FASE1G1_UI_REGRESSION_RECOVERY.md`
  - `CIERRE_FASE1G1_UI_REGRESSION_RECOVERY.md`
  - `backend/scripts/validate_omniview_ui_regression_phase1g1.py`
- **Veredicto**: Sin cambios sucios ajenos al fraude que comprometan la fase. Los modified files son de F1G1, no de fraud.

## 3. Archivos clave

| Archivo | Estado |
|---|---|
| `AUDITORIA_FASE1F5B_THRESHOLD_CALIBRATION_IMPLEMENTACION.md` | EXISTE |
| `fraud.rule_threshold_config` (migration 148) | EXISTE |
| `config_version = trip_behavior_v1_calibrated` | EXISTE en `fraud_behavioral_routines.py:29` y `fraud_seed_thresholds.py` |
| `fraud_remediate_precalibration_cases.py` | EXISTE |
| `fraud_trip_behavior_audit.py` | EXISTE |
| `fraud_seed_thresholds.py` | EXISTE |
| `validate_fraud_trip_behavior_phase1f5.py` | EXISTE |

## 4. Open Cases (estimado)

- 256 open cases total (reportado en 1F-5B)
- 236 behavioral (May 20)
- 223 pre-calibration detectables (repeated_origin/repeated_route solo)
- 33 a mantener (bank cluster + combos)

## 5. Migraciones disponibles

| Migracion | Descripcion |
|---|---|
| `144_fraud_risk_foundation` | Schema fraud + 7 tablas base |
| `145_payment_identity_onboarding` | payment_identity_source |
| `146_routine_run_log` | routine_run_log |
| `147_trip_behavior_route_features` | Columnas de ruta en trip_risk_features |
| `148_threshold_config_calibration` | rule_threshold_config + calibration cols |

**Pendiente**: Migracion `149` para `case_confidence_score` y `behavioral_profile_class`.

## 6. Threshold Config Status

- `rule_threshold_config` poblado con 10 thresholds + guardrails
- `config_version = trip_behavior_v1_calibrated`
- `CASE_CREATION_GUARDRAILS` activo:
  - `max_cases_per_run = 50`
  - `max_cases_per_rule = 20`
  - `max_cases_per_park = 10`
  - `max_cases_per_driver = 1`
  - `min_risk_score_for_case = 60`

## 7. GO/NO-GO Precheck

| Item | Estado |
|---|---|
| Rama limpia (sin cambios en fraud) | GO |
| Archivos auditoria existen | GO |
| Thresholds calibrados existen | GO |
| Scripts de remediacion existen | GO |
| Migration 148 aplicada | GO |
| Migration 149 pendiente (crear) | PARA TAREA 1 |
| Omniview no tocado | GO |
| Plan vs Real no tocado | GO |
| Acciones reales = 0 | GO |

**GO para iniciar FASE 1F-5C.**
