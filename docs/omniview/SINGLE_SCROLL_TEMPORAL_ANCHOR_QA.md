# SINGLE SCROLL + TEMPORAL ANCHOR — QA

**Date**: 2026-05-25
**Mode**: Vs Proyección

---

## 1. SINGLE HORIZONTAL SCROLL

| Check | Status |
|---|---|
| Solo una barra horizontal visible en modo normal | ✅ `overflow: clip` en outer + `overflow-x-auto` único en scroll master |
| Solo una barra horizontal en fullscreen | ✅ Overlay fullscreen usa `overflow-hidden`, no crea scroll context |
| Root `overflow-x-hidden` no interfiere | ✅ Full-bleed layout funciona, sin scroll de página horizontal |
| Zoom no crea scroll adicional | ✅ `overflow: clip` + `min-w-0` contienen scale() |

## 2. SINGLE VERTICAL SCROLL

| Check | Status |
|---|---|
| Solo un scroll vertical para la matriz | ✅ `scrollContainerRef` con `overflow-y-auto` + `maxHeight` |
| Fullscreen no duplica scroll vertical | ✅ Overlay `overflow-hidden`, sin `overflow-y-auto` |
| Página no crea scroll por matriz | ✅ `maxHeight: calc(100vh - 240px)` contiene la tabla |
| Sticky intacto | ✅ Header/Totals/City columns dentro del scroll master |

## 3. TEMPORAL ANCHORING

| Check | Status |
|---|---|
| Daily: abre centrado en HOY | ✅ `scrollToCurrentPeriod` usa `displayProjMatrix.allPeriods` |
| Weekly: abre centrado en semana actual | ✅ `resolveCurrentPeriodIndex` con ISO week |
| Monthly: abre centrado en mes actual | ✅ First day of month cálculo |
| HOY visible sin scroll manual | ✅ Centrado en viewport: `targetLeft - viewportWidth/2 + colW/2` |
| Cambio de grain re-ancla | ✅ `autoScrollAppliedRef` reset en grain change |
| Cambio de filtro re-ancla | ✅ Reset también en country, city, year, month, businessSlice |
| Usuario puede scrollear sin pelea | ✅ `userHasScrolledRef` detecta wheel/touchmove |
| "Ir a hoy" funciona | ✅ Botón resetea `userHasScrolledRef` y llama `scrollToCurrentPeriod` |

## 4. PAST / PRESENT / FUTURE

| Check | Status |
|---|---|
| Pasado degradado (opacidad) | ✅ `computePastAgingOpacity` hasta 55% |
| Presente dominante (emerald border/glow) | ✅ `isCurrentPeriod` en cell renderer |
| Futuro tenue (ghosted) | ✅ `futureDim: opacity-45 grayscale-[30%]` |
| Badge HOY visible | ✅ Badge emerald en columna actual |
| Delta comparable más legible en presente | ✅ `text-[16px] extrabold` en current vs `text-[13px]` normal |

## 5. FULLSCREEN / DRILL / STICKY

| Check | Status |
|---|---|
| Fullscreen sin doble scroll | ✅ Overlay `overflow-hidden`, tabla es único scroll owner |
| Drill panel funcional | ✅ Sidebar independiente, intacto |
| ESC cierra fullscreen | ✅ keydown listener intacto |
| Sticky headers/columns intactos | ✅ Dentro del scroll master |

## 6. BUILD

| Check | Status |
|---|---|
| Build PASS | ✅ 816 módulos, 4.17s |
| No console errors esperados | ✅ Sin cambios en lógica de datos |
| No rerender storms | ✅ Sin nuevos efectos costosos |
| Evolution wiring intacto | ✅ Zero cambios en Evolution mode |

---

## VERDICT: PASS

Single scroll architecture + temporal anchoring operacionalmente correcto.
