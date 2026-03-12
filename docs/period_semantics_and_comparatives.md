# Period Semantics + Comparative Analytics (Weekly / Monthly / Daily)

**Proyecto:** YEGO CONTROL TOWER  
**Fase:** Semántica temporal + comparativos WoW/MoM + vista diaria  
**Estado:** Fase A documentada; Fases B–J en diseño/implementación.

**Nomenclatura comparativa oficial:** MoM (month-over-month), WoW (week-over-week), DoD (day-over-day). Siempre con esta capitalización; nunca MOM, WOW, DOD. Detalle y auditoría: [comparative_semantics_audit.md](comparative_semantics_audit.md).

---

## FASE A — Estado actual de la semántica temporal (mapeo)

### 1. Definición y uso de `week_start` / `week_end` / `month_start`

| Ubicación | Uso |
|-----------|-----|
| **MVs Real LOB** (042, 044) | `week_start` = `DATE_TRUNC('week', fecha_inicio_viaje)::DATE` (lunes ISO). `month_start` = `DATE_TRUNC('month', fecha_inicio_viaje)::DATE`. No existe `week_end` explícito; fin de semana = `week_start + 6`. |
| **real_lob_service** | `get_real_lob_meta()`: `MAX(week_start)` y `MAX(month_start)` desde `ops.mv_real_trips_by_lob_week` / `_month`. Sin `week_start` en weekly devuelve **última semana disponible** (puede ser la semana actual = abierta). |
| **real_lob_service_v2** | Igual: default = `MAX(week_start)` / `MAX(month_start)` desde `ops.mv_real_lob_week_v2` / `_month_v2`. |
| **real_lob_drill_pro_service** | Calendario: `min_week` / `min_month` desde `v_real_data_coverage` hasta `current_week` / `current_month` (`date_trunc('week'|'month', CURRENT_DATE)::date`). Incluye **siempre la semana/mes actual**. |
| **real_drill_service** | `bounds`: `current_month` = primer día del mes actual, `current_week` = lunes de la semana actual (ISO). |
| **Supply** | `week_start` en `mv_supply_segments_weekly`, `mv_driver_weekly_stats`; formato S{week}-{year} vía `supply_definitions.format_iso_week()`. |

- **Conclusión:** Semana = ISO (lunes a domingo). No hay columna `week_end`; se asume `week_start + 6`. Mes = primer día del mes calendario.

### 2. Period labels en backend y UI

| Capa | Formato |
|------|---------|
| **real_lob_service** | `_display_week` → `YYYY-MM-DD`, `_display_month` → `YYYY-MM`. |
| **Supply** | `format_iso_week(week_start)` → `S{week}-{year}` (ej. S6-2026). |
| **Drill PRO** | `period_label` = `str(period_start)[:7]` (mes) o `[:10]` (semana). No incluye "Cerrada"/"Abierta" en el label. |
| **Frontend (RealLOBDrillView)** | `formatPeriod(periodStart, periodType)`: semanal → "Semana YYYY-MM-DD", mensual → "Mes Año" (ej. "Mar 2026"). |

- **Conclusión:** No hay label unificado tipo "S10-2026 — Cerrada" / "S11-2026 — Abierta (parcial)" en la UI. El estado (Cerrado/Abierto/Falta data/Vacío) se muestra en columna aparte.

### 3. Freshness y PARTIAL_EXPECTED

| Componente | Comportamiento |
|------------|----------------|
| **ops.data_freshness_expectations** | Config por dataset: grain (day/week), expected_delay_days, source/derived. |
| **ops.data_freshness_audit** | Por ejecución: source_max_date, derived_max_date, expected_latest_date, status. |
| **Status** | `OK`, `PARTIAL_EXPECTED`, `LAGGING`, `MISSING_EXPECTED_DATA`, `SOURCE_STALE`, `DERIVED_STALE`. |
| **PARTIAL_EXPECTED** | "Periodo abierto o retraso menor: esperado hasta {expected_latest}, último {effective_max}". No se considera error. |
| **data_freshness_service.get_freshness_alerts()** | Para PARTIAL_EXPECTED: mensaje "El periodo actual está abierto; se considera parcial, no error." |

- **Conclusión:** La idea de periodo abierto/parcial ya existe en freshness; no está unificada con la semántica de "última semana cerrada" en Real LOB.

### 4. Estados de periodo en UI y backend

| Origen | Estados |
|--------|---------|
| **Drill PRO (real_lob_drill_pro_service)** | Por fila: `estado` = CERRADO | ABIERTO | FALTA_DATA | VACIO. Lógica: `expected_loaded_until = today - 1`; si `period_end_expected <= expected_loaded_until` y hay data hasta ese día → CERRADO; si periodo actual y data hasta ayer → ABIERTO; si falta data → FALTA_DATA; sin viajes → VACIO. |
| **MVs v2 (044)** | `is_open` = (period_start = DATE_TRUNC(period, global_max)). Es decir, el periodo que contiene el último viaje es "abierto". |
| **Frontend** | `isPeriodOpen(periodStart)`: compara con `currentWeekStart` / `currentMonthStart` (calculado en JS). Badge en tabla: Cerrado / Abierto / Falta data / Vacío. |

- **Conclusión:** El drill ya distingue cerrado/abierto por fila, pero la API no expone en `meta` qué semana/mes es "última cerrada" ni "actual abierta". El usuario ve "Último periodo" en KPIs = primer periodo de la lista (puede ser abierto).

### 5. Lógica weekly/monthly en Real LOB, Driver Lifecycle y Supply

| Área | Semanal | Mensual |
|------|---------|---------|
| **Real LOB** | MV por `week_start`; default = MAX(week_start). Incluye semana actual en calendario del drill. | MV por `month_start`; default = MAX(month_start). Incluye mes actual. |
| **Driver Lifecycle** | `mv_driver_weekly_stats`, `week_start`; freshness vía `last_completed_ts` → `mv_driver_weekly_stats`. | — |
| **Supply** | `mv_supply_segments_weekly` por `week_start`; formato S{week}-{year}. | — |

- **Conclusión:** No hay en ningún sitio una función única "última semana **cerrada**" usada por toda la API. En scripts (phase2c, phase2b) sí: `get_last_closed_week()` = lunes de la semana anterior; SQL: `DATE_TRUNC('week', NOW())::DATE - INTERVAL '1 week'`.

### 6. Resumen: qué se considera hoy

| Concepto | Estado actual |
|----------|----------------|
| **Semana cerrada** | Implícito en phase2c/phase2b: lunes de la semana anterior. No expuesto en API Real LOB/Drill. |
| **Semana abierta/parcial** | La semana que contiene hoy (current_week). En drill: estado ABIERTO por fila; en MVs v2: is_open = (week_start = current_week). |
| **Mes cerrado** | No hay helper central. Scripts usan `DATE_TRUNC('month', NOW() - INTERVAL '1 month')::DATE`. |
| **Mes abierto/parcial** | Mes actual (current_month). Drill: estado ABIERTO. |
| **ISO week** | Sí: PostgreSQL `DATE_TRUNC('week', x)` = lunes. Supply usa `format_iso_week` (S{week}-{year}). Real LOB no etiqueta S{week}-{year} en API. |

---

## FASE B — Diseño de semántica temporal (entidades y reglas)

### Entidades implementadas (`backend/app/services/period_semantics_service.py`)

- **LAST_CLOSED_DAY:** Último día considerado cerrado (ayer respecto a referencia).
- **LAST_CLOSED_WEEK:** Lunes de la última semana ISO completamente terminada (semana anterior a la actual).
- **CURRENT_OPEN_WEEK:** Lunes de la semana ISO actual (parcial).
- **LAST_CLOSED_MONTH:** Primer día del último mes calendario completamente terminado.
- **CURRENT_OPEN_MONTH:** Primer día del mes calendario actual (parcial).

### Reglas

- Semana cerrada = última semana ISO completamente terminada (lunes a domingo ya pasados).
- Semana actual = abierta/parcial.
- Mes cerrado = último mes calendario completamente terminado.
- Mes actual = abierto/parcial.
- Comparativos WoW y MoM oficiales usan períodos cerrados.

### Labels UI

- Semana: `format_week_label(week_start, closed)` → `S10-2026 — Cerrada` / `S11-2026 — Abierta (parcial)`.
- Mes: `format_month_label(month_start, closed)` → `Feb 2026 — Cerrado` / `Mar 2026 — Abierto (parcial)`.

### Endpoint

- `GET /ops/period-semantics?reference=YYYY-MM-DD` — Devuelve todas las entidades y labels.

---

## FASE C — WoW y MoM

### Implementado

- **WoW:** Última semana cerrada vs semana cerrada anterior. `GET /ops/real-lob/comparatives/weekly`.
- **MoM:** Último mes cerrado vs mes cerrado anterior. `GET /ops/real-lob/comparatives/monthly`.
- Métricas: viajes, margen_total, margen_trip, km_prom, b2b_pct. Salida: value_current, value_previous, delta_abs, delta_pct, trend_direction.
- Fuente: `ops.real_rollup_day_fact` agregado por `date_trunc('week'|'month', trip_day)`.

---

## FASE D — Vista diaria

### Implementado

- **Real LOB Daily** (subvista en Real LOB → "Vista diaria").
- Modos comparativos: D-1 (vs día anterior), same_weekday_previous_week (vs mismo día semana pasada), same_weekday_avg_4w (vs promedio 4 mismos días).
- Endpoints: `GET /ops/real-lob/daily/summary`, `GET /ops/real-lob/daily/comparative`, `GET /ops/real-lob/daily/table`.
- Fuente: `ops.real_rollup_day_fact`. Tabla por LOB o por Park.

---

## FASE E — Definición DoD (Day-over-Day) y labels

- **D-1:** vs día anterior.
- **WoW (same weekday):** vs mismo día de la semana pasada (`same_weekday_previous_week`).
- **vs Avg 4 same weekdays:** vs promedio de los últimos 4 mismos días de la semana (`same_weekday_avg_4w`).

---

## Fase F — Endpoints y servicios

| Endpoint | Descripción |
|----------|-------------|
| `GET /ops/period-semantics` | Semántica temporal (last_closed_week/month, current_open_*, labels). |
| `GET /ops/real-lob/comparatives/weekly` | WoW: última semana cerrada vs anterior. |
| `GET /ops/real-lob/comparatives/monthly` | MoM: último mes cerrado vs anterior. |
| `GET /ops/real-lob/daily/summary` | KPIs por día (default: último día cerrado). |
| `GET /ops/real-lob/daily/comparative` | Comparativo diario (baseline: D-1, same_weekday_previous_week, same_weekday_avg_4w). |
| `GET /ops/real-lob/daily/table` | Tabla por LOB o Park para un día. |

**Servicios:** `period_semantics_service`, `comparative_metrics_service`, `real_lob_daily_service`.  
**Drill PRO:** ahora devuelve `meta` con `last_closed_week_label`, `current_open_week_label`, `last_closed_month_label`, `current_open_month_label`.

---

## Fase G — UX / Frontend

- **RealLOBDrillView:** banner con "Última semana cerrada" / "Semana actual (parcial)" (y equivalente mensual). Sección comparativo WoW/MoM con deltas % y flechas. Enlace "Vista diaria".
- **RealLOBDailyView:** selector de día (default último cerrado), selector de baseline (D-1, mismo día semana pasada, promedio 4 mismos días), KPIs por país, comparativo con deltas, tabla por LOB.

---

## Fases H–J

- **H:** Validación con datos reales (última semana cerrada mostrada, WoW/MoM con períodos correctos, daily D-1 y same-weekday).
- **I:** Este documento actualizado.
- **J:** Resumen ejecutivo abajo.

---

---

## Resumen ejecutivo (Fase J)

1. **Definición closed/open/partial:** Semana cerrada = última semana ISO terminada (lunes anterior). Semana abierta = semana actual. Mes cerrado = último mes calendario terminado. Mes abierto = mes actual.
2. **Última semana cerrada:** Lunes de la semana anterior a la actual (`period_semantics_service.get_last_closed_week()`).
3. **Último mes cerrado:** Primer día del mes anterior al actual (`get_last_closed_month()`).
4. **WoW implementado:** `GET /ops/real-lob/comparatives/weekly`; semanas cerradas; métricas con delta_abs, delta_pct, trend_direction.
5. **MoM implementado:** `GET /ops/real-lob/comparatives/monthly`; meses cerrados.
6. **Vista diaria implementada:** Subvista "Vista diaria" en Real LOB; endpoints daily/summary, daily/comparative, daily/table.
7. **Modos comparativos diarios:** D-1, same_weekday_previous_week, same_weekday_avg_4w.
8. **Componentes/servicios:** period_semantics_service, comparative_metrics_service, real_lob_daily_service; ops.py (endpoints); RealLOBDrillView (meta, WoW/MoM, enlace Daily); RealLOBDailyView (nuevo).
9. **Validación:** Pendiente ejecución con datos reales (backend y frontend listos).
10. **Veredicto:** **LISTO CON OBSERVACIONES** — Implementación completa; falta validación en entorno con datos y posible ajuste fino de labels/UX según feedback.

---

## Referencias de código (Fase A)

| Archivo | Uso |
|---------|-----|
| `backend/app/services/real_lob_service.py` | get_real_lob_meta, get_real_lob_weekly/monthly, _display_week/month, MAX(week_start) default |
| `backend/app/services/real_lob_service_v2.py` | Idem para MVs v2, is_open en MVs |
| `backend/app/services/real_lob_drill_pro_service.py` | Calendario current_week/current_month, estado CERRADO/ABIERTO por fila |
| `backend/app/services/data_freshness_service.py` | get_freshness_audit, get_freshness_alerts, PARTIAL_EXPECTED |
| `backend/app/services/supply_definitions.py` | format_iso_week(week_start) → S{week}-{year} |
| `backend/scripts/phase2c_snapshot_and_sla.py` | get_last_closed_week() = lunes semana anterior |
| `backend/sql/phase2b_weekly_checks.sql` | last_closed_week = DATE_TRUNC('week', NOW())::DATE - 1 week |
| `backend/alembic/versions/044_real_lob_v2_lob_group_segment.py` | is_open en mv_real_lob_week_v2 / month_v2 |
| `backend/alembic/versions/072_data_freshness_audit_and_expectations.py` | data_freshness_expectations, data_freshness_audit, status |
| `frontend/src/components/RealLOBDrillView.jsx` | formatPeriod, isPeriodOpen, estado Cerrado/Abierto en tabla, meta.last_period_* |
