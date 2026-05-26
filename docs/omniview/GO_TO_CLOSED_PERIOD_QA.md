# GO TO CLOSED PERIOD — QA

**Date**: 2026-05-25

---

| Check | Status |
|---|---|
| Usa `closedPeriodAnchor.anchorPeriodKey` | ✅ `scrollToCurrentPeriod` en `Matrix.jsx` |
| Centra último cierre en daily | ✅ `maxDataDate` de `projectionMeta.data_freshness` |
| Centra última semana cerrada en weekly | ✅ Busca `weekState === 'closed'`, fallback penúltima |
| Centra último mes completo en monthly | ✅ Busca `comparison_basis === 'full_month'`, fallback penúltimo |
| No pelea con scroll manual | ✅ `userHasScrolledRef` guard |
| Botón "Ir al cierre" label dinámico | ✅ `getAnchorButtonLabel()` muestra "Ir al cierre" si hoy es parcial |
| Botón funciona en daily/weekly/monthly | ✅ Mismo callback `scrollToCurrentPeriod` para todos |
| Fullscreen no rompe anclaje | ✅ `scrollContainerRef` se re-attacha correctamente |

## VERDICT: PASS
