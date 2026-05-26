# CLOSED PERIOD SIGNAL AUDIT

**Date**: 2026-05-25
**Mode**: Vs Proyección

---

## SIGNALS CLASSIFICATION

### reliable_closed_period_signal

| Señal | Fuente | Grain | Uso |
|---|---|---|---|
| `projectionMeta.data_freshness.max_data_date` | Proyección API meta | daily/weekly/monthly | Última fecha con data real. Ideal para anchor daily. |
| `week_state = "closed"` | Row-level, weekly/daily rows | weekly, daily | El backend ya clasifica el período como cerrado. |
| `week_state = "future"` | Row-level, weekly/daily rows | weekly, daily | Período en el futuro — ghosted. |
| `comparison_basis = "full_month"` | Row-level | monthly | Mes completo — comparable cerrado. |
| `comparison_basis = "partial_month"` | Row-level | monthly | Mes parcial — tratamiento especial. |

### usable_with_guard

| Señal | Fuente | Guard |
|---|---|---|
| `week_state = "current"` | Row-level (weekly/daily) | Es "current" pero podría ser parcial o cerrado. Cruce con `max_data_date`. |
| `freshnessInfo.derived_max_date` | API separada `getDataFreshnessGlobal` | Fallback si `projectionMeta.data_freshness` no existe. |
| `week_state` en monthly | Solo via serving fact fallback | No garantizado en runtime path. |

### missing (para proyección)

| Señal | Nota |
|---|---|
| `period_states` (OPEN/CLOSED/PARTIAL) | Solo en matrix regular, no en proyección. |
| `sliceMaxTripDate` | Solo en matrix regular, no en proyección. |
| `period_closure_registry` | Existe en DB pero no se expone en API de proyección. |

### unsafe

| Señal | Nota |
|---|---|
| `is_partial_period` en momentum drill | Hardcoded `False`. Ignorar. |

---

## ESTRATEGIA DE ANCHOR

### Daily:
1. Leer `projectionMeta?.data_freshness?.max_data_date`
2. Si existe: anchor = último día con data ≤ `max_data_date`
3. Si no existe: anchor = ayer calendario (safe fallback)
4. "Hoy" calendario SIEMPRE es partial si no hay data cerrada para hoy

### Weekly:
1. Leer `week_state` de cada período semanal (viene del backend)
2. Anchor = última semana con `week_state = "closed"`
3. Si ninguna cerrada: anchor = penúltima semana del rango
4. Semana actual con `week_state = "current"` → partial badge

### Monthly:
1. Leer `comparison_basis` de cada período mensual
2. Anchor = último mes con `comparison_basis = "full_month"` y `week_state !== "future"`
3. Si no disponible: último mes con data (por `actual != null`)
4. Mes actual → partial badge si `comparison_basis = "partial_month"`
