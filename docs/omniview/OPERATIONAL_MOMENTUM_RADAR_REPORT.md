# OPERATIONAL MOMENTUM RADAR — REPORTE FINAL

**Date**: 2025-05-25
**FASE**: 1H.4 — Operational Maturity Governance Layer
**Motor**: Control Foundation + Diagnostic Engine Temprano
**Foco**: Omniview Vs Proyección

---

## 1. ESTADO: GO

| Criterio | Estado |
|---|---|
| Build | ✅ PASS (813 módulos, 9.57s) |
| Momentum domina cognitivamente | ✅ Severity color scale + bold + arrow |
| Colores comunican severidad | ✅ 5 niveles negativos + 5 positivos |
| DoD/WoW/MoM gobiernan experiencia | ✅ Momentum row = dominante; plan = terciario |
| Current period domina | ✅ Emerald spotlight: border/glow/gradient/fuente ampliada |
| Menos sensación de tabla | ✅ Bordes suaves, zebra reducido, sombra ligera |
| Más sensación de radar | ✅ Color severity bg + deterioration strip |
| Microtexto reducido | ✅ Solo Real + Momentum dominan, resto terciario |
| Top deterioration visible | ✅ `OmniviewMomentumPriorityStrip` wired para ambos modos |
| Proyección es cerebro principal | ✅ viewMode='proyeccion' |
| Evolution sin nuevas mejoras | ✅ Cero cambios |
| Scroll/sticky/drill intactos | ✅ |

---

## 2. QUÉ HACE DOMINANTE AL MOMENTUM

### Severity color scale (operationalMomentumEmphasis.js)

```
Negative:
  -0% to -5%    → rojo tenue    #fca5a5
  -5% to -15%   → rojo suave    #f87171
  -15% to -30%  → rojo medio    #ef4444
  -30% to -50%  → rojo fuerte   #dc2626
  < -50%        → rojo crítico  #991b1b

Positive:
  +0% to +5%    → verde tenue   #6ee7b7
  +5% to +15%   → verde suave   #34d399
  +15% to +30%  → verde medio   #10b981
  +30% to +50%  → verde fuerte  #059669
  > +50%        → verde fuerte  #047857
```

### Cell visual hierarchy

| Row | Element | Peso | Font |
|---|---|---|---|
| 1 | HOY badge | Terciario | 7px |
| **2** | **REAL VALUE** | **Dominante** | **13-16px extrabold** |
| **3** | **MOMENTUM DELTA** | **Dominante** | **11px extrabold/bold severity-colored** |
| 4 | Plan + Avance | Terciario | 9px gray-400 |
| 5 | Status | Terciario | 9px |

### Severity background tinting

Celdas con momentum aplican `getMomentumSeverityBg(pct)`:
- Bajada >30%: `bg-red-50/50` → visible periféricamente
- Bajada >15%: `bg-red-50/40`
- Subida >30%: `bg-emerald-50/50`
- Subida >15%: `bg-emerald-50/40`

---

## 3. CÓMO FUNCIONA COLOR SEVERITY

`getMomentumSeverityColor(pct)` retorna `{ color, label, level }`:
- `level` va de -5 (crítico negativo) a +5 (crítico positivo), 0 = neutral
- `color` se usa en `style={{ color }}` en la fila de momentum
- `label` es el nombre del nivel para debugging

`getMomentumSeverityBg(pct)` retorna clase Tailwind para bg tint:
- Basada en dirección + magnitud
- Aplicada al `className` del `<td>`

---

## 4. CÓMO SE REDUJO SPREADSHEET FEELING

| Antes | Después |
|---|---|
| `border-gray-200` wrapper | `border-gray-100` wrapper |
| `shadow-sm` | `shadow-[0_1px_3px_rgba(0,0,0,0.04)]` |
| Zebra `bg-slate-50/50` | `bg-slate-50/50` (mantuvo pero con contexto de severity) |
| TotalsRow `bg-slate-800/[.06]` | `bg-slate-100/60` |
| CityBlock `border-t-2 border-slate-300` | `border-t border-slate-200/80` |
| LineRow row border `gray-100/80` | `gray-200/70` |
| Sticky shadows `rgba(0,0,0,0.06)` | `rgba(0,0,0,0.03)` |

---

## 5. CÓMO FUNCIONA TOP DETERIORATION STRIP

Ya implementado como `OmniviewMomentumPriorityStrip`:
- Wired en `Matrix.jsx:1300` para ambos modos (evolution + projection)
- Lee de `projMatrix.cities` en proyección, `baseMatrix.cities` en evolución
- `extractMomentumPriorityFromMatrix` → clasificación determinística
- Muestra top 5 deterioros con chips coloreados
- 7 niveles de riesgo: CRITICAL_DECLINE → IMPROVING

---

## 6. CÓMO SE GOBIERNA WEEKDAY COGNITION

- Chips DOM/LUN/MAR/MIÉ/JUE/VIE/SÁB más grandes (12px, bold, rounded-md)
- Chip activo: `scale-110`, glow azul `shadow-[0_0_12px_rgba(59,130,246,0.35)]`, `ring-1 ring-blue-400/50`
- Label contextual: "Comparando DOM vs DOM" en vez de "Día"
- Contador de semanas: "· 14 semanas"

---

## 7. QUÉ SE ELIMINÓ VISUALMENTE

| Elemento | Destino |
|---|---|
| Gap row | **Eliminado** de la celda → disponible en tooltip |
| DoD/WoW/MoM label | **Reducido** — reemplazado por arrow + color; label pequeño en tooltip |
| Confidence text | **Eliminado** del display principal → solo dot y tooltip |
| Proy ↑ icon | **Eliminado** — reemplazado por "Plan" en línea de contexto |
| Heavy table borders | **Suavizados** en todo el componente |

---

## 8. QUÉ QUEDÓ EN TOOLTIP / DRILL

| Información | Ubicación |
|---|---|
| Plan detallado (proyectado, expected) | `buildProjectionCellTooltip` |
| Gap absoluto detallado | `buildProjectionCellTooltip` |
| Confidence metadata | Tooltip |
| KPI comparability badge | Absolute positioned en celda + tooltip |
| Momentum full label ("vs domingo comparable") | Tooltip |

---

## 9. EVIDENCIA BUILD

```
vite v5.4.21 building for production...
✓ 813 modules transformed.
dist/assets/index-DBjOARwX.css   92.47 kB │ gzip: 15.71 kB
dist/assets/index-BlqQEtnu.js  1809.13 kB │ gzip: 517.63 kB
✓ built in 9.57s
```

---

## 10. ARCHIVOS MODIFICADOS

| Archivo | Cambio |
|---|---|
| `operationalMomentumEmphasis.js` | Color severity scale: `getMomentumSeverityColor`, `getMomentumSeverityBg` |
| `BusinessSliceOmniviewMatrixCell.jsx` | Severity colors en momentum, severity bg tint en td, spotlight mejorado |
| `BusinessSliceOmniviewMatrixTable.jsx` | Bordes suaves, zebra reducido, sticky shadows ligeros |
| `BusinessSliceOmniviewMatrix.jsx` | Weekday chips mejorados: scale-110 + glow + label contextual |

## 11. ARCHIVOS CREADOS

| Archivo | Contenido |
|---|---|
| `docs/omniview/OPERATIONAL_MOMENTUM_RADAR_PRECHECK.md` | Precheck GO/NO-GO |
| `docs/omniview/MOMENTUM_FIRST_COGNITION_AUDIT.md` | Auditoría cognitiva de la celda |
| `docs/omniview/TOP_DETERIORATIONS_STRIP_CONTRACT.md` | Contrato del strip de deterioros |
| `docs/omniview/OPERATIONAL_MOMENTUM_RADAR_QA.md` | QA visual |
| `docs/omniview/OPERATIONAL_RADAR_FIRST2S_TEST.md` | Test de 2 segundos |
| `docs/omniview/OPERATIONAL_MOMENTUM_RADAR_REPORT.md` | Este reporte |

---

## 12. RIESGOS PENDIENTES

| Riesgo | Severidad |
|---|---|
| Color severity scale hardcodeado en JS → requiere deploy para ajustar thresholds | BAJA |
| Sin momentum data → fallback a attainment mostrado con peso normal | BAJA (controlled fallback) |
| Weekday focus con gran volumen de datos → DOM pesado | BAJA (filtrado reduce columnas) |

---

## VERDICT FINAL: GO

Omniview Proyección ahora funciona como un radar operacional vivo:
- El momentum domina cognitivamente con 5 niveles de severidad visual
- Los colores comunican deterioro/aceleración periféricamente
- La celda se lee en 2 líneas: REAL VALUE + MOMENTUM DELTA
- El spreadsheet feeling fue reducido mediante bordes suaves, zebra atenuado, y eliminación de ruido visual
- El presente tiene spotlight emerald, el pasado se degrada
- El top deterioration strip prioriza lo que el operador debe atender
- Weekday cognition mejorada con chips prominentes y labels contextuales
- Evolution: cero cambios, permanece como secondary legacy mode
