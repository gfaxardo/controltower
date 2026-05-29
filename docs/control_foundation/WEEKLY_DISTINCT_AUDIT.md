# Weekly Distinct Audit — Active Drivers

## Fecha: 2026-05-29
## Scope: active_drivers across daily/weekly/monthly grains

---

## Cálculo Diario (CORRECT)

**Source**: `ops.real_business_slice_day_fact`
**Loader**: `load_business_slice_day_for_month()` → `_RESOLVE_AND_AGG_DAY_FROM_TEMP`

```sql
-- business_slice_incremental_load.py line 341
COUNT(DISTINCT r.driver_id) FILTER (WHERE r.completed_flag) AS active_drivers
```

**Grupo**: `trip_date, country, city, business_slice_name, ...`
**Origen datos**: Vista `_bs_enriched_month` (temp table pre-materializada de `ops.v_real_trips_business_slice_resolved`)

**Resultado**: Distinct drivers que completaron viajes en CADA día individual.

**Ejemplo** — Lunes 2026-05-26:
```
Driver A: 8 viajes → cuenta 1
Driver B: 5 viajes → cuenta 1
Total: 2 distinct drivers
```

**Veredict**: CORRECTO. `COUNT(DISTINCT)` es la definición canónica.

---

## Cálculo Semanal (INCORRECTO — SUM PROXY)

**Source**: `ops.real_business_slice_week_fact`
**Loader**: `load_business_slice_week_for_month()` → `_WEEK_ROLLUP_FROM_DAY_FACT`

```sql
-- business_slice_incremental_load.py line 581
SUM(COALESCE(d.active_drivers, 0))::bigint AS active_drivers
```

**Grupo**: `date_trunc('week', trip_date), country, city, business_slice_name, ...`
**Origen datos**: `ops.real_business_slice_day_fact` (el day_fact, NO los trips crudos)

**Resultado**: SUM de los counts diarios individuales.

**Ejemplo** — Semana 2026-05-26 a 2026-06-01 (parcial, solo Mon-Thu):
```
Lunes: Driver A (8 viajes) + Driver B (5 viajes) = 2
Martes: Driver A (6 viajes) + Driver B (4 viajes) + Driver C (3 viajes) = 3
Miércoles: Driver A (7 viajes) + Driver B (5 viajes) = 2
Jueves: Driver A (9 viajes) + Driver C (2 viajes) = 2

SUM weekly: 2 + 3 + 2 + 2 = 9
TRUE weekly distinct: Driver A + Driver B + Driver C = 3
```

**Sobreestimación**: 9 / 3 = 3x (para esta semana parcial). Para semana completa con 7 días: hasta 7x si los mismos drivers operan todos los días.

**Veredict**: INCORRECTO. Debería ser `COUNT(DISTINCT driver_id)` desde los trips crudos, NO `SUM(daily_counts)`.

---

## Cálculo Mensual (CORRECT)

**Source**: `ops.real_business_slice_month_fact`
**Loader**: `load_business_slice_month()` → `_RESOLVE_AND_AGG_FROM_TEMP`

```sql
-- business_slice_incremental_load.py line 51
COUNT(DISTINCT r.driver_id) FILTER (WHERE r.completed_flag) AS active_drivers
```

**Grupo**: `trip_month, country, city, business_slice_name, ...`
**Origen datos**: Vista `_bs_enriched_month` (trips crudos enriquecidos)

**Resultado**: Distinct drivers en todo el mes.

**Veredict**: CORRECTO. `COUNT(DISTINCT)` canónico.

---

## ¿Por qué existe la diferencia?

La arquitectura de refresh es:
1. **Month fact**: Lee trips crudos → computa `COUNT(DISTINCT)` → correcto.
2. **Day fact**: Lee trips crudos → computa `COUNT(DISTINCT)` por día → correcto.
3. **Week fact**: Lee DAY FACT (no trips crudos) → `SUM(daily distincts)` → **incorrecto**.

La week_fact es un ROLLUP del day_fact, no una agregación directa desde trips. Esto es intencional por performance (el day_fact ya está pre-agregado, rápido de SUM), pero pierde la semántica distinct.

### ⚠️ Nota importante
El `_WEEK_ROLLUP_FROM_DAY_FACT` se ejecuta en el mismo job que el día (`refresh_all_operational_mvs.py` o `run_business_slice_real_refresh_job`). El day_fact se refresca primero, luego el week_fact hace rollup. Si el day_fact se refrescó para días 26-29 de mayo, el week_fact refleja esos 4 días en la semana parcial.

---

## ¿Week_fact tiene DAY_FACT con driver_id?

**NO**. El day_fact es una tabla agregada: no tiene `driver_id`. Tiene columnas agregadas como `trips_completed`, `active_drivers`, `revenue_yego_net`, etc. No es posible hacer `COUNT(DISTINCT driver_id)` desde el day_fact porque el driver_id ya no está en la tabla.

Por eso la única opción actual es `SUM(active_drivers)` desde day_fact — y por eso el rollup es incorrecto.

---

## Impacto en Omniview

| Modo | Grain | active_drivers source | Impacto |
|------|-------|----------------------|---------|
| Evolution | Weekly | `FACT_WEEKLY` | Inflado (SUM proxy) |
| Vs Proyección | Weekly | `FACT_WEEKLY` → `_REAL_WEEKLY_SQL` | Inflado (SUM proxy) |
| Serving Fact | Weekly | `FACT_WEEKLY` via `get_omniview_projection()` | Inflado (SUM proxy) |
| Evolution | Daily | `FACT_DAILY` | Correcto |
| Vs Proyección | Daily | `FACT_DAILY` | Correcto |
| Todos | Monthly | `FACT_MONTHLY` / `FACT_MONTHLY_RAW` | Correcto |

---

## Conclusión

- **Daily**: CORRECT
- **Monthly**: CORRECT
- **Weekly**: INCORRECT — `SUM(daily_counts)` no es equivalente a `COUNT(DISTINCT driver_id)` semanal.

El error es material: para una semana típica de 7 días con ~100 drivers activos, el SUM puede ser 400-700 vs los 100 reales. Esto infla attainment vs plan (real >> esperado semanal) y subestima TPD.
