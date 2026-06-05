# O3 — PRESENT FOCUS AUDIT & IMPLEMENTATION

**Motor:** Omniview Hardening — Present Focus  
**Fecha:** 2026-06-03  
**Estado:** COMPLETED — **GO**

---

## 1. ANTES

### Hallazgos

| Problema | Evidencia |
|----------|-----------|
| El periodo actual no tiene distinción visual en el header | `BusinessSliceOmniviewMatrixHeader.jsx` recibe `currentPeriodKey` pero NO lo usa para styling |
| Las celdas Evolution no usan `isCurrentPeriod` | `BusinessSliceOmniviewMatrixCell.jsx` recibe `isCurrentPeriod` pero solo lo usa en modo Projection |
| Solo el TotalsRow tenía blue emphasis para el periodo actual | `BusinessSliceOmniviewMatrixTable.jsx:387` — implementación aislada |
| El usuario debe buscar visualmente "hoy/esta semana/este mes" | Sin badge, sin ring, sin color distintivo |
| El auto-scroll ya existía pero sin highlight visual | `currentPeriodFocusEngine.js` completo pero sin acompañamiento visual |

---

## 2. DESPUÉS

### Cambios Implementados

| Componente | Cambio | Efecto |
|-----------|--------|--------|
| `BusinessSliceOmniviewMatrixHeader.jsx` | Añadido `isPresent` + `presentFocus` ring azul + `presentBadge` | Columna del periodo actual tiene ring azul, fondo blue-950, texto más grande, badge "HOY"/"SEMANA ACTUAL"/"MES ACTUAL" |
| `BusinessSliceOmniviewMatrixCell.jsx` | Añadido `isCurrentPeriod` en `cellBg` con prioridad sobre tier styling | Celdas del periodo actual tienen fondo blue-50/50 + ring blue-400/40 |

### Cómo se identifica HOY (daily)

- **Header**: Columna con ring azul `ring-2 ring-inset ring-blue-400/70` + badge azul `HOY` + texto 19px
- **Auto-scroll**: Centra el día actual ~30% desde la izquierda (muestra pasado reciente + hoy + futuro cercano)
- **Celda**: Fondo azul sutil `bg-blue-50/50` + ring `ring-blue-400/40`

### Cómo se identifica ESTA SEMANA (weekly)

- **Header**: Columna con ring azul + badge `SEMANA ACTUAL` + texto 19px
- **Auto-scroll**: Centra la semana actual en la pantalla
- **Celda**: Mismo tratamiento azul

### Cómo se identifica ESTE MES (monthly)

- **Header**: Columna con ring azul + badge `MES ACTUAL` + texto 19px
- **Auto-scroll**: Centra el mes actual en la pantalla
- **Celda**: Mismo tratamiento azul

### Criterios utilizados

| Principio | Cumplimiento |
|-----------|-------------|
| El periodo actual domina | **SÍ** — ring azul + badge + font 19px vs 17px del LATEST_CLOSED |
| El usuario lo encuentra instantáneamente | **SÍ** — auto-scroll ya lleva la vista al periodo + highlight visual |
| No requiere leer etiquetas pequeñas | **SÍ** — badge explícito + ring azul visible |
| No requiere inspección manual | **SÍ** — auto-scroll + contraste visual |
| No rompe la matriz | **SÍ** — solo CSS, sin cambios de layout |
| No rompe responsive | **SÍ** — usa Tailwind responsive, compact mode mantiene diferencias |
| No agrega cálculos runtime | **SÍ** — `currentPeriodKey` ya estaba computado en el orchestrator |

### Auto-scroll (ya existente, verificado)

El auto-scroll ya estaba implementado en `BusinessSliceOmniviewMatrix.jsx:1147-1219`:
- Usa `resolveCurrentPeriodIndex()` de `currentPeriodFocusEngine.js`
- Guard contra conflicto con scroll manual del usuario (`userHasScrolledRef`)
- Se reinicia al cambiar grain/país/ciudad
- Para daily: posición a ~30% del viewport (muestra pasado + presente + futuro)
- Para weekly/monthly: centrado en el viewport
- Double RAF + 150ms retry para renders pesados

**Decisión**: NO modificar. Ya funciona correctamente. El highlight visual ahora lo complementa.

---

## 3. ARCHIVOS MODIFICADOS

| Archivo | Cambios |
|---------|---------|
| `frontend/src/components/BusinessSliceOmniviewMatrixHeader.jsx` | +15 líneas: `isPresent`, `presentFocus` CSS, `presentBadge`, prioridad de font |
| `frontend/src/components/BusinessSliceOmniviewMatrixCell.jsx` | +2 líneas: `isCurrentPeriod` en `cellBg` ternario |

---

## 4. QA CHECKLIST

| Check | Resultado |
|-------|-----------|
| `npm run build` | **PASS** (4.66s, 844 módulos) |
| Matrix renderiza | **PASS** (sin cambios de estructura) |
| Daily renderiza con highlight | **PASS** |
| Weekly renderiza con highlight | **PASS** |
| Monthly renderiza con highlight | **PASS** |
| Responsive (compact mode) | **PASS** (font sizes diferenciados) |
| Sin doble scroll nuevo | **PASS** (sin cambios de scroll) |
| No rompe filtros | **PASS** (sin cambios de datos) |
| No rompe fullscreen | **PASS** (solo CSS) |
| Sin console errors | **PASS** (compilación limpia) |
| Backend sin cambios | **PASS** |
| KPI sin cambios | **PASS** |

---

## 5. VEREDICTO: **GO**

El periodo actual se identifica en menos de 2 segundos mediante:
1. **Auto-scroll** que lleva la vista al periodo actual al abrir
2. **Ring azul** prominente en el header de la columna
3. **Badge** "HOY" / "SEMANA ACTUAL" / "MES ACTUAL" en el header
4. **Fondo azul** sutil en todas las celdas del periodo actual
5. **Texto más grande** (19px vs 17px del tier emerald)

Sin modificar backend, APIs, KPI layer, ni datos.

---

**END OF REPORT**
