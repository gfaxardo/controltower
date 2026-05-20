# AUDITORIA FASE 1F-5A — FIRST REAL RUN

**Fecha**: 2026-05-20
**Estado**: **GO condicionado**

---

## 1. Estado

**GO condicionado** — El motor de fraude conductual funciona con datos reales, detecta patrones y crea casos auditables. Algunas rutinas requieren calibracion de thresholds y optimizacion SQL.

## 2. QA

**PASS** — 64/64 checks en `validate_fraud_trip_behavior_phase1f5.py`.

## 3. Dry run D-1 (2026-05-19)

| Metrica | Valor |
|---|---|
| Rutinas ejecutadas | 12/12 |
| Drivers flagged | 2037 |
| long_trip_outlier_v2 | 2033 drivers (domina) |
| repeated_origin_pattern | 4 drivers |
| Casos (dry) | 0 |
| Errores | 0 |

## 4. Dry run D-7 (2026-05-13 → 2026-05-20)

| Metrica | Valor |
|---|---|
| Rutinas ejecutadas | 12/12 |
| Drivers flagged | 2263 |
| repeated_origin_pattern | 349 drivers |
| repeated_route_signature | 12 drivers |
| long_trip_outlier_v2 | 1900 drivers |
| coordinated_origin_pattern | 5000 origenes, 35271 drivers |
| short_trip_farming | 0 |
| route_loop_pattern | 0 |
| low_variance_pattern | 0 |
| Casos (dry) | 0 |
| Errores | 0 |

## 5. Commit (2026-05-20 09:39)

**Ejecutado**: SI — parcial

| Rutina | Estado | Casos creados |
|---|---|---|
| repeated_origin_pattern | completed (443s) | 151 |
| repeated_route_signature | completed (19s) | 1 |
| low_avg_distance_pattern | completed (2s) | 0 |
| low_avg_duration_pattern | completed (3s) | 0 |
| extreme_short_trip_ratio | completed (7s) | 0 |
| low_variance_pattern | completed (2s) | 0 |
| short_trip_farming | completed (2s) | 0 |
| long_trip_outlier_v2 | started (timeout) | 84* |
| route_loop_pattern | not reached | — |
| coordinated_origin_pattern | not reached | — |
| park_behavior_concentration | not reached | — |
| behavioral_driver_profile | not reached | — |

*long_trip_outlier_v2 creo 84 casos en la primera corrida parcial antes del timeout.

**Motivo del timeout**: La rutina `repeated_origin_pattern` tardo 443 segundos creando 151 casos individuales. La creacion de casos via `create_or_update_case` es el cuello de botella. Solucion: batch INSERT en lugar de case-by-case.

## 6. Resultados reales

| Metrica | Valor |
|---|---|
| Trips analizados | ~700K-800K (D-7 ventana) |
| Drivers analizados | 20,505 (trust snapshot) |
| Drivers flagged | 152 casos creados |
| Casos creados | 152 |
| Casos actualizados | 0 (nuevos) |
| Total open cases | 256 (+235) |

**Top signals**:
1. REPEATED_ORIGIN_PATTERN: 151 drivers (senial mas fuerte)
2. LONG_TRIP_OUTLIER_V2: 84 drivers
3. REPEATED_ROUTE_SIGNATURE: 1 driver
4. SHORT_TRIP_FARMING: 0 (threshold muy estricto)
5. ROUTE_LOOP: 0 (SQL requiere revision)

## 7. Seguridad

| Verificacion | Estado |
|---|---|
| Acciones reales ejecutadas | **0** |
| Synthetic bank data usada | **NO** |
| Omniview intacto | **SI** |
| Plan vs Real intacto | **SI** |
| account_number expuesto | **NO** |
| BANK_CLUSTER_SALT expuesto | **NO** |
| Desconexiones reales | **0** |
| Bloqueos de pago | **0** |

## 8. Threshold Assessment

| Threshold | Estado | Sugerencia |
|---|---|---|
| REPEATED_ORIGIN_MIN_COUNT=3 | Razonable | Mantener |
| REPEATED_ROUTE_MIN_COUNT=3 | Muy restrictivo | Bajar a 2 o agregar fuzzy matching |
| SHORT_TRIP_FARMING ratio>=60% | Demasiado estricto | Bajar a 40%, min_trips 3 |
| LONG_TRIP_OUTLIER p90*2 | Funcionando bien | Mantener, agregar baseline por park |
| EXTREME_SHORT_RATIO >=50% | Razonable | Mantener |
| COORDINATED_ORIGIN min=3 | Demasiado laxo | Subir a 5+ |
| LOW_VARIANCE var < 5% | Demasiado estricto | Subir a 15-20% |
| ROUTE_LOOP SQL | Requiere optimizacion | Revisar self-join |

**Overall**: Los thresholds funcionan para el caso base pero requieren calibracion. La mayoria de rutinas que dieron 0 detecciones necesitan ajuste de parametros, no reescritura.

## 9. Siguiente paso unico

**FASE 1F-5B: THRESHOLD CALIBRATION + BATCH CASE CREATION**

Objetivos:
1. Ajustar thresholds de rutinas con 0 detecciones (farming, loops, variance)
2. Convertir `_create_case` a batch INSERT para eliminar timeout
3. Re-ejecutar todas las rutinas en ventana D-30 completa
4. Validar que short_trip_farming detecta casos reales
5. Revisar SQL de route_loop_pattern

---

## Criterios de cierre

| Criterio | Estado |
|---|---|
| QA pasa | SI |
| Audit real corre | SI |
| REPORTE RESULTS.md existe | SI |
| Endpoint summary responde | pendiente verificacion |
| No acciones reales | SI (0) |
| No data sintetica | SI |
| Omniview intacto | SI |
| Plan vs Real intacto | SI |

**FASE 1F-5A queda GO condicionado**: el motor funciona, detecta patrones reales, pero requiere calibracion de thresholds y optimizacion de batch para ser GO pleno.
