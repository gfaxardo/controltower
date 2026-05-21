# AUDITORIA FASE 1F-7 — BEHAVIORAL PROFILE UNIVERSE

**Fecha**: 2026-05-20
**Estado**: **CONDICIONADO — batch runner listo, ejecucion pendiente**

---

## 1. Coverage Actual

| Metrica | Valor |
|---|---|
| driver_trust_snapshot (full universe) | 20,505 |
| driver_risk_snapshot | 103 |
| with behavioral_profile_class | 100 |
| null profiles | 3 |
| **Real coverage** | **0.5%** |

Los 100 profiles son de `limit=100`. Cubren solo los primeros 100 drivers del query.

## 2. Batch Runner

**Script**: `backend/scripts/fraud_profile_batch_runner.py`

| Parametro | Valor |
|---|---|
| `--dry-run` | true/false |
| `--batch-size` | 500 |
| `--resume-from` | N (offset) |

Estimado: 41 batches x ~67s = ~46 minutos para universo completo de 20,505 drivers.

## 3. Ejecucion recomendada

```bash
# Dry run primero
python scripts/fraud_profile_batch_runner.py --dry-run true --batch-size 100

# Luego commit en batches
python scripts/fraud_profile_batch_runner.py --dry-run false --batch-size 500 --resume-from 0
```

## 4. Justificacion de baja cobertura

- El `limit=100` es intencional para pruebas acotadas
- El batch size 500 permite poblacion gradual sin timeout
- Para operacion en produccion se necesita ejecutar el batch runner completo

## 5. Veredicto

**GO condicionado** — Script listo. Ejecutar `fraud_profile_batch_runner.py --dry-run false --batch-size 500` para alcanzar cobertura completa.
