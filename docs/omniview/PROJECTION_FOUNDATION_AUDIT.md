# PROJECTION FOUNDATION AUDIT — FASE 1

**Date**: 2025-05-25
**Motor**: Control Foundation + Diagnostic Engine Temprano
**Status**: COMPLETE

---

## OBJECTIVE

Entender exactamente cómo funciona Vs Proyección hoy — rutas reales, componentes vivos, data flow, y todo código legacy/muerto — como base para la migración hacia el Projection Command Center unificado.

---

## KEY FINDING

**Vs Proyección NO es una ruta separada. Es un MODE TOGGLE (`viewMode === 'proyeccion'`) dentro de `BusinessSliceOmniviewMatrix.jsx`, en la misma ruta `/operacion/omniview-matrix`, misma tab "Operación".**

El botón "Vs Proyección" en la barra de controles (línea 1378) activa el modo sin cambiar de URL. Esto es crítico: cualquier momentum/deterioration/insight que se quiera añadir a Proyección debe vivir dentro de este mismo componente.

---

## 1. ROUTING AUDIT

### Ruta activa

| Atributo | Valor |
|---|---|
| **URL** | `/operacion/omniview-matrix` |
| **Tab** | Operación |
| **Componente** | `BusinessSliceOmniviewMatrix` (envuelto en `OmniviewErrorBoundary`) |
| **Archivo** | `frontend/src/components/BusinessSliceOmniviewMatrix.jsx` |
| **Render en App.jsx** | Línea 365 |
| **State toggle** | `viewMode` (`'evolucion'` | `'proyeccion'`), línea 263 |
| **Detección** | `isProjectionMode = viewMode === 'proyeccion'`, línea 284 |

### Controles de navegación (Maturity Registry)

| Key | Maturity | Phase | Visible | Engine |
|---|---|---|---|---|
| `operacion_omniview_matrix` | `STABLE` | 1H | `true` | `CONTROL_FOUNDATION` |
| `operacion_omniview` | `LEGACY` | — | `false` | — |
| `real_vs_projection` | `EXPERIMENTAL` | BACKLOG | **`false`** | `FORECAST` (not active) |

### Rutas muertas / legacy detectadas

| Ruta | Componente | Estado |
|---|---|---|
| `/en-revision/real-vs-proyeccion` | `RealVsProjectionView` | **DEAD** — tab `En revisión` hidden, route catches `BacklogPlaceholder` |
| `/operacion/omniview` | `BusinessSliceOmniview` | **LEGACY** — hidden, replaced by Matrix |
| `/operacion/business-slice` | (legacy) | **LEGACY** — hidden |

### Feature flags que afectan Proyección

| Flag | Tipo | Efecto |
|---|---|---|
| `VITE_OMNIVIEW_MATRIX_MANUAL_LOAD` | Env var | Dev only — difiere queries pesadas hasta click "Cargar datos" |
| `heavyQueriesEnabled` | State | Debe ser `true` para que projection cargue datos |
| `planVersion` | State | Debe estar seleccionada para que proyección cargue |
| `blockedByCountry` | Computed | Bloquea semanal/diario sin país en Evolución; afecta condicionales |
| `VITE_SHOW_FORECAST_EXPERIMENTAL` | Env var | Controla `real_vs_projection` (dead route) |

---

## 2. DATA FLOW AUDIT

### Endpoint dominante

```
GET /ops/business-slice/omniview-projection
```

Llamado desde `doLoadProjection()` en `BusinessSliceOmniviewMatrix.jsx` línea 619.

### Flujo de datos completo

```
trigger (filter change / manual reload)
  │
  ├── doLoad() [línea 694]  →  if isProjectionMode → doLoadProjection(signal)
  │
  └── doLoadProjection(signal) [línea 619]
       ├── projectionRequestIdRef++  (race guard)
       ├── getOmniviewProjection(params, {signal})
       ├── setProjectionRows(res.data)
       ├── setProjectionMeta(res.meta)
       ├── setProjectionResolvedKey(requestKey)  → detect staleness
       ├── validateProjectionOmniviewContract(meta, rows)
       └── logProjectionYtdPopDebug(meta, rows)
            │
            ▼
       projectionRows + projectionMeta
            │
            ├──→ projMatrix = buildProjectionMatrix(rows, grain) [useMemo]
            │         { cities, allPeriods, totals, cityVolumeMap,
            │           lineVolumeMap, periodMeta }
            │
            ├──→ displayProjMatrix = filterWeeklyFocus → filterWeekdayFocus [useMemo]
            │         → BusinessSliceOmniviewMatrixTable (mode="projection")
            │
            └──→ Subcomponentes condicionales (ver sección 3)
```

### State de proyección (14 variables)

| Variable | Tipo | Línea | Rol |
|---|---|---|---|
| `viewMode` | string | 263 | `'evolucion'` / `'proyeccion'` |
| `planVersion` | string | 266 | Plan version key seleccionada |
| `planVersions` | array | 267 | Merge de 3 fuentes de versiones |
| `servingVersions` | array | 268 | Subset con `hasServingFact === true` |
| `projectionRows` | array | 270 | Raw response rows |
| `projectionMeta` | object | 271 | Meta (ytd_summary, integrity, etc.) |
| `projectionResolvedKey` | string | 272 | Cache key para staleness |
| `projectionRequestIdRef` | ref | 273 | Race-condition guard (monotonic counter) |
| `projectionContractReport` | object | 275 | `{ok, issues}` de validación |
| `uploadModalOpen` | boolean | 277 | Modal de upload |
| `uploadFile` | File | 278 | Archivo seleccionado |
| `projectionPending` | boolean | 423 | True cuando filtros cambiaron pero fetch no resuelto |
| `projectionReady` | boolean | 429 | `!loading && !projectionPending` |
| `projectionIntegrityBroken` | boolean | 430 | `meta.integrity_status.status === 'broken'` |

### Race-condition protection

```js
const thisRequestId = ++projectionRequestIdRef.current  // antes del fetch
// ... fetch ...
if (projectionRequestIdRef.current !== thisRequestId) return  // descartar stale
```

### Componentes que INDEPENDIENTEMENTE fetchean datos de proyección

| Componente | API usada | Duplicación |
|---|---|---|
| `OperationalOpportunitiesView` | `getOmniviewProjection(params)` | **SÍ** — fetchea la misma API para leer `operational_suggestions` y `contextual_suggestions` |
| `ControlLoopPlanVsRealView` | `uploadControlLoopProjection`, `getControlLoopPlanVersions` | **NO** — es upload + plan versions, distinto |
| `OmniviewMomentumDrillChart` | `getOmniviewMomentumDrill` | **NO** — endpoint de momentum drill |
| `RealVsProjectionView` | `getRealVsProjection*` (5 APIs) | **NO** — está muerto |

**Duplicación detectada**: `OperationalOpportunitiesView` llama `getOmniviewProjection` independientemente para leer suggestions. Podría absorberlo desde el mismo fetch si se comparte estado.

### Funciones de API MUERTAS (definidas en api.js, nunca llamadas)

| # | Función | Endpoint |
|---|---|---|
| 1 | `getPlanUnmappedSummary` | `/plan/unmapped-summary` |
| 2 | `getProjectionIntegrityAudit` | `/plan/projection-integrity-audit` |
| 3 | `getLobAliasCatalog` | `/plan/lob-alias-catalog` |
| 4 | `getPlanReconciliationAudit` | `/plan/reconciliation-audit` |
| 5 | `getRealVsProjectionSystemSegmentation` | `/ops/real-vs-projection/system-segmentation-view` |
| 6 | `getRealVsProjectionProjectionSegmentation` | `/ops/real-vs-projection/projection-segmentation-view` |

---

## 3. COMPONENT AUDIT — VIVOS vs LEGACY vs MUERTOS

### LEGEND
- **ALIVE**: Renderizado en code paths activos
- **LEGACY**: Importado pero nunca renderizado; hidden from nav; ruta desviada por BacklogPlaceholder
- **DEAD**: Self-declared deprecated o cero imports

---

### ALIVE (14 componentes core de proyección)

| # | Componente | Archivo | Rol en Proyección |
|---|---|---|---|
| 1 | `OmniviewProjectionDrill` | `OmniviewProjectionDrill.jsx` | Side panel drill al clickear celda |
| 2 | `ProjectionVersionSelector` | `projections/ProjectionVersionSelector.jsx` | Selector de versión de plan |
| 3 | `RenameProjectionVersionModal` | `projections/RenameProjectionVersionModal.jsx` | Renombrar versión inline |
| 4 | `OmniviewPriorityPanel` | `OmniviewPriorityPanel.jsx` | Prioridades del periodo (projection-only) |
| 5 | `MatrixExecutiveBanner` | `MatrixExecutiveBanner.jsx` | Trust banner (ambos modos) |
| 6 | `ProjectionIntegrityBanner` | `BusinessSliceOmniviewMatrix.jsx:2392` | Estado de integridad |
| 7 | `ProjectionYtdSummaryBar` | `BusinessSliceOmniviewMatrix.jsx:3396` | Sumario YTD |
| 8 | `ProjectionYtdAlertsBlock` | `BusinessSliceOmniviewMatrix.jsx:3335` | Alertas YTD |
| 9 | `OperationalOpportunitiesSummary` | `BusinessSliceOmniviewMatrix.jsx:2188` | Oportunidades operativas |
| 10 | `ProjectionContextBar` | `BusinessSliceOmniviewMatrix.jsx:3497` | Barra de contexto (lag, curva, confianza) |
| 11 | `UnmappedBadge` | `BusinessSliceOmniviewMatrix.jsx:3714` | Filas no mapeadas |
| 12 | `ProjectionCellRender` | `BusinessSliceOmniviewMatrixCell.jsx:198` | Celda en modo proyección |
| 13 | `ProjectionTotalsRow` | `BusinessSliceOmniviewMatrixTable.jsx:388` | Fila de totales proyección |
| 14 | `BusinessSliceOmniviewMatrixHeader` | `BusinessSliceOmniviewMatrixHeader.jsx` | Header con proyección |

### Utility modules vivos

| Archivo | Líneas | Rol |
|---|---|---|
| `projectionMatrixUtils.js` | 937 | buildProjectionMatrix, KPIs, signals, YTD, pacing, labels |
| `projectionContractValidation.js` | 95 | Validación de 7 contratos estructurales |

### LEGACY (1 componente)

| Componente | Archivo | Por qué es legacy |
|---|---|---|
| `RealVsProjectionView` | `RealVsProjectionView.jsx` | Importado en App.jsx:44, registrado en tab "En revisión" oculta, ruta `/en-revision/...` siempre muestra `BacklogPlaceholder`. Es un proto-forecast que nunca se activó. |
| `BusinessSliceOmniview` | `BusinessSliceOmniview.jsx` | Reemplazado por Matrix. Tab hidden. |

### DEAD (2 archivos, auto-declarados deprecated)

| Componente | Archivo | Estado |
|---|---|---|
| `BusinessSliceOmniviewProjectionTable` | `BusinessSliceOmniviewProjectionTable.jsx` | `@deprecated FASE 3.1B` — absorbido por `MatrixTable` |
| `BusinessSliceOmniviewProjectionCell` | `BusinessSliceOmniviewProjectionCell.jsx` | `@deprecated FASE 3.1B` — absorbido por `ProjectionCellRender` |

Ambos son zero-imports en todo `src/`. Seguros de eliminar.

### Dead import en App.jsx

```js
// App.jsx línea 44
import RealVsProjectionView from './components/RealVsProjectionView'  // ← NUNCA USADO
```

---

## 4. CONDITIONAL RENDERING MAP

Todos los siguientes bloques existen dentro de `BusinessSliceOmniviewMatrix.jsx`. Condición raíz: `isProjectionMode === true`.

```
viewMode === 'proyeccion'
  │
  ├── ProjectionVersionSelector  (línea 1386)
  │     │  cond: isProjectionMode
  │
  ├── MatrixExecutiveBanner       (línea 1251)
  │     │  cond: heavyQueriesEnabled
  │     │  datos: usa projectionRows en proyección
  │
  ├── ProjectionIntegrityBanner   (línea 1596)
  │     │  cond: heavyQueriesEnabled && projectionReady && meta.integrity_status
  │     │  hidden: !projectionReady || integrity broken
  │
  ├── ProjectionYtdSummaryBar     (línea 1601)
  │     │  cond: meta.ytd_summary && !meta.ytd_summary.error
  │     │  hidden: projectionIntegrityBroken
  │
  ├── ProjectionYtdAlertsBlock    (línea 1613)
  │     │  cond: meta.ytd_alerts?.length > 0 && !projectionIntegrityBroken
  │
  ├── OperationalOpportunitiesSummary (línea 1617)
  │     │  cond: projectionReady && projectionMeta
  │
  ├── ProjectionContextBar        (línea 1622)
  │     │  cond: isProjectionMode
  │
  ├── UnmappedBadge               (línea 1630)
  │     │  cond: meta.unresolved?.count > 0
  │     │  lazy fetch: getPlanMappingAudit al expandir
  │
  ├── OmniviewPriorityPanel       (línea ~1851)
  │     │  cond: projMatrix && projectionRows.length > 0 && !projectionIntegrityBroken
  │
  ├── OmniviewProjectionDrill     (línea ~1897)
  │     │  cond: selection activa en modo proyección
  │     │  muestra: gap, root cause, action suggestions, control loop history
  │
  ├── BusinessSliceOmniviewMatrixTable (mode="projection")  (línea ~1910+)
  │     │  recibe: displayProjMatrix
  │     │  usa: ProjectionCellRender, ProjectionTotalsRow, attainment badges
  │
  └── SmartEmptyState             (línea ~1925+)
        │  conds anidadas:
        │    - blockedByCountry → 'Selecciona país'
        │    - !planVersion → 'Selecciona versión'
        │    - plan_without_real → 'Sin ejecución'
        │    - projectionEmptyKind
```

---

## 5. WHAT PROJECTION CURRENTLY HAS vs DOESN'T HAVE

### Tiene (ACTIVO hoy)

| Capacidad | Implementación |
|---|---|
| Plan vs Real | projectionMatrixUtils — attainment, gap, signal |
| Cumplimiento | attainment_pct, gap_to_expected, gap_pct |
| Proyección | projected_total, projected_expected, expected_to_date |
| Ejecución vs target | comparison_basis (E/F), completion_pct |
| Integridad | integrity_status (OK/WARNING/BROKEN) |
| YTD | ytd_summary, ytd_alerts, ytd_slice, authoritative_ytd |
| Prioridades | OmniviewPriorityPanel (projection-only alerts) |
| Drill | OmniviewProjectionDrill (root cause, actions) |
| Reconciliación | reconciliation data in meta |
| Oportunidades | operational/contextual/decision suggestions |
| Upload | Modal de upload de archivo Ruta 27 |
| Trust | MatrixExecutiveBanner (ambos modos) |

### NO tiene (momentum/evolution features AUSENTES en proyección)

| Capacidad | Dónde existe hoy |
|---|---|
| **Momentum Color Authority** (DoD/WoW/MoM) | Solo en modo Evolución |
| **Weekday Focus** (VIE/LUN/etc.) | Solo en modo Evolución |
| **Momentum Drill** | Solo en Evolution (OmniviewMomentumDrillChart) |
| **Momentum Severity** | Solo en Evolution (operationalMomentumPriority) |
| **Priority Strip** | Solo en Evolution (OmniviewMomentumPriorityStrip) |
| **Insight Engine** | Solo en Evolution (insightEngine, insights panel) |
| **Comparative Cognition** (same-weekday) | Solo en Evolution |
| **Deterioration Priority** | Solo en Evolution |

---

## 6. LEGACY / DEAD CODE — CLEANUP CANDIDATES

### Seguros de eliminar (zero impact)

| Tipo | Elemento | Archivo:línea |
|---|---|---|
| Componente dead | `BusinessSliceOmniviewProjectionTable.jsx` | archivo entero |
| Componente dead | `BusinessSliceOmniviewProjectionCell.jsx` | archivo entero |
| Import dead | `import RealVsProjectionView` | `App.jsx:44` |
| API dead | `getPlanUnmappedSummary` | `api.js:250` |
| API dead | `getProjectionIntegrityAudit` | `api.js:262` |
| API dead | `getLobAliasCatalog` | `api.js:271` |
| API dead | `getPlanReconciliationAudit` | `api.js:277` |
| API dead | `getRealVsProjectionSystemSegmentation` | `api.js:813` |
| API dead | `getRealVsProjectionProjectionSegmentation` | `api.js:817` |

---

## 7. DUPLICACIÓN DETECTADA

| Duplicación | Detalle |
|---|---|
| **Projection data fetch** | `OperationalOpportunitiesView` hace su propio fetch de `getOmniviewProjection` para leer suggestions, en paralelo al fetch del Matrix principal. Podría compartir estado. |
| **Plan versions fetch** | Tanto `BusinessSliceOmniviewMatrix` como `OperationalOpportunitiesView` y `ControlLoopPlanVsRealView` fetchean `getPlanVersions` + `getControlLoopPlanVersions` independientemente. |

---

## 8. CRITERIO GO — FASE 1

| Check | Estado |
|---|---|
| Entendemos cómo Proyección renderiza hoy | **SÍ** — mode toggle en BusinessSliceOmniviewMatrix |
| Sabemos qué componentes están vivos | **SÍ** — 14 vivos, 1 legacy, 2 dead |
| Sabemos qué APIs están vivas | **SÍ** — 1 dominante (`/omniview-projection`), 6 dead |
| Sabemos qué puede absorber momentum | **SÍ** — `ProjectionCellRender`, `ProjectionTotalsRow`, `OmniviewProjectionDrill` |
| Sabemos qué paths están muertos | **SÍ** — `RealVsProjectionView`, 2 deprecated files, 6 dead APIs |

### GO — FASE 1 COMPLETA

---

## NEXT: FASE 2 — MOMENTUM PARITY INSIDE PROJECTION

Puntos de inyección identificados para momentum dentro de Proyección:

1. **Color Authority**: Modificar `ProjectionCellRender` para que DoD/WoW/MoM tengan peso visual principal, attainment pase a secundario
2. **Weekday Focus**: El filtro `filterWeekdayFocus` ya existe en `displayProjMatrix` — activarlo visiblemente en modo proyección
3. **Momentum Drill**: Añadir toggle en `OmniviewProjectionDrill` para graficar momentum
4. **Momentum Severity**: `classifyMomentumRisk` ya existe — aplicarlo a filas de proyección
5. **Priority Strip**: `OmniviewMomentumPriorityStrip` podría recibir `projMatrix` además de `baseMatrix`

**Regla de cableado**: Todo nuevo código debe conectarse a estos componentes **vivos**, no a los legacy/muertos de la lista de la sección 6.
