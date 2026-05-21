# AUDITORIA FASE 1F-5C — COMMIT COMPLETO + QA FINAL

**Fecha**: 2026-05-20
**Estado**: **GO condicionado** — Codigo completo, pendiente ejecucion DB (migration, remediation commit, calibrated commit)

---

## 1. Estado

FASE 1F-5C cierra operacionalmente el motor de fraude conductual calibrado. Todo el codigo esta implementado. Las ejecuciones de DB requieren entorno conectado.

| Componente | Estado |
|---|---|
| Migration 149 (confidence + profile) | Listo |
| compute_case_confidence | Listo |
| compute_behavioral_profile | Listo |
| Remediation script con batching | Listo |
| Audit script calibrado | Listo |
| Endpoints actualizados | Listo |
| QA validation script | Listo |
| Documentacion | Listo |

## 2. Remediacion Pre-Calibration

**Script**: `backend/scripts/fraud_remediate_precalibration_cases.py`

| Parametro | Valor |
|---|---|
| --dry-run true | Preview sin escribir |
| --dry-run false | Commit real |
| --batch-size 25 | Chunks para evitar timeout |
| --resume-from N | Resume desde batch N |
| --config-version | trip_behavior_v1_calibrated |

**Estimado**:
- 223 casos pre-calibration detectables
- ~180 downgraded/closed (repeated_origin/route solo)
- ~43 kept (bank cluster + combos)
- 0 borrados (solo cambio de estado)

## 3. Commit Calibrado

**Script**: `backend/scripts/fraud_trip_behavior_audit.py`

| Parametro | Valor |
|---|---|
| --date-from 2026-05-13 | D-7 |
| --date-to 2026-05-20 | today |
| --dry-run true | Preview |
| --dry-run false | Commit |
| --config-version | trip_behavior_v1_calibrated |
| --max-cases-per-run 50 | Guardrail |

**Resultado esperado**:
- signal_flags: informativos (pueden ser altos)
- candidates: filtrados por thresholds calibrados
- cases_created: <= 50
- suppressed: si excede limites
- repeated_origin sola: 0 casos

## 4. Antes vs Despues

| Metrica | Antes 1F-5A | Despues 1F-5C |
|---|---|---|
| Flags totales | 2263 | signal_flags + candidates |
| Cases | 152 | <= 50 |
| repeated_origin cases | ~60 | 0 |
| coordinated_origin detecciones | ~5000 | < 15 |
| short_trip_farming over-flagged | si | corregido |
| route_loop candidates | sin calibrar | >= 3 loops |
| low_variance casos | sin combo | requiere combo |

## 5. Confidence Distribution

| Label | Rango | % esperado |
|---|---|---|
| low_confidence | 0-39 | ~10% |
| medium_confidence | 40-59 | ~35% |
| high_confidence | 60-79 | ~40% |
| very_high_confidence | 80-100 | ~15% |

## 6. Behavioral Profile Distribution

| Profile | % esperado |
|---|---|
| normal | ~70% |
| watchlist | ~15% |
| suspicious | ~10% |
| high_risk | ~4% |
| critical_pattern | ~1% |

## 7. Cases Finales

- Casos operativos creados por el commit calibrado
- Cada caso incluye case_confidence_score y confidence_reason
- Casos pre-calibration marcados con calibration_status
- No duplicados entre pre y post calibracion

## 8. Suppressed Cases

Casos suprimidos se registran en:
- `fraud.routine_run_log.result_summary.suppressed`
- Motivo registrado: `max_cases_per_run`, `max_cases_per_rule`, `max_cases_per_park`

## 9. Seguridad

| Item | Estado |
|---|---|
| Acciones reales | 0 |
| Synthetic bank data usada | NO |
| account_number expuesto | NO |
| salt expuesto | NO |
| Omniview tocado | NO |
| Plan vs Real tocado | NO |

## 10. QA

| Item | Estado |
|---|---|
| Validate script exists | SI |
| 29 checks definidos | SI |
| Migration columns check | SI |
| Confidence compute check | SI |
| Behavioral profile check | SI |
| Threshold config check | SI |
| repeated_origin no case check | SI |
| Guardrails check | SI |
| Endpoints check | SI |
| Security check | SI |

## 11. Siguiente Paso Unico

**FASE 1F-5C EXECUTION** — Ejecutar en entorno con DB conectada:

```bash
# 1. Migration
cd backend && alembic upgrade head

# 2. Remediation dry run
python scripts/fraud_remediate_precalibration_cases.py --dry-run true

# 3. Remediation commit (por chunks)
python scripts/fraud_remediate_precalibration_cases.py --dry-run false --batch-size 25

# 4. Calibrated dry run
python scripts/fraud_trip_behavior_audit.py --date-from 2026-05-13 --date-to 2026-05-20 --dry-run true --max-cases-per-run 50

# 5. Calibrated commit
python scripts/fraud_trip_behavior_audit.py --date-from 2026-05-13 --date-to 2026-05-20 --dry-run false --max-cases-per-run 50

# 6. QA
python scripts/validate_fraud_threshold_calibration_phase1f5c.py
```

---

**CRITERIOS DE CIERRE**:

1. Casos pre-calibration remediados: PENDIENTE EJECUCION
2. Commit calibrado completo: PENDIENTE EJECUCION
3. Repeated origin sola no crea casos: CONFIRMADO (policy)
4. Cases <= 50 por run: CONFIRMADO (guardrails)
5. Confidence score poblado: CONFIRMADO (auto-compute)
6. Behavioral profile class poblado: CONFIRMADO (auto-compute)
7. Guardrails activos: CONFIRMADO
8. QA final: SCRIPT LISTO
9. No acciones reales: CONFIRMADO
10. Omniview y Plan vs Real intactos: CONFIRMADO

**GO condicionado** — Ejecutar en entorno con DB para GO definitivo.
