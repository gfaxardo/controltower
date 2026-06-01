# UX-H2 — TEMPORAL VISUAL HIERARCHY

**Motor:** Control Foundation UX Hardening  
**Versión:** 1.0.0  
**Fecha:** 2026-05-31  

---

## 1. Resumen

La línea temporal de Omniview se lee ahora visualmente sin necesidad de texto. El cerebro identifica instantáneamente qué está cerrado, qué es parcial, y qué es futuro.

---

## 2. Modelo de Estados Temporales

Se introduce `TEMPORAL_VISUAL_TIERS`, un modelo de 4 niveles que mapea los estados de periodo a una jerarquía visual explícita:

| Tier | Estado de Periodo | Significado |
|------|------------------|-------------|
| `HISTORICAL_CLOSED` | CLOSED (anteriores al último cierre) | Pasado cerrado, atenuado progresivamente |
| `LATEST_CLOSED` | CLOSED (el más reciente) | Último dato completo y confiable → ANCLA DOMINANTE |
| `CURRENT_PARTIAL` | PARTIAL, CURRENT_DAY, OPEN | Periodo actual en curso, datos incompletos |
| `FUTURE` | FUTURE | Proyección, sin datos reales |

### 2.1 Algoritmo de Determinación

La función `computeTemporalVisualTiers()` recorre los periodos de derecha a izquierda (más reciente primero):

1. Encuentra el periodo más reciente con estado `CLOSED` y fecha ≤ hoy → `LATEST_CLOSED`
2. Todos los `CLOSED` anteriores → `HISTORICAL_CLOSED`
3. `PARTIAL` / `CURRENT_DAY` / `OPEN` → `CURRENT_PARTIAL`
4. `FUTURE` → `FUTURE`

### 2.2 Cálculo de Distancia Temporal

`temporalDistance(pk, latestClosedPk, grain)` retorna pasos de distancia desde el ancla:
- **Daily:** días
- **Weekly:** semanas
- **Monthly:** meses

### 2.3 Degradado Temporal (Timeline Gradient)

`timelineOpacityDecay(distance)` retorna factor de atenuación:
- Distancia 0 → 0% atenuación (opacidad completa)
- Cada paso adicional → +5% atenuación
- Máximo: 35% atenuación (floor en 65% opacidad)

Esto crea un gradiente natural: mientras más lejos del presente, menos contraste visual.

---

## 3. Jerarquía Visual por Tier

### 3.1 LATEST CLOSED — Ancla Dominante

**Header:**
- Background: `bg-emerald-900/95` (verde oscuro premium)
- Texto: `text-emerald-100`
- Borde: `border-[3px] border-emerald-400/80` con shadow verde
- Glow: `ring-1 ring-inset ring-emerald-400/40`
- Escala tipográfica: +28% (17px comfortable, 14px compact)
- Badge: "Último cierre" en `bg-emerald-600`

**Celdas:**
- Background: `bg-white/95` (más brillante que todo)
- Borde: `border-l-2 border-r-2 border-emerald-400/60` con shadow
- Valor: `font-extrabold`, 16px
- Delta: `font-bold`, 12px
- Sin atenuación de opacidad

**Objetivo:** Identificable en <2 segundos incluso con zoom reducido.

### 3.2 CURRENT PARTIAL — "Está Corriendo"

**Header:**
- Background: `bg-sky-900/90` (azul cielo oscuro)
- Texto: `text-sky-100`
- Borde: `border-l-2 border-r-2 border-sky-400/50`
- Escala tipográfica: +12% (15px comfortable, 13px compact)
- Badge: "Parcial" en `bg-sky-600/90`

**Celdas:**
- Background: `bg-sky-50/20` (tinte azul claro)
- Borde: `border-l-2 border-r-2 border-sky-400/40`
- Valor normal con tratamiento de periodo actual

**Objetivo:** Claramente distinto del ancla, transmite "datos en formación".

### 3.3 HISTORICAL CLOSED — Pasado Atenuado

**Header:**
- Zebra estándar (sin tier override)
- Tipografía base
- Sin badge

**Celdas:**
- Zebra normal
- Opacidad reducida por distancia: `1 - timelineOpacityDecay(distance)`
- Mientras más lejos, más tenue

### 3.4 FUTURE — Atenuado

**Header:**
- Texto: `text-slate-400`, opacidad 60%
- Badge: suprimido
- Escala tipográfica: -15% (10px comfortable, 8px compact)
- Sin etiqueta secundaria (fechas omitidas)

**Celdas:**
- Background: `bg-slate-50/10`
- Texto: `text-gray-400`
- Opacidad general: `opacity-35`
- Sin énfasis de outlier

---

## 4. Jerarquía de Encabezados de Columna

La fila de KPI (segunda fila del header) también responde a los tiers:

| Tier | Background | Texto | Tamaño |
|------|-----------|-------|--------|
| LATEST_CLOSED | `bg-emerald-900/80` | `text-emerald-200` | 14px |
| CURRENT_PARTIAL | `bg-sky-900/70` | `text-sky-200` | 11px |
| HISTORICAL_CLOSED | zebra slate | `text-slate-300` | 11px |
| FUTURE | `bg-slate-800/60` | `text-slate-500` | 10px |

---

## 5. Orden KPI en Celdas (Evolution Mode)

El orden es estrictamente:

```
VALOR (grande, bold)
  ↓
DELTA (comparación, coloreado)
```

En LATEST_CLOSED, el valor es `font-extrabold` para máxima dominancia.

---

## 6. Énfasis de Outliers

Cuando `|delta_pct| > 15%`, la celda recibe un highlight sutil:

- **>40%:** `ring-1 ring-inset ring-amber-300/40 bg-amber-50/15` (borde ámbar sutil)
- **15%-40%:** `bg-amber-50/8` (tinte apenas perceptible)

No es un semáforo. Es una señal visual que permite detectar anomalías al escanear la matriz.

---

## 7. Reducción de Ruido

| Elemento | Antes | Ahora |
|----------|-------|-------|
| Badges "En curso" / "Carga incompleta" en columnas | Visible | Suprimido cuando el tier ya lo comunica visualmente |
| Etiquetas secundarias en FUTURE | Visible | Omitidas (sin fechas en columnas futuras) |
| Badge "HOY" / "SEMANA ACTUAL" / "MES ACTUAL" | Siempre visible | Reemplazado por el tier badge |
| Texto redundante en celdas vacías | "—" con tooltip | Mantenido pero sin opacidad completa en FUTURE |

---

## 8. QA Visual

### Verificaciones

1. **¿Se identifica Latest Closed en <2 segundos?** — Columna con borde verde intenso en header y celdas, tipografía más grande.
2. **¿Se identifica Partial en <2 segundos?** — Columna con borde azul cielo, badge "Parcial".
3. **¿Se identifica Future en <2 segundos?** — Columnas visiblemente atenuadas, texto gris claro.
4. **¿Future compite visualmente?** — No. Opacidad 35%, sin bordes destacados, sin badges.
5. **¿Latest Closed domina?** — Sí. Es la única columna con borde de 3px, shadow, y tipografía +28%.
6. **¿Outliers son visibles?** — Sí. Tinte ámbar sutil en celdas con delta grande.

---

## 9. Archivos Modificados

| Archivo | Cambio |
|---------|--------|
| `frontend/src/components/omniview/omniviewMatrixUtils.js` | Añadido `TEMPORAL_VISUAL_TIERS`, `computeTemporalVisualTiers`, `temporalDistance`, `timelineOpacityDecay`, `temporalColumnBg`, `temporalCellBorder`, `temporalHeaderEmphasis`, `outlierEmphasisClass` |
| `frontend/src/components/BusinessSliceOmniviewMatrixHeader.jsx` | Jerarquía visual por tier en headers, badges de tier, escala tipográfica |
| `frontend/src/components/BusinessSliceOmniviewMatrixCell.jsx` | Jerarquía por tier en celdas evolution, degradado temporal, énfasis de outliers, proyección mejorada |
| `frontend/src/components/BusinessSliceOmniviewMatrix.jsx` | Cómputo y propagación de `temporalTiers` |
| `frontend/src/components/BusinessSliceOmniviewMatrixTable.jsx` | Propagación de `temporalTiers` y `latestClosedPk` a header y celdas |
