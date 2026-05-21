# AUDITORIA FASE 1F-9 — AUTOCOBRO POLICY CALIBRATION & EXCEPTION REVIEW — CLOSURE

**Fecha:** 2026-05-21
**Policy v1:** autocobro_v1_preview
**Policy v2:** autocobro_v2_preview
**Veredicto:** GO

---

## 1. ESTADO: GO

FASE 1F-9 cerrada. Política autocobro calibrada, excepciones auditadas, v2 simulada y validada.

---

## 2. V1 EXCEPTION AUDIT

| Categoría | Count | % | Acción F1F-9 |
|-----------|-------|---|-------------|
| eligible | 13,190 | 64.3% | **Bug: 7,584 falsos positivos** (default status) |
| review_required | 4,443 | 21.7% | R5 movido a stale_profile |
| restricted | 34 | 0.2% | Todos legítimos (open high cases) |
| unknown | 2,838 | 13.8% | Todos U3 (<3 trips), correcto |

---

## 3. R5 RESOLUTION

| Sub-type | Count | V2 Status |
|----------|-------|-----------|
| R5A (no risk snapshot) | 2,680 | stale_profile |
| R5B (in risk snapshot, no profile) | 0 | profile_gap |

**Decisión:** R5A drivers son históricos sin actividad D-30. No son elegibles ni restringidos. Clasificados como `stale_profile` — requieren actividad reciente para recalificar.

---

## 4. U3 RESOLUTION

| Trips | Trust | Count |
|-------|-------|-------|
| 1 | new_or_unproven | 1,793 |
| 2 | new_or_unproven | 1,045 |

**Decisión:** Todos los unknown son drivers con 1-2 viajes. Clasificación correcta. Sin cambios necesarios.

---

## 5. R1 RESOLUTION

| Trip Bucket | Count |
|------------|-------|
| 30-39 | 1,011 |
| 40-49 | 751 |

**Decisión:** R1 se mantiene como review_required. No hay near_eligible (todos son new_or_unproven, no trusted). Correcto.

---

## 6. RESTRICTED REVIEW

| Métrica | V1 | V2 |
|---------|-----|-----|
| Total restricted | 34 | 38 |
| Triggered by X2 (high case) | 34 | 34 |
| Triggered by X3 (critical case) | 0 | 4 |
| False positives | 0 | 0 |
| Park concentration (2 parks) | 83% | 83% |

**Decisión:** Todos los restricted son legítimos. V2 agregó 4 casos con critical_case_count > 0 (antes no detectados).

---

## 7. V2 DISTRIBUTION

| Categoría | Count | % |
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

## 8. V1 vs V2 DELTA

| Cambio | Delta | Causa |
|--------|-------|-------|
| eligible | -7,584 | Bug fix: default status ya no es "eligible" |
| review_required | -2,680 | R5 movido a stale_profile |
| stale_profile | +2,680 | Nuevo: trusted sin actividad D-30 |
| unclassified | +7,580 | Nuevo: catch-all para new_or_unproven 3-29 trips |
| restricted | +4 | X3: critical_case_count detection |

---

## 9. SAMPLE VALIDATION (V2)

### Eligible (5,606)
- trusted + >=50 trips + normal/watchlist profile + no high/critical cases + clean flags
- 100% cumplen las 10 reglas de elegibilidad

### Stale Profile (2,680)
- trusted + >=50 trips + NO risk snapshot (sin actividad D-30)
- Históricos, posiblemente inactivos

### Unclassified (7,580)
- new_or_unproven + 3-29 trips
- Zona gris: ni elegibles ni restringidos, necesitan más historial
- 72% sin behavioral profile, 28% con normal

### Restricted (38)
- 34 con high case, 4 con critical case
- 0 falsos positivos

---

## 10. ENDPOINTS

| Endpoint | V2 Support |
|----------|-----------|
| GET /fraud/autocobro/eligibility/summary?policy_version=autocobro_v2_preview | YES |
| GET /fraud/autocobro/eligibility?policy_version=v2&status=stale_profile | YES |
| GET /fraud/autocobro/eligibility/{driver_id}?policy_version=v2 | YES |
| POST /fraud/autocobro/eligibility/recompute?policy_version=v2 | YES |

---

## 11. SEGURIDAD

| Control | Estado |
|---------|--------|
| Acciones reales | 0 |
| Autocobro real modificado | 0 |
| APIs externas | 0 |
| Data sintética | 0 |
| Omniview | Intacto |
| Plan vs Real | Intacto |

---

## 12. QA

**17/17 PASS**

---

## 13. ENTREGABLES

| Archivo | Tipo |
|---------|------|
| docs/fraud/AUDITORIA_FASE1F9_PRECHECK.md | Doc |
| docs/fraud/AUDITORIA_FASE1F9_EXCEPTION_DISTRIBUTION.md | Doc |
| docs/fraud/AUDITORIA_FASE1F9_R5_TRUSTED_WITHOUT_PROFILE.md | Doc |
| docs/fraud/AUDITORIA_FASE1F9_R1_NEAR_TRUSTED.md | Doc |
| docs/fraud/AUDITORIA_FASE1F9_RESTRICTED_REVIEW.md | Doc |
| docs/fraud/AUDITORIA_FASE1F9_POLICY_V2_SIMULATION.md | Doc |
| docs/fraud/AUDITORIA_FASE1F9_AUTOCOBRO_POLICY_CALIBRATION_CLOSURE.md | Doc |
| backend/scripts/fraud_autocobro_exception_audit.py | Script |
| backend/scripts/fraud_seed_policy_v2.py | Script |
| backend/scripts/validate_fraud_autocobro_policy_calibration_phase1f9.py | QA |
| backend/app/services/fraud/fraud_autocobro_eligibility_service.py | Service (updated) |
| backend/scripts/fraud_autocobro_eligibility_preview.py | Script (updated) |

---

## 14. SIGUIENTE PASO ÚNICO

**FASE 1F-10 — ACTION ENGINE PREVIEW (si se autoriza)**
- Crear contratos de integración externa (API autocobro)
- Ejecutar solo en modo preview/dry-run
- Sin modificar estado real de autocobro
- Requiere autorización explícita del equipo de operaciones
