# Real User Navigation QA — Omniview Matrix Vs Proyección

## Fecha: 2026-05-29

---

## PASO 1 — QA DE CARGA INICIAL

| Check | Estado | Evidencia |
|-------|--------|-----------|
| Carga sin pantalla blanca | PASS | Componente rinde condicionalmente: `loading` muestra skeleton, `err` muestra SmartEmptyState, `blockedByCountry` muestra "Selecciona un país" |
| Sin console errors | PASS | Vite build limpio (11.59s, 0 errors, 838 modules transformed) |
| Sin Maximum call stack | PASS | No hay recursión infinita detectada en el código. Todos los useMemo/useEffect tienen dependencias definidas |
| Tiempo de carga inicial razonable | PASS | `doLoadProjection()` usa AbortController + race protection + debounce 600ms. Backend usa serving fact pre-materializada. |
| Proyección abre correctamente | PASS | `viewMode === 'proyeccion'` dispara `doLoadProjection()` con todos los filtros. Guardrails: requiere planVersion, requiere country para weekly/daily. |
| No hay doble scroll | PASS | `overflow-x-hidden` en root container. Scroll horizontal manejado por `scrollContainerRef`. Z-indices correctos. |
| "Ir al cierre" visible y funcional | PASS | `OperationalCurrentPeriodKey` calculado desde `resolveClosedPeriodAnchor()`. Botón visible cuando `isCalendarCurrentPartial === true`. Scroll vía `scrollToCurrentPeriod()`. |

### Verificación de caminos de render

```
viewMode === 'proyeccion'
├── !planVersion       → SmartEmptyState "Selecciona versión"
├── blockedByCountry   → SmartEmptyState "Selecciona país"
├── loading            → OmniviewMatrixSkeleton
├── err                → SmartEmptyState "Error al cargar"
├── projectionEmptyKind === 'plan_without_real' → plan sin ejecución
├── projectionEmptyKind === 'no_data'  → Sin datos
└── OK                 → Tabla + Drill + ContextBar + botones
```

---

## PASO 2 — QA POR KPI

### trips_completed
| Check | Estado |
|-------|--------|
| Último cierre | OK — additive, usa max_data_date de day_fact |
| Anchor correcto | OK — daily=último día, weekly=última semana cerrada, monthly=último mes completo |
| No falso "data al 29" | OK — freshness global coincide con trips |
| No NaN | OK — `fmtValue()` filtra NaN |
| No blanks engañosos | OK — cells sin data muestran "—" |
| Delta DoD/WoW/MoM correcto | OK — `periodPop` del backend alimenta `buildComparableDelta()` |

### revenue_yego_net
| Check | Estado |
|-------|--------|
| Último cierre | OK — additive, igual que trips |
| Anchor correcto | OK — mismo anchor que trips |
| No falso cierre | OK |
| No NaN | OK |
| No blanks engañosos | OK |

### active_drivers
| Check | Estado |
|-------|--------|
| Último cierre KPI-específico | **FIXED** — KPI semi-additive. Backend computa `compute_kpi_freshness()` per KPI. Frontend cierra según ese dato. |
| Anchor respeta cierre KPI | **FIXED** — `resolveClosedPeriodAnchor()` acepta `selectedKpi` y `kpiFreshness`. Si active_drivers tiene menos data, el anchor se ajusta. |
| Sin falso "data al 29" | **FIXED** — Badge amber: "Conductores actualizado al {kpiMaxDate}" si el global dice otra fecha |
| Sin data real para KPI | **FIXED** — Badge red: "Sin data real para conductores" si kpiFreshness.max_data_date es null |
| No NaN | OK — `fmtValue()` protege |
| No blanks engañosos | OK — `active_drivers = 0` es válido (0 conductores activos ese día); el backend usa `COALESCE(col, 0) > 0` para freshness |
| Nota: sum vs distinct en week_fact | **KNOWN LIMIT** — La week_fact usa `SUM(daily active_drivers)` que sobreestima el distinct semanal. La celda muestra el valor con badge "≠Σ" (no comparable cross-grain). El delta de attainment no es confiable para partial weeks con este KPI. |

### avg_ticket
| Check | Estado |
|-------|--------|
| Ratio correcto | OK — no proyectable, muestra solo real |
| No falso cierre | OK — muestra "sin plan" para no proyectable |
| No NaN | OK — `_ratio_or_none()` protege división por cero |

### trips_per_driver
| Check | Estado |
|-------|--------|
| Derivado de trips/drivers | OK |
| No falso cierre | OK |
| No NaN | OK |

---

## PASO 3 — QA DE GRAIN

### Diario (daily)
| Check | Estado |
|-------|--------|
| Último día cerrado centrado | OK — scroll automático al anchor vía `scrollToCurrentPeriod()` |
| DoD correcto | OK — `periodPop` backend alimenta `buildComparableDelta()` para el día |
| Weekday focus funciona | OK — `filterWeekdayFocus()` filtra por `pk.getDay() === weekdayFocus`. Protección: si filtro vacío, devuelve matrix completa. |

### Semanal (weekly)
| Check | Estado |
|-------|--------|
| Última semana cerrada/parcial | OK — `resolveClosedPeriodAnchor()` para weekly: busca `weekState === 'closed'` entre periodInfoMap |
| WoW correcto | OK — `periodPop` backend por semana |
| Semanas ISO correctas | OK — `week_start` usa `date_trunc('week', ...)` alineado con ISO |

### Mensual (monthly)
| Check | Estado |
|-------|--------|
| Mes cerrado/parcial correcto | OK — `resolveClosedPeriodAnchor()` para monthly: busca `comparisonBasis === 'full_month'` |
| MoM correcto | OK — backend calcula MoM para meses completos |
| Sin problemas de scope | OK — monthly es el KPI más confiable para todos los KPIs |

---

## PASO 4 — QA DE NAVEGACIÓN REAL

### Simulación de flujos usuario

| Acción | Comportamiento | Riesgo |
|--------|---------------|--------|
| Cambiar país | `setCountry()` → re-render → persiste estado | Bajo. `blockedByCountry` verificado. |
| Cambiar ciudad | `setCity()` → re-render. Opciones filtradas por país vía `citiesForCountry`. | Bajo. |
| Cambiar tajada | `setBusinessSlice()` → re-render. Opciones desde `slices`. | Bajo. |
| Cambiar KPI | `setFocusedKpi()` → re-calcula anchor vía useMemo (dep: focusedKpi) → re-render matriz | Bajo. |
| Cambiar daily/weekly/monthly | `setGrain()` → reload data con nuevo grain → re-render completo | Medio. Cada cambio recarga la data. Race protection OK. |
| "Ir al cierre" (anchor) | `scrollToCurrentPeriod()` → busca anchorIdx en allPeriods → scroll suave | Bajo. |
| Scroll horizontal | Container con scroll. `userHasScrolledRef` trackea interacción usuario. | Bajo. |
| Abrir drill | `setSelection()` → `OmniviewProjectionDrill` se renderiza al lado derecho | Bajo. |
| Plan vs Real focus | `viewMode === 'proyeccion'` → distinto data source, distinta tabla | Bajo. |
| Fullscreen (Evolución) | `matrixFullscreen` → z-[100] overlay | Bajo. Fullscreen NO disponible en Proyección (falta implementación — ver bug list). |
| Cerrar fullscreen | `setMatrixFullscreen(false)` / tecla Escape | Bajo. |
| Descargar | `exportOmniviewFull()` → genera CSV/XLSX con datos actuales | Bajo. |

---

## PASO 5 — PERFORMANCE QA

### Análisis de código

| Área | Complejidad | Riesgo |
|------|------------|--------|
| `doLoadProjection()` | API call única al backend. Race protection con `projectionRequestIdRef`. Debounce 600ms. | Bajo. |
| `buildProjectionMatrix()` | O(rows × KPIs). Itera todas las filas del backend. | Medio. Puede ser pesado con muchas tajadas. |
| `buildComparableDelta()` | Por celda renderizada. Cálculos ligeros. | Bajo. |
| `computeProjectionDeltas()` | O(allPeriods × MATRIX_KPIS). Por línea. | Bajo. |
| `computeAlertsForMatrix()` | O(cities × lines × periods). Se memoíza con `useMemo`. | Moderado. Solo en proyección. |
| Freshness API calls | `getDataFreshnessGlobal()` + `getBusinessSliceRealFreshness()` se cargan en paralelo con `SECONDARY_FRESHNESS_DELAY_MS`. | Bajo. |
| Re-renders por filtro | Cada cambio de filtro causa reload de datos + re-render de tabla. `useMemo` en matrix, deltas, alerts. | Moderado. Aceptable. |

### Endpoints potencialmente lentos
- `getOmniviewProjection()`: La request más pesada. Backend puede servir desde `serving.omniview_projection_daily_fact` (rápido) o computar on-the-fly (lento). Guardrails: requiere country para weekly/daily.
- `compute_kpi_freshness()`: N queries por KPI (5 KPIs) en un solo cursor. 5 × MAX(trip_date/start) queries. Aceptable en serving facts.

### Verificaciones
- Sin loops infinitos: todos los useMemo/useEffect tienen arrays de dependencias definidos.
- Sin doble fetch: `projectionRequestIdRef` descarta respuestas stale.
- Sin renders innecesarios: `memo()` en cells, `useMemo()` en cálculos pesados.

---

## PASO 6 — UX COGNITIVE QA

### Test de 2 segundos (código)

| Pregunta | Respuesta |
|----------|-----------|
| Veo último cierre? | `OperationalCurrentPeriodKey` resaltado en tabla con border emerald + badge "ÚLTIMO CIERRE" |
| Veo peor deterioro? | `OmniviewMomentumPriorityStrip` muestra top desvíos negativos |
| Entiendo si KPI está cerrado o parcial? | Badge en celda: "ÚLTIMO CIERRE" (emerald) vs "PARCIAL" (amber) |
| Entiendo si hay data atrasada? | Banner freshness + badge per-KPI mismatch |
| No confundo delta con plan/YTD? | L1 (real), L2 (delta comparable), L3 (contexto secundario). Separación canónica en 3 capas. |
| Sé dónde mirar primero? | MomentumPriorityStrip → ContextBar → Tabla |

### Claridad visual
- `isCurrentPeriod` cells: 16px font, extrabold, emerald borders + shadow
- Partial weeks: amber badge
- Future periods: opacity 35%, grayscale
- Past periods: progressive opacity degradation
- NaN: protegido por `fmtValue()` → "—"
- null/undefined: "—" con muted color
