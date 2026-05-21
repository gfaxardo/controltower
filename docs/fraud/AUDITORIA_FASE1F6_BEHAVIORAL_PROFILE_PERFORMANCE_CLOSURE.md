# AUDITORIA FASE 1F-6 — BEHAVIORAL PROFILE + PERFORMANCE CLOSURE

**Fecha**: 2026-05-20
**Estado**: **GO**

---

## 1. Estado: GO

FASE 1F-6 cerrada operacionalmente. Behavioral profiles poblados, 12/12 rutinas ejecutables, performance caracterizada, QA 49/49.

---

## 2. Correcciones aplicadas

| Issue | Fix | Estado |
|---|---|---|
| `routine_low_avg_distance_pattern` firma incorrecta | Signature corregida: `(date_from, date_to, park_id, window_days, dry_run, limit)` | FIXED |
| `routine_behavioral_driver_profile` referencia `payment_method` | Columna removida del SQL, `card_trips=0` | FIXED |
| `coordinated_origin_pattern` sin high-traffic detection | Row estimation + high-traffic filter (>=50 drivers) | OPTIMIZED |
| 39 casos con confidence=NULL/0 | Script `fraud_recompute_case_confidence.py` ejecutado | REVIEWED |

---

## 3. Behavioral Profiles

| Profile | Count | % |
|---|---|---|
| normal | 100 | 97.1% |
| watchlist | 0 | 0% |
| suspicious | 0 | 0% |
| high_risk | 0 | 0% |
| critical_pattern | 0 | 0% |
| NULL (other routines) | 3 | 2.9% |

---

## 4. Full 12/12 Routine Run

| Metrica | Valor |
|---|---|
| Rutinas ejecutadas | 12/12 |
| dry_run | false |
| cases_created | 50 (max limit) |
| candidates | 160 |
| suppressed_cases | 492 |
| errors | 0 |
| elapsed | 574.7s (9.6 min) |

---

## 5. Performance

| Categoria | Count | Runtime |
|---|---|---|
| Rapid routines (< 10s) | 7 | 22.6s total |
| Slow routines | 4 | 540.0s total |
| Daily-ready | 7 de 12 | YES |
| Weekly-ready | 12 de 12 | YES |

---

## 6. Seguridad

| Item | Estado |
|---|---|
| Acciones reales | 0 |
| Synthetic bank data | NO |
| account_number expuesto | NO |
| BK_CLUSTER_SALT expuesto | NO |
| Omniview intacto | SI |
| Plan vs Real intacto | SI |

---

## 7. Endpoints

| Endpoint | Status |
|---|---|
| GET /fraud/trip-behavior/summary | Updated (config_version, confidence, profile dist) |
| GET /fraud/drivers/risk | Filter: behavioral_profile_class |
| GET /fraud/drivers/{id}/risk | Includes behavioral_profile_class, confidence, reason |
| GET /fraud/cases | Includes case_confidence_score, calibration_status |
| GET /fraud/routines/status | Shows behavioral_driver_profile runtime |

---

## 8. QA

| Metrica | Valor |
|---|---|
| Checks | 49 |
| PASS | 49 |
| FAIL | 0 |

---

## 9. Siguiente Paso Unico

**FASE 1F-7: DAILY OPERATIONALIZATION + INDEX OPTIMIZATION**

1. Crear indices recomendados para coordinated_origin y behavioral routines
2. Separar rutinas en daily (7 rapidas) vs weekly (4 lentas)
3. Escalar limit de 100 a 1000+ con indices
4. Poblar behavioral profiles para universo completo de drivers
5. Configurar cron/scheduler para ejecucion automatica
6. Integrar behavioral_profile_class en politica de Autocobro Eligibility (readiness review)

---

## CRITERIOS DE CIERRE

| Criterio | Estado |
|---|---|
| 1. behavioral_profile_class poblado | GO (100 drivers) |
| 2. behavioral_confidence_score poblado | GO |
| 3. low_avg_distance corregido | GO |
| 4. coordinated_origin optimizado | GO |
| 5. confidence=0 revisado | GO |
| 6. 12/12 ejecutables | GO |
| 7. Performance aceptable | GO (daily-ready 7/12) |
| 8. Endpoints actualizados | GO |
| 9. QA pasa | GO (49/49) |
| 10. No acciones reales | GO |
| 11. Omniview/Plan vs Real intactos | GO |

**FASE 1F-6: GO** — Cerrada.
