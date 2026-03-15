# Real — Mapa de Legacy

**Objetivo**: Dejar claro qué es camino principal (operational hourly-first) y qué queda como legacy o avanzado.

---

## Camino principal (Operativo)

| Capa / Componente | Descripción |
|-------------------|-------------|
| **UI** | Tab Real → sub-tab **Operativo** (por defecto). Incluye: Hoy/Ayer/Semana, Comparativos, Por día, Por hora, Cancelaciones. |
| **Endpoints** | `GET /ops/real-operational/snapshot`, `/day-view`, `/hourly-view`, `/cancellations`, `/comparatives/today-vs-yesterday`, etc. |
| **Fuente de datos** | `ops.mv_real_lob_day_v2`, `ops.mv_real_lob_hour_v2` (derivadas de `v_real_trip_fact_v2`). |
| **Servicios** | `real_operational_service`, `real_operational_comparatives_service`. |

---

## Legacy / Avanzado (secundario)

| Artefacto | Tipo | Reemplazado por / Notas |
|-----------|------|--------------------------|
| **UI** | Tab Real → sub-tab **Drill y diario (avanzado)** | Contenido: RealLOBDrillView (drill mensual/semanal + vista diaria). Mantenido para usuarios que ya lo usan; no es el camino principal de decisión. |
| `GET /ops/real-lob/monthly` | Endpoint | Lee `mv_real_trips_by_lob_month` (legacy). Preferir datos operativos o v2/v3. |
| `GET /ops/real-lob/weekly` | Endpoint | Idem legacy. |
| `GET /ops/real-lob/monthly-v2` | Endpoint | Lee `mv_real_lob_month_v2` (agregado directo desde vista 120d, no desde hourly). Mantener por compatibilidad; migración futura a month_v3. |
| `GET /ops/real-lob/weekly-v2` | Endpoint | Lee `mv_real_lob_week_v2`. Idem. |
| `GET /ops/real-lob/v2/data` | Endpoint | Lee month_v2 y week_v2. Contrato usado por RealLOBView / drill. **Legacy**: en el futuro puede apuntar a week_v3/month_v3. |
| `GET /ops/real-lob/filters` | Endpoint | Lee month_v2/week_v2 para dropdowns. **Legacy** si se migra filtros a capa v3. |
| `GET /ops/real-lob/drill` | Endpoint | Drill Pro desde `real_drill_dim_fact` / `mv_real_drill_dim_agg`. **Legacy**: no hourly-first. |
| `GET /ops/real-lob/drill/children` | Endpoint | Idem. |
| `GET /ops/real-lob/drill/parks` | Endpoint | Idem. |
| `GET /ops/real-lob/daily/*` | Endpoints | Vista diaria desde `real_rollup_day_fact`. **Legacy**: sin outcomes/cancelación/duración; la vista operativa Por día usa `mv_real_lob_day_v2`. |
| `GET /ops/real-lob/comparatives/weekly` | Endpoint | WoW desde capa legacy. Comparativos operativos están en `/real-operational/comparatives/*`. |
| `GET /ops/real-lob/comparatives/monthly` | Endpoint | MoM desde capa legacy. |
| **MVs** | `ops.mv_real_lob_month_v2`, `ops.mv_real_lob_week_v2` | Siguen existiendo y alimentando endpoints legacy. No eliminadas; marcadas como legacy. La agregación principal es hour_v2 → day_v2 → week_v3, month_v3. |
| **Tablas** | `ops.real_rollup_day_fact`, `ops.real_drill_dim_fact` | Usadas por daily y drill. Legacy; no se eliminan mientras los endpoints sigan activos. |

---

## Deprecación futura (opcional)

- Migrar `real_lob_v2_data_service` a leer de `mv_real_lob_month_v3` y `mv_real_lob_week_v3` cuando se quiera unificar todo en hourly-first.
- Unificar filtros (filters) con dimensiones derivadas de day_v2/hour_v2 si se desea una sola fuente.
- Mantener drill Pro y daily legacy hasta que no haya dependencias; entonces marcar como deprecated y redirigir a Operativo.

---

## Resumen

- **Principal**: Operativo (RealOperationalView + endpoints `/real-operational/*`) y capas hour_v2, day_v2, week_v3, month_v3.
- **Legacy**: Drill Pro, vista diaria antigua, monthly-v2, weekly-v2, v2/data, filters y MVs month_v2/week_v2, real_rollup_day_fact, real_drill_dim_fact. Todo ello accesible desde "Drill y diario (avanzado)" o endpoints existentes, sin eliminación.
