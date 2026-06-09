# LG-R2.10 — Driver Explainability Discovery

**Date:** 2026-06-07
**Phase:** LG-INFRA-R1.7 Discovery
**Status:** DISCOVERY ONLY — NO IMPLEMENTATION

---

## QUESTION

¿Podemos explicar exactamente por qué un conductor cayó en un programa?

---

## ANSWER: PARTIAL

---

## WHAT EXISTS TODAY

### Per-Driver State (driver_state_snapshot)

Cada conductor tiene 3 dimensiones de estado:

| Dimensión | Valores |
|-----------|---------|
| lifecycle_state | PROSPECT, REGISTERED, ACTIVATED, EARLY_LIFE, ESTABLISHED, REACTIVATED, CHURNED |
| performance_state | NO_TRIPS, LOW, MEDIUM, TARGET, HIGH |
| retention_state | HEALTHY, WATCHLIST, AT_RISK, CHURN_RISK |

### Program Assignment (program_eligibility_daily)

Cada conductor es asignado a uno o más programas basado en su snapshot state:

| Programa | Criterio Principal |
|----------|-------------------|
| PROGRAM_CHURN_PREVENTION | retention_state = CHURN_RISK, decline evidence |
| PROGRAM_14_90 | Inactivo 14-90 días, lifecycle = CHURNED |
| PROGRAM_ACTIVE_GROWTH | Activo, por debajo de target semanal |
| PROGRAM_HIGH_VALUE_RECOVERY | Alto valor histórico, recientemente inactivo |

### Scored & Ranked (prioritized_opportunity_daily)

Cada conductor recibe:
- `opportunity_score` — compuesto de impact_score, urgency_score, probability_score
- `final_rank` — posición en la lista priorizada
- `is_actionable_today` — dentro del capacity cap (500)
- `exclusion_reason` — razón si no es accionable

---

## WHAT CAN BE EXPLAINED TODAY

| Pregunta | ¿Explicable? | Evidencia |
|----------|:---:|-----------|
| ¿En qué programa está? | YES | `program_eligibility_daily.program_code` |
| ¿Cuál es su lifecycle_state? | YES | `driver_state_snapshot.lifecycle_state` |
| ¿Cuál es su retention_state? | YES | `driver_state_snapshot.retention_state` |
| ¿Cuál es su performance_state? | YES | `driver_state_snapshot.performance_state` |
| ¿Cuántos viajes hizo esta semana? | YES | `completed_orders_week` |
| ¿Cuál es su score final? | YES | `prioritized_opportunity_daily.opportunity_score` |
| ¿Qué posición tiene? | YES | `prioritized_opportunity_daily.final_rank` |
| ¿Por qué EXACTAMENTE está en CHURN_PREVENTION? | PARTIAL | Sabemos que `retention_state=CHURN_RISK` pero no la regla exacta que activó |
| ¿Qué threshold se aplicó? | NO | Thresholds están en código, no en una tabla consultable |
| ¿Qué datos históricos se usaron? | PARTIAL | `avg_orders_4w`, `best_week_12w` existen pero no linkeados a la regla |

---

## WHAT IS MISSING

1. **Rule-to-driver traceability**: No hay una tabla que diga "Driver X está en Programa Y porque la regla Z se activó con valor V contra threshold T"
2. **Parameter visibility**: Los thresholds (critical=50, low=70, etc.) están en `opportunity_policy_config` pero no expuestos por driver
3. **Score decomposition**: El `opportunity_score` es compuesto (impact*0.4 + urgency*0.3 + probability*0.3) pero los componentes individuales no se muestran
4. **Historical context**: Los promedios históricos existen pero no se vinculan a la decisión de clasificación

---

## PATH TO YES

Para llegar a YES se necesita:

1. **Rule audit table**: `growth.yego_lima_driver_program_rule_audit` que registre para cada driver/programa: rule_name, parameter_name, parameter_value, threshold, matched (boolean)
2. **Explainability endpoint**: `GET /drivers/{id}/explain` que devuelva el desglose completo
3. **Score decomposition**: Exponer impact_score, urgency_score, probability_score separados

---

## VEREDICT

```
PARTIAL — Evidencia existe pero no está estructurada para explicabilidad.
Se puede responder QUÉ pero no POR QUÉ con trazabilidad completa.
```

---

## FIRMA

```
DRIVER EXPLAINABILITY DISCOVERY
LG-INFRA-R1.7
Status: DISCOVERY COMPLETE — NO IMPLEMENTATION
```
