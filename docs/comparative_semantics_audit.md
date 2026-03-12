# Auditoría de semántica comparativa — YEGO Control Tower

**Fecha:** 2025-03-09  
**Objetivo:** Nomenclatura única MoM / WoW / DoD y comparativos en fila principal y en items disgregados en todas las grillas.

---

## FASE A — MATRIZ DE AUDITORÍA

| view_name | grid/component | comparative_types_present | naming_status | row_level_status | child_row_status | issues_found |
|-----------|----------------|--------------------------|---------------|------------------|------------------|--------------|
| Real LOB Drill | RealLOBDrillView.jsx | WoW, MoM (fila principal) | OK (WoW/MoM en headers) | Implementado (main row) | **Faltaba:** children sin Δ%/pp; backend no devolvía comparativos por hijo | Backend extendido; frontend muestra comparativos en drill rows |
| Real LOB Daily | RealLOBDailyView.jsx | DoD / baseline (D-1, WoW same weekday, avg 4w) | Parcial: headers "Δ%" sin label DoD | Implementado por fila | N/A (cada fila es LOB/park) | Headers unificados con DoD/baseline label; uso gridSemantics |
| Driver Lifecycle | DriverLifecycleView.jsx | No comparativos WoW/MoM en tabla | N/A | No | N/A | Backlog: documentado; sin comparativos por diseño actual |
| Driver Supply Dynamics | SupplyView.jsx | WoW % en Overview/Composition | OK (WoW en labels) | Sí (serie por periodo) | N/A (segment rows con WoW) | Sin cambios naming |
| Snapshot | ExecutiveSnapshotView.jsx | KPICards, no grilla | N/A | N/A | N/A | N/A |
| CoreTable | CoreTable.jsx | Delta Abs / Delta % (genérico) | No usa MoM/WoW | Sí | N/A | Backlog: naming si se añade periodo |
| Plan Tabs | PlanTabs.jsx | No comparativos | N/A | No | N/A | N/A |

---

## FASE B — ESTÁNDAR GLOBAL DE NOMENCLATURA

### Oficial del sistema
- **Monthly** = **MoM** (month-over-month)
- **Weekly** = **WoW** (week-over-week)
- **Daily** = **DoD** (day-over-day)

### Uso en UI
- Labels de columnas: `MoM Δ%`, `WoW Δ%`, `DoD Δ%` (o baseline: `D-1 Δ%`, `WoW Δ%` para same weekday).
- Cambios en participación: `MoM pp`, `WoW pp`, `DoD pp`.
- **Prohibido:** MOM, WOW, DOD (mayúsculas incorrectas). Siempre MoM, WoW, DoD.

### Constantes frontend
- `frontend/src/constants/gridSemantics.js` exporta `COMPARATIVE_LABELS`:
  - `MoM`, `WoW`, `DoD`
  - `deltaPctLabel(periodType)` → "MoM Δ%" | "WoW Δ%" | "DoD Δ%"
  - `ppLabel(periodType)` → "MoM pp" | "WoW pp" | "DoD pp"
  - `comparativeTitle(periodType)` para títulos de bloque (ej. "Comparativo MoM (último mes cerrado vs anterior)").

---

## FASE C–D — COMPARATIVOS POR FILA E HIJO

### Comportamiento definido
- **Fila principal del período:** muestra comparativo (WoW o MoM) según vista; ya implementado en Real LOB Drill.
- **Items disgregados (children):** cada fila de desglose (LOB, Park, Tipo de servicio) debe mostrar el mismo comparativo (WoW en weekly, MoM en monthly), calculado en backend.

### Backend: comparativos para children
- **Endpoint:** `GET /ops/real-lob/drill/children` (sin cambio de contrato).
- **Respuesta:** cada item en `data[]` incluye, además de viajes/margen/km/b2b:
  - `viajes_prev`, `viajes_delta_pct`, `viajes_trend`
  - `margen_total_prev`, `margen_total_delta_pct`, `margen_total_trend`
  - `margen_trip_prev`, `margen_trip_delta_pct`, `margen_trip_trend`
  - `km_prom_prev`, `km_prom_delta_pct`, `km_prom_trend`
  - `pct_b2b_prev`, `pct_b2b_delta_pp`, `pct_b2b_trend`
  - `comparative_type`: "WoW" | "MoM"
  - `is_partial_comparison`: bool (opcional)
- **Lógica:** se consulta el mismo MV para `period_start` (actual) y `prev_period_start` (anterior); se hace merge por `dimension_key` y se aplica helper reutilizable que añade delta_pct y trend por métrica.

### Frontend: mostrar en drill rows
- RealLOBDrillView: las celdas de comparativo en filas de desglose ya tienen el mismo layout que la fila principal (13 columnas). Se rellenan con los campos que devuelve el backend (`viajes_delta_pct`, `viajes_trend`, etc.) usando `getComparativeClass(trend)` y mismo formato (↑/↓/→ + % o pp).

---

## FASE E–F — OTRAS GRILLAS

- **Driver Lifecycle:** no se exige WoW/MoM en esta fase; documentado como backlog si en el futuro se añaden comparativos por periodo.
- **Driver Supply Dynamics:** ya usa WoW en labels; sin cambios.
- **Real LOB Daily:** headers con "DoD Δ%" o label del baseline (D-1, WoW, etc.); celdas con getComparativeClass.

---

## FASE G–H — VALIDACIÓN Y DOCUMENTACIÓN

- Validar en UI: Real LOB monthly (MoM en main + children), weekly (WoW en main + children), daily (DoD/baseline en headers y filas).
- No debe aparecer MOM, WOW ni DOD en mayúsculas en ninguna parte visible.
- Este documento y `docs/period_semantics_and_comparatives.md` / `docs/comparative_grids_weekly_monthly_daily.md` referencian el estándar.

---

## Resumen de cambios realizados

1. **docs/comparative_semantics_audit.md** — Creado (este documento).
2. **frontend/src/constants/gridSemantics.js** — Añadido `COMPARATIVE_LABELS` (MoM, WoW, DoD, deltaPctLabel, ppLabel, comparativeTitle).
3. **backend real_lob_drill_pro_service.py** — `get_drill_children()`: consulta periodo anterior, merge por dimension_key, añade campos comparativos por hijo (`_add_child_comparative`).
4. **frontend RealLOBDrillView.jsx** — Headers usan `COMPARATIVE_LABELS`; filas de desglose muestran comparativos cuando el API los envía.
5. **frontend RealLOBDailyView.jsx** — Headers "DoD Δ%" / baseline label; celdas de tendencia usan `getComparativeClass`.
6. **Nomenclatura:** Revisión global; no se encontraron MOM/WOW/DOD incorrectos; estándar fijado en constantes para evitar futuras incoherencias.

---

## FASE I — ENTREGABLE FINAL

1. **Vistas/grillas auditadas:** Real LOB (Drill, Daily), Driver Lifecycle, Driver Supply Dynamics, Snapshot, CoreTable, Plan Tabs.
2. **Lugares donde se unificó nomenclatura:** No se encontraron MOM/WOW/DOD incorrectos; estándar fijado en `COMPARATIVE_LABELS` (MoM, WoW, DoD, deltaPctLabel, ppLabel, comparativeTitle, dailyDeltaPctLabel, dailyPpLabel). Headers y títulos usan estas constantes en RealLOBDrillView y RealLOBDailyView.
3. **Componentes/backend tocados:**
   - **Backend:** `app/services/real_lob_drill_pro_service.py` — `_add_child_comparative()`, y en `get_drill_children()` segunda consulta por periodo anterior + merge por dimension_key + comparativos por hijo.
   - **Frontend:** `components/RealLOBDrillView.jsx` (COMPARATIVE_LABELS en headers/título; celdas de drill con comparativos cuando el API los envía), `components/RealLOBDailyView.jsx` (headers DoD/baseline; getComparativeClass en celdas), `constants/gridSemantics.js` (COMPARATIVE_LABELS).
4. **Comparativos en items disgregados:** El endpoint `GET /ops/real-lob/drill/children` devuelve por cada item: `viajes_delta_pct`, `viajes_trend`, `margen_total_delta_pct`, `margen_total_trend`, `margen_trip_delta_pct`, `margen_trip_trend`, `km_prom_delta_pct`, `km_prom_trend`, `pct_b2b_delta_pp`, `pct_b2b_trend`, `comparative_type`. RealLOBDrillView renderiza esas celdas con la misma semántica visual que la fila principal (getComparativeClass, flechas, %/pp).
5. **Evidencia:** Código y docs actualizados; validación en UI recomendada (Drill monthly/weekly con desglose LOB/Park/Tipo de servicio; Daily con baseline).
6. **Archivos modificados:**
   - `docs/comparative_semantics_audit.md` (nuevo)
   - `docs/period_semantics_and_comparatives.md` (referencia al estándar)
   - `frontend/src/constants/gridSemantics.js` (COMPARATIVE_LABELS)
   - `frontend/src/components/RealLOBDrillView.jsx` (labels + comparativos en filas de desglose)
   - `frontend/src/components/RealLOBDailyView.jsx` (labels DoD/baseline + getComparativeClass)
   - `backend/app/services/real_lob_drill_pro_service.py` (_add_child_comparative + comparativos en get_drill_children)

---

## Veredicto

**LISTO PARA PROBAR EN UI**

- Nomenclatura estándar definida y centralizada (MoM, WoW, DoD).
- Comparativos en items disgregados: backend devuelve por hijo; frontend los muestra en Real LOB Drill.
- Daily: headers DoD/baseline y semántica visual unificada.
- Resto de grillas auditadas; backlog documentado donde aplica.
