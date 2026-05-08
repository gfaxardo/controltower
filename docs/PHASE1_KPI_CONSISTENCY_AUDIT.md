# FASE 1 — P2 KPI consistency (auto-generado)

## Resumen ejecutivo

- **Fecha referencia (MAX day_fact.trip_date):** 2026-05-03
- **Periodos evaluados:** 2026-04(last_closed_month), 2026-05(current_calendar_month_open)
- **Checks totales:** 826 (si 0, no hay celdas en month/week/day facts para los filtros)
- **ok / warning / fail / not_certified (agregado validator):** {'ok': 189, 'warning': 47, 'fail': 0, 'not_certified': 590}
- **Veredicto:** **P2 KPI CONSISTENCY GO (condicionado: revisar warnings)**

## Fuentes por grain (Omniview Matrix REAL)

| Grain | Tabla | Columna tiempo | KPIs (extracto) |
|-------|-------|------------------|-------------------|
| Daily | `ops.real_business_slice_day_fact` | `trip_date` | `trips_completed`, `trips_cancelled`, `active_drivers`, `revenue_yego_net`, componentes ticket |
| Weekly | `ops.real_business_slice_week_fact` | `week_start` (ISO) | mismas columnas agregadas |
| Monthly | `ops.real_business_slice_month_fact` | `month` (primer día mes) | mismas columnas |

- **Completados vs cancelados:** `trips_completed` y `trips_cancelled` son columnas separadas; KPIs de volumen completado usan `trips_completed`.
- **active_drivers:** semi-aditivo (distinct por periodo en agregación); no comparar con SUM(daily).
- **avg_ticket:** derivado de `ticket_sum_completed` / `ticket_count_completed` (no promedio de promedios).

## Normalización de filtros (CLI vs columnas en facts)

- País: alias `pe`→`peru`, `co`→`colombia`; comparación con `lower(trim(country))`.
- Ciudad / business_slice: comparación case-insensitive en SQL.
- No se alteran datos en tablas; solo cómo el validador empareja el filtro.

## Regla canónica multi-grain (aditivos)

Para KPIs aditivos, la base de FAIL es **monthly_value ≈ SUM(day_fact en mes calendario)**.
La suma de **semanas ISO completas** que tocan el mes (`weekly_sum_full_iso`) es **solo informativa**
(cruce semana/mes documentado en `validate_kpi_grain_consistency.py`).

## Resultados

- **FAIL:** 0
- **WARNING:** 47
- **not_certified:** 590

### Bloqueadores (status=fail)

_Ninguno._

## Riesgos remanentes

- Ventana **mes abierto**: datos parciales pueden generar warning entre daily y monthly.
- **Cross-country revenue:** no se mezclan monedas en un solo total; filtros por país.

## Artefacto JSON

Ver `backend/scripts/outputs/kpi_multigrain_audit_*.json` para detalle reproducible.

## P2B — Ejecución sobre datos poblados (evidencia)

### Descubrimiento previo (facts)

Comando: `python -m scripts.discover_kpi_fact_population` → genera `backend/scripts/outputs/kpi_fact_discovery_<ts>.json`.

Resumen (corrida local con BD poblada):

| Objeto | Filas | MIN | MAX |
|--------|------:|-----|-----|
| `ops.real_business_slice_day_fact` | 7933 | 2025-01-01 | 2026-05-03 |
| `ops.real_business_slice_week_fact` | 1199 | 2024-12-30 | 2026-04-27 |
| `ops.real_business_slice_month_fact` | 300 | 2025-01-01 | 2026-05-01 |

**Dimensiones dominantes (por `trips_completed` acumulado en facts):** países `colombia`, `peru` (minúsculas en columna); ciudades `lima`, `cali`, `barranquilla`, `medellin`, `trujillo`, `arequipa`; `business_slice` típicos `Auto regular`, `Taxi Moto`, `Delivery`.

**Diagnóstico del caso `pe:lima` con 0 celdas:** el validador comparaba `country = 'pe'` literal; en BD el valor es `peru`. **Corrección aplicada:** normalización de alias (`pe`→`peru`, `co`→`colombia`) y comparación `lower(trim(...))` en `validate_kpi_grain_consistency.py` (sin cambiar tablas).

### Auditoría multigrain P2B

Comando: `python -m scripts.audit_kpi_consistency_multigrain --p2b`

- **JSON:** `backend/scripts/outputs/kpi_multigrain_audit_<timestamp>.json` (ejemplo de corrida: `kpi_multigrain_audit_20260508T174832.json`)
- **Periodos:** último mes cerrado `2026-04` (`last_closed_month` desde `MAX(trip_date)`), mes abierto `2026-05` (`current_calendar_month_open`, con filas diarias).
- **Escenarios:** 10 descubiertos en `month_fact` para 2026-04 (top país/ciudad/slice, anclas CO/PE/Lima/Cali/Medellín/Trujillo/Arequipa, slices Delivery, GLOBAL). Lista en el campo `scenarios` del JSON.
- **Checks:** 826 (10 escenarios × 2 periodos × celdas × KPIs Omniview; `merged>0` en todos los escenarios).
- **Agregado validator (`raw_summary_counts`):** `ok=189`, `expected_non_comparable=590` (ratios/semi-aditivos — en UI P2 como *not_certified*), `warning=47`, `fail=0`.
- **Warnings:** todos en KPI **aditivo** `trips_completed`: la base canónica **daily vs monthly** está en **ok**; el aviso proviene del cheque **secundario** `weekly_sum_intersect` vs mensual (ponderación de semanas ISO en el mes), documentado como posible divergencia por **parciales de semana** — **esperado por grano**, no se clasifica como bug de trips diario↔mensual.

### Ventanas 14 días / 4 semanas ISO

En el JSON: bloque `short_window_context_from_daily_fact` (sumas globales en `day_fact` para últimos 14 días desde `MAX(trip_date)` y 4 buckets de semana en lookback 28d). **No** son criterio adicional de FAIL; la certificación contractual sigue siendo **mes calendario** (`daily_in_month` vs `month_fact`).

### Veredicto bloqueador P2 / P2B

**P2 KPI CONSISTENCY GO (condicionado a revisión de 47 warnings de `weekly_intersect`).** No hay `fail`; la trazabilidad daily↔monthly de KPIs aditivos cuadró. Los warnings no invalidan la regla canónica mensual; reflejan la métrica complementaria de intersección semana–mes.

Si se exige **GO estricto sin warnings**, habría que relajar o silenciar el aviso de `weekly_intersect` en el validador (cambio de política de tolerancia), fuera del alcance mínimo solicitado aquí.