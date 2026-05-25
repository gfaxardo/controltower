# INCIDENTE 1H.2F — WEEKLY ISO FROM DAILY CLOSED FACTS + UX CONTRACT

## Veredicto Final: GO (tras regeneración de serving fact)

---

## 1. Causa Raíz

### Tipo de falla: B + C — Serving fact stale + UI contract OK

El código backend YA tenía el fix de JOIN corregido (Fase 1H.2E — INCIDENTE_1H2E_WEEKLY_SEMANTICS), pero el **serving fact `serving.omniview_projection_daily_fact` para grain=weekly fue generado ANTES del fix**. Contenía 1487 filas con `trips_completed = NULL` y `comparison_status = 'plan_without_real'` para todas.

### Cadena completa

```
ops.real_business_slice_week_fact (datos reales existen, 1283 filas, ej: Lima/Auto regular W1=98,155)
     ↓
_load_real_weekly() → FIX APPLIED: usa week_start.isoformat() en vez de _month_key()
     ↓
_build_weekly() → join correcto real_map ↔ weekly_plan_map
     ↓
get_omniview_projection() → runtime path produce 422 matched rows
     ↓
refresh_omniview_projection_facts.py → SELF-FEEDING BUG: lee desde serving fact existente (stale)
     ↓  en lugar de usar runtime path → reinserta datos NULL
serving.omniview_projection_daily_fact → 1487 rows, todas plan_without_real, trips_completed=NULL
     ↓
API /ops/business-slice/omniview-projection → served_from=fact, actual_value=NULL
     ↓
UI → 0, 0.0%, "Sin ejecución"
```

### Self-feeding bug del refresh script

El script `refresh_omniview_projection_facts.py` llama `get_omniview_projection(_allow_runtime_fallback=True)`, pero `_try_load_from_serving_fact()` encontró datos (stale) y los devolvió sin pasar por el runtime path. El refresh **reinsertó los mismos datos NULL**.

Para romper el ciclo: borrar el serving fact primero, luego regenerar.

---

## 2. Confirmación Fuente Semanal Real

### Weekly se calcula desde daily closed facts: CONFIRMADO

| Componente | Archivo:Línea | Evidencia |
|-----------|--------------|-----------|
| Week fact DDL | `alembic/versions/119_business_slice_day_week_facts.py` | Tabla `ops.real_business_slice_week_fact` |
| Week fact population | `business_slice_incremental_load.py:1128` | `load_business_slice_week_for_month()` |
| Rollup SQL | `business_slice_incremental_load.py:568` | `_WEEK_ROLLUP_FROM_DAY_FACT` — `date_trunc('week', d.trip_date)::date` |
| ISO week source | PostgreSQL `date_trunc('week', ...)` | ISO Monday como week_start |
| Backend read | `projection_expected_progress_service.py:2719` | `_load_real_weekly()` → `ops.real_business_slice_week_fact` |
| Key format | `projection_expected_progress_service.py:2757` | `r["week_start"].isoformat()[:10]` (NO `_month_key()`) |

### NO se usa monthly como source semanal

- `load_business_slice_week_for_month()` → rollup desde `day_fact` (no desde `month_fact`)
- `_load_real_weekly()` → lee `FACT_WEEKLY` directamente (no agrega desde monthly)
- Plan semanal → derivado desde plan mensual via `_build_plan_distribution()` → `_build_iso_plan_maps()` con ISO weeks que cruzan meses

---

## 3. SQL de Reconciliación Daily → Weekly

### Resultado: 20/20 MATCH (100%)

Semana verificada: **2026-01-05** (lunes) a **2026-01-11** (domingo)

```sql
SELECT country, city, business_slice_name, SUM(trips_completed) AS daily_sum
FROM ops.real_business_slice_day_fact
WHERE trip_date >= '2026-01-05' AND trip_date < '2026-01-12'
GROUP BY country, city, business_slice_name;
```

Comparado contra:

```sql
SELECT country, city, business_slice_name, trips_completed AS weekly_fact
FROM ops.real_business_slice_week_fact
WHERE week_start = '2026-01-05';
```

| Slice | Daily Sum | Week Fact | Match |
|-------|-----------|-----------|-------|
| Lima/Auto regular | 98,155 | 98,155 | OK |
| Lima/Delivery | 2,188 | 2,188 | OK |
| Trujillo/Auto regular | 9,211 | 9,211 | OK |
| Cali/Auto regular | 42,502 | 42,502 | OK |
| ... 16 more rows | ... | ... | OK |

**Todas las 20 claves concuerdan.** daily_sum == week_fact para cada (country, city, business_slice).

---

## 4. Serving Fact — Before / After

### Before (stale — generado antes del fix)

```
Total rows:        1487
With actual > 0:   0
Matched:           0
Plan-only:         1487
comparison_basis:  NULL
generated_at:      2026-05-23T09:29:49
```

### After (regenerado con fix)

```
Total rows:        1495
With actual > 0:   418
Matched:           422
Plan-only:         1065
Real-only:         8
comparison_basis:  full_week (para semanas cerradas)
generated_at:      2026-05-25T08:07:33
```

### Filas ejemplo (Perú)

| Week | City | Slice | Real Trips | Proj Trips | Att% | Status |
|------|------|-------|-----------|-----------|------|--------|
| 2026-01-05 | lima | Auto regular | 98,155 | 121,067 | 81.07% | matched |
| 2026-01-05 | trujillo | Auto regular | 9,211 | 13,401 | 68.73% | matched |
| 2026-01-05 | lima | Delivery | 2,188 | 2,501 | 87.50% | matched |
| 2026-05-04 | lima | Auto regular | 88,780 | 412,717 | 21.51% | matched |
| 2026-05-18 | lima | Auto regular | 79,864 | 412,717 | 19.35% | matched |

### Filas ejemplo (Colombia)

| Week | City | Slice | Real Trips | Proj Trips | Att% | Status |
|------|------|-------|-----------|-----------|------|--------|
| 2026-01-05 | cali | Auto regular | 42,502 | 708 | 6000% | matched |
| 2026-01-05 | bogota | Delivery | NULL | 39 | — | plan_without_real |

Nota: Colombia tiene attainment >100% porque el plan mensual es muy bajo para el volumen real semanal. Es un issue de datos de plan, no de este fix.

---

## 5. Cambios Realizados

### Fix 1 (ya aplicado previamente — Fase 1H.2E)

**Archivo:** `backend/app/services/projection_expected_progress_service.py:2757`

```python
# Antes:
mk = _month_key(r["week_start"])

# Ahora:
mk = (
    r["week_start"].isoformat()[:10]
    if hasattr(r["week_start"], "isoformat")
    else str(r["week_start"])[:10]
)
```

### Fix 2 (aplicado en este incidente)

**Archivo:** `backend/scripts/refresh_omniview_projection_facts.py:131`

```python
# Antes:
r.get("comparison_status"), r.get("comparison_basis"),

# Ahora:
r.get("comparison_status"), r.get("comparison_basis") or r.get("trips_completed_comparison_basis"),
```

El runtime response almacena `comparison_basis` como campo per-KPI (`trips_completed_comparison_basis`), no como campo top-level. El refresh script debe leer del campo correcto.

### Acción: Regeneración del serving fact

```bash
# 1. Borrar datos stale
DELETE FROM serving.omniview_projection_daily_fact 
WHERE plan_version='ruta27_2026_04_21' AND grain='weekly';

# 2. Regenerar (runtime path, no desde serving fact)
python backend/scripts/refresh_omniview_projection_facts.py \
  --plan-version ruta27_2026_04_21 --grain weekly --year 2026
```

---

## 6. Contrato Semántico Final

### Reglas de estado semanal

| week_state | Condición | Label UI |
|-----------|-----------|----------|
| future | today < week_start | Plan pendiente |
| current | week_start <= today <= week_end | Parcial |
| closed | today > week_end | attainment % (con real) / Sin ejecución (sin real) |

### Reglas de comparación

| Estado | comparison_basis | Significado |
|--------|-----------------|-------------|
| closed + real + plan | full_week | actual vs plan semanal completo |
| current + real + plan | expected_to_date_week | actual vs expected acumulado al corte |
| closed/current + plan + sin real | full_week | plan como referencia (Sin ejecución/Parcial) |
| future | full_week | plan como referencia (Plan pendiente) |

---

## 7. QA Results

### Validación directa DB

| Check | Resultado |
|-------|-----------|
| daily_sum == week_fact (20 keys) | 20/20 PASS |
| week_fact tiene datos (1283 rows) | PASS |
| serving fact tiene actual > 0 (418 rows) | PASS |
| serving fact tiene comparison_basis (1495 rows) | PASS |
| serving fact tiene matched rows (422) | PASS |
| generated_at es fresco (2026-05-25) | PASS |

### QA script (validate_phase1h2e_weekly_semantics.py)

36/40 PASS, 3 FAIL (metadata), 1 WARN. Los FAIL son por campos de metadata (`intraweek_expected_method`) que no se almacenan en el serving fact. No afectan los valores reales.

---

## 8. Contrato ISO Week

- **week_start**: ISO Monday (`date_trunc('week', trip_date)::date`)
- **week_end**: ISO Sunday (`week_start + 6 days`)
- **Semanas cruzan meses**: Correcto — `_build_plan_distribution()` usa `_iso_week_context()` que detecta semanas multi-mes
- **NO se usa `_month_key` para agrupar semanas**: Verificado en `_load_real_weekly()` — usa `week_start.isoformat()[:10]`
- **NO se reparte mensual a semanas**: Plan semanal se deriva desde daily_plan → suma diaria por semana ISO

---

## 9. GO / NO-GO

### GO conditions:
- [x] Weekly se calcula desde daily closed facts (no desde monthly)
- [x] ISO weeks cruzan meses correctamente
- [x] `_load_real_weekly()` usa week_start ISO exacto (no `_month_key()`)
- [x] Serving fact tiene actual_value > 0 (418 filas)
- [x] Serving fact tiene comparison_status = matched (422 filas)
- [x] Daily → weekly reconciliation 20/20
- [x] comparison_basis poblado en serving fact
- [x] week_state computado correctamente desde serving fact
- [x] Regeneración completada (1495 filas, generated_at fresco)
- [x] Frontend code revisado — `getProjectionStatusLabel()` y `ProjectionCellRender` manejan week_state correctamente

### Pendiente (requiere servidor backend operativo):
- [ ] API endpoint responde con actual_value > 0 (servidor requiere restart tras regeneración)
- [ ] UI validation manual (Perú y Colombia)
- [ ] QA script completo sin timeouts

### NO-GO conditions:
- [ ] Ninguna — los datos son correctos en DB, la UI los mostrará cuando el servidor se reinicie

---

## 10. Notas Adicionales

### Self-feeding serving fact bug

El refresh script `refresh_omniview_projection_facts.py` tiene un bug de diseño: cuando el serving fact ya tiene datos (aunque sean stale/NULL), `_try_load_from_serving_fact()` los devuelve y el script los reinserta sin pasar por el runtime path. Workaround: borrar los datos antes de regenerar.

### Plan Colombia con valores bajos

El plan mensual para Colombia (fuente: `ops.plan_trips_monthly`) tiene valores muy bajos comparados con el volumen real. Esto produce attainment >1000% en la vista semanal. No es un bug de este fix — requiere revisión de datos de plan.

### Campo intraweek_expected_method ausente en serving fact

El campo `trips_completed_intraweek_expected_method` no está en el INSERT_COLS del refresh script ni en la tabla serving fact. La metadata de método de cálculo intra-semana se pierde al servir desde fact. No afecta valores reales pero causa un FAIL en el QA script. Pendiente para futura migración de serving fact.

---

## 11. Restart Validation (2026-05-25 08:15)

### Procesos matados

| PID | Type | WorkingSet | Acción |
|-----|------|-----------|--------|
| 16128 | uvicorn main | 22 MB | Killed (stale, :8001) |
| 31976 | uvicorn worker | 139 MB | Killed (hung) |

### Proceso nuevo

| PID | Type | Puerto | Estado |
|-----|------|--------|--------|
| 44740 | reloader | :8000 | OK |
| 30412 | worker | :8000 | OK (luego reemplazado por 20044) |

### Serving fact verified

```
generated_at:  2026-05-25 08:07:33.865698-05:00  ← fresco
total_rows:    1495
with_actual:   418  (> 0)
matched:       422
```

### curl endpoints (desde backend limpio)

**Peru:** `served_from=fact | 513 rows | 153 matched | 153 with actual > 0`
```
2026-01-05 lima  Auto regular  real=98155  proj=121067  att=81.07%  basis=full_week  ws=closed
2026-01-05 lima  Delivery      real=2188   proj=2501    att=87.50%  basis=full_week  ws=closed
2026-05-25 lima  Auto regular  real=None   expected=58960               basis=expected_to_date_week  ws=current
2026-06-01 lima  Auto regular  real=None   status=plan_without_real      ws=future
```

**Colombia:** `served_from=fact | 957 rows | 250 matched | 240 with actual > 0`
```
2026-01-05 cali  Auto regular  real=42502  proj=708  att=6000%  ws=closed
2026-01-05 bogota Delivery    real=None  proj=38  status=plan_without_real  ws=closed
```

### GO/NO-GO runtime

| Check | Resultado |
|-------|-----------|
| `served_from=fact` (no runtime fallback) | GO |
| `fact_generated_at` fresco | GO |
| `actual_value > 0` en matched rows | GO |
| `comparison_basis=full_week` en closed | GO |
| `comparison_basis=expected_to_date_week` en current | GO |
| `week_state=closed` en semanas pasadas | GO |
| `week_state=current` en semana actual | GO |
| `week_state=future` en semanas futuras | GO |
| No hay falsos `Sin ejecución` en future weeks | GO |
| No hay falsos `0%` en closed weeks con datos | GO |
| Cross-country (Peru + Colombia) OK | GO |
| Frontend sin cambios necesarios (contract OK) | GO |

**VEREDICTO FINAL: GO**
