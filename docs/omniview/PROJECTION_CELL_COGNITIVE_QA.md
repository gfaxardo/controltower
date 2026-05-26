# PROJECTION CELL COGNITIVE QA

**Date**: 2025-05-25
**Mode**: Vs Proyección

---

## CELL HIERARCHY

| Row | Element | Font | Weight | Color | Status |
|---|---|---|---|---|---|
| 1 | HOY badge | 7px | bold | emerald-500 | ✅ Terciario |
| **2** | **REAL VALUE** | **13-16px** | **extrabold** | **gray-900** | **✅ DOMINANTE** |
| **3** | **MOMENTUM DELTA** | **11px** | **extrabold/bold** | **severity** | **✅ DOMINANTE** |
| 4 | Plan + Avance | 9px | normal | gray-400 | ✅ Terciario |
| 5 | Status label | 9px | medium | colored | ✅ Terciario |

## CHECKS

| Check | Status |
|---|---|
| Valor real domina (extrabold, más grande) | ✅ |
| Delta domina (colored, bold, inmediatamente abajo) | ✅ |
| Color comunica dirección (green=up, red=down) | ✅ |
| Intensidad comunica severidad (5 niveles) | ✅ |
| Gap eliminado de la celda (tooltip only) | ✅ |
| Plan (Proy) colapsado a línea de contexto ultra-small | ✅ |
| Avance % atenuado (contexto) | ✅ |
| No aparece NaN | ✅ `fmtAttainment`, `fmtGapPct` guarded |
| No aparece undefined | ✅ Todos los paths tienen fallback |
| No aparece null textual | ✅ Convertido a '—' |
| No hay microtexto excesivo | ✅ Solo 2 líneas dominantes + 2 línea contextual |

## VERDICT: GO
