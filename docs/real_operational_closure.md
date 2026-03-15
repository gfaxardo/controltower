# CT-REAL-OPERATIONAL-ARCHITECTURE — Cierre

**Fecha**: 2026-03-15  
**Estado**: CERRADO ✓

---

## A. Qué necesidad de negocio quedó resuelta

- **Lectura operativa inmediata**: Hoy, ayer, esta semana con pedidos, completados, cancelados, revenue, margin, duración y tasas.
- **Vista por día**: Desempeño por día con drill por ciudad/park/lob/servicio.
- **Vista por hora del día**: Desempeño por hora (0-23) con las mismas métricas y drill.
- **Cancelaciones / fricción**: Top motivos de cancelación por razón, grupo, hora, ciudad, park o servicio.
- **Comparativos accionables**: Hoy vs ayer; hoy vs promedio últimos 4 mismos días de semana; hora actual vs mismo tramo histórico; esta semana vs semanas anteriores. Incluye variación en pedidos, completados, cancelaciones, revenue, margin, cancel rate y duración.
- **Arquitectura no atada a tablas crudas**: Day/week/month derivan de hourly; sistema listo para cambiar la fuente base.
- **UI unificada**: Lo nuevo (Operativo) es la vista principal del tab Real; lo antiguo (Drill y diario) queda en sub-tab "avanzado" y documentado como legacy.

---

## B. Qué arquitectura nueva quedó

- **Source / Fact**: `ops.v_trips_real_canon_120d` → `ops.v_real_trip_fact_v2` (1 fila por viaje, source-agnostic).
- **Operational recent**: Ventana 120d en canon_120d; capa fact es la única que toca la fuente granular.
- **Aggregated**: `mv_real_lob_hour_v2` → `mv_real_lob_day_v2`, `mv_real_lob_week_v3`, `mv_real_lob_month_v3`. Day/week/month leen **solo** de hourly.
- **API operativa**: `/ops/real-operational/*` (snapshot, day-view, hourly-view, cancellations, comparatives).
- **UI**: Tab Real → **Operativo** (por defecto) con subvistas: Hoy/Ayer/Semana, Comparativos, Por día, Por hora, Cancelaciones.

---

## C. Qué capa canónica quedó

`ops.v_real_trip_fact_v2`: 1 fila por viaje; incluye trip_id, fechas, trip_hour, trip_outcome_norm, is_completed, is_cancelled, motivo_cancelacion_raw, cancel_reason_norm, cancel_reason_group, country, city, park_id, park_name, real_tipo_servicio_norm, lob_group, segment_tag, gross_revenue, margin_total, distance_km, trip_duration_seconds/minutes. Lee de `ops.v_trips_real_canon_120d` (único punto de contacto con raw).

---

## D. Qué capa horaria quedó

`ops.mv_real_lob_hour_v2`: Agregación por trip_date, trip_hour, country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag, trip_outcome_norm, cancel_reason_norm, cancel_reason_group. Métricas: requested_trips, completed_trips, cancelled_trips, unknown_outcome_trips, gross_revenue, margin_total, distance_total_km, duration_total_minutes, duration_avg_minutes, cancellation_rate, completion_rate. Base para day/week/month y para todas las vistas operativas.

---

## E. Cómo quedaron day/week/month

- **Day**: `ops.mv_real_lob_day_v2` — derivada solo de hourly; usada por snapshot y day-view operativos.
- **Week**: `ops.mv_real_lob_week_v3` — derivada solo de hourly (legacy week_v2 sigue existiendo para endpoints antiguos).
- **Month**: `ops.mv_real_lob_month_v3` — derivada solo de hourly (legacy month_v2 sigue existiendo). Ninguna lee tablas crudas.

---

## F. Cómo quedaron cancelaciones y outcomes

- **Outcomes**: completed, cancelled, other en fact y en todas las agregaciones (hour, day). Métricas: requested_trips, completed_trips, cancelled_trips, unknown_outcome_trips, completion_rate, cancellation_rate.
- **Cancelaciones**: motivo_cancelacion_raw, cancel_reason_norm (normalizado), cancel_reason_group (cliente, conductor, timeout_no_asignado, sistema, duplicado, otro). Disponibles en fact, hourly, day y en endpoint/vista de cancelaciones.

---

## G. Cómo quedó duración de viaje

- **En fact**: trip_duration_seconds, trip_duration_minutes con validación (solo si inicio/fin válidos y diferencia entre 30s y 10h).
- **En agregados**: duration_total_minutes, duration_avg_minutes en hourly y day. Usados en snapshot operativo y en comparativos.

---

## H. Qué comparativos operativos quedaron

- **Hoy vs ayer**: Variación % en pedidos, completados, cancelados, revenue, margin, cancel rate (pp), duración.
- **Hoy vs mismo día de semana**: Promedio últimos 4 mismos días (ej. últimos 4 lunes); mismas variaciones.
- **Hora actual vs histórico**: Misma hora en las últimas 4 semanas; variación en pedidos, completados, cancel rate, revenue.
- **Esta semana vs comparable**: Lunes a hoy vs promedio de las últimas 4 semanas; variaciones. Lógica reutilizable en `real_operational_comparatives_service`.

---

## I. Cómo se refleja en UI

- **Tab Real**: Al entrar se muestra la sub-tab **Operativo** (por defecto).
- **Operativo** incluye: (1) Hoy / Ayer / Esta semana con KPIs; (2) Comparativos (hoy vs ayer, hoy vs mismo día, hora actual vs histórico, semana vs comparable); (3) Por día (tabla últimos 14 días); (4) Por hora (tabla 0–23h últimos 7 días); (5) Cancelaciones (top por grupo de motivo).
- **Drill y diario (avanzado)**: Sub-tab secundaria con RealLOBDrillView (drill mensual/semanal y vista diaria legacy). Marcada como avanzado; no es el camino principal de decisión.

---

## J. Qué quedó en legacy

- **UI**: Contenido de "Drill y diario (avanzado)" (RealLOBDrillView).
- **Endpoints**: `/ops/real-lob/monthly`, `/weekly`, `/monthly-v2`, `/weekly-v2`, `/v2/data`, `/filters`, `/drill`, `/drill/children`, `/drill/parks`, `/daily/*`, `/comparatives/weekly`, `/comparatives/monthly`. Documentados en `docs/real_legacy_map.md`.
- **MVs**: `mv_real_lob_month_v2`, `mv_real_lob_week_v2` (siguen existiendo; no eliminadas).
- **Tablas**: `real_rollup_day_fact`, `real_drill_dim_fact` (usadas por daily y drill legacy). Sin eliminación; compatibilidad mantenida.

---

## K. Cómo queda preparado el sistema para cambiar la fuente base

- **Source contract**: `docs/real_trip_source_contract.md` con columnas mínimas, reglas semánticas, outcomes, cancelaciones, timestamps, revenue/margin/km y procedimiento de onboarding.
- Solo es necesario reemplazar o redefinir la vista de entrada (hoy `v_trips_real_canon_120d`) para apuntar a otra tabla/flota; fact → hourly → day → week → month y todos los endpoints operativos siguen igual.

---

## L. Resultado final de governance

```
OVERALL: OK
fact_view_ok: True
dims_populated: True
canonical_no_dupes: True
hourly_populated: True (599,871)
day_populated: True (59,482)
week_populated: True (2,322)
month_populated: True (746)
cancel_reason_norm_populated: True
trip_duration_reasonable: True
week_no_raw_deps: True
month_no_raw_deps: True
```

---

## M. ¿Quedó cerrado o no?

**SÍ, quedó cerrado.** Se cumple el criterio de éxito:

- Capa canónica por viaje: ✓  
- Capa horaria usable: ✓  
- Day/week/month derivan de hourly: ✓  
- Cancelaciones y duración modeladas: ✓  
- Comparativos operativos implementados: ✓  
- UI refleja lo nuevo (Operativo por defecto): ✓  
- Legacy claramente separado (sub-tab avanzado + real_legacy_map.md): ✓  
- Sistema preparado para cambiar la fuente (source contract): ✓  
- Governance valida correctamente: ✓  
- Todo documentado: ✓  
