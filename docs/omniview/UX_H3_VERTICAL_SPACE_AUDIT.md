# UX-H3 — VERTICAL SPACE AUDIT

**Motor:** Control Foundation  
**Fecha:** 2026-05-31  

---

## 1. Altura Antes de la Matriz (Estimado)

| # | Componente | Altura antes | Altura después |
|---|---|---|---|
| 1 | OmniviewCommandHeader + MatrixExecutiveBanner | 78-120px | 78-120px (sin cambios) |
| 2 | MomentumPriorityStrip | 28px (cond.) | 28px (cond.) |
| 3a | Filter row | 55-100px | 44-80px (padding reducido) |
| 3b | OmniviewDataHelp wrapper | 56px | 36px (py-1) |
| 3c | Visualization controls | 36-100px | 30-70px (py-1) |
| 4 | Active tasks bar | 30px (cond.) | 30px (cond.) |
| 5 | OperationalStatusBar | 28px (cond.) | 28px (cond.) |
| 6 | sliceRealFreshnessBanner | 36px (cond.) | 36px (cond.) |
| 7-15 | Projection banners (YTD, alerts, etc.) | 250-600px (cond.) | 250-600px (cond.) |
| 16 | **KPI Focus card** | **80px** | **0px (mergeado)** |
| 17 | Insights panel | 150-350px (cond.) | 150-350px (cond.) |
| — | space-y-2 gaps (~10 elementos) | 80px | 72px |
| **Total header** | | **~720-900px** | **~640-800px** (~11-15% reduction) |

---

## 2. Principales Consumidores de Espacio (Antes)

| Ranking | Componente | Altura | Acción |
|---------|-----------|--------|--------|
| 1 | Insights Panel | 150-350px | Ya colapsable. Focus Mode lo oculta. |
| 2 | KPI Focus Card | 80px | Mergeado a controls row inline |
| 3 | Projection banners | 250-600px | Condicionales. Focus Mode los oculta. |
| 4 | CommandHeader + ExecutiveBanner | 78-120px | Mantenido por governance |
| 5 | Filter row | 55-100px | Padding reducido |
| 6 | Controls row | 36-100px | Padding reducido, layout compactado |

---

## 3. Cambios Aplicados

| Componente | Antes | Después | Ahorro |
|-----------|-------|---------|--------|
| KPI Focus | Card separada (80px) | Inline en controls row (+0px) | ~80px |
| Filter row | `px-3 py-1.5 gap-x-3 gap-y-1.5` | `px-3 py-1 gap-x-2 gap-y-1` | ~10-20px |
| Controls row | `px-4 py-2 gap-x-4 gap-y-2` | `px-3 py-1.5 gap-x-3 gap-y-1.5` | ~10-15px |
| DataHelp wrapper | `px-4 py-2` | `px-3 py-1` | ~8px |
| **Total ahorro** | | | **~110-125px** |

---

## 4. Objetivo de Reducción

Objetivo: 40-60% reducción (~300-500px).

Logrado: ~11-15% (~100-125px).

La reducción significativa requiere usar **Focus Mode** (que elimina items 3b, 5, 7-15, 16, 17, reduciendo ~500-800px). Sin Focus Mode, las alertas y banners de proyección dominan la altura, pero son necesarios para governance.

**Recomendación UX-H4:** Hacer persistentes las preferencias de Focus Mode entre sesiones, o activarlo por defecto para usuarios recurrentes.
