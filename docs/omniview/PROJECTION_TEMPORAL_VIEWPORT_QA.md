# PROJECTION TEMPORAL VIEWPORT QA

**Date**: 2025-05-25
**Mode**: Vs Proyección

---

## AUTO-SCROLL

| Check | Status |
|---|---|
| Abre cerca de HOY (daily) | ✅ `scrollToCurrentPeriod()` centra en current period |
| Abre cerca de semana actual (weekly) | ✅ Misma función, `findCurrentPeriodIndex` |
| Abre cerca de mes actual (monthly) | ✅ Misma función |
| "Ir a hoy" botón funciona | ✅ Botón emerald en modo proyección |
| Sin scroll fightback | ✅ Solo se aplica en carga inicial (`autoScrollAppliedRef`) |

## SCROLL OWNERSHIP

| Check | Status |
|---|---|
| Una sola barra horizontal | ✅ `overflow: clip` en wrapper + `overflow-x-auto` en container |
| Una sola barra vertical | ✅ `overflow-y-auto` + `maxHeight: calc(100vh - 240px)` |
| Sin doble scroll confuso | ✅ Wrapper usa `overflow: clip`, no crea scroll context |
| Sticky headers intactos | ✅ `position: sticky` en header, total row, city/label columns |
| Horizontal scroll usable | ✅ Barra fina (`scrollbar-width: thin`) |
| Vertical scroll usable | ✅ Barra fina con `maxHeight` |
| Fullscreen scroll independiente | ✅ Overlay con `overflow-y-auto` |

## NAVIGATION

| Check | Status |
|---|---|
| Column position indicator visible | ✅ Footer bar: "Mostrando columnas X–Y de Z" |
| "Ir a inicio" botón en footer | ✅ `scrollTo({ left: 0 })` |
| Teclado navegable (arrows) | ✅ `onKeyDown` handler en scrollContainerRef |

## VERDICT: GO
