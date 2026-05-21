# AUDITORIA FASE 1F-6 — FULL ROUTINE RUN

**Fecha**: 2026-05-20
**Estado**: **COMPLETO**

---

## 1. Ejecucion

| Metrica | Valor |
|---|---|
| Rutinas | 12/12 |
| dry_run | false (COMMIT) |
| config_version | trip_behavior_v1_calibrated |
| date range | 2026-05-13 a 2026-05-20 |
| window_days | 7 |
| limit | 100 |
| Elapsed total | 574.7s (~9.6 min) |

## 2. Resultados por rutina

| Rutina | Cases | Suppressed | Candidates | Signals | Runtime |
|---|---|---|---|---|---|
| repeated_origin_pattern | **0** | 0 | 60 | 40 | 7.6s |
| repeated_route_signature | 20 | 0 | 0 | 0 | 86.9s |
| low_avg_distance_pattern | 0 | 0 | 0 | 0 | 2.2s |
| low_avg_duration_pattern | 1 | 0 | 0 | 0 | 3.9s |
| extreme_short_trip_ratio | 1 | 0 | 0 | 0 | 3.2s |
| low_variance_pattern | 0 | 0 | 0 | 0 | 2.1s |
| short_trip_farming | 0 | 0 | 0 | 0 | 2.2s |
| long_trip_outlier_v2 | 20 | 0 | 0 | 0 | 82.3s |
| route_loop_pattern | 0 | 0 | 0 | 0 | 3.3s |
| coordinated_origin_pattern | 8 | **492** | 100 | 0 | 303.9s |
| park_behavior_concentration | 0 | 0 | 0 | 0 | 2.9s |
| behavioral_driver_profile | 0 | 0 | 0 | 0 | 67.3s |

## 3. Totales

| Metrica | Valor |
|---|---|
| cases_created | **50** (limit alcanzado) |
| cases_suppressed | **492** (guardrails activos) |
| candidates | 160 |
| signal_flags | 40 |
| errors | 0 |

## 4. Validaciones

| Validacion | Resultado |
|---|---|
| 12/12 ejecutadas | PASS |
| repeated_origin_cases = 0 | PASS |
| coordinated_origin controlado | PASS (492 suppressed) |
| low_avg_distance funciona | PASS (signature fixed) |
| max_cases_per_run = 50 honored | PASS (50 exact) |
| guardrails activos | PASS |
| confidence_score auto-computado | PASS |
| behavioral_profiles actualizados | PASS |

## 5. Veredicto

**GO** — Las 12 rutinas ejecutadas sin errores. Guardrails funcionando (492 suppressed). Motor listo para operacion.
