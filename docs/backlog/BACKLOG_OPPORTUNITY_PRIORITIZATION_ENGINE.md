# BACKLOG — Opportunity Prioritization Engine

**Date:** 2026-06-06
**Phase:** BACKLOG (NO IMPLEMENTAR)
**Registry:** LG-UX-R2.8A — Parte B

---

## VISION

Cuando `actionable_total > capacity_total`, el sistema debe asegurar que los **mejores conductores entren primero**.

Hoy (2026-06-06) la priorizacion es puramente por `final_rank` (ranking generado por el policy engine). No hay scoring visible, no hay penalizacion por fatiga, no hay trazabilidad individual.

## R2.8C DISCOVERY FINDINGS

### Estado actual del ranking (auditado 2026-06-06)

- `final_rank` se construye como: `opportunity_score = impact*0.4 + urgency*0.3 + probability*0.3 + PROGRAM_BONUS`
- `PROGRAM_BONUS` domina: HVR=+200, CP=+100, 14_90=+50, AG=+0 → >99% del score final
- Dentro de un mismo programa, los scores difieren en centesimas (ej: 100.72 vs 100.78)
- Variables usadas: completed_orders_week, best_week_12w, lifecycle_state, retention_state
- Variables NO usadas: performance_state, supply_hours_7d/30d, revenue, recencia
- Pesos: hardcodeados en SQL. No configurables.

### READY vs UNASSIGNED

- WITH_CHANNEL avg trips/w = 7.13, UNASSIGNED avg trips/w = 17.83
- UNASSIGNED tiene MAS viajes semanales, pero score casi identico (~100.72)
- La diferencia se explica por capacidad (310 lleno), no por scoring

### Missed Opportunities

- Conductores UNASSIGNED con 32 trips/sem y 141 best_week puntuan 100.7432
- Conductores READY con 10 trips/sem y 78 best_week puntuan 100.7458
- Diferencia: 0.0026 puntos — funcionalmente indistinguible

### Fatigue Readiness: NO

- Result Sync: 0 registros (tabla existe, vacia)
- Sin columnas de contact tracking en assignment_queue
- Sin last_contact_at, contact_attempts, last_result

### R2.8C Recommendation

**NO implementar score hasta que:**
1. Result Sync este poblado con datos reales
2. Exista contact tracking por driver
3. Attribution proporcione linea base de medicion

---

## PRIORITY SCORE

```
priority_score = opportunity_score - fatigue_penalty
```

Todo deterministico. NO IA. NO forecast. NO ML.

---

## OPPORTUNITY SCORE

Componentes futuros posibles:

| Componente | Que mide | Peso sugerido |
|-----------|----------|:---:|
| Recencia de actividad | Dias desde ultimo viaje | 0.15 |
| Trips 7d | Viajes completados ultima semana | 0.20 |
| Trips 14d | Viajes completados ultimos 14 dias | 0.10 |
| Revenue historico | Revenue generado 30d | 0.15 |
| Lifecycle | Estado actual (ej: AT_RISK pesa mas) | 0.10 |
| Contactabilidad | Tiene telefono valido, canal asignado | 0.05 |
| Valor estrategico | Definido por programa | 0.15 |
| Probabilidad operativa | Reglas deterministicas | 0.10 |

Los pesos son sugeridos. Deben ser configurables en el futuro.

---

## FATIGUE PENALTY

Debe bajar prioridad cuando el conductor ya fue contactado sin exito:

| Intentos recientes (ventana N dias) | Penalty |
|-------------------------------------|:------:|
| 0 intentos | 0.00 |
| 1-2 intentos, sin respuesta | -0.10 |
| 3-4 intentos, sin respuesta | -0.25 |
| 5+ intentos, sin respuesta | -0.50 |
| Contactado con exito (respondio) | 0.00 (reset) |
| Trabajado recientemente (positivo) | -0.05 (enfriamiento) |

---

## UI REQUIREMENT

Cada registro en Queue debe mostrar:

- `priority_score` — score total
- `opportunity_score` — antes de penalty
- `fatigue_penalty` — cuanto se resto
- `razon_priorizacion` — que componentes contribuyeron
- `razon_penalizacion` — por que se penalizo (si aplica)
- `ultimo_intento` — fecha del ultimo contacto
- `intentos_recientes` — cuantos intentos en ventana N

El operador debe poder responder:

- **Por que este conductor esta arriba?** → opportunity_score alto, sin penalty
- **Por que este conductor bajo?** → fatigue_penalty aplicado

---

## CONFIGURABILITY (Futuro)

Los pesos deben ser configurables via `opportunity_policy_config` o tabla equivalente:

```json
{
  "weights": {
    "recency": 0.15,
    "trips_7d": 0.20,
    "trips_14d": 0.10,
    "revenue_30d": 0.15,
    "lifecycle": 0.10,
    "contactability": 0.05,
    "strategic_value": 0.15,
    "operational_probability": 0.10
  },
  "fatigue": {
    "window_days": 14,
    "penalty_per_attempt": 0.08,
    "max_penalty": 0.50,
    "reset_on_response": true
  }
}
```

NO crear configuracion todavia. Solo backlog.

---

## DEPENDENCIAS

| Dependencia | Estado | Bloquea |
|-------------|--------|---------|
| LoopControl Result Sync | BACKLOG | Intentos y respuestas (fatigue) |
| Attribution | BACKLOG | Resultado positivo/negativo |
| Driver State Snapshot | IMPLEMENTADO | Recencia, lifecycle, trips, revenue |
| Channel Allocation | IMPLEMENTADO | Contactabilidad |
| Priority Registry | IMPLEMENTADO | Valor estrategico |

---

## GOVERNANCE

No abrir Program Builder.
No abrir AI.
No abrir Forecast.
No abrir Attribution.
No abrir Impact.

Este engine pertenece a **Deterministic Prioritization / Control Foundation Hardening** hasta que exista evidencia suficiente para motores superiores.

---

## MULTICHANNEL INTEGRATION (R2.8B)

El priority score no solo decide ranking. Tambien debe alimentar la asignacion de canal/campana:

- **Fatigue penalty aplica por canal.** Un conductor puede tener 3 intentos fallidos en Call Center pero 0 en WhatsApp. El penalty debe ser separado por canal.
- **Frecuencia maxima multicanal.** No solo cuantos intentos totales, sino cuantos por canal especifico en una ventana de tiempo.
- **Prioridad considera canal humano vs masivo.** Call Center (humano, alto costo) debe reservarse para los conductores de mayor valor. BOT/WhatsApp (masivo, bajo costo) para volumen.
- **Scoring diferencial por canal.** Un conductor puede ser prioridad alta para WhatsApp pero media para Call Center.
- **El score alimenta multichannel allocation.** Despues de calcular priority_score, el sistema decide que canal es optimo para cada conductor segun score, costo, capacidad y fatiga por canal.

Ver: `docs/backlog/BACKLOG_CONTROL_LOOP_MULTICHANNEL_ALLOCATION.md`

---

## FIRMA

```
BACKLOG REGISTRY ENTRY
Opportunity Prioritization Engine
Registered: 2026-06-06
Phase: LG-UX-R2.8A — Parte B
Status: BACKLOG — NO IMPLEMENTAR
Next review: Post Result Sync + Attribution foundation
```
