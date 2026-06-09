# BACKLOG — Driver Explainability Layer

**Date:** 2026-06-07
**Phase:** BACKLOG
**Registry:** LG-INFRA-R1.6

---

## OBJECTIVE

Permitir que un operador humano entienda por qué un conductor específico está en la lista operativa: qué reglas lo clasificaron, qué datos se usaron, y cuál es su trayectoria.

---

## SCOPE (Read-Only Only)

- ¿Por qué este driver está en PROGRAM_CHURN_PREVENTION?
- ¿Qué datos determinaron su eligibility?
- ¿Cuál fue su lifecycle_state / performance_state / retention_state al momento de clasificarse?
- ¿Qué fecha de snapshot se usó?
- ¿Qué policy_id/versión aplicó?

---

## DEPENDENCIES

| Dependency | Status |
|-----------|:---:|
| driver_state_snapshot | EXISTS |
| program_eligibility_daily | EXISTS |
| prioritized_opportunity_daily | EXISTS |
| driver_list_history | EXISTS (R1.5) |
| Program rule visibility | BACKLOG (R1.5) |

---

## PROPOSED ENDPOINTS

| Method | Path | Description |
|--------|------|-------------|
| GET | `/yego-lima-growth/drivers/{id}/explain` | Full explainability for one driver |
| GET | `/yego-lima-growth/drivers/{id}/lineage` | Data lineage for one driver |

---

## STATUS: BACKLOG

Do not implement until Control Foundation achieves real GO.

---

## FIRMA

```
BACKLOG REGISTRY ENTRY
Driver Explainability Layer
Registered: 2026-06-07
Phase: LG-INFRA-R1.6
Status: BACKLOG — NO IMPLEMENTAR
```
