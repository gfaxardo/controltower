# OPERATIONAL SCAN SPEED — REPORTE FINAL

**Date**: 2026-05-25
**FASE**: 1H.4
**Motor**: Control Foundation
**Foco**: Omniview Vs Proyección

---

## 1. ESTADO: GO

| Criterio | Estado |
|---|---|
| Build | ✅ PASS (818 módulos, 5.13s) |
| Peor deterioro visible más rápido | ✅ Worst-in-row ring-2 + border-l-2 + shadow |
| Delta domina visualmente | ✅ Coloreado, bold, sin attainment en celda |
| Celda menos saturada | ✅ Solo L0+L1+L2, attainment movido a tooltip |
| Último cierre sigue dominante | ✅ Emerald glow intacto |
| No heatmap agresivo | ✅ Severity autolimitante, 1 worst por fila |
| Evolution no tocada | ✅ Zero cambios |
| Sticky/Fullscreen/Drill intactos | ✅ |
| Single scroll intacto | ✅ |

---

## 2. MEJORAS DE SCANABILITY

| Mejora | Antes | Después |
|---|---|---|
| **Worst-in-row** | `ring-1 ring-red-300/50 border-l-2` | `ring-2 ring-red-300/55 border-l-2 border-red-400/70 shadow-[inset_0_0_6px_rgba(239,68,68,0.10)]` |
| **Futuro dimming** | `opacity-45 grayscale-[30%]` | `opacity-35 grayscale-[40%]` |
| **Past degradation** | Steps: daily 60, weekly 40, monthly 24 | Steps: daily 90, weekly 52, monthly 36 (más agresivo) |
| **Cell noise** | "Avance X%" en todas las celdas | Solo en planFallback. Momentum → tooltip |
| **Header anchor** | Header usaba calendario, no operational anchor | Header ahora usa `currentPeriodKey` prop (operational anchor) |

---

## 3. WORST-IN-ROW — CÓMO SE MARCA

```
Celda normal:           Celda worst-in-row:
┌─────────────┐         ┌─────────────┐
│  12,710      │         │  8,523       │
│  ▼ -21% DoD  │         │  ▼ -35% DoD  │ ← ring-2 rojo
│              │         │              │ ← border-l-2 rojo
└─────────────┘         └─────────────┘ ← shadow inset
```

El worst-in-row:
- Solo 1 celda por fila (la de peor `periodPop.pct`)
- Si coincide con último cierre: el emerald glow domina sobre el ring rojo
- Si está seleccionada: el ring azul domina
- Guard: nunca en selected ni current period
- El cálculo es O(n) sobre allPeriods, liviano

---

## 4. QUÉ SE DEGRADÓ / MOVIÓ

| Elemento | Acción |
|---|---|
| "Avance X%" en celda con momentum | **Eliminado** de la celda. Disponible en tooltip. |
| "Avance X%" en planFallback | **Conservado** como línea L3 contextual. |
| Futuro | Más tenue: `opacity-35` (antes 45). |
| Pasado | Degradación más rápida y profunda. |

---

## 5. ESTADO DEL SCROLL

Sin cambios. Single scroll architecture estable desde fase anterior.

---

## 6. ARCHIVOS MODIFICADOS

| Archivo | Cambio |
|---|---|
| `BusinessSliceOmniviewMatrixCell.jsx` | Worst-in-row hardening, future dimming, cell line reduction, past degradation steps ampliados |
| `BusinessSliceOmniviewMatrixHeader.jsx` | Acepta y usa `currentPeriodKey` prop para highlight operacional |

## 7. ARCHIVOS CREADOS

| Archivo |
|---|
| `docs/omniview/OPERATIONAL_SCAN_SPEED_PRECHECK.md` |
| `docs/omniview/OPERATIONAL_SCAN_SPEED_AUDIT.md` |
| `docs/omniview/VISIBLE_WORST_DETECTION_DECISION.md` |
| `docs/omniview/OPERATIONAL_SCAN_SCROLL_FOLLOWUP.md` |
| `docs/omniview/OPERATIONAL_SCAN_FIRST2S_TEST.md` |
| `docs/omniview/OPERATIONAL_SCAN_SPEED_QA.md` |
| `docs/omniview/OPERATIONAL_SCAN_SPEED_REPORT.md` |

---

## 8. EVIDENCIA BUILD

```
✓ 818 modules transformed.
dist/assets/index-D5msPjpp.css   96.23 kB │ gzip: 16.26 kB
dist/assets/index-Ca4InfFO.js  1830.31 kB │ gzip: 523.33 kB
✓ built in 5.13s
```

---

## 9. RIESGOS PENDIENTES

| Riesgo | Severidad | Nota |
|---|---|---|
| Worst-in-row depende de `focusedKpi` | BAJA | Si se cambia de KPI, el worst cambia. Comportamiento esperado. |
| Degradación más agresiva puede hacer pasado ilegible | BAJA | 55% max opacity reduction es conservador. Texto sigue legible. |

---

## VERDICT FINAL: GO

Omniview Vs Proyección ahora permite escaneo operacional rápido:

- **Worst-in-row** con ring-2 + shadow: el ojo detecta el peor deterioro por fila sin leer todas las celdas
- **Celda menos ruidosa**: solo badge + real + delta. Attainment en tooltip cuando hay momentum.
- **Futuro más tenue**: no compite con datos reales.
- **Pasado más degradado**: el contraste natural empuja el foco hacia el presente.
- **Header alineado**: el highlight azul del header ahora coincide con el operational anchor.
- **Sin heatmap agresivo**: solo celdas realmente severas rompen el patrón visual.
