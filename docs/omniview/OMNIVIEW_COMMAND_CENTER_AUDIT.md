# OMNIVIEW COMMAND CENTER AUDIT

**Date**: 2026-05-25

---

## MUST FIX

| # | Issue | Impact | Plan |
|---|-------|--------|------|
| 1 | Sin command header — matrix arranca directamente | Falta contexto operacional arriba | Agregar OmniviewCommandHeader con estado general + attention summary |
| 2 | Dificultad para detectar blocked/critical | Operador debe scrollear la matriz para encontrar problemas | Severity system existente → attention-first strip |
| 3 | Filtros ocupan demasiado espacio | Toolbar vertical con grano, país, ciudad, KPI, sort, etc. | Compactar con ct-toolbar-compact |
| 4 | MatrixExecutiveBanner es el único elemento de contexto | Si está oculto, no hay resumen | Envolver en command header que SIEMPRE muestra estado |

## SHOULD FIX

| # | Issue | Impact | Plan |
|---|-------|--------|------|
| 5 | Exceso de opciones simultáneas visibles | Grain selector + 8 filters + sort + KPI focus + plan version | Progressive disclosure: essentials visibles, advanced colapsados |
| 6 | Sin indicador de modo actual claro | Compact/normal, evolution/projection — no se lee rápido | Badge de modo en command header |
| 7 | Sin integración con sistema de severities existente | Severities implementadas pero no visibles en Omniview | Usar DecisionPriorityStrip, DecisionSeverityBadge |

## PRESERVE

| # | Elemento | Razón |
|---|----------|-------|
| 8 | BusinessSliceOmniviewMatrix.jsx core | Complejidad crítica. 3601 líneas. NO tocar lógica interna. |
| 9 | BusinessSliceOmniviewMatrixTable.jsx | Sticky headers, scroll, drill. Intacto. |
| 10 | MatrixExecutiveBanner | Ya funciona bien. Envolver, no reemplazar. |
| 11 | ECharts | Intacto. |
| 12 | Projection logic | Intacto. |
| 13 | Fullscreen mode | Preservado. |

## DO NOT TOUCH

| # | Elemento | Razón |
|---|----------|-------|
| 14 | Cell rendering (BusinessSliceOmniviewMatrixCell) | Crítico. No modificar. |
| 15 | Data fetching / matrix building | Complejo. No modificar. |
| 16 | Alerting/insight engine | Complejo. No modificar. |
| 17 | Serving facts | Gobernado. No modificar. |
