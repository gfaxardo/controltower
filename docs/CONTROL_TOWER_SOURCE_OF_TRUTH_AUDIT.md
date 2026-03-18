# Control Tower — Auditoría operativa: fuente de verdad y gobierno de datos

**Modo:** Auditoría operativa. Sin rediseño UI, sin tocar batch, sin features nuevas.  
**Objetivo:** Determinar con evidencia exacta si Control Tower usa una sola fuente de verdad o varias cadenas, y documentar qué pantalla usa qué grano, vista y freshness real.

---

## Resumen ejecutivo

| Pregunta | Respuesta |
|----------|-----------|
| **¿Existe hoy una sola fuente de verdad para REAL?** | **NO** |
| **¿Cuántas cadenas reales existen?** | **Al menos 3:** (1) hourly-first canónica, (2) legacy mensual/semanal `mv_real_trips_*`, (3) Real LOB legacy `mv_real_trips_by_lob_*`. |
| **¿Qué pantallas usan cada una?** | Ver matriz y sección Fase 2. |
| **¿Cuál debe ser la canónica?** | La cadena **hourly-first** (v_trips_real_canon_120d → v_real_trip_fact_v2 → day_v2 → rollup → real_drill_dim_fact). |
| **¿Qué pantallas pueden estar leyendo data vieja o universo incompleto?** | Resumen, Plan vs Real (mensual y semanal), Real vs Proyección y cualquier vista que dependa solo de `mv_real_trips_monthly` / `mv_real_trips_weekly` si no se refrescan o están desalineadas con la cadena hourly-first. |

**Veredicto formal:** `SINGLE_SOURCE_OF_TRUTH = NO`

---

## FASE 1 — Matriz de trazabilidad

Para cada pantalla solicitada: pantalla, endpoint(s), servicio backend, vista/MV/tabla base, grano, cadena, freshness real (max fecha/periodo), estado.

### 1. Performance > Resumen

| Campo | Valor |
|-------|--------|
| **Pantalla** | Performance > Resumen |
| **Componente** | `ExecutiveSnapshotView` → `KPICards` |
| **Endpoint(s)** | `GET /ops/real/monthly`, `GET /ops/plan/monthly` (y por país PE/CO para revenue); opcionalmente `GET /core/summary/monthly` (que usa plan + real summary). |
| **Servicio backend** | `plan_real_split_service.get_real_monthly`, `plan_real_split_service.get_plan_monthly`; `real_normalizer_service.get_real_monthly_summary` vía `real_repo.get_real_monthly_data` para `/real/summary/monthly`. |
| **Vista/MV/tabla base** | **Real:** `ops.mv_real_trips_monthly`. **Plan:** `ops.v_plan_trips_monthly_latest`. |
| **Grano** | **monthly** |
| **Cadena** | **Legacy** (agregación directa desde trips, no desde la cadena hourly-first 120d). |
| **Freshness real** | Depende de `REFRESH MATERIALIZED VIEW ops.mv_real_trips_monthly`. Consultar `ops.data_freshness_audit` dataset `real_lob` o equivalente; si no existe, `MAX(month)` sobre `ops.mv_real_trips_monthly`. |
| **Estado** | **LEGACY** — No es la cadena canónica hourly-first. Riesgo de desalineación con Operación > Drill y Performance > Real (diario). |

---

### 2. Performance > Plan vs Real

| Campo | Valor |
|-------|--------|
| **Pantalla** | Performance > Plan vs Real |
| **Componente** | `MonthlySplitView`, `WeeklyPlanVsRealView` |
| **Endpoint(s)** | **Mensual:** `GET /ops/plan-vs-real/monthly`, `GET /ops/plan-vs-real/alerts`, `GET /ops/real/monthly`, `GET /ops/plan/monthly`, `GET /ops/compare/overlap-monthly`. **Semanal:** `GET /phase2b/weekly/plan-vs-real`, `GET /phase2b/weekly/alerts`. |
| **Servicio backend** | `plan_vs_real_service` (monthly), `phase2b_weekly_service` (weekly). |
| **Vista/MV/tabla base** | **Mensual:** `ops.v_plan_vs_real_realkey_final` (real side suele provenir de agregaciones tipo `mv_real_trips_monthly` o equivalente en la definición de la vista). **Semanal:** `ops.v_plan_vs_real_weekly` → **Real:** `ops.mv_real_trips_weekly`. |
| **Grano** | **monthly** (plan-vs-real mensual), **weekly** (plan-vs-real semanal). |
| **Cadena** | **Legacy** — Plan vs Real mensual y semanal dependen de vistas/MVs que no son la cadena hourly-first canónica. |
| **Freshness real** | Mensual: según vista final (real). Semanal: `MAX(week_start)` sobre `ops.mv_real_trips_weekly` o según `data_freshness_audit`. |
| **Estado** | **LEGACY** — Coherencia con Resumen (misma cadena legacy), pero no con Real (diario) ni con Operación > Drill. |

---

### 3. Performance > Real (diario)

| Campo | Valor |
|-------|--------|
| **Pantalla** | Performance > Real (diario) |
| **Componente** | `RealOperationalView` |
| **Endpoint(s)** | `GET /ops/real-operational/snapshot`, `GET /ops/real-operational/day-view`, `GET /ops/real-operational/hourly-view`, `GET /ops/real-operational/cancellations`, `GET /ops/real-operational/comparatives/today-vs-yesterday`, `today-vs-same-weekday`, `current-hour-vs-historical`, `this-week-vs-comparable`. |
| **Servicio backend** | `real_operational_service`, `real_operational_comparatives_service`. |
| **Vista/MV/tabla base** | `ops.mv_real_lob_day_v2`, `ops.mv_real_lob_hour_v2`. Ambas alimentadas por la cadena hourly-first (v_real_trip_fact_v2 → hourly → day). |
| **Grano** | **hourly**, **daily** (day = trip_date). |
| **Cadena** | **Hourly-first canónica** |
| **Freshness real** | `MAX(trip_date)` en `mv_real_lob_day_v2`; `MAX(trip_hour)` en `mv_real_lob_hour_v2`. Registrable en `ops.data_freshness_audit` como `real_operational`. |
| **Estado** | **CANONICAL** — Fuente correcta para “real operativo”. |

---

### 4. Operación > Drill

| Campo | Valor |
|-------|--------|
| **Pantalla** | Operación > Drill (Real LOB Drill) |
| **Componente** | `RealLOBDrillView` (drill PRO + opcional legacy; también pestaña diaria `RealLOBDailyView`) |
| **Endpoint(s)** | `GET /ops/real-lob/drill`, `GET /ops/real-lob/drill/children`, `GET /ops/real-lob/drill/parks`, `GET /ops/period-semantics`, `GET /ops/real-lob/comparatives/weekly`, `GET /ops/real-lob/comparatives/monthly`; opcional `GET /ops/real-margin-quality`. Diario: `GET /ops/real-lob/daily/summary`, `GET /ops/real-lob/daily/comparative`, `GET /ops/real-lob/daily/table`. |
| **Servicio backend** | `real_lob_drill_pro_service`, `comparative_metrics_service`, `period_semantics_service`, `real_lob_daily_service`, `real_margin_quality_service`. |
| **Vista/MV/tabla base** | **Drill principal:** `ops.mv_real_drill_dim_agg` (vista sobre `ops.real_drill_dim_fact`), `ops.v_real_data_coverage`, `ops.real_rollup_day_fact` (vista sobre `mv_real_lob_day_v2`), `ops.v_real_lob_coverage`; children: `ops.mv_real_drill_service_by_park`, `ops.mv_real_drill_dim_agg`. **Comparativos:** `ops.real_rollup_day_fact`. **Diario:** `ops.real_rollup_day_fact` / day_v2. **Margin quality:** `ops.v_real_trip_fact_v2`. |
| **Grano** | **daily**, **weekly**, **monthly** (desde fact table / rollup poblado desde hourly-first). |
| **Cadena** | **Hourly-first canónica** (real_drill_dim_fact y real_rollup_day_fact alimentados desde cadena 120d / day_v2). |
| **Freshness real** | `real_rollup_day_fact`: `MAX(trip_day)`; `real_drill_dim_fact`: max period_start por grano. `v_real_data_coverage`: last_trip_date, last_month_with_data, last_week_with_data. |
| **Estado** | **CANONICAL** — Drill PRO y comparativos/diario usan la misma cadena. |

---

### 5. Proyección > Real vs Proyección

| Campo | Valor |
|-------|--------|
| **Pantalla** | Proyección > Real vs Proyección |
| **Componente** | `RealVsProjectionView` |
| **Endpoint(s)** | `GET /ops/real-vs-projection/overview`, `GET /ops/real-vs-projection/dimensions`, `GET /ops/real-vs-projection/mapping-coverage`, `GET /ops/real-vs-projection/real-metrics`, `GET /ops/real-vs-projection/projection-template-contract` (y opc. system-segmentation-view, projection-segmentation-view). |
| **Servicio backend** | `real_vs_projection_service`. |
| **Vista/MV/tabla base** | **Métricas reales:** `ops.v_real_metrics_monthly` (definida en migración 097 desde **ops.mv_real_trips_monthly**). **Proyección:** `ops.projection_upload_staging`, `ops.projection_dimension_mapping`. Comparativos: `ops.v_real_vs_projection_system_segmentation`, `ops.v_real_vs_projection_projection_segmentation`. |
| **Grano** | **monthly** (real). |
| **Cadena** | **Legacy** — Real vs Proyección usa `v_real_metrics_monthly` → `mv_real_trips_monthly`, no la cadena hourly-first. |
| **Freshness real** | Mismo que `mv_real_trips_monthly` (mensual). |
| **Estado** | **LEGACY** — Puede mostrar real desalineado con Drill y Real (diario). Completa a nivel de vista/tabla; el riesgo es coherencia con el resto del sistema. |

---

### 6. Drivers > Supply

| Campo | Valor |
|-------|--------|
| **Pantalla** | Drivers > Supply |
| **Componente** | `SupplyView` |
| **Endpoint(s)** | `GET /ops/supply/geo`, `GET /ops/supply/overview-enhanced`, `GET /ops/supply/composition`, `GET /ops/supply/migration`, `GET /ops/supply/migration/drilldown`, `GET /ops/supply/migration/weekly-summary`, `GET /ops/supply/migration/critical`, `GET /ops/supply/alerts`, `GET /ops/supply/alerts/drilldown`, `GET /ops/supply/freshness`, `GET /ops/supply/definitions`, `GET /ops/supply/segments/config`. |
| **Servicio backend** | `supply_service`. |
| **Vista/MV/tabla base** | `dim.v_geo_park`, `ops.v_dim_park_resolved`; `ops.mv_supply_weekly`, `ops.mv_supply_monthly`; `ops.mv_supply_segments_weekly`; `ops.mv_supply_alerts_weekly`, `ops.mv_supply_segment_anomalies_weekly`, `ops.v_supply_alert_drilldown`; migración: `ops.mv_driver_segments_weekly`, `ops.mv_supply_segments_weekly`. |
| **Grano** | **weekly**, **monthly** (supply no es “real de viajes”; es supply de conductores). |
| **Cadena** | **Propia** — Supply se basa en driver lifecycle / segmentos (mv_driver_weekly_stats, etc.), no en la cadena real de viajes hourly-first. No es “legacy real” ni “canónica real”; es otra fuente de verdad para supply. |
| **Freshness real** | `GET /ops/supply/freshness` y `ops.supply_refresh_log`; MVs: `MAX(week_start)` / `MAX(month_start)` en mv_supply_weekly / mv_supply_monthly. |
| **Estado** | **CANONICAL** para su dominio (supply). No mezcla con la cadena real de viajes. |

---

### 7. Drivers > Ciclo de vida

| Campo | Valor |
|-------|--------|
| **Pantalla** | Drivers > Ciclo de vida |
| **Componente** | `DriverLifecycleView` |
| **Endpoint(s)** | `GET /ops/driver-lifecycle/parks`, `GET /ops/driver-lifecycle/weekly`, `GET /ops/driver-lifecycle/monthly`, `GET /ops/driver-lifecycle/series`, `GET /ops/driver-lifecycle/summary`, `GET /ops/driver-lifecycle/drilldown`, `GET /ops/driver-lifecycle/parks-summary`, `GET /ops/driver-lifecycle/base-metrics`, `GET /ops/driver-lifecycle/base-metrics-drilldown`, `GET /ops/driver-lifecycle/cohorts`, `GET /ops/driver-lifecycle/cohort-drilldown`. |
| **Servicio backend** | `driver_lifecycle_service`. |
| **Vista/MV/tabla base** | `ops.mv_driver_lifecycle_base`, `ops.mv_driver_weekly_stats`, `ops.mv_driver_monthly_stats`, `ops.mv_driver_lifecycle_weekly_kpis`, `ops.mv_driver_lifecycle_monthly_kpis`, `ops.v_driver_weekly_churn_reactivation`; cohortes: `ops.mv_driver_cohorts_weekly`, `ops.mv_driver_cohort_kpis`; parks: `ops.v_dim_park_resolved`, `dim.dim_park`. Fuente viajes: `public.trips_unified` (trips_all ∪ trips_2026) → `v_driver_lifecycle_trips_completed`. |
| **Grano** | **weekly**, **monthly** (y driver-level). |
| **Cadena** | **Propia** — Driver lifecycle (trips_unified + drivers/parks). No es la cadena real hourly-first de Control Tower; es coherente para “ciclo de vida” pero distinta fuente. |
| **Freshness real** | Según refresh de MVs de lifecycle; típicamente `MAX(week_start)` / `MAX(month_start)` en las MVs de KPIs. |
| **Estado** | **CANONICAL** para su dominio. No mezcla con la cadena real de viajes. |

---

### 8. Riesgo > Alertas de conducta (behavior alerts)

| Campo | Valor |
|-------|--------|
| **Pantalla** | Riesgo > Alertas de conducta |
| **Componente** | `BehavioralAlertsView` |
| **Endpoint(s)** | `GET /ops/behavior-alerts/summary`, `GET /ops/behavior-alerts/insight`, `GET /ops/behavior-alerts/drivers`, `GET /ops/behavior-alerts/driver-detail`, `GET /ops/behavior-alerts/export`. Geo: `GET /ops/supply/geo`. |
| **Servicio backend** | `behavior_alerts_service`. |
| **Vista/MV/tabla base** | `ops.v_driver_behavior_alerts_weekly` (o `ops.mv_driver_behavior_alerts_weekly`); `ops.v_driver_last_trip`. |
| **Grano** | **weekly** (driver-week). |
| **Cadena** | **Propia** — Alertas de conducta (basadas en segmentos/actividad driver). No es la cadena real de viajes hourly-first. |
| **Freshness real** | `MAX(week_start)` en vista/MV de alertas. Timeout 600s en servicio (vista puede ser pesada). |
| **Estado** | **Completa** a nivel de vistas/API. Si la vista no existe o falla, la pantalla queda rota o lenta. Ver Fase 4. |

---

### 9. Riesgo > Fuga de flota (leakage)

| Campo | Valor |
|-------|--------|
| **Pantalla** | Riesgo > Fuga de flota |
| **Componente** | `FleetLeakageView` |
| **Endpoint(s)** | `GET /ops/leakage/summary`, `GET /ops/leakage/drivers`, `GET /ops/leakage/export`. Geo: `GET /ops/supply/geo`. |
| **Servicio backend** | `leakage_service`. |
| **Vista/MV/tabla base** | `ops.v_fleet_leakage_snapshot` (fuente: mv_driver_segments_weekly, v_driver_last_trip, dim.v_geo_park, v_dim_driver_resolved). |
| **Grano** | Snapshot por conductor (ref_week). |
| **Cadena** | **Propia** — Leakage (conductores en riesgo). No es la cadena real de viajes. |
| **Freshness real** | Depende del refresh de `v_fleet_leakage_snapshot` y sus fuentes (segmentos, last_trip). |
| **Estado** | **Completa** si la vista existe y está poblada. Ver Fase 4. |

---

## FASE 2 — ¿Existe una sola fuente de verdad para REAL?

### 2.1 Respuesta directa

1. **¿Existe hoy una sola fuente de verdad para REAL?**  
   **No.** El sistema usa varias cadenas para “real”:
   - **Cadena hourly-first canónica:** `v_trips_real_canon_120d` → `v_real_trip_fact_v2` → `mv_real_lob_hour_v2` / `mv_real_lob_day_v2` → `real_rollup_day_fact` → `real_drill_dim_fact` / `mv_real_drill_dim_agg`. Usada por: **Performance > Real (diario)**, **Operación > Drill** (drill PRO, comparativos, diario), **real-margin-quality**.
   - **Cadena legacy mensual/semanal:** `ops.mv_real_trips_monthly`, `ops.mv_real_trips_weekly`. Usada por: **Performance > Resumen**, **Performance > Plan vs Real** (v_plan_vs_real_realkey_final y v_plan_vs_real_weekly), **Proyección > Real vs Proyección** (v_real_metrics_monthly → mv_real_trips_monthly).
   - **Cadena legacy Real LOB (sin 120d):** `ops.mv_real_trips_by_lob_month`, `ops.mv_real_trips_by_lob_week` → usadas por endpoints legacy `/ops/real-lob/monthly` y `/ops/real-lob/weekly` (no v2). La UI principal del drill usa drill PRO (hourly-first); las vistas legacy pueden seguir usadas por otros consumidores o rutas alternativas.

2. **¿Cuántas cadenas reales existen?**  
   **Al menos 3:** (1) hourly-first canónica, (2) legacy mensual/semanal (`mv_real_trips_monthly` / `mv_real_trips_weekly`), (3) legacy Real LOB (`mv_real_trips_by_lob_*`).

3. **¿Qué pantallas usan cada una?**  
   - **Hourly-first canónica:** Performance > Real (diario), Operación > Drill (principal y diario), real-margin-quality (lectura desde v_real_trip_fact_v2).  
   - **Legacy mensual/semanal:** Resumen (KPIs), Plan vs Real (mensual y semanal), Real vs Proyección (métricas reales).  
   - **Legacy Real LOB:** Rutas `/ops/real-lob/monthly` y `/ops/real-lob/weekly` (no v2); en la UI actual el foco es v2/drill PRO.

4. **¿Cuál debe ser la canónica?**  
   La cadena **hourly-first** (origen en `v_trips_real_canon_120d` / `v_real_trip_fact_v2`, día/hora → rollup → drill). Es la única que soporta grano horario/diario y está documentada como arquitectura objetivo.

5. **¿Qué pantallas pueden estar leyendo data vieja o universo incompleto?**  
   - Cualquier pantalla que dependa **solo** de `mv_real_trips_monthly` o `mv_real_trips_weekly`: **Resumen**, **Plan vs Real**, **Real vs Proyección**.  
   - Riesgo: si esas MVs no se refrescan con la misma frecuencia o reglas que la cadena hourly-first, o si el universo (país/ciudad/LOB) difiere (p. ej. 120d vs todo histórico), la UI puede mostrar real **viejo**, **incompleto** o **inconsistente** respecto a Performance > Real (diario) y Operación > Drill.

---

## FASE 3 — Validación de freshness real

Para cada fuente usada por la UI que aporta “real”, obtener (vía consultas a BD o `ops.data_freshness_audit`):

| Fuente (vista/MV/tabla) | Grano | Métrica freshness sugerida | Dónde consultar |
|-------------------------|-------|----------------------------|------------------|
| `ops.mv_real_lob_day_v2` | daily | max(trip_date) | SELECT MAX(trip_date) FROM ops.mv_real_lob_day_v2 |
| `ops.mv_real_lob_hour_v2` | hourly | max(trip_hour) | SELECT MAX(trip_hour) FROM ops.mv_real_lob_hour_v2 |
| `ops.real_rollup_day_fact` | daily | max(trip_day) | SELECT MAX(trip_day) FROM ops.real_rollup_day_fact |
| `ops.real_drill_dim_fact` | week/month | max(period_start) por breakdown | Por period_type y breakdown |
| `ops.mv_real_trips_monthly` | monthly | max(month) | SELECT MAX(month) FROM ops.mv_real_trips_monthly |
| `ops.mv_real_trips_weekly` | weekly | max(week_start) | Según definición de la MV (columna de semana) |
| `ops.v_real_metrics_monthly` | monthly | Igual que mv_real_trips_monthly | Vista sobre mv_real_trips_monthly |
| `ops.v_real_trip_fact_v2` | viaje (día) | max(trip_date) | SELECT MAX(trip_date) FROM ops.v_real_trip_fact_v2 |

**Distinción por grano:**

- **Hourly real:** `mv_real_lob_hour_v2` (max trip_hour).  
- **Daily real:** `mv_real_lob_day_v2` o `real_rollup_day_fact` (max trip_date / trip_day).  
- **Weekly real (canónica):** derivado de day → real_drill_dim_fact week_start o MVs week_v3.  
- **Monthly real (canónica):** derivado de day → real_drill_dim_fact month_start o MVs month_v3.  
- **Monthly real (legacy):** `mv_real_trips_monthly` (max month).  
- **Weekly real (legacy):** `mv_real_trips_weekly` (max week_start o equivalente).

Si existe `ops.data_freshness_audit` con `dataset_name` y `derived_max_date`, usarlo como referencia oficial; si no, las consultas anteriores dan la evidencia de freshness por fuente.

---

## FASE 4 — Features incompletas o rotas

### real-margin-quality

- **Estado:** **Completa** a nivel de backend y vistas. Lee `ops.v_real_trip_fact_v2` (cadena hourly-first) en ventana reciente (días configurables).  
- **Riesgo:** Si `v_real_trip_fact_v2` no tiene datos (p. ej. 120d vacío o vista rota), el endpoint puede devolver vacío o errores. No depende de vistas inexistentes; la vista está en la migración 099.  
- **Recomendación:** Mantener en la UI; es coherente con la cadena canónica. Monitorear que la ventana 120d esté poblada.

### real-vs-projection

- **Estado:** **Completa** en vistas y API. Usa `ops.v_real_metrics_monthly` (desde `mv_real_trips_monthly`), `projection_upload_staging`, `projection_dimension_mapping`.  
- **Riesgo:** Real viene de **legacy** (mv_real_trips_monthly), no de hourly-first. Puede haber desalineación con Drill y Real (diario).  
- **Recomendación:** No sacar de navegación; documentar que “real” en esta pantalla es legacy y, a medio plazo, alimentar desde la cadena canónica (p. ej. mes desde real_drill_dim_fact o month_v3) para una sola fuente de verdad.

### behavior-alerts

- **Estado:** **Completa** si existen `ops.v_driver_behavior_alerts_weekly` y `ops.mv_driver_behavior_alerts_weekly`. El servicio usa la vista (timeout 600s).  
- **Riesgo:** Si la vista no existe o la query es muy pesada, la pantalla puede fallar o ser inusable.  
- **Recomendación:** Verificar en BD que la vista/MV existan. Si son inestables, considerar sacar temporalmente de la navegación principal o mostrar solo resumen hasta optimizar.

### leakage

- **Estado:** **Completa** si existe `ops.v_fleet_leakage_snapshot` y sus dependencias.  
- **Recomendación:** Verificar existencia y población. Si está estable, mantener; si no, etiquetar como “en revisión” o sacar temporalmente hasta estabilizar.

---

## FASE 5 — Entrega ejecutiva

### 1. Documento

- Este archivo: `docs/CONTROL_TOWER_SOURCE_OF_TRUTH_AUDIT.md`.

### 2. Matriz resumida (pantalla → endpoint → vista → grano → cadena → freshness)

| Pantalla | Endpoint(s) principal(es) | Vista/MV base (real) | Grano | Cadena | Freshness |
|----------|----------------------------|----------------------|-------|--------|-----------|
| Performance > Resumen | /ops/real/monthly, /ops/plan/monthly | mv_real_trips_monthly | monthly | Legacy | MAX(month) MV |
| Performance > Plan vs Real | /ops/plan-vs-real/monthly, /phase2b/weekly/plan-vs-real | v_plan_vs_real_realkey_final, mv_real_trips_weekly | monthly, weekly | Legacy | Según vista / MV |
| Performance > Real | /ops/real-operational/* | mv_real_lob_day_v2, mv_real_lob_hour_v2 | daily, hourly | Hourly-first canónica | MAX(trip_date), MAX(trip_hour) |
| Operación > Drill | /ops/real-lob/drill, /ops/real-lob/drill/children, comparatives, daily | mv_real_drill_dim_agg, real_rollup_day_fact, real_drill_dim_fact | daily, weekly, monthly | Hourly-first canónica | v_real_data_coverage, MAX(period_start) |
| Proyección > Real vs Proyección | /ops/real-vs-projection/* | v_real_metrics_monthly → mv_real_trips_monthly | monthly | Legacy | MAX(month) |
| Drivers > Supply | /ops/supply/* | mv_supply_weekly, mv_supply_monthly, mv_supply_segments_weekly, etc. | weekly, monthly | Propia (supply) | supply/freshness, supply_refresh_log |
| Drivers > Ciclo de vida | /ops/driver-lifecycle/* | mv_driver_lifecycle_*, mv_driver_weekly_stats, etc. | weekly, monthly | Propia (lifecycle) | MAX(week_start/month_start) MVs |
| Riesgo > Alertas de conducta | /ops/behavior-alerts/* | v_driver_behavior_alerts_weekly | weekly | Propia | MAX(week_start) |
| Riesgo > Fuga de flota | /ops/leakage/* | v_fleet_leakage_snapshot | snapshot | Propia | Según refresh |

### 3. Veredicto

- **SINGLE_SOURCE_OF_TRUTH = NO**  
  El Control Tower **no** usa una sola fuente de verdad para REAL. Conviven la cadena **hourly-first canónica** y las cadenas **legacy** (mv_real_trips_monthly, mv_real_trips_weekly y, en su caso, mv_real_trips_by_lob_*).

### 4. Lista de pantallas por estado

- **Seguras (canónicas o dominio propio estable):**  
  Performance > Real (diario), Operación > Drill, Drivers > Supply, Drivers > Ciclo de vida, real-margin-quality (backend).
- **Legacy (real no canónico):**  
  Performance > Resumen, Performance > Plan vs Real, Proyección > Real vs Proyección.
- **Riesgo de rotas o inestables (validar en BD):**  
  Riesgo > Alertas de conducta (vista pesada o faltante), Riesgo > Fuga de flota (si la vista no existe o no se refresca).

### 5. Recomendaciones de gobernanza

- **Canónico:**  
  - Definir como **única fuente de verdad para real de viajes** la cadena **hourly-first**: `v_trips_real_canon_120d` → `v_real_trip_fact_v2` → `mv_real_lob_hour_v2` / `mv_real_lob_day_v2` → `real_rollup_day_fact` → `real_drill_dim_fact` / agregados week/month.  
  - Todas las pantallas que muestren “real” de viajes deberían, a medio plazo, leer de esta cadena (o de vistas/MVs derivadas explícitas de ella).
- **Legacy:**  
  - Etiquetar como **legacy** y documentar: `ops.mv_real_trips_monthly`, `ops.mv_real_trips_weekly`, vistas que dependan de ellas (`v_plan_vs_real_realkey_final`, `v_plan_vs_real_weekly`, `v_real_metrics_monthly`).  
  - Mantener refrescos y soporte hasta migrar consumidores a la cadena canónica; no añadir nuevos consumidores a estas fuentes.
- **Salida temporal de UI:**  
  - Si **behavior-alerts** o **leakage** fallan de forma recurrente por vistas faltantes o timeouts: mover a una sección “En revisión” o sacar de la navegación principal hasta tener vistas/MVs estables y rápidas.

---

*Auditoría operativa. No se ha modificado UI, batch ni lógica de negocio; solo documentación y evidencia.*
