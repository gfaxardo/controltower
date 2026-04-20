# FASE — Projection Integrity Engine

Documentación del motor de integridad de la proyección Omniview (plan mensual como fuente de verdad, distribución semanal/diaria derivada).

## Reglas canónicas

1. **Plan mensual** es la única fuente persistida; grano semanal y diario se **derivan** vía `seasonality_curve_engine` + reconciliación.
2. **Clave de semana**: `week_start` = lunes (fecha) ISO/calendar; la etiqueta UI “S{x}-{año}” se deriva de esa fecha.
3. **Alineación temporal (REAL semanal)**: las semanas se filtran por **intersección** con el mes objetivo (`week_start` entre el lunes de la semana que contiene el día 1 y el lunes de la semana que contiene el último día), no por `EXTRACT(MONTH FROM week_start)`. Así **S1 de un año** cuyo lunes cae en diciembre del año anterior sigue asociada a enero cuando corresponde.
4. **Conservación**: tras reparto semanal/diario con redondeos, se fuerza  
   `SUM(fracción semanal o diaria del KPI) ≈ plan mensual` ajustando la **última** celda del periodo si el drift supera tolerancia.
5. **Smoothing**: mezcla **histórico** vs **uniforme/lineal** con α configurable para reducir picos espurios.

## ISO-week y `week_start`

Usamos **lunes ISO** como inicio de bloque. Una semana “pertenece” al mes de análisis si su intervalo [lunes, domingo] **intersecta** ese mes calendario, no si el lunes cae dentro del mes. El bug clásico (enero 2026 / `week_start = 2025-12-29`) se corrige cargando REAL semanal con el rango de intersección descrito arriba.

## Conservación

- Por cada tajada `(country, city, business_slice)` y mes:
  - Se suman los `*_projected_total` semanales (o diarios).
  - Si `drift_abs <= 1` **o** `drift_pct <= PROJECTION_CONSERVATION_TOLERANCE_PCT` respecto al plan mensual → OK.
  - Si no → se suma la diferencia a la **última** semana (o último día) y se recalculan KPIs derivados en esa fila.

## Smoothing (α)

- **Acumulado mensual** (`compute_expected_ratio`):  
  `smoothed = α_day · ratio_hist + (1 - α_day) · (cutoff_day / total_days)`  
  Variable de entorno: `PROJECTION_SMOOTHING_ALPHA_DAY` (default `0.7`).
- **Participación semanal en el mes** (`compute_weekly_expected_ratio`):  
  `week_share = α_week · share_hist + (1 - α_week) · (1 / N_semanas_en_mes)`  
  `PROJECTION_SMOOTHING_ALPHA_WEEK`.
- **Participación diaria** (`compute_daily_expected_ratio`):  
  `daily_share = α_day · share_día + (1 - α_day) · (1 / días_del_mes)`.

La renormalización exacta respecto al plan mensual ocurre en el paso de **conservación** si el redondeo introduce drift.

## Jerarquía de fallback (curvas)

Sin cambio de semántica (niveles 1–4 históricos geográficos, 5 = `linear_fallback`). El resumen por nivel llega en `meta.plan_derivation.fallback_level_summary`.

## Evidencia QA (`meta.qa_checks`)

- **year_end_week / plan**: comprobación de filas en el límite de año con real pero sin plan.
- **Conservación (muestra)**: grupos con ≥3 semanas y `trips_completed`.
- **Volatilidad**: semanas con `week_plan_trip / promedio_slice > 1.5` listadas como anomalías informativas.

## Parámetros `.env`

| Variable | Descripción | Default |
|----------|-------------|---------|
| `PROJECTION_SMOOTHING_ALPHA_WEEK` | Peso histórico en share semanal | `0.7` |
| `PROJECTION_SMOOTHING_ALPHA_DAY` | Peso histórico en ratio acumulado y share diario | `0.7` |
| `PROJECTION_CONSERVATION_TOLERANCE_PCT` | Drift %% aceptable antes de ajustar última celda | `0.1` |

## Endpoint de auditoría

`GET /plan/projection-integrity-audit?plan_version=...&year=...&month=...`

Devuelve `issues[]` con tipos `temporal_alignment`, `conservation`, `volatility`, `fallback_usage` y un `summary` agregado.

## Referencias de código

- `backend/app/services/projection_expected_progress_service.py` — SQL semanal, reconciliación, meta, QA.
- `backend/app/services/seasonality_curve_engine.py` — smoothing y conteo de semanas en mes.
- `backend/app/settings.py` — α y tolerancia.
- `backend/app/services/plan_normalization_service.py` — `get_projection_integrity_audit`.
