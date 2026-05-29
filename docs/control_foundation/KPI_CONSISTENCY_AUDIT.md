# KPI Consistency Audit — Daily vs Weekly vs Monthly

## Fecha: 2026-05-29
## Scope: All Omniview KPIs across grains

---

## trips_completed

| Aspect | Daily | Weekly | Monthly | Consistent? |
|--------|-------|--------|---------|-------------|
| Fórmula | COUNT(completed) per day | SUM(daily trips) | COUNT(completed) per month | YES |
| Freshness | MAX(trip_date) | same | MAX(month) | YES |
| SUM(weekly) = monthly? | N/A | YES (additive) | N/A | YES |
| SUM(daily_in_month) = monthly? | YES | N/A | N/A | YES |

**Veredict**: PASS — Totalmente consistente. Additive puro.

---

## revenue_yego_net

| Aspect | Daily | Weekly | Monthly | Consistent? |
|--------|-------|--------|---------|-------------|
| Fórmula | SUM(revenue) per day | SUM(daily revenue) | SUM(revenue) per month | YES |
| Freshness | Same as trips | Same as trips | Same as trips | YES |
| SUM(weekly) = monthly? | N/A | YES + conservation adjustment | N/A | YES |
| SUM(daily_in_month) = monthly? | YES | N/A | N/A | YES |

**Nota**: La projection weekly aplica conservación (conservation adjustment) para que SUM(weekly projected) = monthly plan. Para real, el SUM ya es correcto.

**Veredict**: PASS — Totalmente consistente.

---

## active_drivers

| Aspect | Daily | Weekly | Monthly | Consistent? |
|--------|-------|--------|---------|-------------|
| Fórmula | COUNT(DISTINCT driver_id) per day | **SUM(daily distincts)** | COUNT(DISTINCT driver_id) per month | **NO** |
| Freshness | MAX(trip_date WHERE active_drivers > 0) | Same (derived from day fact) | MAX(month) | YES |
| SUM(weekly) = monthly? | N/A | **NO** (SUM proxy != distinct) | N/A | **NO** |
| SUM(daily_in_month) = monthly? | **NO** (suma de distinct diarios != distinct mensual) | N/A | N/A | **NO** |

**Veredict**: FAIL in weekly grain. Daily consistent with itself, monthly consistent with itself. But cross-grain:
- SUM(daily) ≠ monthly → expected for distinct counts
- SUM(weekly proxy) ≠ monthly → by construction (incorrect weekly formula)
- SUM(daily) ≠ weekly canonical → if weekly were correct, would match SUM(daily_in_week) only if all drivers appear every day

---

## avg_ticket

| Aspect | Daily | Weekly | Monthly | Consistent? |
|--------|-------|--------|---------|-------------|
| Fórmula | AVG(ticket) per day | Weighted AVG of daily AVGs | AVG(ticket) per month | YES (semantically equivalent) |
| Recomputation | N/A | SUM(ticket_sum) / SUM(ticket_count) | Direct AVG | YES |
| Freshness | Same as trips | Same as trips | Same as trips | YES |

**Veredict**: PASS — Ratio recomputed correctly at each grain level.

---

## trips_per_driver

| Aspect | Daily | Weekly | Monthly | Consistent? |
|--------|-------|--------|---------|-------------|
| Fórmula | trips / active_drivers | trips / active_drivers (**weekly denominator inherits SUM proxy**) | trips / active_drivers | **NO (weekly only)** |
| Freshness | Derived from parent KPIs | Derived | Derived | YES |

**Veredict**: FAIL in weekly grain (inherits active_drivers SUM proxy). Daily and monthly correct.

---

## Summary Matrix

| KPI | Daily Correct? | Weekly Correct? | Monthly Correct? | Cross-Grain Consistent? |
|-----|---------------|-----------------|-------------------|------------------------|
| trips_completed | YES | YES | YES | YES |
| revenue_yego_net | YES | YES | YES | YES |
| active_drivers | YES | **NO** | YES | **NO** |
| avg_ticket | YES | YES | YES | YES |
| trips_per_driver | YES | **NO** | YES | **NO** |

---

## Conclusion

**2 de 5 KPIs tienen inconsistencia en weekly grain**: `active_drivers` y `trips_per_driver`.

La raíz es una sola: `_WEEK_ROLLUP_FROM_DAY_FACT` usa `SUM(daily_counts)` para active_drivers en lugar de `COUNT(DISTINCT driver_id)`.

Corregir active_drivers weekly resuelve ambos KPIs (trips_per_driver se corrige automáticamente al tener el denominador correcto).
