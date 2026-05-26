# VIEWPORT DOMINANCE — QA

**Date**: 2025-05-25
**Mode**: Vs Proyección

---

## 1. PRESENTE DOMINANTE

| Check | Status |
|---|---|
| Columna HOY visible sin scroll manual | ✅ Auto-scroll centers on current period after data loads |
| Badge HOY / SEM ACT / MES ACT visible | ✅ Badge rendered in ProjectionCellRender for current period |
| Fuente Real más grande en columna actual | ✅ `text-[15px]` (vs `text-[13px]`) en modo cómodo, bold |
| Borde emerald en columna actual | ✅ `border-l-2 border-r-2 border-emerald-400/60` |
| Glow/box-shadow en columna actual | ✅ `shadow-[inset_0_0_16px_rgba(16,185,129,0.10),0_0_8px_rgba(16,185,129,0.08)]` |
| Fondo degradado emerald | ✅ `bg-gradient-to-b from-emerald-50/40 to-emerald-50/20` |

## 2. PASADO DEGRADADO

| Check | Status |
|---|---|
| Columnas antiguas con opacidad reducida | ✅ `computePastAgingOpacity` reduce opacidad hasta 55% |
| Degradación progresiva (no abrupta) | ✅ 2.5% por paso en daily, escalonado en weekly/monthly |
| Período actual NO degradado | ✅ `isCurrentPeriod` y períodos futuros excluidos |
| Selección NO degradada | ✅ `!isSelected` excluye celda seleccionada |

## 3. VIEWPORT CENTRADO

| Check | Status |
|---|---|
| Auto-scroll al cargar proyección | ✅ Trigger en `useEffect` con `projectionRows.length` |
| "Ir a hoy" botón en proyección | ✅ Mostrado con color emerald |
| Scroll usa displayProjMatrix | ✅ `displayProjMatrix?.allPeriods` para match exacto |
| Centrado horizontal (HOY al centro) | ✅ `viewportWidth/2 + colW/2` en `scrollToCurrentPeriod` |

## 4. NAVEGACIÓN CLARA

| Check | Status |
|---|---|
| Una sola barra horizontal | ✅ `overflow: clip` elimina el doble scroll |
| Una sola barra vertical | ✅ Scroll container único con maxHeight |
| Sin nested overflow conflict | ✅ Outer wrapper usa `overflow: clip` |
| Scroll natural | ✅ `behavior: 'smooth'` en botón, `'auto'` en carga inicial |

## 5. NO PÉRDIDA ESPACIAL

| Check | Status |
|---|---|
| Operador sabe dónde está HOY | ✅ Badge + border + glow |
| Columnas fijas visibles al scroll | ✅ Sticky `COL1_W` + `COL2_W` con z-index |
| Indicador de posición de columnas | ✅ Footer bar muestra rango de columnas |
| Botón "Ir a inicio" disponible | ✅ En footer bar |

## 6. NO MATRIX CONFUSION

| Check | Status |
|---|---|
| Celdas vacías muestran "—" no NaN | ✅ `fmtAttainment`/`fmtGap`/`fmtGapPct` devuelven '—' o null |
| Momentum no muestra NaN | ✅ `Number.isFinite(momValue)` guard |
| Badges de estado correctos | ✅ `getProjectionStatusLabel` |
| Comparables rotos protegidos | ✅ `showGapPctFallback` cuando `hasNegActual` |

## 7. STICKY INTACTO

| Check | Status |
|---|---|
| Header sticky (top 0, z-20) | ✅ Unchanged |
| Total row sticky (top: headerH, z-18) | ✅ Unchanged |
| City/Label columns sticky left | ✅ Unchanged |
| Sticky elements inside single scroll container | ✅ Still inside `scrollContainerRef` |

## 8. FULLSCREEN INTACTO

| Check | Status |
|---|---|
| Fullscreen overlay scroll | ✅ `overflow-y-auto` on overlay |
| Fullscreen matrix renders correct matrix | ✅ `displayProjMatrix` in fullscreen |
| Escape to exit | ✅ keydown listener |
| Fullscreen preserves mode | ✅ Both evolution and projection fullscreen preserved |

## 9. BUILD

| Check | Status |
|---|---|
| Build PASS | ✅ 813 modules, 9.88s |
| No new warnings | ✅ |
| No compilation errors | ✅ |

---

## VERDICT: PASS

Todos los checks superados. El viewport de proyección está centrado operacionalmente en el presente.
