# INCIDENTE 1H.2E — WEEKLY SEMANTICS BROKEN

## Veredicto Final: GO (tras fix)

---

## 1. Causa Raíz

### Síntoma observado en UI

La tabla "Vs Proyección" en grano semanal mostraba:
- `actual=0`
- `0%`
- `"Sin ejecución"`

para semanas que eran **futuras** o **semana actual parcial**, haciendo que el módulo semanal pareciera completamente roto.

### Causa raíz real

**Doble falla — backend + frontend:**

1. **Backend**: No existía clasificación de estado semanal (`week_state`). Todas las semanas sin datos reales (`plan_without_real`) eran indistinguibles: una semana futura, una semana en curso sin datos aún, y una semana cerrada sin ejecución recibían exactamente el mismo tratamiento (`comparison_status = "plan_without_real"`, `actual = None`).

2. **Frontend**: `getProjectionStatusLabel()` (projectionMatrixUtils.js:252) etiquetaba toda ausencia de real como `"Sin ejecución"`, sin distinguir si la semana era futura (plan pendiente), actual (parcial), o cerrada (sin ejecución real).

### Cadena completa

```
plan_without_real row → actual=None → hasReal=false
  → hasPlan=true → statusLabel = "Sin ejecución"
  → UI muestra badge rojo engañoso en semanas futuras
```

---

## 2. Contrato Semántico Final

### Estados semanales (`week_state`)

| Estado | Condición | Label UI | Visual |
|--------|-----------|----------|--------|
| `future` | `today < week_start` | "Plan pendiente" | slate-400, opacity-60 |
| `current` | `week_start <= today <= week_end` | "Parcial" (sin real) / avance % (con real) | indigo-500 |
| `closed` | `today > week_end` | "Sin ejecución" (sin real) / attainment % (con real) | slate-500 |

### Labels de celda (proyección)

| Condición | hasPlan | hasReal | week_state | Label |
|-----------|---------|---------|------------|-------|
| Futuro | true | false | future | Plan pendiente |
| Actual sin datos | true | false | current | Parcial |
| Cerrado sin real | true | false | closed | Sin ejecución |
| Con real | true | true | — | Sobre plan / En línea / Bajo plan |
| Sin plan | false | true | — | Sin proy. |
| Sin plan ni real | false | false | — | — (vacío) |

### Comparison basis

| Estado | Basis | Sufijo |
|--------|-------|--------|
| Semana cerrada | `full_week` | (F) |
| Semana actual | `expected_to_date_week` | (E) |
| Semana futura | `full_week` (plan completo como referencia) | (F) |

---

## 3. Archivos Modificados

### Backend

| Archivo | Cambio |
|---------|--------|
| `backend/app/services/projection_expected_progress_service.py` | `_build_weekly_row_from_iso_plan()`: añade campo `week_state` (future/current/closed/unknown) basado en today vs week_start/week_end. `_build_no_plan_row()`: añade `week_state` para filas sin plan. `_serving_fact_row_to_display()`: añade `week_state` computado desde serving fact. Nueva función `_compute_week_state_from_row()`. |

### Frontend

| Archivo | Cambio |
|---------|--------|
| `frontend/src/components/omniview/projectionMatrixUtils.js` | `buildProjectionMatrix()`: propaga `week_state` desde raw a cell entry. `computeProjectionDeltas()`: añade `week_state` al delta object. `getProjectionStatusLabel()`: acepta `week_state` y retorna labels semánticos ("Plan pendiente", "Parcial", "Sin ejecución"). `getProjectionStatusColors()`: colores para nuevos labels. |
| `frontend/src/components/BusinessSliceOmniviewMatrixCell.jsx` | `ProjectionCellRender`: extrae `week_state` del delta, lo pasa a `getProjectionStatusLabel`. Añade `futureDim` (opacity-60) para semanas futuras sin real. Habilita label siempre para weeks sin real. |
| `frontend/src/components/BusinessSliceOmniviewMatrixHeader.jsx` | Habilita `isCurrentPeriod` en modo proyección (antes solo evolution). Muestra badge "SEMANA ACTUAL". |
| `frontend/src/components/BusinessSliceOmniviewMatrix.jsx` | Añade `weekFocusOnly` state (default true). Función `filterWeeklyFocus()`: filtra períodos a ±6 semanas alrededor de la semana actual. `displayMatrix` / `displayProjMatrix`: versiones filtradas pasadas a las tablas. Toggle "Año completo" para desactivar filtro. Persistencia de `weekFocusOnly`. |

---

## 4. Before / After

### Before (roto)

```
Semana futura (ej: 2026-08-03):
  Proy: 8500
  Real: 0
  ● 0.0% (F)
  Sin ejecución          ← ENGAÑOSO, parece error
```

### After (corregido)

```
Semana futura (ej: 2026-08-03):
  Proy: 8500
  Real: 0
  ● 0.0% (F)
  Plan pendiente         ← CORRECTO, neutral

Semana actual (ej: 2026-05-25):
  Proy: 8500
  Real: 3200
  ● 64.0% (E)
  Parcial                ← CORRECTO, muestra avance

Semana cerrada sin real (ej: 2026-01-05):
  Proy: 7200
  Real: 0
  ● 0.0% (F)
  Sin ejecución          ← CORRECTO, debería haber datos
```

### Current week focus (nuevo)

```
Default: ±6 semanas alrededor de la semana actual (~13 semanas visibles)
Toggle "Año completo": muestra todas las semanas ISO del año (~52)
```

---

## 5. Reglas de Render

### ProjectionCellRender (BusinessSliceOmniviewMatrixCell.jsx)

```
if !hasPlan:
  → mostrar "Sin proy." (missing_plan)
  → no mostrar badge de estado

if hasPlan && !hasReal && week_state == "future":
  → opacity-60
  → label "Plan pendiente" en slate-400

if hasPlan && !hasReal && week_state == "current":
  → label "Parcial" en indigo-500
  → expected_to_date_week como base

if hasPlan && !hasReal && week_state == "closed":
  → label "Sin ejecución" en slate-500
  → plan completo como base de referencia

if hasPlan && hasReal:
  → attainment %, gap, signal
  → label "Sobre plan" / "En línea" / "Bajo plan"
```

### Header (BusinessSliceOmniviewMatrixHeader.jsx)

```
Semanas futuras: badge FUTURE en slate
Semana actual: badge "SEMANA ACTUAL" en azul + highlight bg
Semanas cerradas: badge OPEN/PARTIAL/STALE según freshness
```

---

## 6. Validación QA

```bash
python backend/scripts/validate_phase1h2e_weekly_semantics.py
```

Validaciones:
1. API responde 200 con datos weekly
2. `served_from == "fact"` (no runtime fallback)
3. Campo `week_state` presente en todas las filas
4. Exactamente una `current` week (o ninguna si el año no incluye la actual)
5. `future` weeks correctamente taggeadas
6. `future` weeks sin datos reales (actual=0/null)
7. `current` week con expected parcial (<= plan total)
8. `closed` weeks con attainment comparable
9. Cross-country: Perú y Colombia ambos OK
10. `comparison_basis` incluye `full_week` y `expected_to_date_week`

---

## 7. GO / NO-GO

### GO conditions:
- [x] `week_state` field exists in all backend rows
- [x] Future weeks show "Plan pendiente", not "Sin ejecución"
- [x] Current week shows "Parcial" when no real data yet
- [x] Closed weeks without real show "Sin ejecución" (correctly)
- [x] Current week focus limits default view to ±6 weeks
- [x] "Año completo" toggle available for full year view
- [x] Semantic colors: neutral for future, indigo for current, muted for closed
- [x] No regression in daily or monthly grains
- [x] No runtime fallback pollution
- [x] QA script passes

### NO-GO conditions:
- [ ] QA script fails
- [ ] Future weeks still show "Sin ejecución"
- [ ] Current week missing or misclassified
- [ ] Regression in daily/monthly projection tables
