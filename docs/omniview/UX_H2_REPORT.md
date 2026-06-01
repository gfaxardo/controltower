# UX-H2 — REPORTE FINAL

**Motor:** Control Foundation UX Hardening  
**Fecha:** 2026-05-31  
**Estado:** COMPLETADO  
**Build:** PASS  

---

## 1. Cambios Realizados

### 1.1 Modelo de Estados Temporales Visuales

Se creó `TEMPORAL_VISUAL_TIERS` con 4 niveles que reemplazan la lectura por badges de texto:

```
HISTORICAL_CLOSED → LATEST_CLOSED → CURRENT_PARTIAL → FUTURE
     (atenuado)       (dominante)      (distinto)      (atenuado)
```

El modelo se computa en `computeTemporalVisualTiers()` y se propaga a través de toda la cadena de componentes: `BusinessSliceOmniviewMatrix` → `MatrixTable` → `MatrixHeader` + `MatrixCell`.

### 1.2 Jerarquía Visual

| Tier | Header | Celdas | Tipografía |
|------|--------|--------|------------|
| LATEST_CLOSED | Emerald oscuro, borde 3px, glow, +28% | Borde verde, bg blanco, shadow | +28% valor, +20% delta |
| CURRENT_PARTIAL | Sky oscuro, borde 2px, +12% | Borde sky, bg sky-50/20 | +12% |
| HISTORICAL_CLOSED | Zebra slate, base | Zebra + degradado temporal | base |
| FUTURE | Slate atenuado, -15%, sin badge | Opacidad 35%, bg tenue | -15% |

### 1.3 Degradado Temporal

```js
timelineOpacityDecay(distance):
  0 pasos → 0% atenuación
  cada paso → +5% (máx 35%)
```

Columnas más lejanas del ancla (`LATEST_CLOSED`) pierden contraste progresivamente, creando un gradiente natural hacia el pasado.

### 1.4 Énfasis de Outliers

Deltas con `|pct| > 15%` reciben un tinte ámbar sutil. No es un semáforo agresivo — es una señal que permite detectar anomalías al escanear visualmente.

### 1.5 Reducción de Ruido

- Badges "En curso"/"Carga incompleta" suprimidos cuando el tier visual ya lo comunica
- Etiquetas secundarias (fechas) omitidas en columnas FUTURE
- Badge de periodo actual reemplazado por tier badge contextual

### 1.6 Proyección Mode

La proyección mantiene su propio modelo temporal (`buildProjectionCellDisplay`) pero se beneficia del nuevo gradiente de opacidad para periodos pasados (`HISTORICAL_CLOSED`).

---

## 2. QA Visual

| Pregunta | Resultado |
|----------|-----------|
| ¿Latest Closed identificable en <2s? | SI — borde 3px emerald, tipografía +28%, shadow |
| ¿Partial identificable en <2s? | SI — borde 2px sky, badge "Parcial" |
| ¿Future identificable en <2s? | SI — opacidad 35%, texto gris, sin badges |
| ¿Future compite visualmente? | NO — atenuado al máximo sin desaparecer |
| ¿Latest Closed domina? | SI — es la columna más brillante y destacada |
| ¿Outliers visibles? | SI — tinte ámbar sutil en celdas con |delta| > 15% |

---

## 3. Verificación de Build

```
npm run build → PASS (844 modules, 8.04s)
```

Sin errores ni warnings nuevos.

---

## 4. Verificación de No-Regresión

- No se modifican cálculos
- No se modifican serving facts
- No se modifica freshness
- No se modifican APIs
- Period states originales (`PERIOD_STATES`) se mantienen intactos
- El nuevo modelo (`TEMPORAL_VISUAL_TIERS`) es una capa adicional, no un reemplazo

---

## 5. Riesgos

| Riesgo | Nivel | Nota |
|--------|-------|------|
| Diferencia visual entre dev y prod | Bajo | Mismo código, misma UI |
| Percepción de "demasiado verde" en LATEST_CLOSED | Bajo | Emerald oscuro (`#064e3b` base), no verde chillón |
| Confusión con trust overlay (rojo) | Bajo | Trust usa `rose/red`, el tier usa `emerald/sky` — dominios cromáticos distintos |

---

## 6. Recomendaciones para UX-H3

1. **Transiciones animadas:** Agregar `transition-all` al cambio de tier cuando el usuario cambia de grano (daily → weekly → monthly).
2. **Indicador de progreso en CURRENT_PARTIAL:** Barra de progreso sutil dentro del mes/semana actual (% de días transcurridos).
3. **Zoom semántico:** Al hacer zoom out extremo, colapsar HISTORICAL_CLOSED en un solo bloque "Histórico".
4. **Atajos de navegación:** Click en LATEST_CLOSED header → scroll instantáneo al ancla.

---

## 7. Archivos Modificados

| Archivo | Acción |
|---------|--------|
| `frontend/src/components/omniview/omniviewMatrixUtils.js` | +120 líneas: modelo de tiers, helpers visuales, outlier, gradiente |
| `frontend/src/components/BusinessSliceOmniviewMatrixHeader.jsx` | Refactorizado: jerarquía por tier, badges de tier, escala tipográfica |
| `frontend/src/components/BusinessSliceOmniviewMatrixCell.jsx` | Refactorizado: tiers en evolution + projection, degradado, outliers |
| `frontend/src/components/BusinessSliceOmniviewMatrix.jsx` | +2 líneas: import + useMemo de `temporalTiers` |
| `frontend/src/components/BusinessSliceOmniviewMatrixTable.jsx` | +10 líneas: propagación de `temporalTiers` y `latestClosedPk` |
| `docs/omniview/UX_H2_TEMPORAL_VISUAL_HIERARCHY.md` | Creado: documentación completa |
| `docs/omniview/UX_H2_REPORT.md` | Creado: este reporte |
