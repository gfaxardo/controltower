# SCROLL OWNERSHIP + GO TO PRESENT — REPORTE FINAL

**Motor:** Control Foundation  
**Ticket:** OMNIVIEW UX-FIX PACK 1B-A  
**Fecha:** 2026-05-31  
**Estado:** COMPLETADO  
**Build:** PASS  

---

## 1. Dueño del Scroll Horizontal

**La tabla (scroll container en `BusinessSliceOmniviewMatrixTable.jsx:280`) es dueña única.**

| Antes | Después |
|-------|---------|
| Root con `overflow-x-hidden` clipaba contenido | Root sin overflow-x, tabla controla |
| Dos scrollbars horizontales (página + tabla) | Un solo scrollbar horizontal (tabla) |

---

## 2. Dueño del Scroll Vertical

**Modo normal:** La página/window es dueña del scroll vertical. La tabla crece a su altura natural.

**Modo fullscreen:** El modal fullscreen (`overflow-y-auto`) es dueño. La tabla tiene `max-height: calc(100vh - 120px)`.

| Antes | Después |
|-------|---------|
| Tabla con `max-height` + `overflow-y-auto` creaba doble scroll vertical | Tabla sin límite de altura en modo normal → un solo scroll vertical |
| Fullscreen con `overflow-hidden` rompía el scroll | Fullscreen con `overflow-y-auto` funciona correctamente |

---

## 3. Cómo se Calcula el Presente

Función `scrollToCurrentPeriod()` en `BusinessSliceOmniviewMatrix.jsx:1149`:

1. Obtiene `currentPeriodKey` vía `getCurrentPeriodKey(grain)`
2. Resuelve índice en `allPeriods` vía `resolveCurrentPeriodIndex()`
3. Calcula scroll target para centrar en viewport: `fixedW + (idx * colW) - (viewportW / 2) + (colW / 2)`
4. Ejecuta `container.scrollTo({ left: scrollTo, behavior: 'smooth' })`

Se ejecuta al cargar datos (doble RAF después de paint). No compite con el usuario: `userHasScrolledRef` desactiva el auto-scroll tras interacción manual.

---

## 4. Cambios Realizados

| Archivo | Cambio | Línea |
|---------|--------|-------|
| `BusinessSliceOmniviewMatrix.jsx` | Root: removido `overflow-x-hidden` | 1408 |
| `BusinessSliceOmniviewMatrix.jsx` | Fullscreen evolution: `overflow-hidden` → `overflow-y-auto` + `isFullscreen={true}` | 1943, 1970 |
| `BusinessSliceOmniviewMatrix.jsx` | Fullscreen projection: `overflow-hidden` → `overflow-y-auto` + `isFullscreen={true}` | 2071, 2105 |
| `BusinessSliceOmniviewMatrixTable.jsx` | Nuevo prop `isFullscreen` | 108 |
| `BusinessSliceOmniviewMatrixTable.jsx` | Scroll container condicional: normal = solo `overflow-x-auto`, fullscreen = `overflow-x-auto overflow-y-auto` + `max-height: calc(100vh - 120px)` | 280 |
| `projectionClosedPeriodEngine.js` | `getAnchorButtonLabel`: removido "Ir al cierre" → siempre grain-specific | 283-291 |

---

## 5. QA

| Verificación | Resultado |
|-------------|-----------|
| 1 scroll horizontal en normal | SI — solo la tabla tiene `overflow-x-auto` |
| 1 scroll vertical en normal | SI — la página scrollea, la tabla no tiene límite de altura |
| 1 scroll en fullscreen | SI — el modal tiene `overflow-y-auto`, la tabla tiene `max-height` |
| Sticky header intacto | SI — `position: sticky; top: 0` funciona en el contenedor de scroll |
| Columnas fijas intactas | SI — `position: sticky; left: 0` en ciudad y línea |
| "Ir al presente" sin "cierre" | SI — etiquetas: "Ir a hoy", "Ir a sem. actual", "Ir a mes actual" |
| Auto-center al cargar | SI — `scrollToCurrentPeriod` con doble RAF |
| No re-scroll tras interacción | SI — `userHasScrolledRef` bloquea |
| Build PASS | SI — 844 modules, 7.24s |
