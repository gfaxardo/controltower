# SINGLE SCROLL OWNERSHIP MAP

**Date**: 2026-05-25
**Mode**: Vs Proyección (y evolución fullscreen)

---

## ÁRBOL REAL DE SCROLL CONTAINERS

```
Window / Document
│
└── <div data-omniview-matrix-root>                              Matrix.jsx:1283
    │   overflow-x-hidden                                          ← CLIP (full-bleed)
    │   width: 100vw; left: 50%; margin-left: -50vw
    │
    └── <div px-3 sm:px-4 space-y-2>                             content wrapper
        │
        ├── OmniviewCommandHeader
        ├── OmniviewMomentumPriorityStrip
        │
        ├── <div overflow-hidden>                                  Matrix.jsx:1318
        │   └── [controls: grain, filters, zoom, etc.]             ← CLIP (no scroll)
        │
        ├── [PROJECTION MODE — non-fullscreen]
        │   └── <div flex gap-3 items-start>                       Matrix.jsx:1918
        │       ├── <div flex-1 min-w-0 zoom>                      Matrix.jsx:1919
        │       │   │   transform: scale(zoom%)
        │       │   │
        │       │   └── BusinessSliceOmniviewMatrixTable
        │       │       ├── <div overflow:clip>                    Table.jsx:256  ← CLIP CSS (NO scroll context)
        │       │       │
        │       │       └── <div ref={scrollContainerRef}          Table.jsx:270  🔴 SCROLL OWNER X+Y
        │       │           │   overflow-x-auto                      ← SCROLLBAR X visible
        │       │           │   overflow-y-auto                      ← SCROLLBAR Y visible
        │       │           │   maxHeight: calc(100vh - 240px)       ← height constraint
        │       │           │
        │       │           └── <table min-w-full>
        │       │               ├── colgroup (COL1_W + COL2_W + N×colW)
        │       │               ├── Header (sticky top: 0, z-20)
        │       │               ├── TotalsRow (sticky top: headerH, z-18)
        │       │               └── Rows (sticky left COL1/COL2, z-10)
        │       │
        │       └── OmniviewProjectionDrill (sidebar)
        │
        ├── [PROJECTION MODE — fullscreen]
        │   └── <div fixed inset-0 z-[100] bg-white>              Matrix.jsx:1874
        │       │   overflow-y-auto                                 🔴 DUPLICATE SCROLL Y
        │       │
        │       └── <div max-w-full mx-auto p-3>
        │           └── ... BusinessSliceOmniviewMatrixTable ...
        │               └── <div ref={scrollContainerRef}          Table.jsx:270
        │                   overflow-x-auto overflow-y-auto          ← SCROLLBAR X+Y (2nd scroll context!)
        │
        ├── [EVOLUTION MODE] (no changes in this phase)
        │   └── (misma estructura de fullscreen, mismo bug)
```

## CLASIFICACIÓN DE WRAPPERS

| # | Wrapper | Archivo:Línea | Acción |
|---|---|---|---|
| 1 | Root `overflow-x-hidden` | Matrix.jsx:1283 | **KEEP** — Necesario para full-bleed sin scroll horizontal de página |
| 2 | Controls `overflow-hidden` | Matrix.jsx:1318 | **KEEP** — Clipping de bordes en panel de filtros |
| 3 | Table outer `overflow: clip` | Table.jsx:256 | **KEEP** — Correcto, no crea scroll context |
| 4 | **Scroll container** | **Table.jsx:270** | **KEEP — SCROLL MASTER** |
| 5 | **Fullscreen overlay `overflow-y-auto`** | **Matrix.jsx:1763, 1874** | **CHANGE → `overflow-hidden`** — Duplica scroll vertical |
| 6 | Zoom `min-w-0` | Matrix.jsx:1919 | **KEEP** — Contención de scale() |

## SCROLL OWNERS FINALES

| Eje | Owner | Condición |
|---|---|---|
| **Horizontal** | `scrollContainerRef.current` (Table.jsx:270) | Siempre |
| **Vertical** | `scrollContainerRef.current` (Table.jsx:270) | Siempre |
| **Vertical (página)** | `window` / `document` | Solo si contenido NO-matriz excede viewport |

No debe existir ningún otro elemento con `overflow-x-auto`, `overflow-y-auto`, `overflow-scroll` que compita con el scroll master de la tabla.
