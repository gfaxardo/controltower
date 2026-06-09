# BACKLOG — Midnight Rollover Certification

**Date:** 2026-06-07
**Phase:** BACKLOG (HARDENING TRACKING)
**Registry:** LG-INFRA-R1.6

---

## OBJECTIVE

Certificar que al cambiar el día operacional el sistema:
- Detecta la nueva fecha cerrada
- Genera nuevas capas base (snapshot, eligibility, prioritized, queue)
- Genera serving facts frescos
- Preserva listas del día anterior
- No pisa exporatdos
- Transiciona today_action_date correctamente

---

## DEPENDENCIES

| Dependency | Status |
|-----------|:---:|
| Daily closed pipeline | EXISTS |
| Serving facts generator | EXISTS |
| Scheduler midnight detection | EXISTS |
| Catch-up logic (R1.5) | EXISTS |
| Historical list trace (R1.5) | EXISTS |

---

## TEST SCENARIO

### Scenario: Day N → Day N+1

1. Day N operational_data_date = 2026-06-05, today_action_date = 2026-06-06
2. Yango API reports new closed data for 2026-06-06
3. Scheduler detects new date → triggers daily closed pipeline OR catch-up
4. New layers generated for 2026-06-06
5. Serving facts regenerated
6. Previous day's queue preserved in driver_list_history

### Success Criteria

- driver_state_snapshot for new date > 0 rows
- program_eligibility for new date > 0 rows
- prioritized_opportunity for new date > 0 rows
- serving_facts for new date = 8/8
- Previous date's historical list intact
- No EXPORTED rows overwritten

---

## STATUS: PENDING CERTIFICATION

This backlog tracks the certification criteria. Actual certification evidence lives in:
`docs/lima_growth/LG_INFRA_R1_6_MIDNIGHT_ROLLOVER_SCHEDULER_RELIABILITY_CERTIFICATION.md`

---

## FIRMA

```
BACKLOG REGISTRY ENTRY
Midnight Rollover Certification
Registered: 2026-06-07
Phase: LG-INFRA-R1.6
Status: PENDING CERTIFICATION
```
