# Yego Pro Profitability — Duplication Audit Before P2.1

**Date:** 2026-05-31
**Scope:** Read-only audit. No code changes.
**Question:** Should "Profitability Intelligence" (P2.1) be a new tab, refactor of Diagnostics, or hardening of existing tabs?

---

## FASE 1 — INVENTARIO ACTUAL

### 11 Tabs (top-level)

| # | Tab | Objective | Endpoints | Data Type | Has Drills | Has Traceability |
|---|---|---|---|---|---|---|
| 1 | **Overview** | Ver si Yego Pro gana o pierde. KPIs 30d + ultima billing week. | `GET /overview` | REAL + DERIVED | Yes (top losses, utilization, shift diag, findings, confidence) | Yes (source, metric_type, confidence per KPI) |
| 2 | **Diagnostics** | Clasificar entidades (drivers, vehicles, shifts, portfolio) con causas y severidad. | `GET /diagnostics/{drivers,vehicles,shifts,portfolio}` | REAL + ESTIMATED | Yes (5 sub-tabs) | Yes (classification, causes, severity, confidence, explanation) |
| 3 | **Simulator** | Probar escenarios hipoteticos con inputs editables. | `POST /simulator/run`, 14 more endpoints | ASSUMPTION + REAL references | Yes (inputs, tree, gap, sensitivity, trace, scenarios, comparator) | Full (calculation_trace, math_summary, tree, gap_analysis) |
| 4 | **Weekly Closed** | Historico semanal de billing cerrado. | `GET /weekly` | REAL | No (tabular) | Yes (source, confidence per metric) |
| 5 | **Last Closed Day** | Produccion operativa diaria. Sin datos financieros de costos. | `GET /daily` | REAL | No (tabular + day/night split) | Yes (source) |
| 6 | **Drivers** | Rentabilidad por conductor. Ordenado por perdida. | `GET /drivers` | REAL | No (tabular) | Yes (source) |
| 7 | **Vehicles** | Configuracion de flota y cuotas. | `GET /vehicles` | REAL (LIMITED) | No (tabular) | Yes |
| 8 | **Shifts** | Produccion dia vs noche. | `GET /shifts` | DERIVED | No (tabular) | Yes |
| 9 | **Waterfall** | Estructura P&L: revenue, costos, payout, bonos. | `GET /input-mapping` | REAL + ASSUMPTION | No (waterfall bars + table) | Yes (source_type per input) |
| 10 | **Data Quality** | MV existence, freshness, row counts, warnings. | `GET /quality` | N/A | No (checks list) | Yes (status per MV) |
| 11 | **Coverage Audit** | Gaps operativos: cierres faltantes, billing faltante, placas sin asignar. | Uses overview + quality + root-cause | REAL | No (cards + tables) | Yes (detail per gap) |

### Diagnostics Sub-tabs (5)

| Sub-tab | Objective | Questions answered |
|---|---|---|
| **Portfolio** | Agregado: margen total, % en perdida, top 5 losses/gains, concentracion, impacto hipotetico | ¿Cuanto se pierde en total? ¿Quienes concentran la perdida? ¿Que pasaria si retiro los peores? |
| **Diag-Drivers** | Driver classification: PROFITABLE / RISKY / LOSS / UNKNOWN, con causas, severidad, confianza, explicacion | ¿Que conductores estan en perdida? ¿Por que? ¿Es por volumen, ticket, payout, falta de cierre? |
| **Diag-Vehicles** | Vehicle classification by plate: Rentable / Recuperable / Critico, margen estimado | ¿Que placas no cubren sus costos? ¿Es por baja utilizacion, poco revenue/dia? |
| **Diag-Shifts** | Day vs night gap severity, payout limits | ¿La brecha dia/noche explica la perdida? ¿Cuanto payout maximo soporta cada turno? |
| **Root Causes** | Cause frequency and impact ranking across all entities | ¿Cuales son las causas mas frecuentes de perdida? ¿Cual es su impacto estimado? |

### Simulator Sections (11)

| Section | Purpose | Type |
|---|---|---|
| Inputs | Parametros editables (produccion, costos, pago, bonos) | Interactive |
| Bonus Config | Tablas de bonos Yango persistentes (3 tipos) | Interactive |
| Baseline | Operacion Real desde datos operativos | Read-only (duplicable) |
| Results | KPI cards + subtotales + bonus result | Computed |
| Explainability Tree | Arbol expandible de utilidad | Computed |
| Math Summary | 7 pasos de calculo evaluados | Computed |
| Baseline Delta | Comparacion vs Operacion Real | Computed |
| Gap Analysis | Brecha, levers, ranking, combinaciones | Computed |
| Sensitivity | Tablas de sensibilidad payout/bonos | Computed |
| Calculation Trace | Paso a paso del calculo | Computed |
| Scenarios | CRUD de escenarios gobernados | Interactive |

### Endpoints (24 total)

**Historical/observational (11 GET):**
`/overview` `/weekly` `/daily` `/drivers` `/vehicles` `/shifts` `/input-mapping` `/quality` `/root-cause` `/simulator/defaults` `/simulator/baseline`

**Diagnostics (4 GET):**
`/diagnostics/drivers` `/diagnostics/vehicles` `/diagnostics/shifts` `/diagnostics/portfolio`

**Simulator execution (1 POST):**
`/simulator/run`

**Bonus config (2 GET/POST + 1 RESET):**
`/simulator/bonus-config` x2, `/simulator/bonus-config/reset`

**Scenarios (1 GET, 1 POST, 1 PATCH, 1 duplicate, 1 archive):**
`/simulator/scenarios` x2, `PATCH /{id}`, `POST /{id}/duplicate`, `POST /{id}/archive`

---

## FASE 2 — MATRIZ DE CAPACIDADES

| # | Capacidad | Ya existe donde | Completa / Parcial / No existe | Duplicaria Intelligence | Recomendacion |
|---|---|---|---|---|---|
| 1 | **Executive Overview** | Overview tab | **COMPLETA** — KPIs 30d + billing week, health status, findings, confidence layers | SI | No duplicar. Ya existe. |
| 2 | **Waterfall financiero** | Waterfall tab | **COMPLETA** — Desglose P&L con source/confidence por input | SI | No duplicar. Ya existe. |
| 3 | **Driver ranking** | Drivers tab + Diag-Drivers sub-tab | **COMPLETA** — Tabla de rentabilidad + clasificacion diagnostica con causas, severidad, confianza | SI | No duplicar. Diagnostics ya lo hace. |
| 4 | **Vehicle ranking** | Vehicles tab + Diag-Vehicles sub-tab | **COMPLETA** (LIMITED) — Config de flota + clasificacion con margen proxy | SI | No duplicar. Ya existe. |
| 5 | **Shift analysis** | Shifts tab + Diag-Shifts sub-tab | **COMPLETA** — Produccion dia/noche + diagnostico de brecha + limites de payout | SI | No duplicar. Ya existe. |
| 6 | **Root cause ranking** | Diag Root Causes sub-tab | **COMPLETA** — Causas mas frecuentes, impacto estimado, severidad | SI | No duplicar. Ya existe. |
| 7 | **Pareto/concentracion** | Diag Portfolio sub-tab | **COMPLETA** — Top 5 losses/gains, concentracion top 3, impacto hipotetico de retirar bottom 5 | SI | No duplicar. Ya existe en Portfolio. |
| 8 | **Gap Analysis** | Simulator Gap Analysis | **COMPLETA** — Brecha, 7 levers, ranking de 8 palancas, 6 combinaciones | SI | No duplicar. Ya existe en Simulator. |
| 9 | **Scenario comparison** | Simulator (baseline delta + comparator) | **COMPLETA** — Comparacion vs baseline (8 KPIs) + comparador entre escenarios cargados vs actual | SI | No duplicar. Ya existe en Simulator. |
| 10 | **Explainability Tree** | Simulator Explainability Tree | **COMPLETA** — Arbol expandible con fuente/confianza/impacto, math summary 7 pasos, trace | SI | No duplicar. Ya existe. |
| 11 | **Coverage/Data Quality** | Data Quality + Coverage Audit tabs | **COMPLETA** — MV status, freshness, warnings de cobertura, gaps operativos, root cause audit | SI | No duplicar. Ya existe. |
| 12 | **Operational remediation** | NO existe en ningun lado | **NO EXISTE** — Nadie dice que hacer con el conductor en perdida o el vehiculo no rentable | NO | **Este es el gap real que Intelligence podria llenar.** |
| 13 | **Portfolio impact** | Diag Portfolio sub-tab | **PARCIAL** — Muestra impacto hipotetico de retirar bottom 5 pero NO dice que accion tomar ni prioriza por factibilidad/impacto | PARCIAL | **Extender Portfolio, no duplicarlo.** |

---

## FASE 3 — DUPLICIDADES DETECTADAS

### Lo que ya existe (NO duplicar):

| Funcionalidad | Donde esta | Estado |
|---|---|---|
| Executive Overview | Overview tab | Implementado |
| P&L Waterfall | Waterfall tab | Implementado |
| Driver profitability ranking | Drivers tab | Implementado |
| Driver diagnostic classification | Diag-Drivers | Implementado |
| Vehicle profitability | Vehicles + Diag-Vehicles | Implementado |
| Shift day/night analysis | Shifts + Diag-Shifts | Implementado |
| Root cause ranking | Diag Root Causes | Implementado |
| Pareto/Top-N analysis | Diag Portfolio | Implementado |
| Gap Analysis (breach + levers) | Simulator | Implementado |
| Scenario comparison | Simulator | Implementado |
| Explainability tree/math/trace | Simulator | Implementado |
| Data quality/coverage/freshness | Data Quality + Coverage Audit | Implementado |
| Bonus config persistence | Simulator | Implementado |
| Scenario CRUD | Simulator | Implementado |
| Baseline vs scenario | Simulator | Implementado |
| Sensitivity analysis | Simulator | Implementado |

### Lo que NO existe (gap real):

| Funcionalidad | Estado actual |
|---|---|
| **Operational remediation** ("que hacer con este conductor/vehiculo") | No existe. Diagnostics dice QUE esta mal pero no QUE hacer. Gap Analysis dice CUANTO falta pero no QUIEN debe cambiar. |
| **Actionable priority** (ordenar por factibilidad x impacto) | Parcial en Portfolio (solo impacto hipotetico, sin factibilidad operativa) |
| **Cross-entity analysis** (conductor X usa vehiculo Y, ¿cual es el efecto neto?) | No existe. Asignacion conductor-vehiculo no disponible. |
| **Temporal patterns** (¿el conductor empeora con el tiempo? ¿hay estacionalidad?) | Parcial en Weekly Closed (solo fleet-level, no por conductor) |
| **What-if fleet changes** (agregar/quitar vehiculos, cambiar esquema de pago global) | Parcial en Simulator (1 conductor/vehiculo, no flota completa) |

---

## FASE 4 — PROPUESTA DE REORDENAMIENTO

### Estructura optima propuesta (sin duplicidad):

```
Profitability
├── Overview (KPIs + health + findings + confidence)
├── Diagnostics
│   ├── Drivers (classificacion, causas, severidad, explicacion)
│   │   └── [FUTURO P2.1: "Que hacer" por conductor — accion sugerida, factibilidad, impacto esperado]
│   ├── Vehicles (classificacion, margen proxy, utilizacion)
│   │   └── [FUTURO P2.1: "Que hacer" por vehiculo — rotar, reparar, reasignar]
│   ├── Shifts (brecha dia/noche, limites de payout)
│   ├── Portfolio (top losses/gains, concentracion, impacto hipotetico)
│   │   └── [FUTURO P2.1: Actionable priority matrix — impacto x factibilidad]
│   └── Root Causes (ranking de causas)
├── Simulator
│   ├── Inputs
│   ├── Bonus Config
│   ├── Baseline
│   ├── Results + Tree + Math Summary
│   ├── Gap Analysis + Baseline Delta
│   ├── Sensitivity
│   ├── Trace
│   └── Scenarios
├── Waterfall (P&L structure)
├── Data Quality (MV status, freshness, warnings)
└── Coverage Audit (gaps, root cause audit, billing support)
```

### Lo que NO se debe crear como tab nueva:

- **"Profitability Intelligence" como tab separada** — duplicaria Overview + Diagnostics + Simulator. Seria redundante.

### Lo que SI se debe hacer en P2.1:

- **Extender Diagnostics** con una capa de "Operational Remediation" que responda:
  - Para el conductor en perdida: ¿puede recuperarse con mas volumen? ¿requiere cambio de payout? ¿esta en declive?
  - Para el vehiculo no rentable: ¿se puede rotar? ¿mejorar utilizacion? ¿cambiar de turno?
  - Priorizacion por factibilidad x impacto (no solo impacto hipotetico)

---

## FASE 5 — VEREDICTO

### 1. ¿Conviene crear Intelligence como tab nueva?

**NO.** Crearia una tab que duplica Overview + Diagnostics + Simulator. El 85% de las capacidades de "Intelligence" ya existen distribuidas en las tabs actuales. Una tab nueva seria redundante y confundiria al usuario ("¿esto no es lo mismo que Diagnostics?").

### 2. ¿Conviene fusionar Intelligence dentro de Diagnostics?

**SI, parcialmente.** Diagnostics ya tiene clasificacion de entidades con causas, severidad y confianza. Lo que falta es el "que hacer" — operational remediation. Eso cabe naturalmente como extension de Diagnostics (una columna extra o un panel adicional por entidad), no como tab nueva.

### 3. ¿Que funcionalidades ya existen?

El **85%** de lo que tipicamente se llamaria "Profitability Intelligence" ya esta implementado:
- Ranking de conductores/vehiculos/turnos (Drivers, Vehicles, Shifts, Diag-*)
- Clasificacion por severidad y causa (Diag-Drivers, Diag-Vehicles)
- Pareto/Top-N/Concentracion (Diag Portfolio)
- Gap Analysis y brechas (Simulator)
- Explainability y trazabilidad (Simulator tree + trace + math summary)
- Waterfall P&L (Waterfall tab)
- Data quality y cobertura (Data Quality, Coverage Audit)
- Comparacion de escenarios (Simulator baseline delta + comparator)

### 4. ¿Que funcionalidades faltan realmente?

Lo unico que realmente falta es **operational remediation**:

| Missing | How to address |
|---|---|
| "Que hacer" por conductor en perdida | Nueva columna/seccion en Diag-Drivers con accion sugerida, factibilidad, impacto esperado |
| "Que hacer" por vehiculo no rentable | Nueva columna/seccion en Diag-Vehicles |
| Priorizacion accionable (factibilidad x impacto) | Extender Diag Portfolio con matriz de priorizacion |
| Temporal patterns por conductor | Requiere nueva MV o query (fuera de scope inmediato) |
| Fleet-wide what-if | Simulator necesita extenderse a multi-driver (complejo, P2+) |

### 5. ¿Que se debe eliminar, esconder o renombrar?

**Eliminar:** Nada. Todas las tabs tienen valor.

**Esconder:** Considerar que "Weekly Closed", "Last Closed Day", "Drivers", "Vehicles", "Shifts" podrian colapsarse en un grupo "Raw Data" o "Historical" para simplificar la navegacion (son datos crudos, no analisis).

**Renombrar:** "Diagnostics" → "Entity Diagnostics" para enfatizar que es diagnostico por entidad (no confundir con diagnostico de sistema).

### 6. Siguiente prompt recomendado

```
PROMPT E2E — YEGO PRO PROFITABILITY P2.1 OPERATIONAL REMEDIATION

Extender Diagnostics con capa de remediacion operativa:
- Por cada conductor en LOSS/RISKY, calcular accion sugerida (mas volumen / reducir payout / cambiar turno)
  basada en causas detectadas.
- Factibilidad estimada (LOW/MEDIUM/HIGH) basada en benchmarks del parque.
- Impacto esperado si se ejecuta la accion.
- Priorizacion global: matriz factibilidad x impacto.
- NO crear IA. NO ejecutar acciones. Solo diagnostico accionable deterministico.
```
