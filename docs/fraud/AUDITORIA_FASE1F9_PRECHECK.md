# AUDITORIA FASE 1F-9 — AUTOCOBRO POLICY CALIBRATION & EXCEPTION REVIEW — PRECHECK

**Fecha:** 2026-05-21
**Branch:** `master`
**Policy versions:** `autocobro_v1_preview` (activa), `autocobro_v2_preview` (nueva)

---

## 1. GIT STATE

| Item | Valor |
|------|-------|
| Branch | `master` |
| F1F-8 files | Presentes (fraud_autocobro_eligibility_service, snapshot, endpoints) |
| Dirty changes | F1F-8 + F1F-9 files (fraud scope only) |

---

## 2. FASE 1F-8 CLOSURE VALIDATION

| Item | Estado |
|------|--------|
| fraud.autocobro_eligibility_snapshot | EXISTS (20,505 rows v1) |
| policy autocobro_v1_preview | EXISTS, enabled=true |
| Snapshot v1 tiene 20,505 drivers | YES |
| Endpoints preview responden | YES (tested in QA) |
| QA 19/19 PASS | YES |
| Acciones reales | 0 |

**F1F-8: GO — Cerrada.**

---

## 3. V1 DISTRIBUTION (baseline)

| Categoria | Count | % |
|-----------|-------|---|
| eligible | 13,190 | 64.3% |
| review_required | 4,443 | 21.7% |
| restricted | 34 | 0.2% |
| unknown | 2,838 | 13.8% |

**Bug identificado:** Default status = "eligible" causaba falsos positivos para drivers no clasificados.

---

## 4. V2 DISTRIBUTION (calibrada)

| Categoria | Count | % |
|-----------|-------|---|
| eligible | 5,606 | 27.3% |
| near_eligible | 0 | 0.0% |
| review_required | 1,763 | 8.6% |
| stale_profile | 2,680 | 13.1% |
| profile_gap | 0 | 0.0% |
| restricted | 38 | 0.2% |
| unknown | 2,838 | 13.8% |
| unclassified | 7,580 | 37.0% |

---

## 5. V1 vs V2 DELTA

| Cambio | V1 | V2 | Delta | Explicacion |
|--------|----|----|-------|-------------|
| eligible | 13,190 | 5,606 | -7,584 | Falsos positivos corregidos (default bug) |
| review_required | 4,443 | 1,763 | -2,680 | R5 movido a stale_profile |
| stale_profile | N/A | 2,680 | NEW | Trusted historicos sin actividad D-30 |
| unclassified | N/A | 7,580 | NEW | new_or_unproven con 3-29 trips (zona gris) |
| restricted | 34 | 38 | +4 | Refinamiento de reglas X3 |
| unknown | 2,838 | 2,838 | 0 | Sin cambios |

---

## 6. VEREDICT PRECHECK

**GO para FASE 1F-9.**
