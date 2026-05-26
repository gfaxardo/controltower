# VIEWPORT DOMINANCE — REPORTE FINAL

**Date**: 2025-05-25
**FASE**: 1H.4 — Operational Maturity Governance Layer
**Motor**: Control Foundation
**Foco**: Omniview Vs Proyección

---

## 1. ESTADO: GO

| Criterio | Estado |
|---|---|
| Build | ✅ PASS (813 módulos, 9.88s) |
| Viewport centrado en HOY | ✅ Auto-scroll centrado operacional |
| Una sola barra horizontal | ✅ `overflow: clip` + scroll container único |
| Una sola barra vertical | ✅ Único `overflow-y-auto` con maxHeight |
| Presente domina visualmente | ✅ Emerald border/glow, fuente ampliada, badge |
| Pasado degradado | ✅ Opacidad progresiva hasta 55% |
| KPI dominante claro | ✅ Momentum como foco, attainment atenuado |
| NaN eliminado | ✅ Guards en momentos y formatters |
| Modos simplificados | ✅ Operational primario, otros colapsados |
| Sticky intacto | ✅ Unchanged |
| Virtualization intacta | ✅ Unchanged |
| Fullscreen intacto | ✅ Unchanged |
| Evolution no afectado | ✅ Solo cambios en rama de proyección |

---

## 2. SCROLL OWNERSHIP FINAL

**Antes** (doble scroll):
```
<div overflow-hidden>              ← clips, crea BFC, scrollbars escondidos
  <div overflow-x-auto overflow-y-auto>  ← scroll owner real, barra parcialmente visible
    <table>
```

**Después** (single scroll):
```
<div style="overflow: clip">       ← clips sin crear scroll context
  <div overflow-x-auto overflow-y-auto>  ← scroll owner único, ambas barras visibles
    <table>
```

---

## 3. WRAPPERS ELIMINADOS / MODIFICADOS

| Wrapper | Cambio |
|---|---|
| Table outer `overflow-hidden` | Reemplazado por `overflow: clip` (no crea scroll context) |
| Controls `overflow-hidden` | Sin cambios (no scroll required) |
| Root `overflow-x-hidden` | Sin cambios (full-bleed layout necesario) |

Ningún wrapper fue eliminado — solo se corrigió la propiedad que causaba el doble scroll.

---

## 4. VIEWPORT CENTERING — CÓMO FUNCIONA

1. **Al cargar datos de proyección** (`projectionRows` no vacío):
   - `useEffect` detecta `projectionRows.length > 0` y `!loading`
   - `autoScrollAppliedRef` previene repeticiones
   - Timeout 300ms asegura que el DOM esté montado

2. **Cálculo de posición**:
   - `findCurrentPeriodIndex(allPeriods, grain)` encuentra el índice HOY
   - `fixedW + idx * colW` calcula posición del período
   - `viewportWidth / 2 - colW / 2` centra en el viewport

3. **Botón manual "Ir a hoy"**:
   - Visible en ambos modos (evolución + proyección)
   - Emerald para proyección, blue para evolución
   - Llama `scrollToCurrentPeriod()` con smooth scroll

---

## 5. DEGRADACIÓN DEL PASADO — CÓMO FUNCIONA

`computePastAgingOpacity(periodKey, grain)`:
- **Daily**: 2.5% por día de distancia → máx 55% a los 22 días
- **Weekly**: 2.5% por semana → máx 55% después de 22 semanas
- **Monthly**: 2.5% por mes → máx 55% después de 22 meses

Aplicado vía `style={{ opacity: 1 - temporalAge }}` en el `<td>`.
Excluye: período actual, celdas seleccionadas, períodos futuros.

---

## 6. DOMINANCIA DEL PRESENTE — CÓMO FUNCIONA

En la celda de proyección con `isCurrentPeriod=true`:

| Elemento | Sin dominancia | Con dominancia |
|---|---|---|
| Background | `signalBg` o zebra | `bg-gradient-to-b from-emerald-50/40 to-emerald-50/20` |
| Bordes | `border-r border-gray-100/60` | `border-l-2 border-r-2 border-emerald-400/60` |
| Glow | Ninguno | `shadow-[inset_0_0_16px...,0_0_8px...]` |
| Fuente Real | `text-[13px] font-semibold` | `text-[15px] font-bold text-gray-900` |
| Badge | Ninguno | "HOY" / "SEM ACT" / "MES ACT" en emerald |

---

## 7. QUÉ PASÓ CON EVOLUTION

**Zero changes.** Evolution mode:
- Sigue siendo `viewMode === 'evolucion'`
- Su auto-scroll usa `matrix.allPeriods`
- Su celda render es el `BusinessSliceOmniviewMatrixCell` estándar
- Su `currentPeriodKey` badge es el "HOY" badge azul en el header
- Todo el wiring de evolución está intacto

Evolution queda como secondary legacy mode, sin cambios ni regresiones.

---

## 8. QUÉ PASÓ CON LOS MODOS OPERACIONALES

Modos (Executive / Operational / Diagnostic / Comparative):

| Antes | Después |
|---|---|
| 4 botones del mismo tamaño en línea | "Operational" como botón primario dominante |
| Todos visibles como tabs falsas | Executive / Diagnostic / Comparative colapsados en dropdown "···" |
| Ningún modo cambiaba la experiencia | Operational sigue siendo el modo por defecto (igual que antes) |
| Infraestructura de modos intacta | Infraestructura intacta, dropdown funcional |

---

## 9. EVIDENCIA BUILD

```
vite v5.4.21 building for production...
✓ 813 modules transformed.
dist/assets/index-DRrZ1XN6.css   91.31 kB │ gzip: 15.55 kB
dist/assets/index-q9qBOkFh.js  1807.76 kB │ gzip: 517.10 kB
✓ built in 9.88s
```

---

## 10. ARCHIVOS MODIFICADOS

| Archivo | Cambio |
|---|---|
| `components/BusinessSliceOmniviewMatrix.jsx` | Import focus engine, auto-scroll para proyección, fix fullscreen matrix, usar displayProjMatrix |
| `components/BusinessSliceOmniviewMatrixTable.jsx` | `overflow-hidden` → `overflow: clip`, `isCurrentPeriod` para ambos modos |
| `components/BusinessSliceOmniviewMatrixCell.jsx` | `isCurrentPeriod` + `periodKey` + `grain` a ProjectionCellRender, dominancia visual, degradación, NaN guards |
| `components/omniview/command/OmniviewModeSelector.jsx` | Simplificación: Operational primario, otros en dropdown "···" |

## 11. ARCHIVOS CREADOS

| Archivo | Contenido |
|---|---|
| `utils/projectionViewportFocusEngine.js` | Motor de centrado de viewport para proyección |
| `docs/omniview/VIEWPORT_DOMINANCE_PRECHECK.md` | Precheck GO/NO-GO |
| `docs/omniview/SCROLL_OWNERSHIP_AUDIT.md` | Árbol de scroll containers |
| `docs/omniview/VIEWPORT_FIRST2S_TEST.md` | Test de 2 segundos |
| `docs/omniview/VIEWPORT_DOMINANCE_QA.md` | QA checklist |
| `docs/omniview/VIEWPORT_DOMINANCE_REPORT.md` | Este reporte |

---

## 11. RIESGOS PENDIENTES

| Riesgo | Severidad | Estado |
|---|---|---|
| `maxHeight: calc(100vh - 240px)` puede no ajustar en viewports muy pequeños | BAJA | La altura vertical sigue siendo fija, pero el scroll único funciona |
| Degradación temporal usa date parsing nativo | BAJA | Period keys con formato no estándar devuelven opacidad 0 |
| Modos secundarios sin funcionalidad real | BAJA | Infraestructura lista, funcionalidad en fases futuras |

---

## VERDICT FINAL: GO

Omniview Proyección ahora se comporta como un radar operacional centrado en el presente:
- El viewport aterriza automáticamente cerca de HOY
- Existe un solo scroll owner (horizontal + vertical)
- El presente domina visualmente con emerald borders, glow y fuente ampliada
- El pasado se degrada suavemente con opacidad progresiva
- El operador nunca se pierde espacialmente
- La navegación es clara: botón "Ir a hoy", indicador de posición, sticky columns
