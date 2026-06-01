# Yego Pro Profitability — P1.4.6 Simulator Gap Analysis

## Overview

Nueva capa de Gap Analysis en el Simulator que responde deterministicamente:
- Que tan lejos esta el escenario de break-even
- Que palancas tienen mayor impacto
- Que combinacion minima podria cerrar la brecha

## Formulas de Brecha

```
gap_week = target_profit - current_profit_week    (target default = 0)
gap_month = gap_week * 4.33
break_even_status = "Rentable" si profit >= 0
                  = "Cerca de break-even" si 0 < gap < 200
                  = "Lejos de break-even" si gap >= 200
```

## Palancas (6 minimas)

### 1. trips_needed
```
margin_per_trip = gross_revenue / total_trips - variable_cost_per_trip
trips_needed = gap / margin_per_trip    (si margin_per_trip > 0)
```

### 2. ticket_needed
```
ticket_needed = (gross_revenue + gap) / total_trips
ticket_delta = ticket_needed - ticket_avg_general
```

### 3. payout_needed
```
payout_max = (gross_rev - total_costs + gap) / gross_rev * 100
payout_delta = current_pct - payout_max
```

### 4. premier_needed
```
premier_margin = ticket_premier + bonus_premier_marginal
premier_needed = gap / premier_margin
```

### 5. bonus_needed (next tier)
```
Busca el siguiente tramo de bono general y Premier en la tabla de bonos activa.
next_impact = next_tier_amount - current_bonus_amount
```

### 6. cost_reduction_needed
```
cost_reduce = gap    (reduccion total requerida en costos)
```

### Estructura de cada lever
```
{
  key, label, current_value, required_value,
  delta_abs, delta_pct, estimated_profit_impact,
  feasibility_hint: LOW | MEDIUM | HIGH,
  confidence, formula, explanation
}
```

## Lever Impact Ranking

Calcula el impacto marginal de 8 palancas:
- +1 viaje general
- +1 viaje Premier
- +S/1 ticket general
- -1 pp payout
- -5% combustible
- -5% mantenimiento
- Siguiente tramo bono general
- Siguiente tramo bono Premier

Ordenado por impacto semanal descendente.

## Break-even Combinations (6)

### A. Solo produccion
Viajes generales adicionales para cubrir 100% de la brecha.

### B. Produccion + Premier
60% viajes generales + 40% viajes Premier.

### C. Produccion + payout
50% viajes generales + 50% reduccion de payout.

### D. Produccion + bonos
70% viajes generales (intentando alcanzar siguiente tramo de bono).

### E. Costos + payout
50% reduccion de costos + 50% reduccion de payout.

### F. Mix balanceado
30% viajes + 15% Premier + 25% payout + 15% costos + bono si alcanza.

Cada combinacion devuelve:
- name, changes[], projected_profit_week, projected_profit_month
- closes_gap (true/false), remaining_gap
- confidence, explanation

## Que NO hace

- NO optimizador matematico (solo combinaciones predefinidas)
- NO IA ni machine learning
- NO recomendaciones automaticas ("deberias hacer...")
- NO ejecuta acciones
- NO cambia pagos reales

El texto dice "el modelo muestra", "el escenario requeriria", "la brecha se cerraria si".

## UI

- Toggle "Gap Analysis" en Simulator
- Card principal con estado (Rentable / Cerca / Lejos)
- Cards de "Que falta para llegar a cero" (trips, ticket, payout)
- Tabla de ranking de palancas
- Grid de 6 combinaciones con badge CIERRA BRECHA / Faltan S/X

## QA

| Check | Result |
|---|---|
| `python -m compileall backend\app` | PASS (0 errors) |
| `npm run build` | PASS (7.36s, 843 modules) |
| Gap analysis returns (escenario perdedor) | PASS — 7 levers, 8 ranking, 6 combos |
| Gap analysis returns (escenario rentable) | PASS — "Rentable", gap=0 |
| No NaN | PASS |
| Previous features intact | PASS — Tree, math summary, baseline delta, scenarios, bonus config |
| No toca otros modulos | PASS |

## Limitations

- `feasibility_hint` es heuristico basado en la magnitud del cambio requerido
- Combinaciones no consideran restricciones operativas reales (disponibilidad de conductores, horas)
- Premier trips adicionales asumen mismo payout % que viajes generales
- El impacto de bonos solo considera el tramo inmediatamente siguiente

## GO / NO-GO

**GO.** Gap Analysis funciona deterministicamente sin IA. Builds limpios. Sin regresiones.
