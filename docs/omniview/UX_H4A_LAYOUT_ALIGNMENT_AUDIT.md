# UX-H4A — LAYOUT ALIGNMENT AUDIT

**Motor:** Control Foundation  
**Fecha:** 2026-05-31  

---

## 1. Contenedor del Header

El header visual comprende el `OmniviewCommandHeader` (modo, grano, periodo, stats) + el `MatrixExecutiveBanner` cuando hay problemas. Antes residía en una card independiente con `bg-ct-card`, `border-ct-border`, `ct-radius-lg` y `shadow-sm`.

## 2. Contenedor de la Matriz

La matriz residía en su propia card con `bg-white`, `border-gray-100`, `rounded-lg` y un shadow custom. Usaba tokens de Tailwind vanilla en lugar de `ct-*` variables.

## 3. Por Qué No Coincidían

Tres vocabularios de diseño distintos en una misma página:

| Componente | Background | Border | Radius | Shadow |
|-----------|-----------|--------|--------|--------|
| CommandHeader | `ct-card` | `ct-border` | `ct-radius-lg` | `shadow-sm` |
| Controls | `ct-surface` | `ct-border` | `ct-radius-md` | none |
| MatrixTable | `white` | `gray-100` | `rounded-lg` | custom |

Separados por `space-y-2` (8px gaps) que actuaban como divisores visuales en vez de unir.

## 4. Wrappers que Sobraban

- La card independiente de Controls (bg/border/radius redundante)
- La card independiente de MatrixTable (tokens inconsistentes)
- La card independiente de CommandHeader (bg redundante con el shell)

## 5. Padding Normalizado

| Zona | Antes | Después |
|------|-------|---------|
| Outer wrapper | `px-3 sm:px-4` | `mx-3 sm:mx-4` (margin en vez de padding — el shell se expande hasta el borde) |
| Shell interno | no existía | `rounded-lg border border-ct-border bg-ct-surface overflow-hidden shadow-[...] divide-y` |
| CommandHeader | card propia con bg/border/radius/shadow | solo `border-l-[3px] border-l-ct-accent overflow-hidden` |
| Controls | card propia con bg/border/radius | `overflow-hidden` sin tokens visuales propios |
| MatrixTable | card propia con `bg-white border-gray-100 rounded-lg shadow` | `overflow-hidden` sin tokens visuales propios |

---

## 6. Estructura Después

```
┌─ [100vw hack] root ────────────────────────────────────────┐
│                                                             │
│  ┌─ [mx-3 sm:mx-4] margin wrapper ──────────────────────┐  │
│  │                                                       │  │
│  │  ┌─ SHELL ────────────────────────────────────────┐  │  │
│  │  │ bg=ct-surface, border=ct-border, rounded-lg    │  │  │
│  │  │ overflow-hidden, divide-y                       │  │  │
│  │  │                                                │  │  │
│  │  │  ┌─ CommandHeader (accent left border only) ─┐ │  │  │
│  │  │  ├─ border-t divider ─────────────────────────┤ │  │  │
│  │  │  │ Momentum strip                             │ │  │  │
│  │  │  ├─ border-t divider ─────────────────────────┤ │  │  │
│  │  │  │ Controls + filters + visualization        │ │  │  │
│  │  │  ├─ border-t divider ─────────────────────────┤ │  │  │
│  │  │  │ Status bars, banners, freshness, priority │ │  │  │
│  │  │  ├─ border-t divider ─────────────────────────┤ │  │  │
│  │  │  │ KPI selector (inline) + Insights          │ │  │  │
│  │  │  ├─ border-t divider ─────────────────────────┤ │  │  │
│  │  │  │ Matrix Table (scroll container)           │ │  │  │
│  │  │  └───────────────────────────────────────────┘ │  │  │
│  │  └───────────────────────────────────────────────┘  │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

Todas las secciones comparten `bg-ct-surface`, `border-ct-border`, y `rounded-lg` del shell. Los divisores `divide-y` reemplazan los `space-y-2` gaps.
