# SINGLE SCROLL CONTRACT

**Date**: 2026-05-25
**Version**: 1.0

---

## REGLA ABSOLUTA

> Solo UN contenedor controla scroll horizontal de la matriz.
> Solo UN contenedor controla scroll vertical interno de la matriz.
> La página NO debe crear scrollbars adicionales para navegar la matriz.

---

## HORIZONTAL SCROLL CONTRACT

| Dueño | `scrollContainerRef.current` — Table.jsx:270 |
|---|---|
| Propiedad | `overflow-x-auto` |
| Cálculo de ancho | `COL1_W + COL2_W + allPeriods.length × colW` |
| Contenido sticky | Header (top:0), TotalsRow (top:headerH), COL1/COL2 (left) |
| Zoom | `transform: scale(zoom%)` en wrapper padre — no afecta scrollLeft |
| Fullscreen | Mismo dueño, sin overflow-x en padre |

### PROHIBIDO
- Cualquier `overflow-x-auto` o `overflow-x-scroll` fuera del scroll master
- Root debe usar `overflow-x-hidden` o `overflow-x-clip`
- Tabla outer debe usar `overflow: clip`

---

## VERTICAL SCROLL CONTRACT

| Dueño | `scrollContainerRef.current` — Table.jsx:270 |
|---|---|
| Propiedad | `overflow-y-auto` |
| Altura máxima | `calc(100vh - 240px)` en normal, `calc(100vh - 180px)` en fullscreen |
| Sticky | Header y TotalsRow son sticky dentro del mismo contenedor |
| Filas | Todas accesibles por scroll vertical único |

### PROHIBIDO
- `overflow-y-auto` en fullscreen overlay
- `overflow-y-auto` en wrappers padre de la tabla
- Página con scroll vertical causado por la matriz (maxHeight previene esto)

---

## FULLSCREEN CONTRACT

| Overlay | `fixed inset-0 z-[100]` |
|---|---|
| Overflow | `overflow: hidden` (NO auto, NO scroll) |
| Tabla scroll | Mismo `scrollContainerRef` con maxHeight ajustado al espacio fullscreen |
| Sidebar | Drill/Inspector con `overflow-y-auto` propio — OK, es independiente |

**Regla**: El overlay fullscreen es un contenedor de presentación, NO un scroll owner. La tabla sigue siendo el scroll master.

---

## STICKY CONTRACT

| Elemento | Posición | Dependencia |
|---|---|---|
| Header (`<thead>`) | `sticky top: 0` | Scroll master Y |
| TotalsRow | `sticky top: headerH` | Scroll master Y |
| Columna ciudad (COL1) | `sticky left: 0` | Scroll master X |
| Columna nombre (COL2) | `sticky left: COL1_W` | Scroll master X |

Todos los elementos sticky están dentro del scroll master (Table.jsx:270). No necesitan scroll propio.

---

## "IR A HOY" CONTRACT

| Función | `scrollToCurrentPeriod()` en Matrix.jsx:1052 |
|---|---|
| Target | `scrollContainerRef.current` |
| Cálculo | `fixedW + (idx × colW) - viewportWidth/2 + colW/2` |
| Períodos fuente | `displayProjMatrix.allPeriods` (proyección) / `matrix.allPeriods` (evolución) |
| Behavior | `'smooth'` para botón, `'auto'` para carga inicial |

### PROHIBIDO
- Usar otro scroll container que no sea `scrollContainerRef`
- Hacer scroll parcial (solo unos pixels)
- Depender de Evolution wiring en modo proyección

---

## VIOLACIONES DEL CONTRATO

Si se detecta:
- Doble barra horizontal → hay `overflow-x-auto` fuera del master
- Doble barra vertical → hay `overflow-y-auto` en fullscreen overlay o página
- HOY no centrado → `scrollToCurrentPeriod` usa períodos incorrectos o container equivocado
- "Ir a hoy" no funciona → botón usando ref incorrecto
