# CLOSED PERIOD ANCHORING — QA

**Date**: 2026-05-25
**Mode**: Vs Proyección

---

## 1. DAILY ANCHORING

| Check | Status |
|---|---|
| Si data llega hasta ayer, se centra ayer | ✅ `maxDataDate` de `projectionMeta.data_freshness` |
| Hoy no domina si no tiene data cerrada | ✅ Badge "PARCIAL" en ámbar, sin glow |
| Último cierre visible sin scroll manual | ✅ `scrollToCurrentPeriod` usa anchor |
| Badge "ÚLTIMO CIERRE" en columna anchor | ✅ Emerald badge |
| Delta DoD usa comparable válido | ✅ `periodPop` del backend (período previo cerrado) |

## 2. WEEKLY ANCHORING

| Check | Status |
|---|---|
| Semana cerrada más reciente es anchor | ✅ Busca `weekState === 'closed'` |
| Semana actual parcial etiquetada | ✅ Badge "PARCIAL" si ≠ anchor |
| Anclaje usa penúltima semana si no hay cerrada | ✅ Fallback lógico |

## 3. MONTHLY ANCHORING

| Check | Status |
|---|---|
| Último mes con `comparison_basis = full_month` es anchor | ✅ Busca en `periodInfoMap` |
| Mes parcial etiquetado | ✅ Badge "PARCIAL" |
| Anclaje usa penúltimo mes si no hay full | ✅ Fallback lógico |

## 4. VISUAL HIERARCHY

| Check | Status |
|---|---|
| Último cierre domina visualmente | ✅ Emerald border/glow/bg-gradient |
| Período parcial visible pero secundario | ✅ Ámbar badge, `opacity-85` |
| Futuro tenue | ✅ `opacity-45 grayscale-[30%]` |
| Pasado degradado progresivo | ✅ `computePastAgingOpacity` |
| Delta no usa períodos inválidos | ✅ `periodPop` solo de backend |

## 5. "IR AL CIERRE" BUTTON

| Check | Status |
|---|---|
| Botón muestra "Ir al cierre" si hoy es parcial | ✅ `getAnchorButtonLabel()` |
| Botón muestra "Ir a hoy" si hoy tiene data | ✅ Misma función, contexto correcto |
| Botón centra el período correcto | ✅ `scrollToCurrentPeriod` usa anchor |

## 6. BUILD

| Check | Status |
|---|---|
| Build PASS | ✅ 818 módulos, 10.78s |
| No console errors | ✅ |
| Sin NaN | ✅ |
| Sticky intacto | ✅ |
| Fullscreen intacto | ✅ |
| Drill intacto | ✅ |

---

## VERDICT: PASS
