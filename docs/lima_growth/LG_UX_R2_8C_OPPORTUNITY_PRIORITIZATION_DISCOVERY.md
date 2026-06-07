# LG-UX-R2.8C — Opportunity Prioritization Discovery

**Date:** 2026-06-06
**Phase:** LG-UX-R2.8C Opportunity Prioritization Discovery
**Scope:** Discovery + evidence only. NO implementation.
**Rule:** NO score changes. NO ranking changes. NO new engines.

---

## 1. EXECUTIVE SUMMARY

El ranking actual funciona, pero tiene una limitacion estructural: **el PROGRAM_BONUS domina el score**. Dentro de un mismo programa, la diferenciacion entre conductores es minima (~0.03 puntos entre el mejor y el peor CHURN_PREVENTION actionable). Esto significa que la capacidad —no el merito— decide quien entra y quien queda fuera.

**Hallazgo clave:** Los 190 UNASSIGNED tienen en promedio MAS viajes semanales (17.83) que los WITH_CHANNEL (7.13), pero peor best_week_12w (82 vs 109). La paradoja se debe a que el score apenas diferencia dentro del programa, y el canal se llena por orden de ranking indiferenciado.

---

## 2. ESTADO ACTUAL DEL RANKING

### 2.1 Como se calcula final_rank

```sql
-- impact_score: basado en gap al target y mejor semana historica
impact_score = (gap_to_target / target) * 0.6 + (best_week_12w / target) * 0.4

-- urgency_score: basado en retention_state + zero trips
urgency_score = retention_urgency + zero_trips_bonus
  retention_urgency: CHURN_RISK=0.4, AT_RISK=0.3, else=0.1
  zero_trips_bonus: 0.2 si completed_orders_week = 0

-- probability_score: basado en value + actividad + lifecycle
probability_score = 0.5 + value_bonus + active_bonus + lifecycle_bonus
  value_bonus: best_week>=100 → 0.3, best_week>=50 → 0.15, else 0
  active_bonus: completed_orders_week>0 → 0.2
  lifecycle_bonus: ESTABLISHED → 0.1

-- opportunity_score: composite + program bias
opportunity_score = impact*0.4 + urgency*0.3 + probability*0.3 + PROGRAM_BONUS
  PROGRAM_BONUS: HVR=200, CP=100, 14_90=50, AG=0

-- final_rank: global ordering
final_rank = ROW_NUMBER() OVER (ORDER BY opportunity_score DESC, urgency_score DESC, impact_score DESC)
```

### 2.2 Peso del PROGRAM_BONUS

| Programa | BONUS | Score total real | % del BONUS |
|----------|:-----:|:---------------:|:-----------:|
| HVR | 200 | ~200.8 | **99.6%** |
| CP | 100 | ~100.6 | **99.4%** |
| 14_90 | 50 | ~50.5 | **99.0%** |
| AG | 0 | ~0.63 | 0% |

**El BONUS de programa constituye >99% del score total para programas con bonus.** Las diferencias entre conductores dentro de un programa son de centesimas de punto.

### 2.3 Variables que alimentan el score

| Variable | Fuente | Participa | Peso | Configurable |
|----------|--------|:---:|------|:---:|
| completed_orders_week | driver_state_snapshot | impact + probability | variable | NO |
| best_week_12w | driver_state_snapshot | impact + probability | variable | NO |
| lifecycle_state | driver_state_snapshot | probability | 0.1 (ESTABLISHED) | NO |
| retention_state | driver_state_snapshot | urgency | 0.1-0.4 | NO |
| selected_program_code | eligibility engine | BONUS | 0-200 | PARCIAL (hardcoded) |
| performance_state | driver_state_snapshot | NO | — | — |
| supply_hours_7d | driver_state_snapshot | NO | — | — |
| supply_hours_30d | driver_state_snapshot | NO | — | — |

---

## 3. READY vs UNASSIGNED COMPARISON

### 3.1 Within actionable queue

| Grupo | Count | Avg Score | Avg Rank | Avg TripsW | Avg Best12w | Avg Gap |
|-------|:-----:|:---------:|:--------:|:----------:|:-----------:|:-------:|
| EXPORTED | 160 | 150.81 | 104.9 | 1.06 | 107.26 | 98.9 |
| READY | 150 | 100.78 | 209.5 | **13.61** | 112.02 | 86.4 |
| HELD | 190 | 100.72 | 405.5 | **17.83** | 82.48 | 82.2 |

**Paradoja:** Los HELD/UNASSIGNED tienen mas viajes que los READY, pero estan fuera. Esto NO es un bug del score — es un problema de capacidad. Dentro de CHURN_PREVENTION, los scores son casi identicos (100.72 vs 100.78), y la diferencia de ranking se debe al BOT lleno.

### 3.2 WITH_CHANNEL vs UNASSIGNED

| | WITH_CHANNEL | UNASSIGNED | Diferencia |
|---|:---:|:---:|:---:|
| Count | 310 | 190 | — |
| Avg Score | 126.60 | 100.72 | +25.88 (HVR infla) |
| Avg Rank | 155.5 | 405.5 | — |
| Avg TripsW | 7.13 | **17.83** | UNASSIGNED +10.7 |
| Avg Best12w | 109.56 | **82.48** | WITH_CHANNEL +27 |
| Avg Gap | 92.9 | 82.2 | UNASSIGNED menor gap |

**Interpretacion:** WITH_CHANNEL tiene mejor score por el BONUS de HVR (200). Si miramos solo CHURN_PREVENTION, los UNASSIGNED tienen mas viajes pero peor historico maximo. El score no tiene suficiente granularidad para decidir cual de estos dos perfiles merece mas el canal.

---

## 4. MISSED OPPORTUNITIES

### 4.1 Top UNASSIGNED vs Bottom READY (CHURN_PREVENTION)

| Driver | Status | Score | Rank | TripsW | Best12w | Lifecycle | Retention |
|--------|:------:|:-----:|:----:|:------:|:-------:|-----------|-----------|
| Romero Omar | UNASSIGNED | 100.7434 | 311 | 1 | 63 | ESTABLISHED | CHURN_RISK |
| Roque Yucra Jose | UNASSIGNED | 100.7432 | 314 | 32 | 141 | ESTABLISHED | CHURN_RISK |
| Garcia Suazo Nelson | **READY** | 100.7480 | 296 | 30 | 151 | ESTABLISHED | CHURN_RISK |
| Serna Medina Walter | **READY** | 100.7458 | 299 | 10 | 78 | ESTABLISHED | CHURN_RISK |

**Observacion:** Garcia Suazo Nelson (READY, 30 trips/sem, 151 best_week) merece estar READY. Pero Roque Yucra (UNASSIGNED, 32 trips/sem, 141 best_week) tiene metricas comparables y quedo fuera. La diferencia de score es 0.0048 — invisible.

### 4.2 Riesgo

| Metrica | READY avg | UNASSIGNED avg | Diferencia | Riesgo |
|---------|:--------:|:--------------:|:----------:|--------|
| TripsW | 13.61 | 17.83 | +4.22 | MEDIUM — UNASSIGNED mas activo |
| Best12w | 112.02 | 82.48 | -29.54 | LOW — READY mejor historico |
| Gap a target | 86.4 | 82.2 | -4.2 | LOW — similar |
| Supply hours | 0 | 0 | 0 | N/A — datos faltantes |

**Conclusion:** La diferencia principal no esta en el score sino en la capacidad. Si hubiera 190 slots mas, estos conductores entrarian. El ranking funciona, pero la capacidad es el cuello de botella.

---

## 5. FATIGUE READINESS

### Resultado: **NO**

| Componente | Estado |
|-----------|:------:|
| LoopControl exports | 52 total, 7 exported (140 contacts) |
| Result sync records | **0** (tabla existe pero vacia) |
| Contact tracking per driver | NO (sin columnas) |
| Last contact date | NO |
| Contact attempts | NO |
| Response status | NO |

**Fuentes faltantes para fatigue:**
1. Result Sync debe poblarse con datos de LoopControl (calls made, answered, outcomes)
2. assignment_queue necesita columnas: `last_contact_at`, `contact_attempts`, `last_result`
3. LoopControl campaign export necesita trazabilidad: que driver fue contactado, cuando, con que resultado

**Sin estos datos, fatigue_penalty es imposible de calcular.**

---

## 6. FUTURE SCORE CONTRACT

```json
{
  "priority_score": {
    "opportunity_score": 0.74,
    "fatigue_penalty": 0.00,
    "final_priority_score": 0.74,

    "components": [
      {
        "name": "impact_score",
        "value": 0.85,
        "weight": 0.30,
        "contribution": 0.255,
        "explanation": "Gap al target (86 viajes) + mejor semana historica (151 viajes)"
      },
      {
        "name": "urgency_score",
        "value": 0.40,
        "weight": 0.25,
        "contribution": 0.100,
        "explanation": "CHURN_RISK = 0.4, sin bonus de zero trips"
      },
      {
        "name": "probability_score",
        "value": 0.85,
        "weight": 0.25,
        "contribution": 0.212,
        "explanation": "Alto valor (best_week>100), activo (trips>0), ESTABLISHED"
      },
      {
        "name": "program_priority",
        "value": 100,
        "weight": 0.20,
        "contribution": 0.200,
        "explanation": "CHURN_PREVENTION = rank 2, bonus 100 normalizado"
      }
    ],

    "fatigue": {
      "attempts_recent": 0,
      "last_attempt_at": null,
      "last_result": null,
      "penalty": 0.00,
      "explanation": "Sin datos de contacto. Fatigue no disponible."
    },

    "rank_reason": "CHURN_PREVENTION, alta urgencia, gap significativo al target, sin intentos previos",
    "ui_explanation": "Este conductor esta arriba porque: es CHURN_PREVENTION (prioridad 2), tiene CHURN_RISK (urgencia alta), esta a 86 viajes del target semanal y tiene capacidad de 151 viajes/semana."
  }
}
```

---

## 7. UI EXPLAINABILITY REQUIREMENTS

### En Queue (futuro)

Columnas adicionales:
- `Priority Score` — score final
- `Opportunity Score` — antes de penalty
- `Fatigue Penalty` — cuanto se resto
- `Last Contact` — fecha ultimo intento
- `Attempts` — intentos recientes
- `Why` — tooltip/drawer con explicacion

### Tooltip/Drawer

> "Este conductor esta arriba porque es CHURN_PREVENTION con CHURN_RISK. Tiene 17 viajes esta semana, gap de 83 al target, y su mejor semana historica fue de 82 viajes. Sin intentos previos de contacto."

> "Este conductor bajo 50 posiciones porque tiene 3 intentos sin respuesta en los ultimos 14 dias (fatigue penalty: -0.24)."

> "Este conductor quedo fuera porque la capacidad de BOT (200) esta llena. Puntua 100.72 — suficiente para entrar si hubiera capacidad."

---

## 8. RIESGOS DE IMPLEMENTAR SCORE AHORA

| Riesgo | Severidad | Mitigacion |
|--------|:---------:|------------|
| Score sin fatigue sobre-contacta | HIGH | Fatigue requiere Result Sync primero |
| Cambiar score sin medir impacto | HIGH | No cambiar hasta tener linea base con Attribution |
| UI sin explicacion confunde | MEDIUM | Explainability obligatorio antes de mostrar score |
| Peso de programa domina score | MEDIUM | Rebalancear pesos para que merito pese mas |
| Sin datos de supply_hours | LOW | supply_hours_7d/30d = 0 en DB, sin fuente |

---

## 9. RECOMENDACION

**NO implementar score ahora.** Las condiciones no estan dadas:

1. Result Sync vacio → fatigue imposible
2. Attribution no existe → no hay linea base para medir mejora
3. Dentro del programa, el score apenas diferencia → el ranking actual es funcionalmente aleatorio dentro del programa

**Proximo paso recomendado:** Poblar Result Sync con datos reales de LoopControl antes de tocar el score. Sin loop cerrado, cualquier cambio al ranking es ciego.

---

## 10. BACKLOG ACTUALIZADO

Ver: `docs/backlog/BACKLOG_OPPORTUNITY_PRIORITIZATION_ENGINE.md`

Agregado:
- Hallazgos reales de R2.8C (score dominado por program bonus)
- Variables disponibles y faltantes
- Fatigue readiness = NO (Result Sync vacio)
- UI explainability obligatorio
- Dependencia critica de Result Sync

---

## 11. QA

| Check | Resultado |
|-------|:---------:|
| Backend compile | OK (no code changes) |
| Frontend build | PASS (no code changes) |
| Ranking auditado | YES (final_rank = program bonus + weighted composite) |
| READY vs UNASSIGNED | YES (WITH_CHANNEL=310, UNASSIGNED=190, scores nearly identical within program) |
| Missed opportunities | YES (4 ejemplos con scores diferenciales de 0.005) |
| Fatigue readiness | NO (Result Sync vacio, sin contact tracking) |
| Base suficiente para score | NO — requiere Result Sync + Attribution |
| Backlog actualizado | YES |
