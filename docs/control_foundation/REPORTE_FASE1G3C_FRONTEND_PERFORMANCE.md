# REPORTE FASE 1G.3C — FRONTEND WATERFALL / RENDER PERFORMANCE

## Resumen Ejecutivo

Se auditó el frontend de Omniview Matrix (BusinessSliceOmniviewMatrix, ~3390 líneas) para identificar y corregir causas de lentitud en el render, skeleton/loading prolongado, y waterfall de requests. Se detectaron 8 problemas raíz y se aplicaron optimizaciones sin tocar lógica de negocio ni fases 2.

---

## 1. Auditoría de Requests Reales

### Endpoints disparados al cargar (modo Evolución, monthly)

| Order | Endpoint | Delay inicial | Timeout | Secuencial? |
|-------|----------|---------------|---------|-------------|
| 1 | `GET /ops/business-slice/filters` | 0ms | 120s | No — inmediato |
| 2 | `GET /ops/business-slice/monthly` | 600ms (debounce) | 900s | No — propio |
| 3 | `GET /ops/business-slice/matrix-operational-trust` | 1500ms (delay intencional) | 900s | No — timer |
| 4 | `GET /ops/data-freshness/global` | 2800ms (delay intencional) | 120s | No — timer |
| 5 | `GET /ops/business-slice/coverage-summary` | **Después de monthly** (400ms extra) | 900s | **SÍ — secuencial** |

**Hallazgo**: Coverage-summary se ejecutaba secuencialmente DESPUÉS de que monthly terminara, con un delay adicional de 400ms. Es el único endpoint secuencial.

### Endpoints en modo Proyección

| Order | Endpoint | Delay | Notas |
|-------|----------|-------|-------|
| 1 | `GET /plan/versions` + `GET /ops/control-loop/plan-versions` | 0ms (parallel) | Solo al entrar a proyección |
| 2 | `GET /ops/business-slice/omniview-projection` | 600ms debounce | Matriz de proyección |

---

## 2. Análisis de Skeleton / Loading

### Diagnóstico

El skeleton (`loading && heavyQueriesEnabled`, línea 1337) originalmente solo se mostraba mientras la API principal (monthly/weekly/daily/projection) estuviera en vuelo. **NO esperaba trust ni freshness ni coverage.** Esto era correcto.

**Problema encontrado**: Había un `useEffect` (línea 591-597) que ponía `loading=true` inmediatamente al cambiar filtros en modo proyección, ANTES del debounce de 600ms. Esto causaba:

1. Cambiar filtro → skeleton inmediato
2. Esperar 600ms de debounce
3. Iniciar API call (~2934ms)
4. Skeleton desaparece

El skeleton aparecía durante ~3534ms cuando la API real duraba ~2934ms. **600ms extra de skeleton innecesario.**

### Corrección

Se eliminó el `setLoading(true)` prematuro del efecto de proyección. Ahora `loading` solo se activa dentro de `doLoad`/`doLoadProjection` cuando la API realmente está en vuelo.

---

## 3. Detección de Loops y Re-fetch

### useEffect Dependencies — Callback Identity Cascade

**Problema**: `doLoad` y `doLoadProjection` son `useCallback` con dependencias de 8-10 variables de estado cada una. Al cambiar cualquier filtro:

1. `doLoadProjection` cambia de identidad
2. `doLoad` cambia de identidad (depende de `doLoadProjection`)
3. El `useEffect` del debounce (línea 599) re-ejecuta su cleanup porque `doLoad` cambió

Esto provocaba que en cada cambio de filtro se ejecutara: cleanup del effect → nuevo effect → nuevo setTimeout → debounce. Esto es un **cascade de re-creación innecesario** que ralentiza React.

### Corrección

Se introdujo `filterRef` (useRef) que captura todas las variables de filtro en un solo objeto mutable. Ambos callbacks (`doLoadProjection` y `doLoad`) ahora leen de `filterRef.current` en lugar de tener dependencias de estado, resultando en **identidad estable** (`deps=[]`).

### localStorage Persistencia

**Problema**: `persistState` se escribía en localStorage sincrónicamente en CADA cambio de filtro individual. Si el usuario cambia 5 filtros en rápida sucesión, se hacían 5 writes a localStorage.

### Corrección

Se debounceó a 800ms. Solo se escribe después de que el usuario deja de cambiar filtros por 800ms.

---

## 4. Revisión de Componentes — Memoización

### Sub-componentes Inline

13 sub-componentes definidos como `function` a nivel módulo dentro del archivo de 3390 líneas:

- `OperationalOpportunitiesSummary`
- `OperationalContextBar`
- `ProjectionIntegrityBanner`
- `ProjectionContextualOperationalSuggestionsBlock`
- `ProjectionDecisionRecommendationsBlock`
- `ProjectionGlobalStrategicQueueBlock`
- `ProjectionOperationalSuggestionsBlock`
- `ProjectionYtdAlertsBlock`
- `ProjectionYtdSummaryBar`
- `ProjectionContextBar`
- `ReconciliationSummaryBar`
- `PlanWithoutRealSection`
- `UnmappedBadge`

**Problema**: Aunque son funciones a nivel módulo (no se recrean en cada render), React re-renderiza todos los hijos cuando el padre se re-renderiza, a menos que estén memoizados. Estos 13 componentes se re-renderizaban en cada cambio de estado del padre (44 useState).

### Corrección

Todos fueron envueltos en `React.memo()`. Ahora solo se re-renderizan si sus props cambian.

---

## 5. Corrección de Waterfall

### Coverage-summary Secuencial

**Problema**: En `doLoad`, coverage-summary se ejecutaba DESPUÉS de que la API principal terminara, con 400ms de delay adicional:
```
doLoad → API monthly (2934ms) → setRows → delay 400ms → API coverage → setCoverageSummary
```

### Corrección

Coverage-summary ahora se dispara **en paralelo** con la API principal. Ambas requests vuelan simultáneamente, aprovechando el pool de conexiones HTTP del navegador.

---

## 6. Instrumentación de Performance

Se creó `frontend/src/utils/performanceTimer.js` con clase `PerformanceTimer` que permite:

- Marcar fases: `api_wait`, `parse`, `render`, `total_load`
- Medir tiempo hasta primer render visible
- Log condicional (solo en DEV o con `?perf` en URL)

Se instrumentó el componente con:
- `perfLog('api_wait', ms)` — tiempo de API
- `perfLog('proj_api_wait', ms)` — tiempo de API en proyección
- `perfLog('total_load', { apiMs, parseMs, total })` — ciclo completo
- `perfLog('first_render_visible', { ms, rows })` — tiempo hasta tabla visible (post-API, double RAF)

---

## 7. Resumen de Cambios

| Archivo | Cambio | Impacto |
|---------|--------|---------|
| `performanceTimer.js` | **Nuevo** — utilidad de medición | Instrumentación |
| `BusinessSliceOmniviewMatrix.jsx` | `filterRef` — callbacks estables | Elimina cascade de re-creación |
| `BusinessSliceOmniviewMatrix.jsx` | `doLoad` deps `[]` (usa ref) | Estabilidad de useEffect |
| `BusinessSliceOmniviewMatrix.jsx` | `doLoadProjection` deps `[]` (usa ref) | Estabilidad de useEffect |
| `BusinessSliceOmniviewMatrix.jsx` | Coverage en paralelo (antes secuencial) | -400ms mínimo |
| `BusinessSliceOmniviewMatrix.jsx` | Remove `setLoading(true)` prematuro | -600ms de skeleton falso |
| `BusinessSliceOmniviewMatrix.jsx` | 13 componentes → `memo()` | Evita re-renders masivos |
| `BusinessSliceOmniviewMatrix.jsx` | `persistState` debounced 800ms | Reduce writes a localStorage |
| `BusinessSliceOmniviewMatrix.jsx` | `perfLog` instrumentation | Visibilidad de performance |
| `BusinessSliceOmniviewMatrix.jsx` | Render timing (double RAF) | Mide tiempo hasta tabla visible |

---

## 8. Verificación de Build

```bash
npx vite build  # ✓ built in 13.16s — sin errores
```

---

## 9. Métricas Esperadas (Pre/Post)

| Métrica | Antes | Después |
|---------|-------|---------|
| Skeleton visible (falso) | 600ms extra durante debounce | 0ms extra |
| Coverage fetch | Secuencial +400ms tras API | Paralelo con API |
| Re-renders por cambio de filtro | Todos los 13 sub-componentes | Solo los que cambian props |
| localStorage writes | Sincrónico en cada cambio | Debounced 800ms |
| Callback identity | Cambia en cada filtro | Estable (refs) |
| Tiempo hasta render visible | API + secuencial + falso skeleton | API + paralelo (sin skeleton falso) |

---

## 10. Validación Pendiente (Manual)

- [ ] Cambiar filtros no congela UI
- [ ] Monthly/weekly/daily siguen funcionando
- [ ] Projection/evolución siguen funcionando
- [ ] No hay skeleton infinito
- [ ] No hay loops de requests
- [ ] Medir BEFORE real con `?perf` en URL
- [ ] Medir AFTER real con `?perf` en URL
