# SCROLL OWNERSHIP AUDIT

**Motor:** Control Foundation  
**Fecha:** 2026-05-31  

---

## 1. Jerarquía de Overflow (ANTES)

```
LEVEL 0 — Root: overflow-x-hidden           (CLIPS horizontal)
LEVEL 1 — CommandHeader: overflow-hidden    (internal card)
LEVEL 2 — Controls: overflow-hidden         (filter card)
LEVEL 3 — Fullscreen: fixed overflow-hidden (fullscreen modal)
LEVEL 4 — Table card: overflow: clip         (visual card)
LEVEL 5 — SCROLL CONTAINER: overflow-x-auto overflow-y-auto  max-height: calc(100vh - 240px)
```

### Problemas Identificados

1. **Doble scroll horizontal:** El root `overflow-x-hidden` en LEVEL 0 clipa el contenido antes de que la tabla en LEVEL 5 pueda hacer scroll. El usuario ve parte del contenido cortado y un scrollbar interno que no alcanza.

2. **Doble scroll vertical:** LEVEL 5 tiene `max-height` + `overflow-y-auto`, creando un scroll vertical dentro de la tabla. La página también tiene su propio scroll. Resultado: dos scrollbars verticales.

3. **Fullscreen roto:** LEVEL 3 usa `fixed inset-0 overflow-hidden` que bloquea todo scroll. Solo funcionaba porque LEVEL 5 tenía su propio `overflow-y-auto`. Sin ese, el fullscreen sería inutilizable.

---

## 2. Jerarquía de Overflow (DESPUÉS)

```
LEVEL 0 — Root: relative                     (sin overflow-x)
LEVEL 1 — CommandHeader: overflow-hidden    (sin cambios)
LEVEL 2 — Controls: overflow-hidden         (sin cambios)
LEVEL 3 — Fullscreen: fixed overflow-y-auto  (fullscreen → la página es la tabla)
LEVEL 4 — Table card: overflow: clip         (sin cambios)
LEVEL 5 — SCROLL CONTAINER:
           Normal: overflow-x-auto            (solo horizontal)
           Fullscreen: overflow-x-auto overflow-y-auto max-height: calc(100vh - 120px)
```

### Cambios

| Nivel | Antes | Después | Motivo |
|-------|-------|---------|--------|
| Root | `overflow-x-hidden` | sin overflow-x | Eliminar clip horizontal |
| Fullscreen | `overflow-hidden` | `overflow-y-auto` | Permitir scroll vertical en modal |
| Scroll container (normal) | `overflow-y-auto` + max-height | solo `overflow-x-auto` | El page scroll maneja vertical |
| Scroll container (fullscreen) | `overflow-y-auto` + 240px offset | `overflow-y-auto` + 120px offset | Ajustado para fullscreen |
| `isFullscreen` prop | No existía | Prop booleana | Diferenciar modos |

---

## 3. Dueño del Scroll Horizontal

**La tabla (scroll container en LEVEL 5) es dueña única del scroll horizontal.**

Siempre tiene `overflow-x-auto`. Nunca hay otro elemento con `overflow-x` en la jerarquía superior.

El sticky header (`position: sticky; top: 0`) y las columnas fijas (ciudad, línea) con `position: sticky; left: 0` funcionan dentro de este contenedor.

---

## 4. Dueño del Scroll Vertical

**Modo normal:** El `window` / `body` de la página es dueño del scroll vertical. La tabla crece a su altura natural, sin límite.

**Modo fullscreen:** El modal fullscreen (`fixed inset-0 overflow-y-auto`) es dueño del scroll vertical. La tabla tiene `max-height: calc(100vh - 120px)` para dejar espacio al header del modal.

---

## 5. Navegación al Presente

### 5.1 Botón "Ir al presente"
Se quitó la etiqueta "Ir al cierre". Ahora siempre muestra:
- Daily: "Ir a hoy"
- Weekly: "Ir a sem. actual"
- Monthly: "Ir a mes actual"

### 5.2 Auto-center al cargar
- `scrollToCurrentPeriod()` se ejecuta tras la carga de datos (doble RAF)
- `userHasScrolledRef` previene re-scroll después de interacción manual
- Se reinicia al cambiar filtros (grain, país, ciudad, etc.)

### 5.3 Ventana presente
El motor `currentPeriodFocusEngine.js` calcula el target:
- Daily: día actual o más cercano atrás
- Weekly: semana ISO actual
- Monthly: mes actual

El `calculateScrollTarget()` centra el período en el viewport: `fixedW + (idx * colW) - (viewportW / 2) + (colW / 2)`.
