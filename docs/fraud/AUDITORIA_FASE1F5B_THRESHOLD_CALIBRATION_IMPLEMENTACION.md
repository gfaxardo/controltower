# AUDITORIA FASE 1F-5B — THRESHOLD CALIBRATION + CASE CREATION GUARDRAILS

**Fecha**: 2026-05-20
**Estado**: **GO condicionado**

---

## 1. Estado

Los thresholds estan calibrados basados en distribuciones reales D-7. El sistema de tiers (flag/candidate/case) esta implementado. Los guardrails de creacion de casos estan activos. Pendiente: commit de remediacion (timeout DB) y commit calibrado completo.

## 2. Distribuciones reales (D-7)

| Metrica | p50 | p75 | p90 | p95 | p99 |
|---|---|---|---|---|---|
| trips per driver | 13 | 44 | 83 | 106 | 148 |
| max repeated origin | 1 | 1 | 2 | 2 | 3 |
| max repeated route | 1 | 1 | 1 | 1 | 2 |
| drivers per origin | 1 | 2 | 3 | 4 | 8 |
| short trip ratio | 0 | 0 | 0.03 | 0.06 | 0.14 |
| avg distance m | 6258 | 8354 | 11235 | 13611 | 19703 |
| max trips 24h | 6 | 14 | 23 | 28 | 41 |

## 3. Thresholds calibrados (config_version=trip_behavior_v1_calibrated)

| Regla | Signal | Candidate | Case |
|---|---|---|---|
| REPEATED_ORIGIN | >=3 | >=5 + new | candidate + combo |
| REPEATED_ROUTE | >=2 | >=3 | candidate + combo |
| SHORT_TRIP_FARMING | ratio >=15% | ratio >=25% | candidate + combo |
| LOW_AVG_DISTANCE | p10 baseline | ratio <=35% | candidate + combo |
| LOW_AVG_DURATION | p10 baseline | ratio <=35% | candidate + combo |
| LOW_VARIANCE | p10 variance | p05 variance | candidate + combo |
| COORDINATED_ORIGIN | >=6 drivers | >=10 drivers | candidate >=10 |
| EXTREME_SHORT_RATIO | ratio >=15% | ratio >=25% | candidate + combo |
| BURST_ACTIVITY | p90 trips/day | p95 trips/day | p99 + new |
| TIME_WINDOW_DENSITY | p95 trips/day | p99 trips/day | candidate + combo |
| ROUTE_LOOP | >=2 loops | >=3 loops | candidate + new |

## 4. Case Creation Policy

- Flag: senal debil, solo scoring
- Candidate: combinacion de senales o anomalia fuerte
- Case: solo si score >= 80, o 2+ high rules, o 1 critical + new_or_unproven

**Guardrails activos**:
- max_cases_per_run: 50
- max_cases_per_rule: 20
- max_cases_per_park: 10

## 5. Antes vs Despues

| Metrica | Antes (1F-5A) | Despues (1F-5B) |
|---|---|---|
| Flags detectados (dry) | 2263 | signal_flags + candidates |
| Casos creados | 152 | 0 (single rules no crean casos) |
| Coordinated origins | 5000 | reducido (min=6) |
| Repeated origin sola crea caso | SI | NO |
| Thresholds versionados | NO | SI |
| Guardrails | NO | SI |

## 6. Casos pre-calibration

- 256 open cases total
- 236 behavioral (May 20)
- 223 candidatos a downgrade (repeated_origin/repeated_route solo)
- 33 a mantener (bank cluster + combos)
- Script de remediacion: `fraud_remediate_precalibration_cases.py` (dry_run ok, commit requiere retry)

## 7. Seguridad

- Acciones reales: 0
- Synthetic bank data: NO
- Omniview: intacto
- Plan vs Real: intacto
- account_number: no expuesto
- BANK_CLUSTER_SALT: no expuesto

## 8. Archivos modificados

| Archivo | Tipo |
|---|---|
| `148_threshold_config_calibration.py` | nueva migracion |
| `fraud_seed_thresholds.py` | nuevo |
| `fraud_behavioral_routines.py` | modificado (tiers + guardrails) |
| `fraud_remediate_precalibration_cases.py` | nuevo |
| `fraud_distribution_analysis.py` | nuevo |
| `AUDITORIA_FASE1F5B_*.md` | 3 reportes nuevos |

## 9. QA pendiente

- `validate_fraud_threshold_calibration_phase1f5b.py` — no creado aun
- Commit de remediacion — requiere retry (timeout DB)
- Commit calibrado — requiere completion de rutinas

## 10. Siguiente paso unico

**FASE 1F-5C: COMMIT COMPLETO + QA FINAL**

1. Retry commit de remediacion (223 casos downgrade)
2. Ejecutar commit calibrado con limites
3. Crear QA script completo
4. Validar endpoint summary con tiers
5. Verificar que repeated_origin sola ya no crea casos
