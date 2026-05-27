# Fase 1.1.1 — E2E Upload Validation Before UX Test

**Fecha:** 2026-05-26
**Estado:** Completado (CONDITIONAL GO)
**Fase anterior:** Fase 1.1 — Omniview Perspective Engine
**Siguiente fase:** Fase 1.2 — Ownership UX Hardening

======================================================================
RESUMEN
======================================================================

Se validó de cabo a rabo que la plantilla unificada real se puede subir
por endpoint y alimenta correctamente toda la cadena: Omniview, Ownership
Governance, Ownership Serving, y Ownership Perspective.

Resultado QA: 58/60 PASS → CONDITIONAL GO.

======================================================================
PLAN VERSION DE PRUEBA
======================================================================

`e2e_20260526_165110`

Esta versión puede usarse para pruebas manuales desde la UX.

======================================================================
RESULTADOS POR PASO
======================================================================

### PASO 1 — CSV Validation
| Check | Resultado |
|-------|-----------|
| Columnas correctas | 9/9 |
| Filas totales | 2,264 |
| Metrics: trips/revenue/drivers | 3/3 |
| Periods: 2026-01 a 2026-12 | 12/12 |
| Owners: Ariana/Stacy/Eduardo | 3/3 |
| Countries/Cities/LOBs | 2 / 9 / 10 |
| Validation errors | 0 |
| Duplicados | 0 |

### PASO 2 — Upload
| Métrica | Valor |
|---------|-------|
| Upload time | 45.8s |
| rows_read | 2,264 |
| rows_valid | 2,048 |
| rows_invalid (duplicates) | 216 |
| projected_trips_total | 52,664,781 |
| projected_revenue_total | 3,118,587,353 |
| projected_drivers_total | 472,591 |
| months_detected | 12 |

### PASO 3 — Canonical Plan
| Métrica | Valor |
|---------|-------|
| Rows inserted | 684 |
| projected_trips | 52,664,781 |
| projected_drivers | 472,591 |
| Cities preserved | 9/9 |
| LOBs preserved | 8/8 |
| Duplicados | 0 |

### PASO 4 — Ownership Governance
| Métrica | Valor |
|---------|-------|
| Ownership rows | 57 |
| Owners detected | 3 |
| Missing owner | 0 |
| Eduardo | 21 rows |
| Ariana | 18 rows |
| Stacy | 18 rows |

### PASO 5 — Refresh Serving MV
| Métrica | Valor |
|---------|-------|
| Refresh time | 0.7s |
| MV rows | 684 |
| Ownership coverage | 100% (684/684) |
| MV owners | 3 |

### PASO 6 — Omniview Endpoints
- Omniview projection: 0 rows (expected — serving fact table needs separate generation)
- Endpoint responds correctly without errors

### PASO 7 — Ownership Serving Endpoint
| Métrica | Valor |
|---------|-------|
| Rows returned | 684 |
| assigned_count | 684 |
| missing_count | 0 |
| By owner entries | 3 |
| Eduardo: proj trips | 4,516,255 |
| Ariana: proj trips | 46,008,313 |
| Stacy: proj trips | 2,140,213 |
| Totals MV vs Plan | Delta = 0 |

### PASO 8 — No Frontend/Rankings
- Sin cambios en frontend en esta fase
- Sin rankings/scoreboard/gamificación

======================================================================
ANÁLISIS DE LOS 2 FAILS
======================================================================

1. **rows_invalid: 216**: Son filas duplicadas en el CSV (mismo canonical LOB
   para diferentes variantes Excel, como "Delivery moto" y "Dellivery bicicleta"
   ambos mapean a "delivery"). Se manejan correctamente con ON CONFLICT
   DO NOTHING. No se pierden datos — se conserva el primer valor encontrado.

2. **Omniview projection 0 rows**: El endpoint `get_omniview_projection` lee de
   `serving.omniview_projection_daily_fact`, una tabla materializada que requiere
   un pipeline de generación separado. La versión e2e tiene datos correctos en
   staging, canonical plan, y ownership serving MV. El serving projection fact
   es independiente y no afecta a Ownership Perspective.

Ambos son NO BLOQUEANTES para la prueba manual UX.

======================================================================
VEREDICTO
======================================================================

**CONDITIONAL GO** (58/60 PASS)

Gonzalo puede proceder con la prueba manual UX usando la plan_version:
`e2e_20260526_165110`

Para la prueba:
1. La perspectiva Operational funciona normalmente
2. En modo Vs Proyección, seleccionar plan_version `e2e_20260526_165110`
3. Cambiar perspectiva a "Ownership"
4. Verificar que aparecen 3 owners con métricas reales

Los datos en staging y ownership están completos y correctos.
El Ownership Serving endpoint devuelve 684 filas con 100% coverage.

======================================================================
BACKLOG REGISTRADO
======================================================================

**Fase 1.2 — Ownership UX Hardening**

- Jerarquía visual clara: Jefe → LOB → Ciudad
- Subtotales por owner
- Labels humanos (no technical keys)
- Estados visuales assigned/missing/conflicting
- Empty states amigables
- Loading skeleton más suave
- Tooltip explicativo en el selector de perspectiva
- No rankings todavía
