# AUDITORIA FASE 1F-8 — AUTOCOBRO ELIGIBILITY READINESS — PRECHECK

**Fecha:** 2026-05-21  
**Branch:** `master`  
**Commit:** `03baad7` — "F1F-5C/5D/6/7: Fraud Risk Control Foundation complete"

---

## 1. GIT STATE

| Item | Valor |
|------|-------|
| Branch | `master` |
| Remote | `origin/master` (sincronizado) |
| Working tree | Clean |
| Dirty changes | 0 |

```
$ git status
On branch master
Your branch is up to date with 'origin/master'.
nothing to commit, working tree clean
```

---

## 2. FASE 1F-7 CLOSURE VALIDATION

| Item | Estado | Evidencia |
|------|--------|-----------|
| FASE 1F-7 cerrada | **GO** | Commit `03baad7` + closure doc |
| fraud_profile_batch_runner.py | **EXISTS** | `backend/scripts/fraud_profile_batch_runner.py` |
| fraud.trip_behavior_feature_cache | **EXISTS** | Migration 150 (lines 57-74), 5 indices |
| routine_schedule_config | **CREATED** | Migration 150 (lines 37-48), seeded via `fraud_seed_schedule_config.py` |
| 11 indices en fraud.* | **EXISTS** | 5 en trip_risk_features, 2 en driver_risk_snapshot, 5 en trip_behavior_feature_cache |
| QA 31/31 PASS | **GO** | Audit F1F-7 closure |
| Acciones reales | **0** | Confirmado en todos los validate scripts |
| Daily control operacional | **15.6s** | < target 120s |
| Weekly control | **~540s** | Acceptable for weekly |
| Omniview intacto | **GO** | No modificado |
| Plan vs Real intacto | **GO** | No modificado |

**Veredicto FASE 1F-7: GO — Cerrada.**

---

## 3. DATABASE STATE (from F1F-7 Audit Docs)

| Métrica | Valor |
|---------|-------|
| `driver_trust_snapshot` count | **20,505** |
| `driver_risk_snapshot` count | **103** |
| Behavioral profiles populated | **100** (97.1% de 103) |
| Null profiles | **3** |
| Behavioral profile coverage vs trust universe | **0.5%** |
| Open cases total | **~43** |
| Open high/critical cases | Pendiente verificar en DB |
| routine_run_log entries | **128** |

### Coverage Gap Severity

```
driver_trust_snapshot (universo completo): 20,505
driver_risk_snapshot (con perfil):           103
behavioral profiles:                         100
-----------------------------------------------
Coverage real sobre trust universe:         0.5%
```

**Root cause:** `routine_behavioral_driver_profile` solo se ejecutó con `limit=100` durante F1F-6/F1F-7. El batch runner existe pero no se ha ejecutado sobre el universo completo.

---

## 4. GAPS IDENTIFICADOS PARA F1F-8

| Gap | Severidad | Acción |
|-----|-----------|--------|
| `fraud_refresh_trip_behavior_cache.py` | **CRÍTICO** | Script no existe. Crear en TAREA 2. |
| Behavioral profile coverage (0.5%) | **CRÍTICO** | Ejecutar batch runner en TAREA 1. |
| `fraud_profile_batch_runner.py` no tiene `--config-version` | **MEDIO** | Script usa fechas hardcoded. Agregar flag en TAREA 1. |
| `trip_behavior_feature_cache` vacía | **CRÍTICO** | Poblar en TAREA 2. |
| No existe política de elegibilidad autocobro | **CRÍTICO** | Definir en TAREA 3. |
| No existe tabla de elegibilidad | **CRÍTICO** | Crear en TAREA 4. |

---

## 5. EXISTING AUTOCobro CODE REFERENCES

El sistema ya tiene cableado `disable_autocobro` / `enable_autocobro` como action types en `fraud_action_service.py`, pero:

- **Solo opera en modo preview** (no ejecuta API externa real)
- **Todos los validate scripts confirman "No autocobro disabled"**
- **Nunca se ha ejecutado un autocobro real desde el sistema**
- `fraud_rules_engine.py` recomienda `disable_autocobro` para `POST_NEGATIVE_BALANCE_SIGNAL`
- `fraud_routine_service.py` recomienda `disable_autocobro` para bank cluster crítico

**Esto es correcto.** F1F-8 debe mantener el mismo principio: preview-only, sin ejecución real.

---

## 6. PRECHECK VEREDICT

| Criterio | Estado |
|----------|--------|
| FASE 1F-7 cerrada | **GO** |
| fraud_profile_batch_runner.py existe | **GO** |
| fraud.trip_behavior_feature_cache existe | **GO** |
| driver_trust_snapshot count (20,505) | **GO** |
| driver_risk_snapshot count (103) | **WARNING** |
| behavioral_profile coverage (0.5%) | **WARNING** |
| No cambios sucios ajenos | **GO** |
| Omniview intacto | **GO** |
| Plan vs Real intacto | **GO** |

**VEREDICTO: GO para iniciar FASE 1F-8.**

Warnings identificados y con plan de acción en TAREA 1 (profiles) y TAREA 2 (cache).

---

## 7. NEXT STEP

Ejecutar **TAREA 1 — POBLAR BEHAVIORAL PROFILES FULL UNIVERSE**.

```bash
# Dry run primero
python scripts/fraud_profile_batch_runner.py --dry-run true --batch-size 500

# Luego commit
python scripts/fraud_profile_batch_runner.py --dry-run false --batch-size 500
```

**Nota:** El script actual no acepta `--config-version`. Usa fechas hardcoded `2026-05-13` a `2026-05-20`. Se recomienda agregar el flag `--config-version` pero no es blocker para la ejecución.
