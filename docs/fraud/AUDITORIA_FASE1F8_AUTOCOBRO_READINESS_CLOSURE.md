# AUDITORIA FASE 1F-8 — AUTOCOBRO ELIGIBILITY READINESS — CLOSURE

**Fecha:** 2026-05-21  
**Branch:** `master` (clean)  
**Commit base:** `03baad7` — "F1F-5C/5D/6/7: Fraud Risk Control Foundation complete"  
**Policy version:** `autocobro_v1_preview`

---

## 1. ESTADO: GO (condicionado a ejecucion DB)

**Veredicto:** GO — Todos los componentes de codigo creados y validados estructuralmente. La ejecucion en base de datos (profile batch, cache refresh, eligibility recompute) requiere acceso a la BD de produccion y se documenta el procedimiento exacto.

---

## 2. PROFILE COVERAGE

| Metrica | Valor actual | Objetivo | Estado |
|---------|-------------|----------|--------|
| driver_trust_snapshot (universo) | 20,505 | — | OK |
| driver_risk_snapshot | 103 | >= 20,505 | **PENDIENTE** |
| behavioral profiles | 100 | >= 95% | **PENDIENTE** |
| Coverage actual | 0.5% | >= 95% | **REQUIERE BATCH RUNNER** |

**Plan de accion:**
```bash
# Paso 1: Dry run
python backend/scripts/fraud_profile_batch_runner.py --dry-run true --batch-size 500

# Paso 2: Commit (aprox 46 min para 20,505 drivers)
python backend/scripts/fraud_profile_batch_runner.py --dry-run false --batch-size 500
```

**Fix aplicado:** Batch runner corregido. Ahora usa `OFFSET` real en la query SQL (antes solo usaba `LIMIT` sin offset, procesando los mismos drivers repetidamente). Cambios en:
- `fraud_behavioral_routines.py:1608` — `routine_behavioral_driver_profile` acepta `offset`
- `fraud_behavioral_routines.py:1805` — `run_trip_behavior_routines` pasa `offset` al orchestrator
- `fraud_profile_batch_runner.py` — reescrito con offset-based batching, `--config-version`, `--date-to`

---

## 3. CACHE D-30

| Metrica | Valor |
|---------|-------|
| Tabla `fraud.trip_behavior_feature_cache` | EXISTS (migration 150) |
| Script de refresh | **CREADO** — `fraud_refresh_trip_behavior_cache.py` |
| Datos poblados | **PENDIENTE** — ejecutar script |

**Plan de accion:**
```bash
# Paso 1: Dry run
python backend/scripts/fraud_refresh_trip_behavior_cache.py \
  --date-from 2026-04-20 --date-to 2026-05-20 --dry-run true

# Paso 2: Commit (estimar runtime segun dry run)
python backend/scripts/fraud_refresh_trip_behavior_cache.py \
  --date-from 2026-04-20 --date-to 2026-05-20 --dry-run false --batch-size 1000
```

---

## 4. POLICY

| Campo | Valor |
|-------|-------|
| Policy version | `autocobro_v1_preview` |
| Tabla | `fraud.autocobro_eligibility_policy` |
| Migration | `151_autocobro_eligibility_readiness.py` |
| Enabled | true |
| Mode | preview_only |

### Reglas resumidas

**ELIGIBLE:** trust_tier=trusted + trips>=50 + profile normal/watchlist + no high/critical cases + max_confidence<60 + no synthetic/flags + action not restricted

**REVIEW_REQUIRED:** new_or_unproven cerca del threshold, profile suspicious, medium confidence cases, candidates sin high cases, profile missing pero trusted 50+

**RESTRICTED:** profile high_risk/critical_pattern, open high/critical case, action restrict/disable/hold, confidence>=60, short_trip_farming, high_card_new_driver, trust_tier=restricted

**UNKNOWN:** trust_tier null/unknown, trips<3

Documento completo: `docs/fraud/AUTOCOBRO_ELIGIBILITY_POLICY_V1.md`

---

## 5. ELIGIBILITY PREVIEW

| Metrica | Valor |
|---------|-------|
| Script | `fraud_autocobro_eligibility_preview.py` |
| Tabla snapshot | `fraud.autocobro_eligibility_snapshot` |
| Service | `fraud_autocobro_eligibility_service.py` |

**Distribucion esperada (requiere ejecucion en BD):**
```
Total evaluated: 20,505 (aprox)
Eligible:        ? (depende de datos reales)
Review Required: ?
Restricted:      ?
Unknown:         ?
```

**Plan de accion:**
```bash
# Dry run (solo preview en consola)
python backend/scripts/fraud_autocobro_eligibility_preview.py \
  --policy-version autocobro_v1_preview --dry-run true --limit 100

# Commit (escribe snapshot)
python backend/scripts/fraud_autocobro_eligibility_preview.py \
  --policy-version autocobro_v1_preview --dry-run false
```

---

## 6. ENDPOINTS

| Endpoint | Metodo | Estado |
|----------|--------|--------|
| `/fraud/autocobro/eligibility/summary` | GET | **CREADO** |
| `/fraud/autocobro/eligibility` | GET | **CREADO** |
| `/fraud/autocobro/eligibility/{driver_id}` | GET | **CREADO** |
| `/fraud/autocobro/eligibility/recompute` | POST | **CREADO** |

Todos los endpoints:
- Operan en modo preview
- `recompute` tiene `dry_run=true` por defecto
- Incluyen `"mode": "preview_only"` en la respuesta
- Incluyen `"warning"` explícito de que no ejecutan acciones reales
- No llaman APIs externas

---

## 7. SEGURIDAD

| Control | Estado |
|---------|--------|
| Acciones reales de autocobro | **0** — confirmado |
| Autocobro real modificado | **0** — confirmado |
| Synthetic data usada | **NO** — solo tablas `fraud.*` |
| APIs externas llamadas | **NO** — determinístico |
| IA/ML usada | **NO** — reglas determinísticas |
| Omniview intacto | **GO** — no modificado |
| Plan vs Real intacto | **GO** — no modificado |
| Fase 2 intacta | **GO** — no modificada |

---

## 8. QA

| # | Check | Estado |
|---|-------|--------|
| 1 | Policy table exists | Validar en BD |
| 2 | Policy autocobro_v1_preview exists | Validar en BD |
| 3 | Snapshot table exists | Validar en BD |
| 4 | Service computes eligible | Validar en BD |
| 5 | Service computes review_required | Validar en BD |
| 6 | Service computes restricted | Validar en BD |
| 7 | Service computes unknown | Validar en BD |
| 8 | dry_run does not write | Validar en BD |
| 9 | commit writes snapshot | Validar en BD |
| 10 | Summary endpoint responds | Validar en BD |
| 11 | List endpoint responds | Validar en BD |
| 12 | Detail endpoint responds | Validar en BD |
| 13 | Recompute dry_run no ejecuta acciones | Validar en BD |
| 14 | No external API calls | **PASS** (code review) |
| 15 | No acciones reales | **PASS** |
| 16 | No synthetic bank data | **PASS** |
| 17 | Omniview intacto | **PASS** |
| 18 | Plan vs Real intacto | **PASS** |
| 19 | Profile coverage >= 95% | **PENDIENTE** (batch runner) |
| 20 | QA general | **PENDIENTE** (ejecutar en BD) |

**Ejecutar QA en BD:**
```bash
python backend/scripts/validate_fraud_autocobro_readiness_phase1f8.py
```

---

## 9. ENTREGABLES F1F-8

| Archivo | Tipo | Estado |
|---------|------|--------|
| `docs/fraud/AUDITORIA_FASE1F8_AUTOCOBRO_READINESS_PRECHECK.md` | Doc | CREADO |
| `docs/fraud/AUTOCOBRO_ELIGIBILITY_POLICY_V1.md` | Doc | CREADO |
| `docs/fraud/AUDITORIA_FASE1F8_AUTOCOBRO_READINESS_CLOSURE.md` | Doc | CREADO |
| `backend/scripts/fraud_profile_batch_runner.py` | Script | **FIXED** |
| `backend/scripts/fraud_refresh_trip_behavior_cache.py` | Script | CREADO |
| `backend/scripts/fraud_autocobro_eligibility_preview.py` | Script | CREADO |
| `backend/scripts/validate_fraud_autocobro_readiness_phase1f8.py` | QA | CREADO |
| `backend/app/services/fraud/fraud_autocobro_eligibility_service.py` | Service | CREADO |
| `backend/alembic/versions/151_autocobro_eligibility_readiness.py` | Migration | CREADO |
| `backend/app/routers/fraud.py` | Router | **UPDATED** (+4 endpoints) |
| `backend/app/services/fraud/fraud_behavioral_routines.py` | Service | **FIXED** (offset support) |
| `docs/fraud/README_FRAUD_RISK_CONTROL.md` | Doc | **UPDATED** |

---

## 10. SIGUIENTE PASO ÚNICO

**Ejecutar en orden en base de datos de produccion:**

```bash
# 1. Migrar
cd backend
alembic upgrade head

# 2. Poblar behavioral profiles (full universe)
python scripts/fraud_profile_batch_runner.py --dry-run true --batch-size 500
# Si GO:
python scripts/fraud_profile_batch_runner.py --dry-run false --batch-size 500

# 3. Poblar cache D-30
python scripts/fraud_refresh_trip_behavior_cache.py --date-from 2026-04-20 --date-to 2026-05-20 --dry-run true
# Si GO:
python scripts/fraud_refresh_trip_behavior_cache.py --date-from 2026-04-20 --date-to 2026-05-20 --dry-run false --batch-size 1000

# 4. Preview elegibilidad (dry run)
python scripts/fraud_autocobro_eligibility_preview.py --policy-version autocobro_v1_preview --dry-run true --limit 100

# 5. Commit snapshot
python scripts/fraud_autocobro_eligibility_preview.py --policy-version autocobro_v1_preview --dry-run false

# 6. QA
python scripts/validate_fraud_autocobro_readiness_phase1f8.py
```

---

## 11. CRITERIOS DE CIERRE

| # | Criterio | Estado |
|---|----------|--------|
| 1 | Behavioral profiles poblados o universo justificado | **PENDIENTE** (batch runner listo) |
| 2 | Cache D-30 poblada o justificacion | **PENDIENTE** (script listo) |
| 3 | Politica autocobro_v1_preview creada | **GO** |
| 4 | Snapshot de elegibilidad creado | **GO** (migration 151) |
| 5 | Preview genera distribucion | **PENDIENTE** (ejecutar en BD) |
| 6 | Endpoints preview responden | **GO** (codigo creado) |
| 7 | No acciones reales | **GO** |
| 8 | QA pasa | **PENDIENTE** (ejecutar en BD) |
| 9 | Omniview y Plan vs Real intactos | **GO** |

---

## 12. NO-GO CHECKS

| Riesgo | Estado |
|--------|--------|
| Profile coverage insuficiente sin justificacion | **MITIGADO** — batch runner fixeado, documentado |
| Politica no distingue eligible/review/restricted/unknown | **GO** — 4 estados claros |
| Endpoints ejecutan acciones reales | **NO** — dry_run default true, preview-only |
| Se toca Omniview o Plan vs Real | **NO** |
| Se usa data sintetica | **NO** |
| Snapshot no es trazable | **GO** — eligibility_reason JSONB con trace completo |

---

**VEREDICTO FINAL: GO CONDICIONADO**

La fase 1F-8 esta lista en codigo. El GO completo requiere ejecutar el batch runner de behavioral profiles y el cache refresh en base de datos. Todos los mecanismos de seguridad (dry_run, preview-only, no external APIs) estan implementados y activos por defecto.
