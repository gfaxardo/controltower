# PROJECTION EXPANSION DEFAULT QA

**Date**: 2025-05-25
**Mode**: Vs Proyección

---

## DEFAULT BEHAVIOR

| Check | Status |
|---|---|
| Ciudades desplegadas por defecto (todos los granos) | ✅ `collapsed = new Set()` inicial |
| Daily grain: ciudades visibles sin expandir manualmente | ✅ Ya no colapsa automáticamente |
| Weekly/monthly: ciudades visibles | ✅ Igual que antes (siempre expandido) |

## USER GOVERNANCE

| Check | Status |
|---|---|
| Usuario puede colapsar ciudad individual | ✅ `toggleCity(ck)` |
| Usuario puede expandir todo | ✅ `expandAll()` |
| Usuario puede colapsar todo | ✅ `collapseAll()` |
| Interacción del usuario marcada | ✅ `userToggledRef.current = true` |

## NO FIGHTBACK

| Check | Status |
|---|---|
| No re-expande automáticamente tras colapso manual | ✅ `userToggledRef` previene |
| No re-colapsa automáticamente | ✅ Solo reset en cambio de contexto |
| KPI focus change NO resetea | ✅ Solo `cities` keys change triggerea reset |

## CONTEXT RESET

| Check | Status |
|---|---|
| Cambio de país resetea expansión | ✅ Nuevo conjunto de city keys |
| Cambio de grano resetea expansión | ✅ Nuevo conjunto de city keys |
| Cambio de modo (Evolución ↔ Proyección) | ✅ Nuevo conjunto de city keys |
| Cambio de plan version resetea | ✅ Nuevo conjunto de city keys |
| Scroll/zoom NO resetea | ✅ `cities` keys no cambian |

## PERFORMANCE

| Check | Status |
|---|---|
| Column windowing activo | ✅ `visibleColRange` tracking |
| Usuario puede colapsar para reducir DOM | ✅ Manual collapse available |
| Sin re-render storms por default expandido | ✅ State estable, sin loops |

## VERDICT: GO
