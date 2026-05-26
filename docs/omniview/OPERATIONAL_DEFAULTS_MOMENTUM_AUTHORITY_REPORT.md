# OPERATIONAL DEFAULTS + MOMENTUM AUTHORITY — REPORTE FINAL

**Date**: 2025-05-25
**FASE**: 1H.4 — Operational Maturity Governance Layer
**Motor**: Control Foundation + Diagnostic Engine Temprano
**Foco**: Omniview Vs Proyección

---

## 1. ESTADO: GO

| Criterio | Estado |
|---|---|
| Build | ✅ PASS (813 módulos, 9.83s) |
| Ciudades desplegadas por defecto | ✅ Todos los granos expanden por defecto |
| Usuario puede colapsar sin fightback | ✅ `userToggledRef` respeta preferencia |
| DoD/WoW/MoM mandan visualmente | ✅ `font-extrabold` + color verde/rojo |
| Colores responden a momentum | ✅ Severidad >5% → extrabold, ≤5% → bold |
| Valor + delta dominan celda | ✅ Real (extrabold, 16px) → Momentum (colored, bold) → Context (ultra-small) |
| NaN eliminado | ✅ Guards en fmtAttainment, fmtGapPct, momPctStr |
| Periodo actual domina | ✅ Emerald border/glow/badge/fuente ampliada |
| Proyección es el modo trabajado | ✅ viewMode='proyeccion' |
| Evolution no recibe nueva lógica | ✅ Cero cambios en rama evolution |
| Matrix/sticky/drill intactos | ✅ Unchanged |

---

## 2. QUÉ CAMBIÓ EN DEFAULTS

| Antes | Después |
|---|---|
| Daily grain: todas colapsadas por defecto | Todos los granos: **expandido por defecto** |
| Reset automático en cada cambio de grain/cities | Reset solo cuando cambia el conjunto de ciudades (filtro mayor) |
| Sin tracking de interacción del usuario | `userToggledRef` marca cuando el usuario interactúa |

---

## 3. CÓMO SE GOBIERNA LA EXPANSIÓN

```
Initial load → all expanded (collapsed = Set())
User collapses a city → userToggledRef = true, system respects
Filter/grain/mode/plan changes → prevCityKeys ≠ currentKeys → reset to expanded
KPI/zoom/density/scroll changes → NO reset, user preference preserved
```

El operador nunca pelea con el sistema. Si quiere colapsar, colapsa. Si cambia de país o grano, el estado se limpia (nuevo contexto).

---

## 4. CÓMO MANDA MOMENTUM

### Jerarquía visual en la celda de proyección

| Posición | Elemento | Peso visual |
|---|---|---|
| **Row 1** | HOY badge (solo current) | 6px, badge emerald |
| **Row 2** | **REAL VALUE** | **16px font-extrabold text-gray-900** |
| **Row 3** | **MOMENTUM DELTA** | **11px font-extrabold/bold, colored** |
| Row 4 | Plan + Avance context | 9px text-gray-400, ultra-small |
| Row 5 | Status label | 9px, colored |

### Colores momentum

| Dirección | Color | Severidad |
|---|---|---|
| Subida (>0%) | `#22c55e` (green) | >5% → extrabold, ≤5% → bold |
| Bajada (<0%) | `#ef4444` (red) | >5% → extrabold, ≤5% → bold |
| Neutral (0%) | `#9ca3af` (gray) | normal weight |

---

## 5. CÓMO QUEDA PLAN VS REAL COMO CONTEXTO

- **Proy (plan)**: Movido de la primera fila a un línea de contexto ultra-small (Row 4)
- **Avance (attainment)**: Mismo tratamiento, combinado con Plan en la línea de contexto
- **Gap absoluto**: **Eliminado del cell render**. Disponible en tooltip
- **Sin momentum**: Avance sube a Row 3 con peso normal como fallback

---

## 6. CÓMO SE ELIMINÓ NaN

| Ubicación | Fix |
|---|---|
| `fmtAttainment(pct)` | `pct == null \|\| !Number.isFinite(pct)` |
| `fmtGapPct(pct)` | `pct == null \|\| !Number.isFinite(pct)` |
| `momPctStr` | `Number.isFinite(momValue)` |
| `momBold` | `Number.isFinite(momValue)` |
| `fmtValue` | Already had `!isFinite(n)` guard |

---

## 7. EVIDENCIA BUILD

```
vite v5.4.21 building for production...
✓ 813 modules transformed.
dist/assets/index-DciVGgUY.css   91.34 kB │ gzip: 15.55 kB
dist/assets/index-741z7wwx.js  1807.82 kB │ gzip: 517.20 kB
✓ built in 9.83s
```

---

## 8. ARCHIVOS MODIFICADOS

| Archivo | Cambio |
|---|---|
| `BusinessSliceOmniviewMatrixTable.jsx` | Default expanded cities, user governance, `overflow: clip` |
| `BusinessSliceOmniviewMatrixCell.jsx` | Cell dominant layout: Real + Momentum dominan, Plan/Gap colapsados |
| `OmniviewModeSelector.jsx` | Operational primario, otros en dropdown |
| `projectionMatrixUtils.js` | NaN guards en `fmtAttainment` y `fmtGapPct` |
| `projectionViewportFocusEngine.js` | Nuevo motor de centrado de viewport |

## 9. ARCHIVOS CREADOS

| Archivo | Contenido |
|---|---|
| `docs/omniview/OPERATIONAL_DEFAULTS_MOMENTUM_AUTHORITY_PRECHECK.md` | Precheck GO/NO-GO |
| `docs/omniview/DEFAULT_EXPANDED_CITIES_DECISION.md` | Decisión y governance de expansión |
| `docs/omniview/MOMENTUM_COLOR_AUTHORITY_AUDIT.md` | Auditoría de autoridad visual momentum |
| `docs/omniview/MOMENTUM_NAN_FINAL_CLEANUP.md` | Cleanup NaN final |
| `docs/omniview/PROJECTION_MOMENTUM_WIRING_QA.md` | QA de wiring |
| `docs/omniview/OPERATIONAL_DEFAULTS_VISUAL_QA.md` | QA visual |
| `docs/omniview/OPERATIONAL_DEFAULTS_MOMENTUM_AUTHORITY_REPORT.md` | Este reporte |

---

## 10. RIESGOS PENDIENTES

| Riesgo | Severidad | Mitigación |
|---|---|---|
| Daily con muchas ciudades → DOM pesado | BAJA | Operador puede colapsar manualmente; column windowing activo |
| `periodPop` ausente en backend → momentum no visible | BAJA | Fallback controlado a attainment; no rompe la celda |

---

## VERDICT FINAL: GO

Omniview Vs Proyección ahora es operacionalmente accionable desde el primer vistazo:
- Ciudades desplegadas por defecto, sin fightback con el usuario
- Valor REAL + Momentum DELTA dominan la celda
- Plan y Gap colapsados a contexto ultra-small
- NaN completamente eliminado en todos los caminos
- Evolution sin un solo cambio
- Build limpio en 9.83s
