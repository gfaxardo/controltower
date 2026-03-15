# Real Operational Architecture — Estado Actual e Impacto

**Fecha**: 2026-03-15  
**Contexto**: Post CT-REAL-HOURLY-FIRST; pre CT-REAL-OPERATIONAL-ARCHITECTURE.

---

## 1. Capas de datos actuales

### 1.1 Capa canónica por viaje (NUEVA — hourly-first)

| Objeto | Tipo | Horizonte | Fuente | Uso |
|--------|------|-----------|--------|-----|
| `ops.v_real_trip_fact_v2` | VIEW | 120d (via canon_120d) | `ops.v_trips_real_canon_120d` | Única capa 1-fila/viaje; outcomes, cancelación, duración. **Source-agnostic** (solo depende del contrato canon_120d). |

### 1.2 Capa horaria (NUEVA)

| Objeto | Tipo | Filas | Fuente | Uso |
|--------|------|-------|--------|-----|
| `ops.mv_real_lob_hour_v2` | MV | ~600K | `v_real_trip_fact_v2` | Agregación horaria; requested/completed/cancelled, revenue, margin, distance, duration, cancel_reason. **No usada aún por ningún endpoint ni UI.** |

### 1.3 Capas derivadas (NUEVAS — desde hourly)

| Objeto | Tipo | Filas | Fuente | Uso |
|--------|------|-------|--------|-----|
| `ops.mv_real_lob_day_v2` | MV | ~59K | `mv_real_lob_hour_v2` | Diaria. **No usada por endpoints ni UI.** |
| `ops.mv_real_lob_week_v3` | MV | ~2.3K | `mv_real_lob_hour_v2` | Semanal. **No usada por endpoints ni UI.** |
| `ops.mv_real_lob_month_v3` | MV | ~746 | `mv_real_lob_hour_v2` | Mensual. **No usada por endpoints ni UI.** |

### 1.4 Capas legacy (activas en API y/o UI)

| Objeto | Tipo | Fuente | Consumido por |
|--------|------|--------|----------------|
| `ops.mv_real_lob_month_v2` | MV | `v_real_trips_with_lob_v2_120d` (solo completados) | `real_lob_v2_data_service`, `real_lob_filters_service`, `RealLOBView` (monthly-v2), drill v2 data |
| `ops.mv_real_lob_week_v2` | MV | Idem | `real_lob_v2_data_service`, filters, `RealLOBView` (weekly-v2), drill v2 data |
| `ops.real_rollup_day_fact` | TABLE | `v_trips_real_canon` (backfill script) | `real_lob_daily_service` → `/real-lob/daily/*` |
| `ops.real_drill_dim_fact` | TABLE | `v_trips_real_canon` | `real_lob_drill_pro_service` → `/real-lob/drill`, `/real-lob/drill/children` |
| `ops.mv_real_drill_dim_agg` | VIEW | `real_drill_dim_fact` | Drill Pro |

---

## 2. Endpoints REAL actuales

| Endpoint | Servicio | Fuente de datos | Observación |
|----------|----------|-----------------|-------------|
| `GET /ops/real-lob/monthly` | real_lob_service | mv_real_trips_by_lob_month (legacy) | Legacy |
| `GET /ops/real-lob/weekly` | real_lob_service | mv_real_trips_by_lob_week (legacy) | Legacy |
| `GET /ops/real-lob/monthly-v2` | real_lob_service_v2 | mv_real_lob_month_v2 | Activo; no hourly-first |
| `GET /ops/real-lob/weekly-v2` | real_lob_service_v2 | mv_real_lob_week_v2 | Activo; no hourly-first |
| `GET /ops/real-lob/filters` | real_lob_filters_service | mv_real_lob_month_v2, week_v2 | Activo |
| `GET /ops/real-lob/v2/data` | real_lob_v2_data_service | mv_real_lob_month_v2, week_v2 | Activo; agg_level, totales |
| `GET /ops/real-lob/drill` | real_lob_drill_pro_service | mv_real_drill_dim_agg, real_drill_dim_fact | Activo; no hourly-first |
| `GET /ops/real-lob/drill/children` | real_lob_drill_pro_service | Idem | Activo |
| `GET /ops/real-lob/drill/parks` | real_lob_drill_pro_service | Idem | Activo |
| `GET /ops/real-lob/daily/summary` | real_lob_daily_service | real_rollup_day_fact | Activo; sin outcomes/cancelación/duración |
| `GET /ops/real-lob/daily/comparative` | real_lob_daily_service | real_rollup_day_fact | Activo |
| `GET /ops/real-lob/daily/table` | real_lob_daily_service | real_rollup_day_fact | Activo |
| `GET /ops/real-lob/comparatives/weekly` | comparatives | weekly | WoW |
| `GET /ops/real-lob/comparatives/monthly` | comparatives | monthly | MoM |

**No existen hoy**:
- Endpoints que lean de `mv_real_lob_hour_v2`, `mv_real_lob_day_v2`, `mv_real_lob_week_v3`, `mv_real_lob_month_v3`.
- Endpoints operativos: today, yesterday, this week (snapshot).
- Vista por hora del día (hourly view).
- Vista de cancelaciones / fricción (top motivos, por hora/zona/servicio).
- Comparativos operativos (hoy vs ayer, vs mismo día semana pasada, vs promedio 4 lunes, etc.).

---

## 3. Frontend: tabs y subvistas

### 3.1 Tab Real (mainNav)

- **Componente principal**: `RealLOBDrillView`.
- **Subvistas internas**: `subView = 'drill' | 'daily'`.
  - **Drill**: timeline mensual/semanal por país; doble click → LOB o Park; usa `getRealLobDrillPro`, `getRealLobDrillProChildren`, `getRealLobDrillParks`, comparatives weekly/monthly.
  - **Daily**: `RealLOBDailyView` → día, comparativo D-1, mismo día semana pasada, promedio 4 semanas; usa `getRealLobDailySummary`, `getRealLobDailyComparative`, `getRealLobDailyTable`.

### 3.2 Otras referencias REAL

- `RealLOBView`: usado en algún flujo (Observabilidad / Modo Ejecutivo); llama monthly-v2, weekly-v2.
- `ExecutiveSnapshotView`: KPIs plan vs real (getRealMonthlySplit, etc.).
- `RealVsProjectionView`: bajo Plan y validación → Real vs Proyección.

### 3.3 Lo que no existe en UI

- Vista “Operativo”: hoy / ayer / esta semana.
- Vista por hora del día (heatmap o tabla por hora).
- Vista día-a-día (day view) con drill ciudad/park/servicio usando day_v2.
- Vista cancelaciones / fricción (top motivos, por hora/zona/servicio).
- Comparativos operativos (“a esta hora vamos X% vs promedio 4 lunes”, etc.).
- Ningún componente que consuma hour_v2, day_v2, week_v3 o month_v3.

---

## 4. Dónde viven cancelaciones, outcomes y duración

- **En el modelo de datos (nuevo)**:
  - `v_real_trip_fact_v2`: trip_outcome_norm, is_completed, is_cancelled, motivo_cancelacion_raw, cancel_reason_norm, cancel_reason_group, trip_duration_seconds, trip_duration_minutes.
  - `mv_real_lob_hour_v2` y `mv_real_lob_day_v2`: requested_trips, completed_trips, cancelled_trips, unknown_outcome_trips, cancellation_rate, completion_rate, cancel_reason_norm, cancel_reason_group, duration_total_minutes, duration_avg_minutes.
- **En API/UI**: en ningún endpoint ni vista actual. La daily usa `real_rollup_day_fact`, que no tiene outcomes ni cancelación ni duración.

---

## 5. Resumen: qué es foco vs legacy

| Capa / Funcionalidad | Estado | Acción deseada |
|----------------------|--------|----------------|
| `v_real_trip_fact_v2` | Nueva, lista | Mantener; único contacto con canon_120d. |
| `mv_real_lob_hour_v2` | Nueva, poblada, no usada | **Foco**: convertir en base de operativo (endpoints + UI). |
| `mv_real_lob_day_v2` | Nueva, poblada, no usada | **Foco**: base para day view y today/yesterday/this week. |
| `mv_real_lob_week_v3` / `month_v3` | Nuevas, pobladas, no usadas | **Foco**: opción de migrar v2/data y comparatives a v3. |
| `mv_real_lob_month_v2` / `week_v2` | Activas en API/UI | **Legacy**: marcar; migrar consumo a v3 cuando esté listo. |
| `real_rollup_day_fact` | Activa (daily) | **Legacy**: daily operativo desde day_v2; mantener compatibilidad o redirigir. |
| `real_drill_dim_fact` / drill Pro | Activas (drill) | **Legacy**: mantener; añadir vista operativa nueva (hour/day/cancel) como principal. |
| Today / Yesterday / This week | No existen | **Crear**: backend + UI desde day_v2/hour_v2. |
| Hourly view | No existe | **Crear**: backend + UI desde hour_v2. |
| Cancellation / Friction view | No existe | **Crear**: backend + UI desde hour_v2/day_v2. |
| Comparativos operativos | Solo WoW/MoM genéricos | **Crear**: hoy vs ayer, vs 4/8 mismos días, misma hora vs histórico. |

---

## 6. Horizonte temporal por capa (explícito)

| Capa | Horizonte | Motivo |
|------|-----------|--------|
| **Source / Fact** | Definido por la vista canónica de entrada | Hoy: `v_trips_real_canon_120d` = 120 días (operational recent). El **contrato** es source-agnostic; la ventana 120d es decisión de implementación para performance. |
| **Operational recent** | 120 días en implementación actual | Ventana optimizada (índices, sin full scan). Puede ampliarse o duplicarse (ej. fact sin ventana para histórico) sin cambiar contrato. |
| **Aggregated (hour/day/week/month)** | Mismo que la capa que las alimenta | Hour/day/week/month v2/v3 se construyen desde fact → hourly, por tanto mismo horizonte efectivo (120d) hasta que se cambie la política de la capa fact/canon. |

Este documento se actualizará al consolidar la arquitectura operativa y al marcar legacy en `real_legacy_map.md`.
