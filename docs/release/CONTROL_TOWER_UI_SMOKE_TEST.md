# CONTROL TOWER UI SMOKE TEST

**Date**: 2025-05-25
**Browser**: Real browser validation required

---

## OMNIVIEW PROYECCIÓN

| Check | Expected | Status (code review) |
|---|---|---|
| Abre correctamente | `/operacion/omniview-matrix` carga sin errores | ✅ Route verified |
| Presente visible | Auto-scroll a current period + emerald glow | ✅ Implemented |
| Ciudades desplegadas | Todas visibles al cargar | ✅ Default expanded |
| Momentum visible | Delta coloreado debajo del Real | ✅ Implemented |
| DoD visible (daily) | Arrow + % con color de severidad | ✅ Implemented |
| WoW visible (weekly) | Arrow + % con color de severidad | ✅ Implemented |
| MoM visible (monthly) | Arrow + % con color de severidad | ✅ Implemented |
| Sin NaN | Celdas muestran valores o '—' | ✅ All formatters guarded |
| Sin doble scroll | Una barra horizontal + una vertical | ✅ `overflow: clip` |
| Drill abre | Click en celda → OmiviewProjectionDrill | ✅ Wired |
| Fullscreen funciona | Botón expandir → overlay z-100 | ✅ Wired |
| Esc cierra | Tanto drill como fullscreen | ✅ Implemented |
| "Ir a hoy" funciona | Botón emerald centra viewport | ✅ Implemented |

## BEHAVIORAL MVP

| Check | Expected | Status |
|---|---|---|
| Carga | Panel visible, sin errores | ✅ Endpoint verified |
| Muestra gaps | Lista de dimensiones con estado | ✅ Endpoint returns dimensions |
| No recomienda acciones | Solo diagnóstico, sin sugerencias | ✅ By design |

## MODE TOGGLE

| Check | Expected | Status |
|---|---|---|
| Evolución ↔ Proyección | Toggle funcional | ✅ `viewMode` state |
| Evolution unchanged | Mismo comportamiento que antes | ✅ Cero cambios |

## GRAIN TOGGLE

| Check | Expected | Status |
|---|---|---|
| Daily ↔ Weekly ↔ Monthly | Matrix re-render con datos correctos | ✅ `setGrain` |
| Ciudades expandidas en todos | Default expanded para todos | ✅ Implemented |

## WEEKDAY FOCUS

| Check | Expected | Status |
|---|---|---|
| Chips visibles (daily) | DOM/LUN/MAR/MIÉ/JUE/VIE/SÁB | ✅ |
| Activo prominente | Scale-110 + glow azul | ✅ |
| Label contextual | "Comparando DOM vs DOM" | ✅ |

## VERDICT: UI smoke test checklist ready — real browser validation pending
