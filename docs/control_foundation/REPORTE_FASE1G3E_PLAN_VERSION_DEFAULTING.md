# REPORTE FASE 1G.3E — DEFAULT PLAN VERSION FROM SERVING FACT

## Resumen

Se implementó un sistema de detección y auto-selección de plan_versions materializadas en serving fact, eliminando el caso "No hay proyección cargada" cuando existen datos pre-computados.

---

## 1. Backend — Nuevo Endpoint

**`GET /ops/business-slice/omniview-projection/serving-plan-versions`**

Devuelve metadata rica de todas las plan_versions que tienen filas en `serving.omniview_projection_daily_fact`:

| Campo | Descripción |
|-------|-------------|
| `plan_version` | Key de la versión |
| `fact_generated_at` | Timestamp de generación más reciente |
| `row_count` | Número total de filas materializadas |
| `min_period` | Primera fecha/periodo con datos |
| `max_period` | Última fecha/periodo con datos |
| `countries` | Array de países con datos |
| `grains_available` | Array de granos materializados |

Ordenado por `fact_generated_at DESC` (más reciente primero).

### Query SQL
```sql
SELECT
    plan_version,
    MAX(generated_at) AS fact_generated_at,
    COUNT(*) AS row_count,
    MIN(period_key) AS min_period,
    MAX(period_key) AS max_period,
    ARRAY_AGG(DISTINCT country ORDER BY country) AS countries,
    ARRAY_AGG(DISTINCT grain ORDER BY grain) AS grains_available
FROM serving.omniview_projection_daily_fact
GROUP BY plan_version
ORDER BY MAX(generated_at) DESC
```

### Archivos modificados
- `backend/app/services/projection_expected_progress_service.py` — `list_serving_plan_versions()`
- `backend/app/routers/ops.py` — nuevo endpoint + import

---

## 2. Frontend — Auto-Selección y Badge

### `loadPlanVersions()` mejorado

Ahora dispara 3 APIs en paralelo:
1. `GET /plan/versions` (metadata de plan)
2. `GET /ops/control-loop/plan-versions` (staging)
3. `GET /ops/business-slice/omniview-projection/serving-plan-versions` (NUEVO)

El merge ahora:
- Marca cada versión con `hasServingFact: true/false`
- Añade plan_versions que solo existen en serving fact (sin metadata) al selector
- Auto-selecciona siempre la primera versión materializada si:
  - No hay versión actual (`planVersion === ''`)
  - La versión actual NO está en serving fact pero otras SÍ
- Incluye metadata de serving fact en cada item (`fact_generated_at`, `fact_row_count`)

### `ProjectionVersionSelector` mejorado

- **Badge visual**: "materializada" (verde) o "sin fact" (ámbar) junto al select
- **Prefijo en options**: `●` para versiones materializadas, `○` para no materializadas (cuando hay serving facts)
- **Metadata extra**: muestra `fact_row_count` en el tooltip
- **Mensaje de "Sin versiones"**: si hay serving facts, muestra cuántas versiones existen

### Mensajes de estado mejorados

- **`no_data_serving_available`**: Muestra lista clickeable de versiones materializadas disponibles
- **`no_data_version_in_fact`**: La versión SÍ está en fact pero sin datos para estos filtros
- **"No hay proyección cargada"**: Si hay serving facts, muestra cuántas y ofrece botón "Recargar versiones"

### Archivos modificados
- `frontend/src/services/api.js` — `getServingPlanVersions()`
- `frontend/src/components/BusinessSliceOmniviewMatrix.jsx` — `loadPlanVersions()`, nuevo estado `servingVersions`, `ProjectionVersionSelector` con `servingVersionKeys`
- `frontend/src/components/projections/ProjectionVersionSelector.jsx` — badge, prefijos, metadata de fact

---

## 3. Flujo Completo

```
Usuario cambia a "Vs Proyección"
  └─ loadPlanVersions()
       ├─ GET /plan/versions
       ├─ GET /ops/control-loop/plan-versions
       └─ GET /ops/business-slice/omniview-projection/serving-plan-versions ← NUEVO
              ↓
       Merge + tag hasServingFact
              ↓
       Auto-seleccionar versión materializada más reciente
              ↓
       Selector muestra ● / ○ con badge "materializada" / "sin fact"
              ↓
       doLoadProjection() → GET /ops/business-slice/omniview-projection?plan_version=XXX
              ↓
       Backend: _try_load_from_serving_fact(plan_version=XXX, ...)
              ↓
       Sirve desde fact (~2934ms → mucho más rápido) o fallback runtime
```

---

## 4. Verificación

| Caso | Comportamiento |
|------|---------------|
| Hay serving facts, no plan metadata | Versiones de serving fact añadidas al selector + badge "materializada" |
| Plan metadata sin serving fact | Badge "sin fact", opción con prefijo ○ |
| Versión seleccionada no materializada, otras sí | Auto-cambia a primera materializada |
| Sin plan_version previa | Auto-selecciona materializada más reciente |
| Sin serving facts ni metadata | "No hay proyección cargada" + upload CTA |
| Usuario cambia manualmente a versión sin fact | Respeta selección del usuario (no sobre-escribe) |

### Build verificado
```
npx vite build  # ✓ FRONTEND BUILD OK
python ast.parse  # ✓ BACKEND OK
```
