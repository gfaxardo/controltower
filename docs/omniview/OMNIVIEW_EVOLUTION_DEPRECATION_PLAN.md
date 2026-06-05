# OMNI-P0 — EVOLUTION DEPRECATION AUDIT & PLAN

**Motor:** Omniview Governance — P0 Recovery
**Fecha:** 2026-06-04
**Estado:** AUDITORÍA COMPLETADA — PLAN DEFINIDO

---

## 1. AUDITORÍA DE SUPERFICIE DE EVOLUTION

### 1.1 Componentes que referencian Evolution

| Componente | Archivo | Rol |
|-----------|---------|-----|
| ViewMode state + toggle | `BusinessSliceOmniviewMatrix.jsx:309` | `const [viewMode, setViewMode] = useState(saved?.viewMode || 'evolucion')` |
| isProjectionMode flag | `BusinessSliceOmniviewMatrix.jsx:336` | `viewMode === 'proyeccion'` — Evolution es el default cuando es `false` |
| Mode selector UI | `OmniviewModeSelector.jsx` | Botones Evolution / Vs Proy |
| Matrix builder | `BusinessSliceOmniviewMatrix.jsx:974` | `buildMatrix(rows, grain)` — Evolution usa este builder |
| Cell render | `BusinessSliceOmniviewMatrixCell.jsx:89-231` | Rama Evolution del render de celda |
| Column widths | `BusinessSliceOmniviewMatrixTable.jsx:196` | Evolution: `colW = compact ? 58 : 78` |
| Totals Row | `BusinessSliceOmniviewMatrixTable.jsx:367-422` | `TotalsRow` — Evolution totals |
| City sorting | `BusinessSliceOmniviewMatrixTable.jsx:149-170` | Alfabético, UNMAPPED al final |
| Line sorting | `BusinessSliceOmniviewMatrixTable.jsx:307-320` | `sortLineEntries()` con `lineImpactMap` |
| Inspector | `BusinessSliceOmniviewInspector.jsx` | Drill lateral Evolution |
| Export | `omniviewExport.js:59,75,158,360` | Secciones Evolution en CSV |
| Operational Surface | `BusinessSliceOmniviewMatrix.jsx:1801-1812` | `OperationalStatusBar`, `sliceRealFreshnessBanner` (solo Evolution) |
| Insights panel | `BusinessSliceOmniviewMatrix.jsx:1883-1893` | `insightCellMap`, `insightMode` (solo Evolution) |
| Trust fetching | `BusinessSliceOmniviewMatrix.jsx:482-556` | Compartido, pero Evolution lo muestra diferente |

### 1.2 Endpoints usados por Evolution

| Endpoint | API Function | Uso |
|----------|-------------|-----|
| `/ops/business-slice/monthly` | `getBusinessSliceMonthly()` | Datos mensuales Evolution |
| `/ops/business-slice/weekly` | `getBusinessSliceWeekly()` | Datos semanales Evolution |
| `/ops/business-slice/daily` | `getBusinessSliceDaily()` | Datos diarios Evolution |
| `/ops/business-slice/data-freshness` | `getDataFreshnessGlobal()` | Freshness Evolution |
| `/ops/business-slice/matrix-operational-trust` | `getMatrixOperationalTrust()` | Trust (compartido) |
| `/ops/business-slice/coverage-summary` | `getBusinessSliceCoverageSummary()` | Cobertura Evolution |
| `/ops/business-slice/filters` | `getBusinessSliceFilters()` | Filtros (compartido) |

### 1.3 Utilities exclusivas de Evolution

| Archivo | Función |
|---------|---------|
| `omniviewMatrixUtils.js` | `buildMatrix`, `computeDeltas`, `computePeriodStates`, `computeTemporalVisualTiers`, `MATRIX_KPIS`, `signalColorForKpi`, `signalArrow`, `fmtValue`, `fmtDelta`, `periodLabel`, `buildCellTooltip` |
| `currentPeriodFocusEngine.js` | `resolveCurrentPeriodIndex`, `calculateScrollTarget` |

### 1.4 Diferencias estructurales Evolution vs Vs Proy

| Aspecto | Evolution | Vs Proy |
|---------|-----------|---------|
| Default | **SÍ** (L309) | No |
| Cell model | Simple: valor + delta | L1(Real) + L2(Delta) + L3(Context) + L4(Status) |
| Period status visible | No (solo en tooltip) | Sí (CLOSED/PARTIAL/CURRENT/FUTURE badges) |
| DoD/WoW/MoM | Arrow + pct (inconsistente) | `buildComparableDelta` canónico con severidad |
| Closed period anchor | `getCurrentPeriodKey()` | `resolveClosedPeriodAnchor()` |
| Coloring | `signalColorForKpi` (binario: verde/rojo/gris) | Momentum severity 5 niveles + `projectionSignalColor` |
| Plan vs Real | No aplica | Proy + Real + Avance + Gap |
| Totals | Valor + delta simple | Proy/Real/Avance/Gap + YTD Attainment |
| Inspector | `BusinessSliceOmniviewInspector` | `OmniviewProjectionDrill` (870 líneas) |
| Insights | Sí | No |
| YTD/PoP badges | No | Sí |
| Projection confidence | No | Sí |
| City priority | Alfabético | Perú > Colombia, por volumen |

---

## 2. IMPACTO DE DEPRECAR EVOLUTION

### 2.1 ¿Qué se pierde?

| Funcionalidad | ¿Crítica? | ¿Reemplazable por Vs Proy? |
|---------------|----------|---------------------------|
| Insights panel con IA | Media | No directamente. Vs Proy no tiene insights engine. |
| Vista simple sin plan | Baja | Vs Proy puede mostrar "Sin plan" para periodos sin proyección. |
| Rendimiento más ligero | Baja | Evolution hace menos cálculos. Pero diferencia marginal. |
| Inspector de KPI simple | Baja | ProjectionDrill es más rico pero más pesado. |
| Export CSV Evolution | Baja | Export Vs Proy es más completo. |

### 2.2 ¿Qué se gana?

| Beneficio | Impacto |
|-----------|---------|
| Una sola fuente de verdad operacional | **Crítico** — elimina confusión usuario |
| Consistencia cross-métrica | **Alto** — Vs Proy tiene contrato L1-L4 uniforme |
| CLOSED/PARTIAL visible | **Alto** — el usuario sabe qué periodo está viendo |
| Revenue con datos reales | **Alto** — Vs Proy usa `revenue_yego_final` vía COALESCE |
| Foco temporal correcto | **Alto** — `resolveClosedPeriodAnchor` evita foco en noviembre |
| Certificación más simple | **Medio** — 1 sola vista que certificar |

---

## 3. PLAN DE DEPRECACIÓN (NO DESTRUCTIVO)

### Fase 1: Flag de control (AHORA)

Crear flag de entorno:
```
VITE_OMNIVIEW_EVOLUTION_LEGACY=false
```

En `BusinessSliceOmniviewMatrix.jsx:309`:
```javascript
const EVOLUTION_LEGACY = import.meta.env.VITE_OMNIVIEW_EVOLUTION_LEGACY === 'true';
const [viewMode, setViewMode] = useState(
  saved?.viewMode || (EVOLUTION_LEGACY ? 'evolucion' : 'proyeccion')
);
```

- **Flag=false (default)**: Vs Proy es la vista por defecto. Evolution no aparece.
- **Flag=true**: Evolution disponible como legacy (solo para debug interno).

### Fase 2: Ocultar toggle Evolution (AHORA)

En `OmniviewModeSelector.jsx`:
- Si `VITE_OMNIVIEW_EVOLUTION_LEGACY !== 'true'`, no renderizar el botón "Evolución".
- Solo mostrar "Vs Proy" como único modo (o ningún toggle).

### Fase 3: Bloquear certificación de Evolution

En OMNI-GOV-002 (nuevo framework):
- Regla C1: Evolution no puede ser usado como evidencia de certificación.
- Regla C2: Si Evolution está visible en UI operacional → FAIL automático.

### Fase 4: Cleanup futuro (P2, no ahora)

Cuando Vs Proy esté completamente estabilizado:
- Eliminar `omniviewMatrixUtils.js` (buildMatrix, computeDeltas, etc. de Evolution)
- Eliminar rama Evolution de `BusinessSliceOmniviewMatrixCell.jsx` (L89-231)
- Eliminar `TotalsRow` de Evolution en `BusinessSliceOmniviewMatrixTable.jsx`
- Eliminar `BusinessSliceOmniviewInspector.jsx`
- Eliminar insights engine de Evolution
- Simplificar `omniviewExport.js` quitando secciones Evolution
- Eliminar endpoints si nadie más los usa

### Fase 5: Endpoints (mantener por ahora)

Los endpoints `/ops/business-slice/{monthly,weekly,daily}` son usados por Evolution pero TAMBIÉN pueden ser usados por otros componentes del sistema. No eliminar sin auditar consumidores restantes.

---

## 4. RIESGOS DE LA DEPRECACIÓN

| Riesgo | Mitigación |
|--------|-----------|
| Usuario acostumbrado a Evolution | Mostrar Vs Proy como default con tooltip de bienvenida |
| Insights panel desaparece | P2: Migrar insights engine a Vs Proy (pero NO ahora) |
| Vs Proy requiere plan cargado | Mostrar "Sin plan — usando datos reales solamente" cuando no hay plan |
| Performance Vs Proy más pesada | Medir. Si es problema, P2 optimizar. |
| Export CSV cambia formato | Documentar nuevo formato Vs Proy |

---

## 5. ARCHIVOS A MODIFICAR (Fase 1 + 2)

| # | Archivo | Cambio |
|---|---------|--------|
| 1 | `BusinessSliceOmniviewMatrix.jsx:309` | Default `viewMode` a `'proyeccion'` si flag=false |
| 2 | `OmniviewModeSelector.jsx` | Ocultar botón Evolution si `VITE_OMNIVIEW_EVOLUTION_LEGACY !== 'true'` |
| 3 | `.env` / `.env.local` | Agregar `VITE_OMNIVIEW_EVOLUTION_LEGACY=false` |
| 4 | `BusinessSliceOmniviewMatrix.jsx` (varias) | Asegurar que Vs Proy funcione sin plan (graceful fallback) |

---

## 6. ESTADO FINAL ESPERADO

```
Usuario abre Omniview
  → Ve Vs Proy directamente
  → No ve toggle Evolution/Vs Proy
  → Cada celda tiene: L1 Real, L2 Delta, L3 Context, L4 Status
  → CLOSED/PARTIAL/CURRENT/FUTURE es visible
  → Foco temporal en periodo operativo actual (junio 2026)
  → Revenue muestra revenue_yego_final en todos los grains
  → Alertas coherentes con Trust y datos
```

---

**END OF EVOLUTION DEPRECATION AUDIT**
