# FINAL SCROLL OWNERSHIP AUDIT

**Date**: 2026-05-25

---

## SCROLL MASTER

| Eje | Owner | File:Line | Propiedad |
|---|---|---|---|
| **Horizontal** | `scrollContainerRef.current` | `BusinessSliceOmniviewMatrixTable.jsx:271` | `overflow-x-auto` |
| **Vertical** | `scrollContainerRef.current` | `BusinessSliceOmniviewMatrixTable.jsx:271` | `overflow-y-auto` + `maxHeight: calc(100vh - 240px)` |

## CLIPPERS (NO scroll context)

| Wrapper | File:Line | Propiedad |
|---|---|---|
| Root | `Matrix.jsx:1330` | `overflow-x-hidden` |
| Controls | `Matrix.jsx:1365` | `overflow-hidden` |
| Table outer | `Table.jsx:257` | `overflow: clip` |
| Fullscreen overlay (Evol) | `Matrix.jsx:1810` | `overflow-hidden` |
| Fullscreen overlay (Proj) | `Matrix.jsx:1923` | `overflow-hidden` |

## INDEPENDENT SCROLLS (no conflict)

| Element | File:Line | Propiedad |
|---|---|---|
| Drill sidebar content | `OmniviewProjectionDrill.jsx:149` | `overflow-y-auto` + `max-h-[calc(100vh-200px)]` |
| Inspector sidebar content | `BusinessSliceOmniviewInspector.jsx:301,503` | `overflow-y-auto` + `max-h-[68vh/50vh]` |

## VERDICT

**No duplicate scroll.** El master scroll container es el dueño único de scroll horizontal y vertical de la matriz. Los sidebars tienen scrolls independientes sin conflicto.

## MINOR ISSUE

`maxHeight: calc(100vh - 240px)` es conservador en fullscreen (sobra espacio). No es un bug, es calibración. No requiere cambio.
