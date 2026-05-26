# PROJECTION CELL VISUAL CONTRACT

**Date**: 2026-05-25
**Mode**: Vs Proyección
**Version**: 2.0 — Delta Comparable Isolation

---

## PRINCIPIO RECTOR

> El dato principal es la ejecución real,
> pero la atención visual la manda el delta comparable (DoD/WoW/MoM).
> Plan, attainment, YTD y gap son contexto secundario o terciario.

---

## LAYOUT FINAL DE CELDA

```
┌─────────────────────────────────────────┐
│ [badge HOY]    ← solo en columna actual │
│                                         │
│  12,710        ← L1: EJECUCIÓN REAL     │
│                font-extrabold, text-gray-900, 16px│
│                                         │
│  ↓ -21.6% DoD  ← L2: DELTA COMPARABLE  │
│                colored by severity, font-bold  │
│                                         │
│  Avance 47.3%  ← L3: CONTEXTO SECUNDARIO│
│                text-[7px], text-gray-300, opcional│
│                                         │
│  Pendiente     ← L4: STATUS (solo futuro/sin ejecución)│
│                text-[9px], text-slate-400│
└─────────────────────────────────────────┘
```

### REGLAS POR LÍNEA

#### L1 — Ejecución Real

| Atributo | Valor |
|---|---|
| Tipografía | `font-extrabold` |
| Tamaño | `text-[16px]` normal, `text-[12px]` compact |
| Color | `text-gray-900` con real, `text-gray-400` sin real |
| Negativo | `text-red-700` |
| Futuro | `text-gray-400` |
| Sin datos | `—` en `text-gray-300` |

**NUNCA**: mostrar plan, expected, attainment o gap en L1.

#### L2 — Delta Comparable (DOMINANTE)

| Atributo | Valor |
|---|---|
| Formato | `{flecha} {pct} {label}` — Ej: `↓ -21.6% DoD` |
| Flecha | `▲` up, `▼` down, sin flecha si flat |
| Porcentaje | Entero, sin decimales: `-21%` o `+15%` |
| Label | `DoD` / `WoW` / `MoM` (derivado de `periodPopKind` del backend) |
| Color | Severidad automática: verde para up, rojo para down, gris para flat |
| Tipografía | `font-bold` (<5%), `font-extrabold` (5-15%), `text-lg font-extrabold` (>15%) |
| Tamaño | `text-[11px]` normal, `text-[8px]` compact |

**NUNCA**: mostrar attainment, gap, YTD o plan en L2.
**NUNCA**: mostrar "vs domingo comparable" — es vago y confuso.
**SIEMPRE**: mostrar el label de tipo (DoD/WoW/MoM) junto al porcentaje.

**Si no hay delta comparable** (sin `periodPop`): mostrar `—` en gris, NUNCA attainment como sustituto.

#### L3 — Contexto Secundario

| Condición | Qué mostrar |
|---|---|
| Tiene momentum + attainment | `Avance 47.3%` (text-[7px], text-gray-300) |
| Sin momentum (plan fallback) | `Plan 59.6K` (text-[10px], text-gray-400) |
| Sin plan ni momentum | Nada (oculto) |
| Futuro | Nada (oculto) |

**SIEMPRE**: opacidad < 40%, tamaño mínimo, color gris claro.
**NUNCA**: competir visualmente con L2.

#### L4 — Status

Solo visible cuando:
- `isFuture`: "Pendiente"
- `!hasReal && isProjection`: "Sin ejecución"
- `!delta`: "—"

---

## TOOLTIP / DRILL (on hover/click)

El tooltip debe incluir TODA la información contextual:

```
12,710 Trips completados

DoD ▾ -21.6%  (vs 18 MAY 2026)
   Real hoy:     12,710
   Real comparable: 16,169
   Delta absoluto: -3,459

Plan vs Real
   Plan (mes):        59,600
   Expected al corte: 48,200
   Avance:            26.4%
   Gap:              -35,490

YTD
   Acumulado: 1,245,000
   Attainment YTD: 94.2%

Confianza: high
Método: weekly_curve_v2
```

---

## ESTADOS DE CELDA

### A. Normal con momentum (CASO PRINCIPAL)
```
│  12,710            │
│  ▼ -21.6% DoD      │
│  Avance 47.3%      │
```

### B. Sin momentum, con plan (FALLBACK)
```
│  12,710            │
│  —                 │
│  Plan 59.6K        │
```

### C. Futuro (sin ejecución)
```
│  —                 │
│  —                 │
│  Pendiente         │
```

### D. KPI no proyectable
```
│  12,710            │
│  —                 │
│  sin plan          │
```

### E. Sin datos
```
│  —                 │
```

---

## REGLAS INVARIABLES

1. **L1 siempre es ejecución real**, nunca plan ni expected
2. **L2 siempre es delta comparable**, nunca attainment ni gap
3. **L3 es contextual, secundario, opcional**, nunca compite con L2
4. **Attainment NUNCA debe ocupar el espacio visual del delta**
5. **YTD solo en tooltip/drill**, nunca en celda principal
6. **Gap vs plan solo en tooltip/drill**, nunca en celda principal
7. **Si no hay momentum data, L2 muestra "—", no attainment**
8. **El label del delta (DoD/WoW/MoM) es PARTE de L2**, no una línea separada
