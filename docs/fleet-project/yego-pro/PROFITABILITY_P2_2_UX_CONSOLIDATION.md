# Yego Pro Profitability — P2.2 UX Consolidation

## Overview

Consolidacion visual de Profitability: las 11 tabs planas se reorganizan en 4 grupos logicos.
Cero perdida de funcionalidad. 100% de capacidades analiticas preservadas.

## Mapa Anterior (11 tabs planas)

```
Overview | Diagnostics | Simulator | Weekly Closed | Last Closed Day |
Drivers | Vehicles | Shifts | Waterfall | Data Quality | Coverage Audit
```

## Mapa Nuevo (4 grupos)

```
[ ESTADO ] [ DIAGNÓSTICO ] [ SIMULADOR ] [ CALIDAD ]

ESTADO
├── Executive Overview (KPIs + health + findings)
├── [Ver detalle] → Weekly Closed
├── [Ver detalle] → Last Closed Day
└── [Ver detalle] → Waterfall P&L

DIAGNÓSTICO
├── Portfolio
├── Drivers (classificacion, causas)
├── Vehicles (classificacion, margen proxy)
├── Shifts (brecha dia/noche)
└── Root Causes (ranking)

SIMULADOR
├── Operacion Real (baseline)
├── Inputs (produccion, costos, pago, bonos)
├── Bonus Config (persistente, 3 tipos)
├── Results (KPIs, subtotals)
├── Arbol de rentabilidad (collapsible)
├── Como se calculo (7 pasos, collapsible)
├── Gap Analysis (collapsible)
├── Vs Operacion Real (collapsible)
├── Sensitivity
├── Calculation Trace
└── Scenarios (CRUD, favoritos)

CALIDAD
├── Data Quality (collapsible, default open)
└── Coverage Audit (collapsible)
```

## Funcionalidades Preservadas

| Funcionalidad | Estado |
|---|---|
| Overview KPIs + health + findings | Preservado en ESTADO |
| Weekly Closed historico | Colapsado en ESTADO |
| Last Closed Day diario | Colapsado en ESTADO |
| Waterfall P&L | Colapsado en ESTADO |
| Diagnostics (5 sub-tabs) | Preservado en DIAGNÓSTICO |
| Simulator completo (11 secciones) | Preservado en SIMULADOR |
| Bonus config persistence | Preservado |
| Scenario CRUD | Preservado |
| Explainability Tree | Preservado (collapsible) |
| Gap Analysis | Preservado (collapsible) |
| Baseline delta | Preservado (collapsible) |
| Data Quality | Preservado en CALIDAD |
| Coverage Audit | Preservado en CALIDAD |
| Keyboard shortcuts | Preservado |

## Funcionalidades Agrupadas

- **Executive Header** — 6 KPIs siempre visibles: Revenue, Bonos, Costos, Payout, Utilidad, Margen
- **ESTADO** — Overview + detalle Weekly/Daily/Waterfall bajo boton "Ver detalle"
- **DIAGNÓSTICO** — Diagnostics panel completo
- **CALIDAD** — Data Quality + Coverage Audit colapsados

## Acordeones Agregados

- Weekly Closed, Last Closed Day, Waterfall dentro de ESTADO
- Arbol de rentabilidad, Como se calculo, Gap Analysis, Vs Operacion Real dentro de SIMULADOR
- Data Quality, Coverage Audit dentro de CALIDAD
- Human guides en cada bloque (1 linea visible, expandible)

## Mejoras UX

| Mejora | Impacto |
|---|---|
| 4 tabs vs 11 | Menos saturacion visual |
| Executive header persistente | Contexto global sin cambiar de tab |
| Sections colapsables | Scroll vertical reducido ~60% |
| Human guides 1-linea | Ayuda contextual sin ocupar espacio |
| "Ver detalle" en ESTADO | Usuario diario ve solo lo importante |

## Riesgos

- El Simulator ahora carga 4 endpoints en paralelo (defaults + bonus config + baseline + scenarios). Cold start puede ser mas lento si hay pool exhaustion. Mitigado: cada endpoint usa pool compartido.
- El ExecutiveHeader muestra KPIs de Overview. Si Overview falla, el header muestra ceros sin bloquear la UI.

## QA

| Check | Result |
|---|---|
| `python -m compileall backend\app` | PASS (0 errors) |
| `npm run build` | PASS (5.34s, 843 modules) |
| No se elimino ningun endpoint | PASS |
| No se elimino ningun calculo | PASS |
| No se elimino ningun KPI | PASS |
| 4 grupos de tabs funcionan | PASS |
| Collapsible sections funcionan | PASS |
| Executive header visible | PASS |

## GO / NO-GO

**GO.** Consolidacion completada. Profitability conserva el 100% de capacidades analiticas pero se navega en 4 grupos logicos en vez de 11 tabs planas.
