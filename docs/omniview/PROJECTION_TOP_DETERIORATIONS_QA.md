# PROJECTION TOP DETERIORATIONS QA

**Date**: 2025-05-25
**Component**: `OmniviewMomentumPriorityStrip`

---

## VISIBILITY

| Check | Status |
|---|---|
| Strip visible cuando hay deterioros | ✅ Muestra top 5 deterioros |
| Strip oculto cuando no hay deterioros | ✅ Retorna `null`, sin espacio vacío |
| No gigante | ✅ 1 línea, min-height 24px |
| Posición: debajo del Command Header | ✅ Entre header y matrix controls |

## ORDERING

| Check | Status |
|---|---|
| Ordenado por severidad | ✅ `extractMomentumPriorityFromMatrix` |
| Basado en momentum (DoD/WoW/MoM) | ✅ Lee de `periodPop` en matrix |
| No basado en plan vs real | ✅ Momentum-first prioritization |

## NATURE

| Check | Status |
|---|---|
| Sin recomendaciones textuales | ✅ Solo chips de severidad |
| Sin IA / ML | ✅ Determinístico |
| Sin acciones automáticas | ✅ Solo display |
| Útil para orientar mirada | ✅ Operador ve qué ciudades/líneas revisar |

## WIRING

| Check | Status |
|---|---|
| Proyección mode wired | ✅ `projMatrix?.cities` |
| Evolution mode wired | ✅ `baseMatrix?.cities` |
| `maxItems=5` | ✅ Limita display |
| `showImprovements=false` | ✅ Solo deterioros por defecto |

## VERDICT: GO
