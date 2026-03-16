# FASE 0 — SCAN Y MAPEO TÉCNICO DEL MÓDULO REAL

**Objetivo:** Diagnóstico end-to-end del módulo REAL sin implementar cambios. Trazabilidad para corrección posterior de margen, WoW y cancelaciones.

---

## A. FRONTEND

### Componentes y páginas donde se renderiza REAL

| Ubicación | Componente | Descripción |
|-----------|------------|-------------|
| Tab Real (App.jsx) | `RealLOBView.jsx` | Contenedor con subvistas: Drill y Diario |
| Drill semanal/mensual | `RealLOBDrillView.jsx` | Timeline por país (PE/CO), filas por periodo; doble clic despliega por LOB / Park / Service type |
| Vista diaria | `RealLOBDailyView.jsx` | Resumen por día, comparativo D-1 / WoW / promedio 4 mismos días |
| Real Operacional | `RealOperationalView.jsx` | Hoy, ayer, semana; por día; por hora; cancelaciones y comparativos (fuente: day_v2 / hour_v2) |
| Real vs Proyección | `RealVsProjectionView.jsx` | Comparativa real vs proyección |
| Cards / resumen | KPIs en `RealLOBDrillView` por país: viajes, margen total, margen/trip, km prom, B2B % |
| Tablas por país/LOB/park | Misma grilla del drill: columnas por periodo y subfilas por dimensión |

### Columnas esperadas (drill y diario)

- **margen_total** — valor mostrado como “Margen total” (tooltip: “Margen mostrado en positivo (ABS) para lectura de negocio”).
- **margen_trip** — margen por viaje.
- **WoW/MoM:** `margen_total_delta_pct`, `margen_total_trend`, `margen_trip_delta_pct`, `margen_trip_trend` (y análogos para viajes, km_prom, pct_b2b).

### Decisión de visibilidad y formato (UI)

- **RealLOBDrillView.jsx (líneas 601–606, 634–650, 724–729):**
  - Margen mostrado: `marginTotalPos = row.margin_total_pos ?? (row.margin_total != null ? Math.abs(row.margin_total) : null)` — si el backend manda negativo, el frontend aplica `Math.abs` para mostrar.
  - `formatMargin(n, trips)`: si `trips === 0` o `n` null/NaN → "—"; si no, `Number(n).toFixed(2)`.
  - WoW: clases y flechas vía `getComparativeClass(row.margen_total_trend)` / `row.margen_trip_trend`; valor "—" si `*_delta_pct == null`.
- **RealLOBDailyView.jsx:** usa `margin_total`, `margin_trip` del payload; muestra "—" si null.
- **Cancelaciones:** no se muestran en el drill ni en la vista diaria REAL (tab Real). Sí existen en **Real Operacional** (`/ops/real-operational/cancellations`, `real-operational/snapshot` con completed/cancelled).

### Resumen frontend

- El drill espera `margen_total` / `margen_trip` (y opcionalmente `margin_total_pos` / `margin_unit_pos`). Si llegan null, se muestra "—".
- Hay fallback de signo en UI: `margin_total_pos ?? Math.abs(margin_total)` para que el número mostrado sea positivo; el WoW se calcula en backend sobre `margen_total`/`margen_trip` crudos, por lo que si el backend manda signo contable negativo, el WoW puede verse “invertido” (ej. margen mejor pero delta % negativo por herencia de signo).

---

## B. BACKEND / API

### Endpoints que alimentan REAL y drill

| Ruta | Router | Service | Descripción |
|------|--------|---------|-------------|
| `GET /ops/real-lob/drill` | ops.py | real_lob_drill_pro_service.get_drill | Drill principal: countries[].rows con period_start, estado, viajes, margen_total, margen_trip, km_prom, viajes_b2b, pct_b2b; WoW/MoM por fila |
| `GET /ops/real-lob/drill/children` | ops.py | real_lob_drill_pro_service.get_drill_children | Desglose por LOB / Park / Service type para un (country, period_start) |
| `GET /ops/real-lob/drill/parks` | ops.py | real_lob_drill_pro_service.get_drill_parks | Lista de parks para filtro (fuente: real_drill_dim_fact) |
| `GET /ops/real-lob/daily/summary` | ops.py | real_lob_daily_service.get_daily_summary | Resumen por día (real_rollup_day_fact) |
| `GET /ops/real-lob/daily/comparative` | ops.py | real_lob_daily_service.get_daily_comparative | Comparativo diario vs baseline |
| `GET /ops/real-lob/daily/table` | ops.py | real_lob_daily_service.get_daily_table | Tabla por día con agrupación (lob, etc.) |
| `GET /ops/real-lob/comparatives/weekly` | ops.py | comparative_metrics_service.get_weekly_comparative | WoW agregado (última semana cerrada vs anterior) |
| `GET /ops/real-lob/comparatives/monthly` | ops.py | comparative_metrics_service.get_monthly_comparative | MoM agregado |
| `GET /ops/period-semantics` | ops.py | period_semantics_service | Semántica últimos periodos cerrados/abiertos |
| `GET /ops/real-operational/*` | ops.py | real_operational_service, real_operational_comparatives_service | Snapshot, day-view, hourly-view, cancellations, comparativos (fuente: mv_real_lob_day_v2 / mv_real_lob_hour_v2) |

### Payload drill (get_drill)

- **Fuente de agregación:** `ops.mv_real_drill_dim_agg` (vista = `SELECT * FROM ops.real_drill_dim_fact`).
- **Consultas:** agregado por `(country, period_start)` con `SUM(trips) AS viajes`, `SUM(margin_total) AS margen_total`, `CASE WHEN SUM(trips)>0 THEN SUM(margin_total)/SUM(trips) ELSE NULL END AS margen_trip`, km_prom ponderado, viajes_b2b.
- **Filas:** cada `period_start` del calendario (mes/semana); para cada uno se lee `agg_detail.get(ps)`. Si no hay filas en `real_drill_dim_fact` para ese periodo/país/breakdown, `ad` es None → `margen_total` y `margen_trip` quedan **null**.
- **WoW/MoM:** se calculan en Python con `_add_row_comparative(row, ad, prev_ad, ...)` usando `ad.get("margen_total")`, `prev_ad.get("margen_total")` y `_delta_pct` / `_trend`. Si el valor almacenado es negativo (signo contable), el WoW se calcula sobre ese negativo.
- **Alias al frontend:** `row["margin_total_pos"] = row["margen_total"]`, `row["margin_unit_pos"] = row["margen_trip"]` (sin normalizar signo en backend para el drill).

### Payload diario (real_rollup_day_fact)

- **Fuente:** vista `ops.real_rollup_day_fact` (desde migración 101 = vista sobre `v_real_rollup_day_from_day_v2`).
- **v_real_rollup_day_from_day_v2:** lee `ops.mv_real_lob_day_v2`, agrupa por (trip_date, country, city, park_id, lob_group, segment_tag); expone `margin_total_raw = SUM(margin_total)`, `margin_total_pos = ABS(SUM(margin_total))`, `trips = SUM(completed_trips)` (solo completados).
- Por tanto el **daily** sí recibe margen en “positivo” (margin_total_pos) en la vista; el servicio diario puede exponer margin_total / margin_trip desde esa vista.

### Filtro completados vs cancelaciones

- **Drill:** `real_drill_dim_fact` se puebla con `populate_real_drill_from_hourly_chain`, que hace `SUM(completed_trips)`, `SUM(margin_total)` desde **mv_real_lob_day_v2** sin filtrar por outcome en el SELECT; pero en day_v2 `margin_total` y las métricas de viajes por celda incluyen solo lo que la MV ya agrega: la MV day_v2 tiene por fila `completed_trips`, `cancelled_trips`, `margin_total` (suma sobre todos los viajes del fact, pero en v_real_trip_fact_v2 `margin_total = comision_empresa_asociada`, que típicamente solo tiene valor en completados). El script de populate usa **solo completed_trips** para `trips` y usa **SUM(margin_total)** de day_v2 (que en la práctica es margen de completados). **Cancelaciones no están en el drill.**
- **Real Operacional:** lee day_v2/hour_v2 directamente; sí expone requested_trips, completed_trips, cancelled_trips, cancellation_rate, margin_total.

---

## C. SQL / MODELO DE DATOS

### Cadena hourly-first (vigente)

| Objeto | Tipo | Grain | margin_total / margen |
|--------|------|-------|------------------------|
| ops.v_real_trip_fact_v2 | Vista | Por viaje | margin_total = comision_empresa_asociada (signo contable) |
| ops.mv_real_lob_hour_v2 | MV | (trip_date, trip_hour, country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag, trip_outcome_norm, …) | SUM(margin_total) AS margin_total |
| ops.mv_real_lob_day_v2 | MV | (trip_date, country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag, trip_outcome_norm, …) | SUM(margin_total) AS margin_total |
| ops.mv_real_lob_week_v3 | MV | (week_start, country, city, park_id, …) | SUM(margin_total) AS margin_total |
| ops.mv_real_lob_month_v3 | MV | (month_start, country, city, park_id, …) | SUM(margin_total) AS margin_total |

- **Definición actual de margin_total en fact/hour/day:** valor crudo de `comision_empresa_asociada` (puede ser negativo en contabilidad).
- **WoW en drill:** calculado en backend sobre `margen_total`/`margen_trip` leídos de `mv_real_drill_dim_agg` (real_drill_dim_fact); no hay capa SQL que normalice a “positivo” antes del servicio.

### Objetos usados por el drill y daily

| Objeto | Tipo | Grain | margin_total / margen |
|--------|------|-------|------------------------|
| ops.real_drill_dim_fact | Tabla | (country, period_grain, period_start, segment, breakdown, dimension_key, dimension_id, city) | margin_total numeric, margin_per_trip numeric |
| ops.mv_real_drill_dim_agg | Vista | = SELECT * FROM real_drill_dim_fact | mismo |
| ops.real_rollup_day_fact | Vista (101) | (trip_day, country, city, park_id, lob_group, segment_tag) | margin_total_raw, margin_total_pos, margin_unit_pos (desde day_v2: ABS(SUM(margin_total))) |
| ops.v_real_rollup_day_from_day_v2 | Vista | Idem | SUM(completed_trips) AS trips, SUM(margin_total) AS margin_total_raw, ABS(SUM(margin_total)) AS margin_total_pos |

- **real_drill_dim_fact:** poblada por `populate_real_drill_from_hourly_chain` desde day_v2 (grain day) y week_v3 (grain week). Inserta `SUM(margin_total)` y `CASE WHEN SUM(completed_trips)>0 THEN SUM(margin_total)/SUM(completed_trips) ELSE NULL END` **sin ABS**. Por tanto el drill almacena y sirve **signo contable**.
- **real_rollup_day_fact:** ya normaliza a positivo en SQL (margin_total_pos = ABS(SUM(margin_total))).

### Completados vs cancelaciones en SQL

- **v_real_trip_fact_v2:** incluye todos los viajes (completed, cancelled, other); margin_total = comision_empresa_asociada (en cancelados suele ser NULL/0).
- **mv_real_lob_hour_v2 / day_v2:** tienen requested_trips, completed_trips, cancelled_trips, cancellation_rate, completion_rate; margin_total es suma sobre todos los registros (en la práctica margen de completados).
- **real_drill_dim_fact (populate):** solo usa completed_trips y SUM(margin_total) de day_v2/week_v3; no inserta cancelled_trips ni métricas de cancelación.
- **real_rollup_day_fact (vista 101):** solo expone trips = SUM(completed_trips); no expone cancelaciones.

### Jobs / scripts de refresh e inserción

| Script | Acción | Fuente | Objetos afectados |
|--------|--------|--------|-------------------|
| refresh_real_lob_mvs_v2.py | REFRESH MATERIALIZED VIEW | v_real_trip_fact_v2 | mv_real_lob_hour_v2, mv_real_lob_day_v2, mv_real_lob_week_v3, mv_real_lob_month_v3 |
| populate_real_drill_from_hourly_chain | DELETE ventana + INSERT | mv_real_lob_day_v2, mv_real_lob_week_v3 | ops.real_drill_dim_fact |
| run_pipeline_refresh_and_audit | Orquesta refresh MVs + populate drill | — | Cadena hourly + real_drill_dim_fact |
| backfill_real_lob_mvs.py | Deprecated | v_trips_real_canon (condicion='Completado') | real_drill_dim_fact, real_rollup_day_fact (esta última ya no: 101 convirtió rollup en vista) |

- **Doble inserción posible:** si alguien ejecuta `backfill_real_lob_mvs`, inserta en la misma tabla `real_drill_dim_fact` (y antes también en real_rollup_day_fact; desde 101 rollup es vista, así que backfill ya no puede escribir en rollup). backfill usa signo legacy (en 064 INSERT desde canon con comision_empresa_asociada; en 053 y vistas legacy se usaba (-1)* para “margen en positivo”). populate usa SUM(margin_total) de day_v2 sin invertir. Convivencia de ambos puede mezclar signos y duplicar filas por mismo grain si no se hace UPSERT por clave única.

---

## D. PIPELINE / JOBS

- **Ruta oficial vigente (hourly-first):**
  1. Refresh MVs: hour_v2 → day_v2 → week_v3 → month_v3 (refresh_real_lob_mvs_v2 o equivalente).
  2. real_rollup_day_fact: no requiere paso (es vista sobre day_v2 desde 101).
  3. Poblar drill: `python -m scripts.populate_real_drill_from_hourly_chain` (por defecto días 120, semanas 18).

- **Legacy (deprecated pero aún invocable):**
  - `backfill_real_lob_mvs`: lee v_trips_real_canon, filtra condicion='Completado', escribe en real_drill_dim_fact (y antes en real_rollup_day_fact). No se ejecuta en run_pipeline_refresh_and_audit.

- **Puntos de posible mezcla:**
  - real_drill_dim_fact puede recibir datos de populate (hourly-first) y, si se corre, de backfill (canon). Misma clave única (country, period_grain, period_start, segment, breakdown, dimension_key, dimension_id, city); backfill hace INSERT con ON CONFLICT DO UPDATE en sus bloques, populate hace DELETE por ventana + INSERT. Si primero se corre backfill y luego populate en la misma ventana, populate borra y reescribe; si solo se corre backfill para periodos antiguos y populate para recientes, pueden coexistir dos convenciones de signo (legacy (-1)* vs day_v2 crudo).

---

## E. RESULTADO DEL SCAN — RESUMEN Y PROPUESTA MÍNIMA

### 1. Causa probable de desaparición de margen en semanas recientes

- **Hipótesis principal:** No hay filas en `real_drill_dim_fact` para esos period_start (semanas/meses recientes) porque **no se ejecuta** `populate_real_drill_from_hourly_chain` después del refresh de day_v2/week_v3, o se ejecuta con una ventana que no incluye “hasta ayer” / “hasta semana actual”.
- **Hipótesis secundaria:** day_v2 o week_v3 no tienen datos para esas fechas (MVs no refrescadas o ventana de datos de la fuente limitada).
- **Consecuencia:** Para esos period_start, `agg_detail.get(ps)` es None → margen_total y margen_trip se devuelven null → en UI se muestra "—".

### 2. Causa probable del WoW negativo heredado

- **Hipótesis:** El WoW se calcula sobre `margen_total`/`margen_trip` tal como están en `real_drill_dim_fact` (SUM(margin_total) desde day_v2, sin ABS). Si en origen `comision_empresa_asociada` es negativo (convención contable), el valor almacenado y expuesto es negativo. El frontend muestra el valor en positivo con `Math.abs`, pero los campos `margen_total_delta_pct` y `margen_total_trend` se calculan en backend sobre el valor negativo; por tanto “subir” de -100 a -80 se interpreta como mejora, pero el delta_pct puede ser positivo mientras el número mostrado es positivo, generando confusión; o si en algún periodo había signo invertido (legacy) y en otro no, la mezcla produce WoW “negativo artificial”.
- **Conclusión:** Hay que **normalizar en una capa canónica** (idealmente donde se escribe o se lee para el drill) a “margen visible = positivo”, y que el WoW se calcule sobre esa misma semántica.

### 3. Estado real de coexistencia entre lógica antigua y nueva

- **real_rollup_day_fact:** ya es 100% hourly-first (vista desde day_v2 desde 101); no hay escritura legacy.
- **real_drill_dim_fact:** la ruta oficial de datos es populate_real_drill_from_hourly_chain (day_v2 + week_v3). backfill_real_lob_mvs está deprecated y no se llama en el pipeline estándar; si se ejecuta manualmente, puede escribir en la misma tabla y mezclar convención de signo (legacy a veces con (-1)* en vistas antiguas; en 064 el INSERT es comision_empresa_asociada directo).
- **Conclusión:** Evitar ejecutar backfill sobre real_drill_dim_fact para la misma ventana que alimenta populate; documentar que la única fuente oficial es populate; opcionalmente en populate o en la vista de agregación usar ABS para margen visible.

### 4. Propuesta mínima y segura de corrección (para fases siguientes)

1. **Margen visible y WoW (Fase 2):**
   - Definir una sola convención: “margen visible = positivo” en toda la cadena REAL para negocio.
   - Opción A (recomendada): En el script `populate_real_drill_from_hourly_chain`, escribir en real_drill_dim_fact `margin_total = ABS(SUM(margin_total))` (y margin_per_trip coherente). Así el drill y el WoW consumen ya valor positivo.
   - Opción B: Mantener real_drill_dim_fact con signo crudo y en real_lob_drill_pro_service al leer de mv_real_drill_dim_agg usar ABS al armar margen_total/margen_trip para respuesta y para calcular prev_ps/deltas. Evita cambiar histórico en tabla pero centraliza normalización en un solo servicio.
   - Validar que comparatives (get_weekly_comparative, get_monthly_comparative) y real_lob_daily usen la misma convención (daily ya viene de vista con margin_total_pos).

2. **Semanas recientes con margen (Fase 1 + 3):**
   - Verificar con queries de auditoría que day_v2 y week_v3 tengan datos hasta la semana reciente; que populate se ejecute con ventana suficiente (p. ej. --days 120 --weeks 26) y que esté en el cron/pipeline después del refresh.
   - Asegurar que no haya doble inserción: si backfill se usa solo para recuperación, que sea para periodos fuera de la ventana que populate escribe, o deshabilitar escritura a real_drill_dim_fact en backfill.

3. **Cancelaciones (Fase 4):**
   - Drill/daily actuales: solo completados. Para incorporar cancelaciones sin romper métricas actuales: añadir columnas o filas diferenciadas (ej. viajes completados, viajes cancelados, wow_cancelaciones, tasa_cancelación) en las tablas/vistas que alimentan el drill y la vista diaria, o en endpoints dedicados que el frontend muestre en la misma pantalla (mismo contrato, campos extra).
   - Fuente ya existe: day_v2/week_v3 tienen cancelled_trips y cancellation_rate; falta exponerlas en real_drill_dim_fact (o en una capa agregada que el drill consulte) y en la API/UI del tab Real.

4. **Auditoría (Fase 1 y 6):**
   - Queries que comparen por periodo reciente: viajes completados, cancelados, margen_total, margen_trip, wow_* entre day_v2, week_v3, real_drill_dim_fact, payload API y comprobar null propagation, doble conteo y signo.

---

## LISTA DE ARCHIVOS CLAVE (referencia para fases siguientes)

| Área | Archivos |
|------|----------|
| Frontend drill/daily | frontend/src/components/RealLOBDrillView.jsx, RealLOBDailyView.jsx, RealLOBView.jsx |
| API / contrato | frontend/src/services/api.js (getRealLobDrillPro, getRealLobDailySummary, …) |
| Backend drill | backend/app/services/real_lob_drill_pro_service.py, backend/app/routers/ops.py (real-lob/drill, drill/children, daily/*) |
| Backend daily | backend/app/services/real_lob_daily_service.py |
| Backend comparatives | backend/app/services/comparative_metrics_service.py |
| Backend operacional | backend/app/services/real_operational_service.py, real_operational_comparatives_service.py |
| SQL cadena | backend/alembic/versions/099_real_hourly_first_architecture.py (v_real_trip_fact_v2, hour_v2, day_v2, week_v3, month_v3) |
| SQL rollup/drill | backend/alembic/versions/101_real_rollup_from_day_v2.py, 064_real_lob_trips_canon_and_freshness.py (real_drill_dim_fact, real_rollup_day_fact) |
| Población drill | backend/scripts/populate_real_drill_from_hourly_chain.py |
| Pipeline | backend/scripts/run_pipeline_refresh_and_audit.py, refresh_real_lob_mvs_v2.py |
| Semántica cancelaciones | docs/real_trip_outcome_and_cancellation_semantics.md |

---

**Fin FASE 0.** No se ha modificado código ni datos; este documento sirve como trazabilidad para las fases 1–6.
