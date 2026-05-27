# Fase 1.1 — Omniview Perspective Engine

**Fecha:** 2026-05-26
**Estado:** Completado
**Fase anterior:** Fase 1.0.2 — Unified Projection Template
**Siguiente fase:** Fase 1.2 — Ownership Momentum & Rankings

======================================================================
RESUMEN
======================================================================

Se agregó un selector de perspectiva en Omniview que permite alternar entre:

1. **Operational View** — la vista existente (Evolución + Vs Proyección), intacta.
2. **Ownership View** — consume el endpoint ownership-serving y muestra
   métricas plan vs real agrupadas por Jefe Producto.

La vista Operational se mantiene exactamente como estaba. La vista Ownership
es nueva y solo se activa en modo Vs Proyección (requiere plan_version).

======================================================================
ARQUITECTURA
======================================================================

```
Omniview Matrix
  │
  ├─ Modo: Evolución
  │   └─ Matriz operational (sin cambios)
  │
  └─ Modo: Vs Proyección
      ├─ Perspectiva: Operational
      │   └─ Matriz de proyección existente (sin cambios)
      │
      └─ Perspectiva: Ownership  ← NUEVO (Fase 1.1)
          └─ GET /ops/ownership-serving/monthly?plan_version_key=X
              └─ OwnershipServingView
                  ├─ Cards por Jefe Producto (métricas agregadas)
                  └─ Tabla jerárquica: Jefe → LOB → País/Ciudad
```

======================================================================
IMPLEMENTACIÓN
======================================================================

### Archivos creados

| Archivo | Descripción |
|---------|-------------|
| `src/components/ownership/OwnershipServingView.jsx` | Componente de vista ownership |
| `docs/ownership/FASE_1_1_OMNIVIEW_PERSPECTIVE_ENGINE.md` | Esta documentación |

### Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `src/services/api.js` | Agregado `getOwnershipServingMonthly()` |
| `src/components/BusinessSliceOmniviewMatrix.jsx` | Import + state + selector + rendering condicional |

### Cambios en detalle

1. **`api.js`**: Nueva función `getOwnershipServingMonthly(params)`
   llama a `GET /ops/ownership-serving/monthly`.

2. **`BusinessSliceOmniviewMatrix.jsx`**:
   - `perspective` state (`'operational'` | `'ownership'`)
   - `ownershipRows`, `ownershipByOwner`, `ownershipLoading`, `ownershipError` states
   - `ownershipRequestIdRef` para race protection
   - `useEffect` que carga ownership cuando perspective='ownership' y planVersion cambia
   - Selector UI: botones "Operational" / "Ownership" visibles solo en modo Vs Proyección
   - Render condicional: `OwnershipServingView` cuando perspective='ownership'

3. **`OwnershipServingView.jsx`**: Componente con:
   - Loading state (spinner)
   - Error state (mensaje + volver a Operational)
   - Empty state (no hay ownership)
   - Cards resumen por Jefe Producto
   - Tabla jerárquica: Jefe → LOB → País/Ciudad
   - Métricas: proj_trips, real_trips, proj_revenue, real_revenue, exec%, momentum_status

======================================================================
COMPORTAMIENTO
======================================================================

### Operational View
- Sin cambios. El modo Evolución sigue viendo la matriz Real vs Real.
- El modo Vs Proyección (perspective=operational) sigue viendo la matriz de attainment.
- Todos los filtros, zoom, focus mode, export, inspector siguen funcionando.

### Ownership View
- Se activa al seleccionar "Ownership" en el selector de perspectiva.
- Requiere modo Vs Proyección con plan_version seleccionada.
- Carga datos del endpoint `GET /ops/ownership-serving/monthly`.
- Muestra datos agrupados por Jefe Producto → LOB → País/Ciudad.
- Si no hay ownership, muestra empty state.
- Si falla la carga, muestra error state.
- No recalcula nada en frontend (datos pre-servidos desde el backend).

### Edge cases
- Cambio de perspectiva en modo Evolución: no disponible (ownership necesita plan_version).
- Cambio de plan_version con ownership activo: recarga automáticamente.
- Error de carga: persiste en Operational, el usuario puede volver.
- Sin owners: empty state claro.

======================================================================
REGLAS RESPETADAS
======================================================================

- [x] NO rankings
- [x] NO leaderboards
- [x] NO accountability cards
- [x] NO heatmaps
- [x] NO gamificación
- [x] NO AI
- [x] NO forecast ownership
- [x] NO reachability ownership
- [x] NO frontend heavy grouping (datos pre-servidos)
- [x] NO breaking Operational View
- [x] NO freeze / scroll roto / sticky header roto

======================================================================
BUILD RESULT
======================================================================

```
npm run build → OK (4.83s, 832 modules)
```

Sin errores. Sin warnings nuevos (solo el chunk size warning existente por ~1.9MB).

======================================================================
QA CHECKS
======================================================================

| Check | Estado |
|-------|--------|
| Selector visible (solo en Vs Proyección) | PASS |
| Operational default | PASS |
| Operational View sin cambios | PASS |
| Ownership llama endpoint correcto | PASS |
| Ownership respeta plan_version_key | PASS |
| Ownership muestra 3 owners (si hay datos) | PASS |
| Loading state controlado | PASS |
| Error state controlado | PASS |
| Empty state controlado | PASS |
| No frontend heavy grouping | PASS |
| Build pasa | PASS |
| UI no se congela | PASS |

======================================================================
RIESGOS
======================================================================

1. **Ownership sin datos**: Si `projection_ownership` está vacío o no
   sincronizado con la plan_version seleccionada, Ownership muestra
   empty state. No rompe nada.

2. **Performance**: El endpoint ownership-serving puede ser lento (~1s)
   para grandes volúmenes. La UI muestra loading state mientras carga.

3. **Perspectiva en Evolución**: No disponible. El usuario debe cambiar
   a Vs Proyección primero. Se podría mejorar en fases futuras.

======================================================================
SIGUIENTE FASE
======================================================================

**Fase 1.2 — Ownership Momentum & Rankings** (solo si se requiere):
- Momentum drill por Jefe Producto
- Comparativas inter-owner
- Alertas de desviación por owner
- SIN leaderboards ni gamificación todavía
