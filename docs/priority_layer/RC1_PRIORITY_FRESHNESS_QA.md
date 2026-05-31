# RC-1 PRIORITY FRESHNESS QA

**Fecha**: 2026-05-30
**Motor**: Control Foundation — Priority Layer
**Archivos**:
- `frontend/src/utils/operationalPriorityEngine.js`
- `frontend/src/components/omniview/priority/OperationalPriorityLayer.jsx`
- `frontend/src/utils/comparableDeltaDisplay.js`

---

## 1. Exclusiones Auditadas

### 1.1 Exclusión de Freshness Inválida

| Check | Línea | Estado |
|-------|-------|--------|
| `d.week_state === 'future'` → excluido | `operationalPriorityEngine.js:69` | ✅ |
| `d.attainment_pct == null && d.value == null` → excluido | Línea 68 | ✅ |
| `!comp.hasComparable` → excluido | Línea 73 | ✅ (si no hay periodPop válido, no se incluye) |
| `deltaPct == null \|\| !Number.isFinite(deltaPct)` → excluido | Línea 85 | ✅ |
| `!Number.isFinite(deltaAbs)` → excluido | Línea 86 | ✅ |
| `severity === UNKNOWN` → excluido | Línea 87 | ✅ |
| `severity === NORMAL && abs(deltaPct) < 3` → excluido | Línea 88 | ✅ (filtra ruido) |

### 1.2 Verificación de `buildComparableDelta` (canónico)

```javascript
// comparableDeltaDisplay.js:196-258
export function buildComparableDelta(delta, grain) {
  if (!delta) return empty
  const popObj = delta.periodPop
  if (!popObj || typeof popObj !== 'object') return empty   // ← sin periodPop
  const pct = Number(popObj.pct)
  if (!Number.isFinite(pct)) return empty                     // ← NaN/Infinity excluido
  // ...
}
```

| Check | Estado |
|-------|--------|
| Sin periodPop → `hasComparable: false` | ✅ |
| pct NaN/Infinity → `hasComparable: false` | ✅ |
| Usa `periodPop` del backend, NO attainment/gap | ✅ |
| NO usa plan gap como delta | ✅ |
| NO usa YTD | ✅ |

### 1.3 Exclusión de KPIs No Proyectables en Priority

```javascript
// operationalPriorityEngine.js:61-66
for (const pk of allPeriods) {
  const periodDeltas = deltasMap.get(pk)
  if (!periodDeltas) continue
  const d = periodDeltas[focusedKpi]
  if (!d || !d.isProjection) continue  // ← excluye avg_ticket, trips_per_driver
}
```

`PROJECTION_KPIS = ['trips_completed', 'revenue_yego_net', 'active_drivers']`

| KPI | `isProjection` | Incluido en Priority | Contrato `allowed_for_priority_scoring` |
|-----|---------------|---------------------|----------------------------------------|
| trips_completed | ✅ true | ✅ | `true` |
| revenue_yego_net | ✅ true | ✅ | `true` |
| active_drivers | ✅ true | ✅ | `true` |
| avg_ticket | ❌ false | ❌ | `false` |
| trips_per_driver | ❌ false | ❌ | `false` |

Alineado con `KPI_CONTRACT_FALLBACK`. ✅

### 1.4 Exclusión de kpiNoData

El engine no verifica `kpiNoData` explícitamente. Sin embargo:
- Si un KPI no tiene data real, `periodPop` será null/inválido para todos los períodos
- `buildComparableDelta` retornará `hasComparable: false`
- El engine excluye `!comp.hasComparable`
- **Implicitamente cubierto.** ✅

---

## 2. Señales Usadas (Conforme a RC1_SIGNAL_INVENTORY.md)

| Señal | Fuente | Uso en engine | Conforme |
|-------|--------|---------------|----------|
| DoD/WoW/MoM pct | `periodPop.pct` → `comp.pct` | Scoring | ✅ |
| DoD/WoW/MoM abs | `periodPop.abs` → `comp.abs` | Scoring boost | ✅ |
| Direction | `comp.direction` | Split críticas/oportunidades | ✅ |
| Severity | `comp.severity` | Clasificación + exclusión ruido | ✅ |
| KPI focus | `focusedKpi` | Scope | ✅ |
| Grain | `grain` | Comparable type | ✅ |
| Country/City/Slice | `projMatrix.cities` | Label | ✅ |
| Actual value | `d.value` | Display | ✅ |
| Previous value | `periodPop.prev_real` | Contexto | ✅ |

Señales bloqueadas correctamente:
- Attainment vs Expected → no usado ✅
- Gap vs Plan → no usado ✅
- YTD → no usado ✅
- Curve Confidence → no usado ✅
- Volume Weighting → no usado ✅

---

## 3. Fórmula de Scoring

```javascript
const absScore = absPct * (deltaAbs != null ? Math.log10(Math.abs(deltaAbs) + 1) : 1)
const priorityScore = Math.round(absScore * 100) / 100
```

- `absPct` de `periodPop.pct` (no attainment, no gap) ✅
- `deltaAbs` boost logarítmico ✅
- Round a 2 decimales ✅

---

## 4. Operaciones en OperationalPriorityLayer.jsx

| Check | Línea | Estado |
|-------|-------|--------|
| `useMemo` correcto (deps: projMatrix, focusedKpi, grain) | 38-41 | ✅ |
| Top 3 deteriorations | engine L141 | ✅ |
| Top 3 improvements | engine L142 | ✅ |
| Sin fetch adicional | — | ✅ |
| Label KPI en español | 23-29 | ✅ |
| onClick → navegación a celda | 46-52 | ✅ |

---

## 5. Hallazgos

### OK

| ID | Descripción |
|----|-------------|
| PRI-OK-1 | Todas las exclusiones de RC1_SIGNAL_INVENTORY.md implementadas |
| PRI-OK-2 | NaN/Infinity excluidos en buildComparableDelta + double-check en engine |
| PRI-OK-3 | Periodos future excluidos |
| PRI-OK-4 | Solo KPIs proyectables (trips, revenue, drivers) pasan el filtro `isProjection` |
| PRI-OK-5 | Alineación completa con KPI contract (`allowed_for_priority_scoring`) |

### Observaciones (no bloqueantes)

| ID | Descripción | Severidad |
|----|-------------|-----------|
| PRI-OBS-1 | Priority Layer no recibe `kpiFreshness` ni `closedPeriodAnchor`. No puede excluir períodos partial/inválidos por freshness. Mitigado: los períodos sin data → sin periodPop → excluidos implícitamente. | LOW |
| PRI-OBS-2 | `freshnessStatus` en prioridad usa `d.signal || 'no_data'` (campo de attainment, no de freshness real). Semántica mixta. | LOW |
| PRI-OBS-3 | Priority Layer no muestra advertencia cuando el KPI seleccionado tiene mismatch de freshness. | LOW |

---

## 6. Veredicto

**GO** — Priority Layer limpia. Sin señales inválidas. Exclusiones correctas. Sin uso de attainment/gap/YTD como delta. Sin NaN/Infinity. Alineada con contrato KPI.

