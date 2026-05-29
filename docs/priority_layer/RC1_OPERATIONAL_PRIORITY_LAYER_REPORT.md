# RC-1 Operational Priority Layer Report

## Fecha: 2026-05-29
## Motor: Control Foundation — Priority Layer
## Fase: RC-1

---

## 1. Estado: **GO**

RC-1 Operational Priority Layer implementado y funcional. Build limpio (11.63s). Sin nuevas API calls. Sin AI. Sin recomendaciones.

---

## 2. Señales Usadas

| Señal | Fuente | Uso |
|-------|--------|-----|
| DoD/WoW/MoM pct | `periodPop.pct` en `computeProjectionDeltas` | Scoring + display |
| DoD/WoW/MoM abs | `periodPop.abs` | Scoring boost |
| Severity | `buildComparableDelta()` → `resolveSeverityLevel()` | Clasificación |
| Direction | `buildComparableDelta()` → `resolveDirection()` | Split críticas/oportunidades |
| KPI focus | `focusedKpi` | Scope del engine |
| Grain | `grain` | Comparable type |
| Country/City/Slice | `projMatrix.cities` | Label display |
| Actual value | `delta.value` | Display en prioridad |
| Previous value | `periodPop.prev_real` | Contexto |

---

## 3. Fórmula Scoring

```
priorityScore = abs(deltaPct) * log10(abs(deltaAbs) + 1)
```

- Deteriorations: `direction === DOWN` → sorted by priorityScore DESC
- Improvements: `direction === UP` → sorted by priorityScore DESC
- Top 3 de cada categoría

### Excluidos
- `severity === NORMAL` AND `abs(deltaPct) < 3%` (ruido)
- `severity === UNKNOWN` (sin datos)
- `week_state === 'future'` (período futuro)
- Sin comparable delta (`!comp.hasComparable`)
- NaN / Infinity

---

## 4. Señales Excluidas (conservadas para RC-2+)

| Señal | Razón |
|-------|-------|
| Attainment vs Expected | Ya visible en celda. No es delta comparable. |
| Gap vs Full Month | Contexto mensual. Fuera de scope RC-1. |
| YTD Summary | Scope más amplio que Priority inmediata. |
| Curve Confidence | Técnico. No accionable en 2s. |
| Volume Weighting | Slices pequeños pueden tener variación% grande con volumen bajo. |

---

## 5. Performance

| Métrica | Resultado |
|----------|-----------|
| Memo | `useMemo` en `computeOperationalPriorities` — solo recalcula con `projMatrix`, `focusedKpi`, `grain` |
| Sin fetch adicional | Derivado 100% de `displayProjMatrix` en memoria |
| Sin loops infinitos | Dependencias declaradas. Sin recursion. |
| Sin rerender storm | Componente usa `memo` implícito via `useMemo`. |
| Build time | 11.63s (sin overhead adicional significativo) |
| Build size | 2089 KB (gzip 577 KB) — +11 KB vs CF-H1 |

---

## 6. Archivos Modificados

| Archivo | Tipo | Cambio |
|---------|------|--------|
| `frontend/src/utils/operationalPriorityEngine.js` | **Nuevo** | Engine: scoring, sorting, top-N extraction |
| `frontend/src/components/omniview/priority/OperationalPriorityLayer.jsx` | **Nuevo** | UI: compact panel con críticas + oportunidades |
| `frontend/src/components/BusinessSliceOmniviewMatrix.jsx` | Modificado | Import + render de OperationalPriorityLayer |
| `docs/priority_layer/RC1_SIGNAL_INVENTORY.md` | **Nuevo** | Auditoría de señales |
| `docs/priority_layer/RC1_OPERATIONAL_PRIORITY_LAYER_REPORT.md` | **Nuevo** | Este reporte |

---

## 7. Evidencia Build

```
✓ built in 11.63s
dist/index.html           0.49 kB │ gzip: 0.32 kB
dist/assets/index-Czf0*.css  99.60 kB │ gzip: 16.73 kB
dist/assets/index-C1e4*.js 2089.07 kB │ gzip: 576.68 kB
```

0 errors. 0 warnings (solo chunk size warning existente).

---

## 8. Riesgos Pendientes

| Riesgo | Severidad | Mitigación |
|--------|-----------|------------|
| Prioridades sobre slices con volumen bajo | LOW | Backlog RC-2: weight by volume (trips) |
| Sprint visual si hay 100+ slices | LOW | Top-N solo 3 + 3. No scroll infinito. |
| Comparables ausentes en periodos partiales | LOW | Engine ya excluye cells sin comparable. |
| Severity colors heredados de momentum emphasis | LOW | Mismo sistema visual que la matriz. Consistencia. |

---

## 9. Ubicación en UI

```
┌─────────────────────────────────────────────┐
│ Command Header (grain, filtros, KPI focus) │
├─────────────────────────────────────────────┤
│ Projection Context Bar                      │
│ "Data al 2026-05-29" · Plan: ruta27        │
├─────────────────────────────────────────────┤
│ ★ Operational Priority Layer (RC-1)        │
│                                             │
│ CRÍTICAS           OPORTUNIDADES           │
│ ▼ 21% WoW Lima     ▲ 18% WoW Trujillo      │
│ ▼ 14% DoD Arequipa ▲ 11% DoD Medellín      │
│ ▼  8% MoM Cali     ▲  7% WoW Bogotá        │
├─────────────────────────────────────────────┤
│ Omniview Matrix (Vs Proyección)             │
│                                             │
│          [tabla principal]                   │
│                                             │
└─────────────────────────────────────────────┘
```

---

## 10. Definición de Éxito

- [x] Top 3 críticas visibles en proyección
- [x] Top 3 oportunidades visibles en proyección
- [x] Sin IA
- [x] Sin recomendaciones
- [x] Sin forecast
- [x] Sin runtime pesado (derivado de datos en memoria)
- [x] Build PASS
- [x] La matriz sigue siendo protagonista
- [x] Click en prioridad → selecciona celda en matriz
