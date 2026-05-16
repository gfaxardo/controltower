# YEGO Control Tower — Reglas de Visibilidad en UI de Producción

**Versión:** 1.0.0
**Fecha:** 2026-05-15
**Propósito:** Definir qué vistas, tabs, rutas y componentes pueden aparecer en la UI de producción y bajo qué condiciones.

---

## Principio Rector

> **Una feature implementada en código NO equivale a una feature habilitada en UI.**
> Para aparecer en producción debe estar marcada como `productionReady = true` y pertenecer a la fase ACTIVE o READY NEXT del roadmap canónico.

---

## Clasificación de Visibilidad

Toda vista o ruta se clasifica en una de estas categorías:

| Visibilidad | Significado | Aparece en nav? | Accesible por URL? | Build prod? |
|-------------|-------------|-----------------|-------------------|-------------|
| **KEEP_VISIBLE** | Vista validada, funcional, producción | Sí | Sí | Sí |
| **HIDE_FROM_NAV** | Vista en backlog o legacy duplicada | No | Sí (placeholder) | Sí (placeholder) |
| **DEV_ONLY** | Solo para desarrollo/QA técnico | Solo en dev | Solo en dev | No (tree-shaken) |
| **BACKLOG_ONLY** | Motor en BACKLOG, no listo | No | Sí (placeholder) | Sí (placeholder) |
| **NEEDS_VALIDATION** | Requiere verificación antes de mostrar | No | No | Sí (placeholder) |

---

## Qué Puede Aparecer en UI de Producción

Solamente vistas que cumplan **TODAS** estas condiciones:

1. `engine` pertenece a un motor en estado **ACTIVE** o **READY NEXT**.
2. `visibility === KEEP_VISIBLE`.
3. `productionReady === true`.
4. `requiresValidation === false` (o ya fue validada).

### Motores con Vistas Visibles

| Motor | Estado | Vistas visibles |
|-------|--------|----------------|
| Control Foundation | ACTIVE | Performance (Resumen, Plan vs Real, Real diario), Drivers (Supply, Ciclo de vida), Operación (Omniview Matrix, Control Loop, Reportes, LOB Drill, Business Slice, Omniview), Plan (Acciones, Universo, Validación), Diagnósticos |
| Diagnostic Engine | READY NEXT | Drivers (Alertas de conducta, Fuga de flota), Riesgo (Desviación por ventanas) |

---

## Qué NO Puede Aparecer en UI de Producción

### Vistas de motores en BACKLOG

| Vista | Motor | Razón |
|-------|-------|-------|
| Action Engine (Acciones recomendadas) | Action Engine | BACKLOG — requiere Decision Engine cerrado |
| Real vs Proyección | Forecast Engine | BACKLOG — Forecast no está activo |
| Cualquier vista de Suggestion Engine | Suggestion Engine | BACKLOG |
| Cualquier vista de Decision Engine operacional | Decision Engine | BACKLOG |
| Cualquier vista de Learning Engine | Learning Engine | BACKLOG |
| Cualquier vista de AI Copilot | AI Copilot | BACKLOG |
| Cualquier vista de Reachability Engine | Reachability Engine | BACKLOG |

### Vistas legacy duplicadas

| Ruta legacy | Razón |
|-------------|-------|
| `/en-revision/alertas` | Movida a Drivers > Alertas de conducta |
| `/en-revision/flota` | Movida a Drivers > Fuga de flota |
| `/en-revision/real-vs-proyeccion` | Forecast en BACKLOG |

---

## Cómo se Clasifica una Vista Nueva

### Proceso

1. Identificar el **motor arquitectónico** al que pertenece.
2. Verificar el **estado del motor** en [ARCHITECTURE_CANONICAL_ROADMAP.md](./ARCHITECTURE_CANONICAL_ROADMAP.md).
3. Si el motor está en **BACKLOG** → `visibility = HIDE_FROM_NAV` y `productionReady = false`.
4. Si el motor está en **ACTIVE** o **READY NEXT** → evaluar si la vista está funcional.
5. Si la vista es legado de una fase anterior pero cumple función activa → `KEEP_VISIBLE` con `legacyNote` explicativo.
6. Agregar entrada al `CONTROL_TOWER_NAVIGATION_REGISTRY` en [controlTowerNavigationRegistry.js](../../frontend/src/config/controlTowerNavigationRegistry.js).

---

## Relación con Control Foundation

Control Foundation es el **único motor en estado ACTIVE**. Por lo tanto:

- **Todas las vistas KEEP_VISIBLE actuales pertenecen a Control Foundation** (o a Diagnostic Engine en READY NEXT).
- Cualquier vista nueva debe validar que **no introduce lógica de motores superiores** (Forecast, Suggestion, Decision, Action, Learning).
- Ver [ENGINE_BOUNDARIES.md](./ENGINE_BOUNDARIES.md) para los límites de cada motor.

---

## Tratamiento de Vistas Legacy (2A/2B/2C/2C+)

Las vistas con nombres legacy **no se ocultan automáticamente** por ser legacy. Se clasifican según su función real:

| Vista Legacy | Clasificación | Razón |
|-------------|--------------|-------|
| MonthlySplitView (Fase 2A) | KEEP_VISIBLE | Plan vs Real mensual es Control Foundation |
| WeeklyPlanVsRealView (Fase 2B) | KEEP_VISIBLE | Plan vs Real semanal es Control Foundation |
| Phase2BActionsTrackingView (2B) | KEEP_VISIBLE | Accountability operacional (NO es Action Engine) |
| Phase2CAccountabilityView (2C) | KEEP_VISIBLE | Scoreboard/backlog/breaches es accountability |
| LobUniverseView (2C+) | KEEP_VISIBLE | Universo LOB es Control Foundation |
| RealLOBDrillView (2C+) | KEEP_VISIBLE | Drill LOB es Control Foundation |
| RealVsProjectionView (2A) | HIDE_FROM_NAV | Proto-forecast; Forecast Engine en BACKLOG |

---

## Navegación Post-Limpieza (2026-05-15)

### Tabs visibles

```
Performance          Drivers         Riesgo          Operación           Plan
├─ Resumen           ├─ Supply       └─ Desviación   ├─ Omniview Matrix   ├─ Acciones
├─ Plan vs Real      ├─ Ciclo vida     por ventanas  ├─ Control Loop PvR  ├─ Universo
└─ Real (diario)     ├─ Alertas                      ├─ Reportes          └─ Validación
                     │  de conducta                  ├─ Real LOB / Drill
                     └─ Fuga de flota                ├─ Business Slice
                                                     └─ Omniview
                                                                     Diagnósticos
                                                                     └─ System Health
```

### Vistas removidas de navegación

| Antes | Después |
|-------|---------|
| Tab "En revisión" (3 sub-vistas) | Eliminado |
| Real vs Proyección | Oculto (BACKLOG: Forecast) |
| Riesgo > Acciones recomendadas | Oculto (BACKLOG: Action Engine) |
| Alertas de conducta en "En revisión" | Movido a Drivers |
| Fuga de flota en "En revisión" | Movido a Drivers |

---

## Regla de Placeholder

Si un usuario accede manualmente por URL a una vista `HIDE_FROM_NAV` o `BACKLOG_ONLY`, se muestra el componente `BacklogPlaceholder` con el mensaje:

> "Esta vista está en backlog o requiere validación antes de estar disponible en producción."

No se muestran datos parciales ni pantallas rotas.

---

## Referencias Cruzadas

- [ARCHITECTURE_CANONICAL_ROADMAP.md](./ARCHITECTURE_CANONICAL_ROADMAP.md) — Estados de motores.
- [ENGINE_BOUNDARIES.md](./ENGINE_BOUNDARIES.md) — Límites de cada motor.
- [LEGACY_PHASE_TRANSLATION_MAP.md](./LEGACY_PHASE_TRANSLATION_MAP.md) — Mapeo legacy → canónico.
- [ROADMAP_GOVERNANCE_RULES.md](./ROADMAP_GOVERNANCE_RULES.md) — Reglas de gobierno.
- [controlTowerNavigationRegistry.js](../../frontend/src/config/controlTowerNavigationRegistry.js) — Registry de navegación.
