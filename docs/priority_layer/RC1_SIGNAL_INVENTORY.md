# RC-1 Signal Inventory

## Fecha: 2026-05-29

---

## Señales disponibles en Omniview Vs Proyección

### Fuente `displayProjMatrix` (datos ya en memoria)

| Señal | Fuente | Campo | Clasificación |
|-------|--------|-------|---------------|
| DoD (Day over Day) | `delta.periodPop` → misma día semana anterior | `pct`, `abs`, `cur_real`, `prev_real` | **usable_now** |
| WoW (Week over Week) | `delta.periodPop` → misma semana anterior | `pct`, `abs` | **usable_now** |
| MoM (Month over Month) | `delta.periodPop` → mismo mes año anterior | `pct`, `abs` | **usable_now** |
| Attainment vs Expected | `delta.attainment_pct` | %, NUNCA negativo | usable_now |
| Gap vs Plan | `delta.gap_to_expected` | abs | future_phase |
| Gap vs Full Month | `delta.gap_to_full` | abs | future_phase |
| Completion % | `delta.completion_pct` | % del mes | future_phase |
| Signal | `delta.signal` | green/warning/danger/no_data | usable_now |
| Severity | via `buildComparableDelta()` | critical/elevated/warning/normal | **usable_now** |
| Curve Confidence | `delta.curve_confidence` | high/medium/low/fallback | future_phase |
| Partial Week Flag | `delta.week_state` | partial/current/closed/future | usable_now (exclusion) |

### Fuente `projectionMeta` (meta del endpoint)

| Señal | Campo | Clasificación |
|-------|-------|---------------|
| Freshness Global | `data_freshness.max_data_date` | usable_now |
| Freshness Per-KPI | `kpi_freshness[KPI].max_data_date` | **usable_now** |
| Integrity Status | `integrity_status` | usable_now |
| YTD Summary | `ytd_summary` | future_phase |

### Fuente `projMatrix` (estructura de la matriz)

| Señal | Campo | Clasificación |
|-------|-------|---------------|
| KPI Seleccionado | `focusedKpi` | **usable_now** |
| Grain | `grain` (daily/weekly/monthly) | **usable_now** |
| Country | `cityData.country` | **usable_now** |
| City | `cityData.city` | **usable_now** |
| Business Slice | `lineData.business_slice_name` | **usable_now** |
| Period Key | `pk` (YYYY-MM-DD) | **usable_now** |
| Period Label | formatted from pk + grain | **usable_now** |
| Volume (trips) | `lineData.periods.pk.metrics.trips_completed` | future_phase |

---

## Clasificación

### usable_now (RC-1)
- DoD/WoW/MoM via `periodPop` (pct + abs)
- Severity level (critical >30%, elevated >15%, warning >5%)
- Direction (up/down)
- KPI focus
- Country / City / Slice
- Period label
- Freshness per-KPI
- Actual value (fmtValue)
- Previous value (prev_real)

### future_phase (RC-2+)
- Attainment vs Expected (ya visible en celda)
- Gap vs Full Month (necesita contexto mensual)
- YTD Summary (scope más amplio)
- Curve confidence (técnico)
- Volume weighting (deterioros en slices pequeños)

### blocked (nunca usar en priority)
- Datos de periodos futuros (`week_state === 'future'`)
- Celdas sin comparable (`!comp.hasComparable`)
- NaN / Infinity
- KPIs no proyectables para priority (avg_ticket si no está en PROJECTION_KPIS)

---

## Fórmula de Scoring (RC-1)

```
priorityScore = abs(deltaPct) * log10(abs(deltaAbs) + 1)
```

Donde:
- `deltaPct` = % change (DoD/WoW/MoM) del `periodPop`
- `deltaAbs` = absolute change del `periodPop`
- Si `deltaAbs` no existe o es 0: `priorityScore = abs(deltaPct)`

Exclusiones:
- `severity === NORMAL` AND `abs(deltaPct) < 3` → excluido (ruido)
- `severity === UNKNOWN` → excluido
- `week_state === 'future'` → excluido
- Sin comparable (`!comp.hasComparable`) → excluido
- NaN/Infinity → excluido
