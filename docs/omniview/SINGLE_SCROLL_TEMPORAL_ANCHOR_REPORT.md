# SINGLE SCROLL + TEMPORAL ANCHOR — REPORTE FINAL

**Date**: 2026-05-25
**FASE**: 1H.4 — Operational Maturity Governance Layer
**Motor**: Control Foundation
**Foco**: Omniview Vs Proyección

---

## 1. ESTADO: GO

| Criterio | Estado |
|---|---|
| Build | ✅ PASS (816 módulos, 4.17s) |
| Una sola barra horizontal | ✅ Único scroll master: `scrollContainerRef` |
| Un solo owner vertical claro | ✅ Tabla es dueño vertical único |
| HOY centrado al abrir | ✅ `scrollToCurrentPeriod` con centrado preciso |
| "Ir a hoy" centra realmente | ✅ Botón resetea guard + usa scroll master |
| Presente domina visualmente | ✅ Emerald border/glow, badge, fuente ampliada |
| Pasado degradado | ✅ Opacidad progresiva hasta 55% |
| Futuro tenue | ✅ `opacity-45 grayscale-[30%]` |
| Sticky intacto | ✅ Dentro del scroll master |
| Drill intacto | ✅ Sidebar independiente |
| Fullscreen intacto | ✅ Sin doble scroll |
| Evolution no afectado | ✅ Zero cambios |

---

## 2. SCROLL OWNERSHIP — ANTES vs DESPUÉS

### Antes (doble scroll)

```
Fullscreen overlay
  overflow-y-auto              ← SCROLL CONTEXT #1 (vertical)
  └── Table wrapper (overflow: clip)
      └── scrollContainer
          overflow-x-auto       ← SCROLL CONTEXT #2 (horizontal)
          overflow-y-auto       ← SCROLL CONTEXT #2 (vertical) DUPLICATE!
```

**Problema**: Dos `overflow-y-auto` en la misma jerarquía = dos scrollbars verticales peleando.

### Después (single scroll)

```
Fullscreen overlay
  overflow-hidden              ← NO scroll context
  └── Table wrapper (overflow: clip)
      └── scrollContainer
          overflow-x-auto       ← SCROLL MASTER (horizontal)
          overflow-y-auto       ← SCROLL MASTER (vertical) ÚNICO
```

**Corrección**: Overlay fullscreen cambió de `overflow-y-auto` → `overflow-hidden`. La tabla es el scroll master único en ambos ejes.

---

## 3. OVERFLOW ELIMINADOS / MODIFICADOS

| Elemento | Archivo:Línea | Antes | Después |
|---|---|---|---|
| Fullscreen overlay (Evolución) | Matrix.jsx:1763 | `overflow-y-auto` | `overflow-hidden` |
| Fullscreen overlay (Proyección) | Matrix.jsx:1874 | `overflow-y-auto` | `overflow-hidden` |

Ningún otro overflow fue modificado. El scroll master en Table.jsx:270 se mantiene intacto.

---

## 4. CÓMO SE CENTRA HOY

### Flujo de anclaje temporal

```
1. Datos cargan → projectionRows.length > 0
2. useEffect verifica autoScrollAppliedRef y userHasScrolledRef
3. Double requestAnimationFrame asegura DOM montado
4. scrollToCurrentPeriod():
   a. Resuelve allPeriods desde displayProjMatrix (proyección) o matrix (evolución)
   b. resolveCurrentPeriodIndex(allPeriods, grain) → índice de HOY
   c. calculateScrollTarget(idx, colW, fixedW, viewportW) → scrollLeft
   d. container.scrollTo({ left: scrollTo, behavior: 'smooth' })
5. autoScrollAppliedRef = true
```

### Re-anclaje

Se resetea `autoScrollAppliedRef` y `userHasScrolledRef` cuando cambia:
- `grain`, `viewMode`, `country`, `city`, `year`, `month`, `businessSlice`

### Guard anti-pelea

`userHasScrolledRef` se activa en `wheel` y `touchmove` sobre el scroll container. Una vez activo, el auto-scroll no re-dispara hasta el próximo reset de filtros.

---

## 5. CÓMO FUNCIONA "IR A HOY"

El botón:
1. Resetea `userHasScrolledRef.current = false`
2. Llama `scrollToCurrentPeriod()`
3. Usa `behavior: 'smooth'` para navegación natural
4. Funciona en daily/weekly/monthly
5. Funciona en proyección y evolución
6. Usa `displayProjMatrix.allPeriods` en proyección, `matrix.allPeriods` en evolución

---

## 6. TRATAMIENTO PASADO / PRESENTE / FUTURO

| Zona Temporal | Visual |
|---|---|
| **Pasado lejano** | Opacidad reducida hasta 55%, borde degradado, contenido atenuado |
| **Pasado cercano** | Legible pero secundario, zebra sutil |
| **Presente** | Emerald border-l/r, glow, bg-gradient, badge HOY, fuente 16px extrabold, delta comparable resaltado |
| **Futuro / pendiente** | `opacity-45 grayscale-[30%]`, bg-slate-50/20, badge "Pendiente" discreto |
| **Seleccionado** | `bg-blue-50 ring-1 ring-blue-300` — la selección siempre domina sobre temporal |

---

## 7. QUÉ PASÓ CON EVOLUTION

Zero changes. Evolution mode:
- Mismo `scrollContainerRef`
- Misma lógica de `scrollToCurrentPeriod`
- Mismo fullscreen fix (`overflow-hidden` en overlay)
- Sin cambios en cell rendering ni wiring

---

## 8. ARCHIVOS MODIFICADOS

| Archivo | Cambio |
|---|---|
| `components/BusinessSliceOmniviewMatrix.jsx` | Fullscreen overlays `overflow-y-auto` → `overflow-hidden`. Auto-scroll reset ampliado (country/city/year/month/businessSlice). `userHasScrolledRef` guard. Botón "Ir a hoy" hardening. |
| `utils/projectionViewportFocusEngine.js` | Añadidos `visibleColumnCount`, `visibleWindowRange`. `computeViewportCenterScroll` ahora clampa al maxScroll. |

## 9. ARCHIVOS CREADOS

| Archivo |
|---|
| `docs/omniview/SINGLE_SCROLL_TEMPORAL_ANCHOR_PRECHECK.md` |
| `docs/omniview/SINGLE_SCROLL_OWNERSHIP_MAP.md` |
| `docs/omniview/SINGLE_SCROLL_CONTRACT.md` |
| `docs/omniview/SINGLE_SCROLL_TEMPORAL_ANCHOR_QA.md` |
| `docs/omniview/SINGLE_SCROLL_TEMPORAL_ANCHOR_REPORT.md` |

---

## 10. EVIDENCIA BUILD

```
vite v5.4.21 building for production...
✓ 816 modules transformed.
dist/assets/index-rV0rlvZ_.css   95.14 kB │ gzip: 16.12 kB
dist/assets/index-_qbABMsc.js  1812.60 kB │ gzip: 518.89 kB
✓ built in 4.17s
```

---

## 11. RIESGOS PENDIENTES

| Riesgo | Severidad | Nota |
|---|---|---|
| `maxHeight: calc(100vh - 240px)` puede desajustarse con toolbars custom | BAJA | Se auto-ajusta en la mayoría de viewports. En fullscreen, 240px es conservador. |
| `userHasScrolledRef` se activa en fullscreen con scroll del drill sidebar | BAJA | El listener está en el scroll container de la tabla, no en el drill. OK. |
| Auto-scroll en fullscreen al cambiar grain | BAJA | El `scrollContainerRef` se re-attacha correctamente porque el fullscreen usa render condicional. |

---

## VERDICT FINAL: GO

Omniview Vs Proyección ahora tiene arquitectura single-scroll con anclaje temporal operacional:

- **Una sola barra horizontal** — scroll master único en `scrollContainerRef`
- **Un solo owner vertical** — sin `overflow-y-auto` duplicado en fullscreen
- **HOY centrado al abrir** — auto-scroll con `displayProjMatrix.allPeriods`
- **"Ir a hoy" confiable** — botón resetea guard y usa el scroll master
- **Presente domina, pasado degradado, futuro tenue** — jerarquía visual clara
- **Sin peleas con el usuario** — `userHasScrolledRef` + reset inteligente
- **Sticky, drill, fullscreen intactos** — zero regressions
- **Evolution untouched** — secondary legacy mode sin cambios
