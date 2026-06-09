# LG-R2.11 — Program Explainability Discovery

**Date:** 2026-06-07
**Phase:** LG-INFRA-R1.7 Discovery
**Status:** DISCOVERY ONLY — NO IMPLEMENTATION

---

## QUESTION

¿Podemos explicar la regla, score, threshold, criterio y prioridad para cada programa?

---

## ANSWER: PARTIAL

---

## WHAT EXISTS TODAY

### Program Rules (Embedded in Code)

Las reglas están en `yego_lima_program_eligibility_service.py`, no en una tabla consultable:

| Programa | Regla | Threshold | Ubicación |
|----------|-------|-----------|-----------|
| CHURN_PREVENTION | retention_state = CHURN_RISK | N/A | Código línea ~120 |
| CHURN_PREVENTION | decline detection (avg_4w vs current) | decline > 30% | Código |
| 14_90 | last_order_at 14-90 days ago | 14 < days < 90 | Código |
| 14_90 | lifecycle = CHURNED or REACTIVATED | N/A | Código |
| ACTIVE_GROWTH | active_flag = true | N/A | Código |
| ACTIVE_GROWTH | trips_per_hour < 0.5 | 0.5 | Código |
| ACTIVE_GROWTH | below weekly target | target=50 | Código |
| HIGH_VALUE_RECOVERY | best_week_12w >= 80 | 80 | Policy config |
| HIGH_VALUE_RECOVERY | inactive < 14 days | 14 | Policy config |

### Policy Parameters (Configurable)

La tabla `growth.yango_lima_opportunity_policy_config` contiene parámetros configurables:

| Parámetro | Valor Default |
|-----------|:---:|
| weekly_trips_target | 100 |
| critical_threshold | 50 |
| daily_action_capacity | 500 |
| high_value_min_weekly_trips | 80 |
| high_value_inactive_days | 1 |
| churn_requires_real_decline | true |

### Scoring Formula (Scored)

```python
opportunity_score = impact_score * 0.4 + urgency_score * 0.3 + probability_score * 0.3
+ PROGRAM_HIGH_VALUE_RECOVERY bonus: 200
+ PROGRAM_CHURN_PREVENTION bonus:  100
+ PROGRAM_14_90 bonus:              50
+ PROGRAM_ACTIVE_GROWTH bonus:       0
```

---

## WHAT CAN BE EXPLAINED TODAY

| Pregunta | ¿Explicable? | Evidencia |
|----------|:---:|-----------|
| ¿Qué programas existen? | YES | 4 programas definidos |
| ¿Cuántos drivers hay en cada programa? | YES | `program_eligibility_daily` GROUP BY |
| ¿Cuál es la capacidad diaria por programa? | YES | `program_capacity_policy` |
| ¿Qué parámetros de policy están activos? | YES | `opportunity_policy_config` |
| ¿Cuál es la regla exacta que activa CHURN_PREVENTION? | PARTIAL | Código fuente, no tabla |
| ¿Qué threshold se aplica a cada regla? | PARTIAL | Algunos en policy_config, otros hardcodeados |
| ¿Puedo cambiar un threshold y ver el impacto? | NO | No hay preview |
| ¿Puedo auditar qué regla metió a qué driver? | NO | No hay tabla de auditoría de reglas |

---

## WHAT IS MISSING

1. **Rule registry table**: Las reglas no están externalizadas. Están en código Python.
2. **Rule-to-program mapping**: No hay una tabla que mapee `rule → program → parameter → threshold`
3. **Preview/simulation**: No se puede simular "¿qué pasaría si cambio el threshold de 50 a 40?"
4. **Audit trail**: No hay registro de qué regla específica clasificó a cada driver
5. **Version history**: Los cambios de policy no tienen versionado (aunque `policy_id` existe en prioritized)

---

## PATH TO YES

1. **Externalizar reglas**: Migrar reglas de código a `yego_lima_program_rule_config`
2. **Preview endpoint**: `POST /programs/rules/preview` con parámetros modificados
3. **Audit trail**: `yego_lima_driver_program_rule_audit` con regla + parámetro + threshold + matched
4. **Score transparency**: Exponer fórmula y componentes en UI

---

## PROGRAM SCORING TRANSPARENCY

### Current Scoring Pipeline

```
driver_state → program_eligibility → opportunity_list → [policy engine] → prioritized_opportunity
```

### Scoring Components (per driver)

| Component | Weight | Source |
|-----------|:---:|--------|
| impact_score | 40% | Derived from lifecycle_state, retention_state |
| urgency_score | 30% | Derived from distance_to_target, days_inactive |
| probability_score | 30% | Derived from historical response patterns |
| program_bonus | varies | Fixed bonuses per program |

---

## VEREDICT

```
PARTIAL — Reglas existen en código, parámetros parcialmente en config.
Falta externalización completa, preview, y auditoría de regla por driver.
```

---

## FIRMA

```
PROGRAM EXPLAINABILITY DISCOVERY
LG-INFRA-R1.7
Status: DISCOVERY COMPLETE — NO IMPLEMENTATION
```
