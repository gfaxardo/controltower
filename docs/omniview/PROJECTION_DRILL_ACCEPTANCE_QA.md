# PROJECTION DRILL ACCEPTANCE QA

**Date**: 2025-05-25
**Component**: `OmniviewProjectionDrill`

---

## OPENING

| Check | Status |
|---|---|
| Click en celda abre drill correcto | ✅ `handleCellClick` → `OmniviewProjectionDrill` |
| Drill muestra contexto de la celda | ✅ `selection` con cityKey, lineKey, period, kpiKey |
| Drill en panel lateral | ✅ Layout: matrix + drill side by side |

## CONTENT

| Check | Status |
|---|---|
| "Plan vs Real" disponible | ✅ Toggle between Plan/Real and Momentum |
| "Momentum" disponible | ✅ `OmniviewMomentumDrillChart` renderizado |
| Datos correctos según grano | ✅ Daily/Weekly/Monthly context preserved |

## CLOSING

| Check | Status |
|---|---|
| Escape cierra drill | ✅ `onKey` handler propagado |
| X / botón cerrar | ✅ Icono en drill component |
| Click en otra celda cambia drill | ✅ Nueva selección reemplaza anterior |
| Contexto de celda se conserva | ✅ `selectionHistory` mantiene navegación |

## FULLSCREEN

| Check | Status |
|---|---|
| Fullscreen botón funciona | ✅ `setMatrixFullscreen(true)` |
| Drill visible en fullscreen | ✅ `OmniviewProjectionDrill` en layout fullscreen |
| Escape sale de fullscreen | ✅ `onKey` handler |
| X / botón salir en fullscreen | ✅ "Salir (Esc)" button |

## VERDICT: GO
