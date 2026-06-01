# Yego Pro Profitability — P1.4.5B Explainability Tree

## Overview

El Simulator ahora explica visualmente como se forma la utilidad empresa mediante un arbol
expandible/colapsable, un resumen matematico de 7 pasos, y comparacion contra la Operacion Real.

## Estructura del Arbol

```
Utilidad empresa (S/99.88) [DERIVED]
├── Ingreso total empresa (S/1,875.00) [DERIVED]
│   ├── Revenue general (S/1,275.00) [OPERATIONAL]
│   ├── Revenue Premier (S/150.00) [OPERATIONAL]
│   ├── Bono general Yango (S/320.00) [YANGO_BONUS_TABLE]
│   └── Bono Premier Yango (S/130.00) [YANGO_BONUS_TABLE]
├── Costos operativos (S/1,062.62) [DERIVED]
│   ├── Comision plataforma (S/256.50) [MODULE_BILLING]
│   ├── Combustible (S/252.87) [MODULE_BILLING]
│   ├── Mantenimiento (S/102.00) [MODULE_BILLING]
│   ├── Costos fijos (S/395.00) [FLEET_CONFIG]
│   └── Reserva desgaste (S/56.25) [MANUAL]
└── Pago conductor (S/712.50) [DERIVED]
    ├── Payout conductor (S/712.50) [PAYMENT_TIERS]
    └── Garantia (si aplica)
```

### Cada nodo contiene:
- `key` — identificador unico
- `label` — nombre en espanol
- `value` — monto en S/
- `formula` — expresion de calculo
- `inputs` — parametros usados
- `source` — fuente del dato
- `confidence` — REAL / ESTIMATED / NOT_REACHED
- `sign` — positive / negative / neutral
- `impact_on_profit` — contribucion neta a la utilidad
- `children` — sub-nodos

## Math Summary (7 pasos)

1. **Ingreso por viajes** = (viajes generales x ticket gral) + (viajes Premier x ticket Premier)
2. **Bonos Yango** = bono general + bono Premier
3. **Ingreso total empresa** = ingreso por viajes + bonos Yango
4. **Costos operativos** = combustible + mantenimiento + comision + fijos + reserva
5. **Base de reparto** = ingreso total empresa - costos operativos
6. **Pago conductor** = revenue bruto x payout %
7. **Utilidad empresa** = base de reparto - pago conductor - garantias

Cada paso muestra la expresion evaluada con valores concretos.

## Comparacion contra Operacion Real

Si existe baseline operacional, se calculan deltas:

| KPI | Operacion Real | Escenario | Diferencia | Direccion |
|---|---|---|---|---|
| Revenue bruto | baseline | escenario | delta | better/worse |
| Bonos Yango | baseline | escenario | delta | |
| Costos | baseline | escenario | delta | |
| Pago conductor | baseline | escenario | delta | |
| Utilidad semanal | baseline | escenario | delta | |
| Margen % | baseline | escenario | delta | |
| Payback | baseline | escenario | delta | |
| Break-even | baseline | escenario | delta | |

Cada delta incluye `absolute`, `pct`, y `direction` (better/worse/neutral).

Si no hay baseline, se muestra mensaje controlado: "No hay baseline operacional suficiente para comparacion."

## UI Features

- **Arbol expandible/colapsable**: cada nodo con hijos tiene triangulo para expandir
- **Badges source/confidence**: cada nodo muestra fuente y nivel de confianza
- **Sign colors**: verde = positivo (ingreso), rojo = negativo (costo/gasto)
- **Detalle por nodo**: boton "Detalle" muestra formula, inputs, e impacto en utilidad
- **Math Summary**: panel compacto arriba del trace tecnico
- **Vs Operacion Real**: tabla comparativa con deltas y semaforos mejor/peor/igual

## Limitations

- Baseline usa datos de flota completa; escenario usa 1 conductor/vehiculo. Las comparaciones directas pueden mostrar diferencias grandes por escala.
- El baseline no se recalcula automaticamente al cambiar inputs del escenario.
- No se usa ninguna libreria pesada de visualizacion (implementado con componentes simples).

## QA

| Check | Result |
|---|---|
| `python -m compileall backend\app` | PASS (0 errors) |
| `npm run build` | PASS (6.35s, 843 modules) |
| Tree structure correct | PASS |
| Math summary 7 steps | PASS |
| Baseline delta exists | PASS |
| No NaN / no undefined / no loading infinito | PASS |
| Escenarios guardados siguen funcionando | PASS |
| Bonus config persistida sigue funcionando | PASS |
| No toca otros modulos | PASS |

## GO / NO-GO

**GO.** Builds pass. Tree, math summary, and baseline comparison work end-to-end.
No destructive changes. No contamination of other modules.
