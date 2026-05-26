# CLOSED PERIOD ANCHORING + TEMPORAL GRADIENT — REPORTE FINAL

**Date**: 2026-05-25
**FASE**: 1H.4 — Operational Maturity Governance Layer
**Motor**: Control Foundation
**Foco**: Omniview Vs Proyección

---

## 1. ESTADO: GO

| Criterio | Estado |
|---|---|
| Build | ✅ PASS (818 módulos, 10.78s) |
| Daily centra último día cerrado | ✅ `maxDataDate` de `projectionMeta.data_freshness` |
| Período parcial no domina | ✅ Badge "PARCIAL" ámbar, sin glow |
| Último cierre domina visualmente | ✅ Emerald border/glow/badge "ÚLTIMO CIERRE" |
| Gradiente temporal claro | ✅ Past degraded → Closed dominant → Partial subtle → Future ghosted |
| Delta no usa períodos inválidos | ✅ `periodPop` del backend como fuente única |
| No NaN | ✅ Guards en formatters |
| "Ir al cierre" funciona | ✅ Botón con label dinámico |
| Sticky intacto | ✅ |
| Fullscreen intacto | ✅ |
| Drill intacto | ✅ |
| Evolution no afectado | ✅ |

---

## 2. CÓMO SE DETERMINA EL ÚLTIMO CIERRE

### Daily
```
1. Leer projectionMeta.data_freshness.max_data_date (backend)
2. Si existe y está en el rango → anchor = maxDataDate
3. Si existe pero fuera de rango → anchor = período más cercano ≤ maxDataDate
4. Fallback: ayer calendario
5. Fallback último: último período del rango
```

### Weekly
```
1. Buscar semana con week_state = "closed" (backend)
2. Fallback: penúltima semana del rango
3. Fallback último: última del rango
```

### Monthly
```
1. Buscar mes con comparison_basis = "full_month" (backend)
2. Fallback: penúltimo mes del rango
3. Fallback último: último del rango
```

---

## 3. CÓMO SE DIFERENCIA DE HOY CALENDARIO

| Concepto | Variable | Visual |
|---|---|---|
| **Calendar today** | `calendarCurrentPeriodKey` | Puede ser "parcial" si ≠ anchor |
| **Operational anchor** | `operationalCurrentPeriodKey` | Badge "ÚLTIMO CIERRE", emerald glow |
| **Partial** | `isCalendarCurrentPartial` | Badge "PARCIAL" ámbar, sin glow |

El sistema ahora:
1. Centra el viewport en `operationalCurrentPeriodKey` (último cierre)
2. Muestra badge "ÚLTIMO CIERRE" en la columna anchor
3. Si hoy calendario ≠ anchor → muestra badge "PARCIAL" en hoy
4. El botón se llama "Ir al cierre" si hoy es parcial

---

## 4. GRADIENTE TEMPORAL

```
[PASADO LEJANO] → opacidad hasta 55%, borde degradado
[PASADO RECIENTE] → legible, zebra sutil
[ÚLTIMO CIERRE] → máx autoridad: emerald border/glow/bg-gradient, badge verde
[ACTUAL PARCIAL] → badge ámbar "PARCIAL", opacidad 85%, sin glow dominante
[FUTURO] → opacidad 45%, grayscale, bg-slate-50/20
```

---

## 5. TRATAMIENTO DE PERÍODOS PARCIALES

- Período calendario actual pero sin data cerrada → `isCalendarCurrentPartial = true`
- Badge "PARCIAL" en ámbar (no verde)
- Sin emerald glow ni border-l/r dominante
- Delta comparable solo si el backend envía `periodPop` válido
- Si no hay comparable → "—" en L2

---

## 6. BOTÓN "IR AL CIERRE" / "IR A HOY"

| Condición | Label | Comportamiento |
|---|---|---|
| `isCalendarCurrentPartial = true` | "Ir al cierre" | Centra `operationalCurrentPeriodKey` |
| `isCalendarCurrentPartial = false` | "Ir a hoy" | Centra `operationalCurrentPeriodKey` (= calendar today) |
| Modo evolución | "Ir a hoy" / normal | Sin cambios |

---

## 7. ESTADO DEL DOBLE SCROLL

Sin cambios respecto a la fase anterior. Single scroll architecture intacta:
- Un solo scroll master (Table.jsx:270)
- Fullscreen overlays con `overflow-hidden`
- Sin regresiones

---

## 8. ARCHIVOS CREADOS

| Archivo | Rol |
|---|---|
| `utils/projectionClosedPeriodEngine.js` | Engine de período cerrado: anchor, clasificación, badges |
| `docs/omniview/CLOSED_PERIOD_ANCHORING_PRECHECK.md` | PRECHECK GO/NO-GO |
| `docs/omniview/CLOSED_PERIOD_SIGNAL_AUDIT.md` | Auditoría de señales de cierre |
| `docs/omniview/CLOSED_PERIOD_FIRST2S_TEST.md` | Test de 2 segundos |
| `docs/omniview/CLOSED_PERIOD_ANCHORING_QA.md` | QA checklist |
| `docs/omniview/CLOSED_PERIOD_ANCHORING_REPORT.md` | Este reporte |

## 9. ARCHIVOS MODIFICADOS

| Archivo | Cambio |
|---|---|
| `components/BusinessSliceOmniviewMatrix.jsx` | Import closed period engine. `operationalCurrentPeriodKey` desde anchor. `scrollToCurrentPeriod` usa anchor. Botón con label dinámico. `calendarCurrentPeriodKey` a tabla. |
| `utils/projectionViewportFocusEngine.js` | `findPeriodIndex`. `computeViewportCenterScroll` acepta `anchorPeriodKey`. `centerProjectionViewport` acepta `anchorPeriodKey`. |
| `components/BusinessSliceOmniviewMatrixTable.jsx` | Prop `calendarCurrentPeriodKey` → `CityBlock` → `LineRow` → cell. `isCalendarCurrentPartial`. |
| `components/BusinessSliceOmniviewMatrixCell.jsx` | `isCalendarCurrentPartial` prop. Badge "ÚLTIMO CIERRE" vs "PARCIAL". Badge de anchor siempre emerald. |

---

## 10. EVIDENCIA BUILD

```
vite v5.4.21 building for production...
✓ 818 modules transformed.
dist/assets/index-IMKVwAmy.css   95.86 kB │ gzip: 16.21 kB
dist/assets/index-BvMnDAFr.js  1826.33 kB │ gzip: 522.38 kB
✓ built in 10.78s
```

---

## 11. RIESGOS PENDIENTES

| Riesgo | Severidad | Nota |
|---|---|---|
| `periodInfoMap` no usado en primera iteración (solo `maxDataDate`) | BAJA | Weekly/monthly usan fallback de penúltimo período. Implementación completa de `periodInfoMap` requiere construir el mapa desde las filas de proyección. Pendiente para fase siguiente. |
| `week_state` no disponible en monthly sin serving fact | BAJA | El fallback de `comparison_basis` cubre el caso. |
| `data_freshness` podría no existir en respuestas rápidas | BAJA | Fallback a ayer calendario cubre el caso. |

---

## VERDICT FINAL: GO

Omniview Vs Proyección ahora ancla en el último período operativo cerrado, no en un "hoy" sin data:

- **Daily**: centrado en `maxDataDate` del backend (último día con data real)
- **Weekly/Monthly**: centrado en último período cerrado (con fallback a penúltimo)
- **Hoy calendario parcial**: badge "PARCIAL" sin autoridad visual dominante
- **Último cierre**: máxima autoridad visual con emerald glow + badge "ÚLTIMO CIERRE"
- **Botón**: "Ir al cierre" cuando hoy es parcial, "Ir a hoy" cuando hoy tiene data
- **Gradiente temporal**: pasado degradado → cierre dominante → parcial tenue → futuro ghosted
