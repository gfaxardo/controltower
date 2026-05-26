# VISIBLE WORST DETECTION — DECISION

**Date**: 2026-05-25

---

## DECISIÓN: USAR TODOS LOS PERÍODOS (NO SOLO VISIBLE)

### Razón

El `worstPeriodPk` actual se calcula sobre todos los `allPeriods` de la fila, no solo los visibles en el viewport. Esto es correcto por ahora porque:

1. El cálculo es O(n) con `n = allPeriods.length` (~30-60 períodos). Es insignificante.
2. Limitar a viewport visible requeriría `visibleColRange` state + cross-component sync → complejidad innecesaria.
3. El worst-in-row es una señal de "esta fila tiene un problema en algún período". El operador hace scroll y lo encuentra.
4. Si el worst está fuera del viewport, sirve como guía de navegación: "hay algo peor más allá".

### Futuro (no ahora)

Si en el futuro se necesita "worst visible only", implementar como:
- `LineRow` ya recibe `visibleColRange` implícitamente a través del render
- Se podría filtrar `allPeriods` por rango visible antes de buscar worst
- Costo: O(visible_count) en vez de O(N) — mejora marginal

### Veredicto: **NO IMPLEMENTAR AHORA**

El cálculo actual es correcto, liviano y funcional.
