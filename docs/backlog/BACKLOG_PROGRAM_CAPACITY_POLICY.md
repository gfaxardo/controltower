# BACKLOG — Program Capacity Policy

**Date:** 2026-06-06
**Phase:** BACKLOG (NO IMPLEMENTAR)
**Registry:** LG-UX-R2.8D — Part B

---

## NEED

Hoy la capacidad se distribuye por strict priority order:
- HVR (#1) toma todo lo que necesita
- CP (#2) toma el resto
- 14_90 (#3) y AG (#4) reciben 0 si la capacidad se agota antes

Esto funciona cuando hay pocos accionables. Pero cuando `actionable > capacity` (hoy: 500 > 310), los programas de menor prioridad nunca reciben capacidad, y el sistema no puede garantizar pisos minimos ni limites maximos.

---

## POLICY CONTRACT FUTURO

```json
{
  "program_capacity_policy": {
    "program_code": "PROGRAM_CHURN_PREVENTION",
    "priority_rank": 2,
    "min_daily_capacity": 100,
    "max_daily_capacity": 170,
    "target_share_pct": 55.0,
    "channel_preferences": ["CALL_CENTER", "SAC", "BOT"],
    "enabled": true,
    "policy_reason": "Churn Prevention es el programa de mayor volumen. Maximo 55% para asegurar que otros programas reciban capacidad."
  }
}
```

### Reglas

1. **min_daily_capacity** — asegura piso. Cada programa con accionables > 0 recibe al menos este numero de slots.
2. **max_daily_capacity** — evita que un programa monopolice. Limite superior como % de capacidad total.
3. **target_share_pct** — distribucion proporcional deseada. No garantizada si actionable < share.
4. **priority_rank** — orden operativo. Dentro de min/max bounds, la prioridad decide quien recibe primero.
5. **enabled** — permite desactivar programas sin borrarlos.

---

## UI FUTURE

En Control Config, seccion "Program Capacity Policy":

- Tabla de programas con: rank, name, min, max, target%, channels, enabled
- Editable con preview de impacto
- Preview muestra: "Con esta config, HVR: 80/80, CP: 170/420, 14_90: 10/0, AG: 10/0, Unassigned: 230"
- Confirmacion antes de aplicar
- Versionado (snapshot de policy anterior)

---

## RELACION CON PROGRAM REGISTRY

Esta politica depende de que los programas existan en un Program Registry (no STATIC_REGISTRY). Cada programa tendra su entrada de policy.

Ver: `docs/backlog/BACKLOG_PROGRAM_GOVERNANCE_ENGINE.md`

---

## SIMULATION RESULTS (2026-06-02 data)

| Scenario | HVR | CP | 14_90 | AG | Unassigned |
|----------|:---:|:---:|:---:|:---:|:---:|
| A: Strict priority (current) | 80 | 230 | 0 | 0 | 190 |
| B: Max cap (HVR=40%, CP=60%) | 80 | 186 | 0 | 0 | 234 |
| C: Min floor (HVR=80, CP=50) | 80 | 230 | 0 | 0 | 190 |
| D: Proportional share | 50 | 260 | 0 | 0 | 190 |
| E: Hybrid (caps + floors) | 80 | 170 | 0 | 0 | 250 |

Nota: 14_90 y AG tienen 0 actionable para esta fecha, por eso reciben 0 en todos los escenarios. Si tuvieran actionable > 0, los escenarios C, D, y E les darian capacidad.

---

## RECOMMENDATION

**Scenario E (Hybrid)** es el mas balanceado cuando los programas tienen accionables. Combina:
- Prioridad (HVR primero)
- Caps (previene monopolio)
- Floors (asegura que nadie quede en 0)

**NO implementar hasta que:**
1. Program Registry exista (programas en DB, no hardcodeados)
2. Policy sea configurable via UI
3. Preview de impacto este disponible

---

## FIRMA

```
BACKLOG REGISTRY ENTRY
Program Capacity Policy
Registered: 2026-06-06
Phase: LG-UX-R2.8D — Part B
Status: BACKLOG — NO IMPLEMENTAR
Next review: Post Program Registry Foundation (R3.1)
```
