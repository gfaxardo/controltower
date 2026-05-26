# PROJECTION CELL FIELD SEPARATION AUDIT

**Date**: 2026-05-25
**Mode**: Vs Proyección
**Source**: `frontend/src/utils/projectionCellDisplayModel.js`

---

## 1. FIELD INVENTORY — `buildProjectionCellDisplay()` RETURN

| # | Field | Source | Role | Classification |
|---|---|---|---|---|
| 1 | `realStr` | `delta.value` → `fmtValue()` | Ejecución real | ✅ CORRECTO — L1 visual |
| 2 | `deltaArrow` | Derived from `primaryDirection` | Flecha ▲/▼ para delta | ✅ CORRECTO — L2 visual |
| 3 | `deltaPctStr` | `delta.periodPop.pct` | Porcentaje de cambio DoD/WoW/MoM | ✅ CORRECTO — L2 visual |
| 4 | `deltaLabel` | `delta.periodPopLabel` ⎮⎮ `deriveMomentumLabel(grain)` | Etiqueta DoD/WoW/MoM | ⚠️ AMBIGUO — backend puede sobrescribir con label no estándar |
| 5 | `deltaColor` | `getMomentumSeverityColor(pct)` | Color del delta por severidad | ✅ CORRECTO |
| 6 | `deltaBold` | Math.abs(pct) thresholds | Intensidad tipográfica | ✅ CORRECTO |
| 7 | `comparableLabel` | `comparableContextLabel(grain)` | "vs domingo comparable" | ❌ AMBIGUO — texto vago, no comunica DoD/WoW/MoM claramente |
| 8 | `attainmentStr` | `delta.attainment_pct` → `fmtAttainment()` | Porcentaje de avance vs plan | ⚠️ MEZCLADO — aparece en celda junto al delta como texto secundario |
| 9 | `planStr` | `delta.projected_total` → `fmtValue()` | Valor del plan mensual | ⚠️ MEZCLADO — solo visible en fallback, pero confunde |
| 10 | `statusText` | `weekState` / null | "Pendiente" / "Sin ejecución" | ✅ CORRECTO — status label |
| 11 | `hasReal` | `delta.value > 0` | Booleano de ejecución | ✅ CORRECTO |
| 12 | `hasPlan` | `delta.projected_total > 0` | Booleano de plan | ✅ CORRECTO |
| 13 | `hasNegActual` | `delta.value < 0` | Booleano de valor negativo | ✅ CORRECTO |
| 14 | `isMomentum` | `hasMomentumData` | Hay delta comparable | ✅ CORRECTO |
| 15 | `isPlanFallback` | `isProjection && hasPlan && !hasMomentumData` | Usar plan como fallback | ❌ MEZCLADO — attainment NO es delta comparable |
| 16 | `isFuture` | `weekState === 'future'` | Período futuro | ✅ CORRECTO |
| 17 | `hasMomentumData` | `Number.isFinite(popValue)` | El backend mandó periodPop | ✅ CORRECTO |
| 18 | `severity` | `getMomentumSeverityColor()` | Objeto de severidad | ✅ CORRECTO |
| 19 | `severityBg` | `getMomentumSeverityBg()` | Fondo por severidad | ✅ CORRECTO |
| 20 | `weekState` | `delta.week_state` | Estado de semana | ✅ CORRECTO |

---

## 2. MISSING FIELDS

| Field | Needed? | Why |
|---|---|---|
| `comparableType` | ✅ CRÍTICO | Tipo explícito: `"dod_same_weekday"` / `"wow"` / `"mom"` |
| `comparableAbs` | ✅ ALTO | Valor absoluto del cambio |
| `comparableDisplay` | ✅ ALTO | String formateado: `"↓ -21.6% DoD"` |
| `comparableDirection` | ✅ ALTO | Dirección explícita: `"up"` / `"down"` / `"flat"` |
| `hasComparable` | ✅ CRÍTICO | Booleano claro: ¿hay delta comparable o no? |
| `ytdValue` | ⚠️ MEDIO | Para tooltip/drill, no para celda |
| `gapToPlanPct` | ⚠️ BAJO | Para tooltip/drill contextual |

---

## 3. DATA FLOW TRACE

```
Backend cell.raw.period_over_period
  ↓
  {
    kind: "daily_same_weekday" | "weekly_partial" | "monthly" | null,
    label: "DoD" | "WoW" | "MoM" | "Sequential" | null,
    comparable: "2026-05-18" | "2026-W20-Mon" | "2026-04-01",
    metrics: {
      trips_completed: { abs: -2345, pct: -21.6, basis: "...", cur_real: 8523, prev_real: 10868 },
      revenue_yego_net: { abs: 1200, pct: 5.3, ... },
      ...
    }
  }
  ↓
computeProjectionDeltas() → delta.periodPop = metrics[key]
  ↓
buildProjectionCellDisplay(delta, grain, kpiKey)
  ↓
  periodPopObj = delta.periodPop  →  popValue = periodPopObj.pct
  ↓
  primaryDeltaPct = popValue  (DoD/WoW/MoM %)
  primaryDirection = up/down/neutral
  primaryDeltaLabel = delta.periodPopLabel || deriveMomentumLabel(grain)
  ↓
  returns { deltaArrow, deltaPctStr, deltaLabel, deltaColor, deltaBold, ... }
```

### PROBLEMAS DETECTADOS EN EL DATA FLOW

1. **`derivemomentumLabel` es frágil**: Deriva DoD/WoW/MoM del grain actual, NO del `kind` que manda el backend. Si el backend manda `kind: "daily_same_weekday"` pero el grain es `weekly`, la label dirá "WoW" incorrectamente.

2. **`periodPopLabel` del backend puede ser cualquier cosa**: No hay validación. Podría ser "Sequential", "vPlan", o null.

3. **El backend envía `kind` pero NO se usa**: `periodPopKind` está disponible en `delta` (`projectionMatrixUtils.js:614`) pero NO se lee en `buildProjectionCellDisplay`. Es la fuente de verdad para saber si es dod/wow/mom.

4. **`comparable` (fecha del período comparado) disponible pero NO usado**: `periodPopComparable` permitiría tooltips ricos ("vs 18 MAY 2026") pero se ignora.

5. **Fallback `isPlanFallback` mezcla attainment con delta**: Cuando no hay momentum data, el attainment se muestra en el MISMO espacio visual que el delta. Esto es confuso: el attainment es plan vs real, NO es delta comparable.

---

## 4. RECOMMENDATION

Crear `comparableDeltaDisplay.js` como engine independiente que:

1. Lea `periodPopKind` del backend como fuente de verdad para el tipo
2. Derive tipo del grain SOLO si `periodPopKind` es null
3. Exponga `type`, `label`, `direction`, `pct`, `abs`, `display`, `severity` de forma canónica
4. Separe completamente attainment (plan) de delta (DoD/WoW/MoM)
5. NO use attainment como fallback visual — si no hay momentum, mostrar "—" en la línea delta y relegar attainment a tooltip o línea terciaria

Actualizar `buildProjectionCellDisplay` para consumir este nuevo engine y eliminar `isPlanFallback` como sustituto visual de delta.

---

## 5. CLASSIFICATION SUMMARY

| Total fields | 20 |
|---|---|
| ✅ Correcto | 12 |
| ⚠️ Ambiguo | 4 |
| ❌ Mezclado | 2 |
| 🔴 Faltante (crítico) | 2 |
