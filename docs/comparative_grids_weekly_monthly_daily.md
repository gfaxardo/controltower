# Comparative Grids (Weekly / Monthly / Daily)

**Objetivo:** Integrar WoW, MoM y comparativos diarios en la grilla principal de cada vista, con comparativos por fila calculados en backend.

---

## Fase A — Mapeo de grillas actuales

### Weekly / Monthly (misma grilla, cambia periodo)

| Aspecto | Detalle |
|---------|---------|
| **Componente** | `RealLOBDrillView.jsx` (subView === 'drill', periodType === 'weekly' o 'monthly') |
| **Endpoint** | `GET /ops/real-lob/drill?period=week|month&desglose=...&segmento=...&country=...&park_id=...` |
| **Backend** | `real_lob_drill_pro_service.get_drill()` → MV `ops.mv_real_drill_dim_agg`, agrupado por `period_start` por país |
| **Shape de filas** | `countries[].rows[]`: `period_start`, `period_label`, `estado`, `viajes`, `margen_total`, `margen_trip`, `km_prom`, `viajes_b2b`, `pct_b2b`, `expected_last_date`, `children` |
| **Estado** | `estado`: CERRADO | ABIERTO | FALTA_DATA | VACIO (calculado por period_end vs expected_loaded_until) |
| **Extensible** | Añadir en cada fila campos `*_prev`, `*_delta_pct`, `*_trend`, `is_partial_comparison` sin romper contrato |

### Daily

| Aspecto | Detalle |
|---------|---------|
| **Componente** | `RealLOBDailyView.jsx` (tabla por LOB o Park) |
| **Endpoint** | `GET /ops/real-lob/daily/table?day=...&country=...&group_by=lob|park` |
| **Backend** | `real_lob_daily_service.get_daily_table()` → `ops.real_rollup_day_fact` agrupado por `trip_day`, `country`, `lob_group` o `park_id` |
| **Shape** | `rows[]`: `country`, `dimension_key`, `trips`, `margin_total`, `margin_trip`, `km_prom`, `b2b_trips`, `b2b_pct` |
| **Extensible** | Añadir `baseline` query param; devolver por fila `*_baseline`, `*_delta_pct`, `*_trend` |

---

## Fase B — Diseño comparativos por fila

### Weekly (WoW por fila)

- **Comparativo:** semana actual (fila) vs semana anterior.
- **Por fila:** `viajes_prev`, `viajes_delta_pct`, `viajes_trend`; idem margen_total, margen_trip, km_prom, b2b_pct.
- **is_partial_comparison:** true si la fila es periodo ABIERTO (semana en curso).

### Monthly (MoM por fila)

- **Comparativo:** mes actual (fila) vs mes anterior.
- **Campos análogos** a weekly.

### Daily (baseline por fila)

- **Baseline:** D-1 | same_weekday_previous_week | same_weekday_avg_4w.
- **Por fila:** cada dimensión (LOB/park) tiene valor actual y valor baseline; `trips_baseline`, `trips_delta_pct`, `margin_total_baseline`, etc.

---

## Columnas objetivo (grillas)

- **Weekly:** Periodo | Estado | Viajes | WoW Δ% | Margen | WoW Δ% | M/trip | WoW Δ% | Km prom | WoW Δ% | B2B % | WoW Δ%
- **Monthly:** Mes | Estado | Viajes | MoM Δ% | Margen | MoM Δ% | M/trip | MoM Δ% | Km prom | MoM Δ% | B2B % | MoM Δ%
- **Daily:** Dimensión | Viajes | Δ% | Margen | Δ% | M/trip | Δ% | Km prom | Δ% | B2B % | Δ pp (baseline indicado en cabecera y en título de tabla).

---

## Fase C — Backend (implementado)

### Drill (weekly/monthly)

- **Archivo:** `real_lob_drill_pro_service.py`
- **Lógica:** Para cada fila (period_start) se calcula `prev_ps` = semana anterior (ps - 7d) o mes anterior (primer día del mes anterior). Se obtiene `prev_ad = agg_detail.get(prev_ps)` (mismo país/filtros). Se añade a la fila: `viajes_prev`, `viajes_delta_pct`, `viajes_trend`, `margen_total_prev`, `margen_total_delta_pct`, `margen_total_trend`, `margen_trip_prev`, `margen_trip_delta_pct`, `km_prom_prev`, `km_prom_delta_pct`, `pct_b2b_prev`, `pct_b2b_delta_pp`, `pct_b2b_trend`, `is_partial_comparison` (true si estado == ABIERTO), `comparative_type` (WoW | MoM).

### Daily table

- **Archivo:** `real_lob_daily_service.py`
- **Endpoint:** `GET /ops/real-lob/daily/table?day=...&baseline=D-1|same_weekday_previous_week|same_weekday_avg_4w`
- **Lógica:** Si `baseline` está presente, se consulta la tabla para el día actual y para el/los días baseline; se agrega por (country, dimension_key) y se fusiona en cada fila: `trips_baseline`, `trips_delta_pct`, `trips_trend`, `margin_total_baseline`, `margin_total_delta_pct`, etc., y `baseline_label` en la respuesta.

---

## Fase D — Frontend (implementado)

- **RealLOBDrillView:** La tabla de periodos (weekly/monthly) tiene columnas extra: WoW Δ% o MoM Δ% para viajes, margen total, margen/trip, km prom, y WoW pp / MoM pp para B2B. Cada celda muestra flecha (↑↓→) y porcentaje o puntos porcentuales; color verde/rojo/gris según tendencia. Si la fila es periodo abierto se muestra badge "Parcial" junto al periodo.
- **RealLOBDailyView:** La tabla por LOB recibe `baseline` en la petición; si la respuesta incluye `baseline` y `baseline_label`, se muestran columnas Δ% y Δ pp por métrica. El título de la tabla indica "Baseline: ...".

---

## Endpoints y componentes modificados

| Qué | Dónde |
|-----|-------|
| WoW/MoM por fila en drill | `real_lob_drill_pro_service.get_drill()` — cada row con campos *_prev, *_delta_pct, *_trend, is_partial_comparison |
| Daily table con baseline por fila | `real_lob_daily_service.get_daily_table(baseline=...)` |
| Grilla weekly/monthly | `RealLOBDrillView.jsx` — columnas WoW/MoM Δ% y badge Parcial |
| Grilla daily | `RealLOBDailyView.jsx` — columnas Δ% y Δ pp cuando hay baseline; título con baseline_label |
| API daily table | `GET /ops/real-lob/daily/table?baseline=...` |

---

## Entregable final (Fase H)

1. **Vistas/grid afectadas:** Drill weekly/monthly (RealLOBDrillView), Daily (RealLOBDailyView).
2. **Endpoints/servicios:** `real_lob_drill_pro_service.get_drill()` (añade WoW/MoM por fila), `real_lob_daily_service.get_daily_table(baseline=...)` (añade comparativo por fila), `GET /ops/real-lob/daily/table?baseline=...`.
3. **WoW por fila:** prev_ps = period_start - 7 días; prev_ad = agg_detail.get(prev_ps); deltas y trend para viajes, margen_total, margen_trip, km_prom, pct_b2b (en pp).
4. **MoM por fila:** prev_ps = primer día del mes anterior; mismo merge de prev_ad y campos comparativos.
5. **Daily baseline por fila:** consulta actual por (country, dimension_key); consulta(s) baseline por mismo dimension_key; agregación (promedio si 4w); merge en cada fila: *_baseline, *_delta_pct, *_trend.
6. **Evidencia:** Grilla weekly muestra columnas "WoW Δ%" y badge "Parcial" en periodo abierto; grilla monthly "MoM Δ%"; daily tabla con "Baseline: ..." y columnas Δ% cuando baseline está activo.
7. **Archivos modificados:** `backend/app/services/real_lob_drill_pro_service.py`, `backend/app/services/real_lob_daily_service.py`, `backend/app/routers/ops.py`, `frontend/src/components/RealLOBDrillView.jsx`, `frontend/src/components/RealLOBDailyView.jsx`, `docs/comparative_grids_weekly_monthly_daily.md`.
8. **Veredicto:** LISTO PARA PROBAR EN UI.
