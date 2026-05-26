# OMNIVIEW — RELEASE CANDIDATE REPORT

**Date**: 2026-05-25
**FASE**: 1H.4 — Operational Maturity Governance Layer
**Motor**: Control Foundation
**Foco**: Omniview Vs Proyección

---

## 1. ESTADO: GO

| Criterio | Estado |
|---|---|
| Build | ✅ PASS (821 módulos, 4.76s) |
| Una sola barra horizontal funcional | ✅ |
| Vertical ownership claro | ✅ |
| Último cierre centrado | ✅ `closedPeriodAnchor.anchorPeriodKey` |
| Proyección domina | ✅ Todos los cambios en `viewMode === 'proyeccion'` |
| Delta DoD/WoW/MoM domina | ✅ L2 coloreado, bold, sin attainment |
| Worst-in-row visible | ✅ ring-2 + border-l-2 + shadow |
| No NaN | ✅ Guards en formatters |
| Sticky intacto | ✅ |
| Drill intacto | ✅ |
| Fullscreen intacto | ✅ |
| Single scroll architecture | ✅ Sin duplicados |

---

## 2. ESTADO DEL DOBLE SCROLL

**CERRADO.** El doble scroll fue eliminado en fases anteriores:

| Fase | Fix |
|---|---|
| VIEWPORT DOMINANCE | `overflow: hidden` → `overflow: clip` en outer table wrapper |
| SINGLE SCROLL + TEMPORAL ANCHORING | Fullscreen overlays: `overflow-y-auto` → `overflow-hidden` |

La arquitectura actual tiene un solo scroll master (`BusinessSliceOmniviewMatrixTable.jsx:271`) con `overflow-x-auto overflow-y-auto`. Los sidebars tienen scrolls independientes sin conflicto.

---

## 3. ESTADO DE PROYECCIÓN (Vs Proyección)

### Capacidades activas

| Capacidad | Engine |
|---|---|
| Delta comparable DoD/WoW/MoM | `comparableDeltaDisplay.js` |
| Display model canónico | `projectionCellDisplayModel.js` |
| Severity emphasis | `operationalMomentumEmphasis.js` |
| Closed period anchoring | `projectionClosedPeriodEngine.js` |
| Viewport centering | `projectionViewportFocusEngine.js` |
| Temporal gradient (past/future) | `computePastAgingOpacity` |
| Current period authority | Emerald border/glow/badge |
| Worst-in-row detection | `worstPeriodPk` in `LineRow` |
| Cell line reduction | Sin attainment en momentum |
| Mode simplification | Operational primario |

### Layout visual

```
[PASADO DEGRADADO] [ÚLTIMO CIERRE DOMINANTE] [PARCIAL TENUE] [FUTURO TENUE]
     opacidad           emerald glow           badge ámbar     opacity-35
```

---

## 4. ESTADO DE EVOLUCIÓN (legacy)

Evolución permanece como modo secundario sin cambios:
- Misma arquitectura de scroll
- Mismo auto-scroll a período actual
- Mismo fullscreen/drill
- Celdas con formato original (delta + signal + trust overlays)
- **Zero cambios en esta serie de fases**

---

## 5. EVIDENCIA BUILD

```
vite v5.4.21 building for production...
✓ 821 modules transformed.
dist/assets/index-DOaD90qd.css   96.57 kB │ gzip: 16.31 kB
dist/assets/index-Bh7h0oFn.js  1841.36 kB │ gzip: 525.67 kB
✓ built in 4.76s
```

---

## 6. RIESGOS ACEPTADOS

| Riesgo | Severidad | Mitigación |
|---|---|---|
| `maxHeight: calc(100vh - 240px)` es conservador en fullscreen | BAJA | No rompe funcionalidad. Espacio extra en fullscreen es aceptable. |
| `periodInfoMap` no usado en closed period engine (solo `maxDataDate`) | BAJA | Weekly/monthly usan fallback de penúltimo período. Funciona correctamente. |
| `week_state` no siempre disponible en monthly | BAJA | `comparison_basis` cubre el caso. |
| Inspector/Drill fullscreen usan `overflow-y-auto` mientras Matrix usa `overflow-hidden` | BAJA | Inconsistencia de patrón, sin conflicto funcional. |

---

## 7. QUÉ NO TOCAR ANTES DE RELEASE

- Backend: sin cambios necesarios
- Evolution mode: dejar como está
- Componentes deprecated: no reactivar
- APIs: sin nuevas llamadas
- Cálculos de momentum/projection: core intacto
- Sticky/virtualization: estable

---

## 8. MÉTRICAS DE LA FASE

| Métrica | Valor |
|---|---|
| Fases completadas en esta serie | 7 |
| Archivos JS/JSX modificados | 6 |
| Archivos JS/JSX creados | 4 |
| Documentos de QA/reporte creados | 25+ |
| Build time final | 4.76s |
| Módulos transpilados | 821 |

---

## 9. RECOMENDACIÓN FINAL

### RELEASE: GO

Omniview Vs Proyección está listo para release controlado:

- **Arquitectura de scroll**: un solo dueño horizontal y vertical, sin conflictos.
- **Anclaje temporal**: centrado en último período operativo cerrado, no en un "hoy" sin data.
- **Delta comparable**: DoD/WoW/MoM domina visualmente. Attainment relegado a contexto.
- **Scanability**: worst-in-row con ring-2 + shadow permite detección periférica de deterioros.
- **Evolución**: intacto como modo legacy, sin regresiones.
- **Build**: estable en 821 módulos.
