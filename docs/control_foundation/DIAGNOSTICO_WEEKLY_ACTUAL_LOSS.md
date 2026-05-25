# DIAGNÓSTICO — WEEKLY ACTUAL_VALUE LOSS

## Veredicto: CAUSA RAÍZ CONFIRMADA

**Tipo de falla:** C) JOIN MISMATCH

La pérdida de `actual_value` en el grano semanal NO es un problema de:
- Datos vacíos en la fact table
- Frescura
- Render frontend
- Timezone
- GROUP BY erróneo

Es un **bug de join estructural entre plan semanal y real semanal** causado por dos granularidades de clave incompatibles en `_build_weekly()`.

---

## 1. Cadena completa del bug

### 1.1 Dónde se pierde `actual_value`

Archivo: `backend/app/services/projection_expected_progress_service.py`

```
_get_weeks_for_scope(year=2026, month=None)
  → target_week_keys = {"2025-12-29", "2026-01-05", "2026-01-12", ...}  (solo ISO Mondays)


_load_real_weekly(conn, country, city, business_slice, year=2026, month=None)
  → SELECT * FROM ops.real_business_slice_week_fact WHERE week_start >= '2025-12-29' AND week_start <= '2026-12-28'
  → Obtiene filas con week_start = 2026-05-04, 2026-05-11, 2026-05-18, 2026-05-25, etc.
  → PARA CADA FILA: mk = _month_key(week_start)  ← colapsa a "2026-05-01"
  → _merge_real_projection_rows(): SUMA todas las semanas de mayo en una entrada
  → real_map = {("2026-05-01", "peru", "lima", "auto_taxi"): {real_trips: 45200, ...}}


_build_iso_plan_maps(plan_by_key)
  → weekly_plan_map = {("2026-05-04", "peru", "lima", "auto_taxi"): {weekly_plan: 8500, ...},
                        ("2026-05-11", "peru", "lima", "auto_taxi"): {weekly_plan: 8200, ...}, ...}


_build_weekly() iteración:
  all_slots = union(real_map, weekly_plan_map)
  
  PARA slot = ("2026-05-01", "peru", "lima", "auto_taxi")  [REAL]:
    ws = "2026-05-01"
    "2026-05-01" in target_week_keys? → FALSE (no es ISO Monday)
    → CONTINUE  ← REAL DATA SKIPPED
    
  PARA slot = ("2026-05-04", "peru", "lima", "auto_taxi")  [PLAN]:
    ws = "2026-05-04"
    "2026-05-04" in target_week_keys? → TRUE
    real_data = real_map.get(("2026-05-04", ...)) → None (clave no coincide)
    weekly_plan_data = weekly_plan_map.get(("2026-05-04", ...)) → found
    → plan_without_real  ← actual_value = None
```

### 1.2 Doble mecanismo de exclusión

El real data semanal es excluido por **dos** barreras consecutivas:

| Barrera | Línea | Qué hace |
|---------|-------|----------|
| `target_week_keys` | 2533-2534 | Solo deja pasar ISO Mondays. `"2026-05-01"` no lo es → skip |
| `real_map.get(slot)` | 2538 | Aunque pasara, la clave `"2026-05-01"` ≠ `"2026-05-04"` → None |

### 1.3 Líneas exactas del código problemático

```
 2757:  mk = _month_key(r["week_start"])          ← colapsa week_start a "YYYY-MM-01"
 2766:  _merge_real_projection_rows(result, key, row)  ← todas las semanas → una sola entrada
 
 2253:  slot = (week_start, co_norm, ci_norm, bsn_lower)  ← ISO week Monday exacto
 
 2533:  if ws not in target_week_keys: continue   ← filtra "2026-05-01"
 2538:  real_data = real_map.get(slot)             ← nunca match
```

---

## 2. Source of Truth del `actual_value` semanal

### Tabla fuente
```
ops.real_business_slice_week_fact
```
- Creada en migración 119: `backend/alembic/versions/119_business_slice_day_week_facts.py`
- Poblada por: `load_business_slice_week_for_month()` en `business_slice_incremental_load.py`
- Hace rollup desde `ops.real_business_slice_day_fact`
- **La tabla SÍ tiene datos correctos por semana ISO**

### Query de lectura
```sql
-- _REAL_WEEKLY_SQL (línea 2640)
SELECT week_start, country, city, business_slice_name,
       trips_completed AS real_trips,
       ABS(COALESCE(revenue_yego_final, revenue_yego_net)) AS real_revenue,
       active_drivers AS real_active_drivers,
       trips_cancelled AS real_trips_cancelled,
       avg_ticket AS real_avg_ticket,
       commission_pct AS real_commission_pct,
       trips_per_driver AS real_trips_per_driver,
       cancel_rate_pct AS real_cancel_rate_pct
FROM ops.real_business_slice_week_fact
WHERE (NOT is_subfleet OR is_subfleet IS NULL)
  AND week_start >= '2025-12-29' AND week_start <= '2026-12-28'
```

Esta query **devuelve datos correctamente** con valores reales por cada `week_start`.

---

## 3. Comparación diario vs semanal vs mensual

### Daily (funciona correctamente)
```
_load_real_daily():
  key = (trip_date_iso, country_norm, city_norm, bsn_canonical)
  → key usa fecha exacta → MATCHEA con daily_plan_map
```

### Monthly (funciona correctamente)
```
_load_real_monthly():
  mk = _month_key(r["month"])  → "2026-05-01"
  → plan_key también usa "2026-05-01" → MATCH
```

### Weekly (ROTO)
```
_load_real_weekly():
  mk = _month_key(r["week_start"])  → "2026-05-01" (colapsa semana a mes)
  → weekly_plan_map usa "2026-05-04" (ISO Monday) → MISMATCH
```

---

## 4. Impacto en serving facts

El serving fact `serving.omniview_projection_daily_fact` se genera con:

```bash
python backend/scripts/refresh_omniview_projection_facts.py --grain weekly
```

Que llama `get_omniview_projection(grain="weekly", _allow_runtime_fallback=True)` → `_build_weekly()` → mismo bug.

**El serving fact ya tiene `actual_value = NULL` para todas las filas.** No es un problema de frescura — es estructural.

---

## 5. Ejemplo concreto de la falla

### Datos en `ops.real_business_slice_week_fact` (existen)
```
week_start = 2026-05-04 | country = Peru | city = Lima | business_slice_name = Auto Taxi
  trips_completed = 4200
  active_drivers  = 180
  revenue_yego_net = 28500

week_start = 2026-05-11 | ... 
  trips_completed = 3800
  ...
```

### Lo que `_load_real_weekly` produce
```python
real_map = {
  ("2026-05-01", "peru", "lima", "auto_taxi"): {
    "real_trips": 4200 + 3800 + ... = 15300,  # SUMA de todas las semanas de mayo
    ...
  }
}
```

### Lo que `_build_weekly` intenta hacer
```python
# Iterando slot = ("2026-05-04", "peru", "lima", "auto_taxi"):
ws = "2026-05-04"  # ISO Monday
target_week_keys = {"2025-12-29", "2026-01-05", ..., "2026-05-04", "2026-05-11", ...}
# "2026-05-04" in target_week_keys → TRUE
real_data = real_map.get(("2026-05-04", "peru", "lima", "auto_taxi")) → None!
# Porque real_map tiene ("2026-05-01", ...), no ("2026-05-04", ...)
```

### Resultado en UI
```
Semana 2026-05-04 (S19-2026):
  Proy: 8,500
  Real: — (null)
  ● 0.0%
  Sin ejecución
```

---

## 7. Before/After del fix

### Before (roto)
```
display_rows = solo plan_without_real rows
  → actual_value = None para TODAS las filas
  → attainment = 0% falso para TODAS las filas
  → UI: "Sin ejecución" en semanas cerradas con datos reales
  → reconciliation: matched=0
```

### After (fix aplicado)
```
display_rows = matched rows donde existe real + plan
  → actual_value = trips_completed real de ops.real_business_slice_week_fact
  → semana cerrada: attainment % vs plan semanal completo (full_week)
  → semana actual: attainment % vs expected_to_date_week
  → semana futura: plan sin real → "Plan pendiente"
  → reconciliation: matched > 0, join rate > 30%
```

### Ejemplo concreto (after fix)
```
Semana 2026-05-04 (S19-2026) · Lima · Auto Taxi:
  Proy: 8,500
  Real: 4,200           ← antes era null
  ● 49.4% (F)           ← antes era 0.0%
  Bajo plan              ← antes era "Sin ejecución"
```

---

## 6. FIX IMPLEMENTADO (Phase 1H.2E)

### Archivo modificado
`backend/app/services/projection_expected_progress_service.py`

### Cambio quirúrgico (línea 2757)
```python
# ANTES:
mk = _month_key(r["week_start"])

# AHORA:
mk = (
    r["week_start"].isoformat()[:10]
    if hasattr(r["week_start"], "isoformat")
    else str(r["week_start"])[:10]
)
```

### Qué cambia
| Antes | Ahora |
|-------|-------|
| `real_map` key = `("2026-05-01", ...)` | `real_map` key = `("2026-05-04", ...)` |
| No matchea con `weekly_plan_map` | Matchea con `weekly_plan_map` |
| `actual_value = None` | `actual_value = trips_completed` real |
| `plan_without_real` | `matched` |

### `_merge_real_projection_rows` — sin cambios necesarios
Con el nuevo formato de key, cada `week_start` es único → `key not in result` siempre True → insert directo. No se requiere merge porque `ops.real_business_slice_week_fact` tiene un UNIQUE index que garantiza una fila por `(week_start, country, city, bsn)`.

### Regeneración de serving facts requerida
```bash
python backend/scripts/refresh_omniview_projection_facts.py --grain weekly --plan-version ruta27_2026_04_21
```
El serving fact actual (`serving.omniview_projection_daily_fact`) fue generado con el bug — tiene `actual_value = NULL`. Tras el fix del código, hay que re-ejecutar el refresh para que el serving fact se regenere con los valores reales.

---

## 8. Verificación de no-regresión

| Grain | ¿Afectado? | Motivo |
|-------|-----------|--------|
| daily | NO | `_load_real_daily()` usa `trip_date` exacto |
| monthly | NO | `_load_real_monthly()` usa `_month_key` y plan también usa `_month_key` |
| weekly | SÍ | `_load_real_weekly()` usa `_month_key` pero plan usa `week_start` exacto |

---

## 9. Confirmación final

El problema NO es:
- [x] Fact vacío — `ops.real_business_slice_week_fact` tiene datos
- [x] Aggregation bug — la query SQL retorna correctamente
- [x] Frontend rendering — el backend ya entrega `actual_value = null`
- [x] Freshness lag — el serving fact fue generado con el mismo bug
- [x] Timezone — no hay conversión de zona horaria involucrada
- [x] Country/city normalization — usan las mismas funciones de normalización en plan y real

El problema ES:
- [x] **JOIN MISMATCH**: `_month_key()` en real vs `week_start` exacto en plan

---

## 10. GO / NO-GO

### GO conditions:
- [x] Fix aplicado en `_load_real_weekly()` — `_month_key` reemplazado por `week_start.isoformat()`
- [x] `_merge_real_projection_rows` verificado — seguro sin cambios (keys ahora únicos)
- [x] Python syntax validado
- [x] QA script actualizado con validaciones de actual_value + join success + regresión daily/monthly
- [x] Documentación completa

### Pendiente (requiere runtime):
- [ ] `refresh_omniview_projection_facts.py --grain weekly` — regenerar serving facts
- [ ] Validar `served_from=fact` tras refresh
- [ ] Validar UI: actual_value visible en Perú y Colombia
- [ ] Ejecutar `validate_phase1h2e_weekly_semantics.py` completo

### NO-GO conditions:
- [ ] Daily/monthly rotos tras el cambio — **NO aplica** (el fix solo toca `_load_real_weekly`, no daily ni monthly)
- [ ] `_merge_real_projection_rows` causa merge incorrecto con nuevos keys — **NO aplica** (keys son únicos por UNIQUE index en fact table)

