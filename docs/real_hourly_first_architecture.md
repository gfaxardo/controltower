# Real Hourly-First Architecture

## Resumen ejecutivo

Rediseño completo de la cadena analítica REAL de viajes. Se pasa de una arquitectura donde week/month leían directamente de vistas sobre tablas crudas, a un modelo desacoplado y escalable:

```
fuente_raw (trips_all + trips_2026)
  → ops.v_trips_real_canon_120d          (único punto de contacto con raw)
    → ops.v_real_trip_fact_v2             (1 fila por viaje, canónica, limpia)
      → ops.mv_real_lob_hour_v2          (MV horaria, base para todo)
        → ops.mv_real_lob_day_v2         (derivada de hourly)
        → ops.mv_real_lob_week_v3        (derivada de hourly)
        → ops.mv_real_lob_month_v3       (derivada de hourly)
```

## Arquitectura anterior

```
trips_all / trips_2026
  → v_trips_real_canon / v_trips_real_canon_120d
    → v_real_trips_service_lob_resolved / _120d
      → v_real_trips_with_lob_v2 / _120d
        → mv_real_lob_month_v2           (MV, solo completados)
        → mv_real_lob_week_v2            (MV, solo completados)
```

### Problemas de la arquitectura anterior

1. **Week/month leían de cadena pesada**: Las MVs agregaban directamente desde vistas encadenadas sobre trips_all/trips_2026.
2. **Solo viajes completados**: No se podían analizar cancelaciones ni pedidos.
3. **Sin hora del día**: No existía granularidad horaria.
4. **Sin motivo de cancelación**: `motivo_cancelacion` no se incluía.
5. **Sin duración de viaje**: No se calculaba.
6. **Acoplado a la fuente**: Cambiar trips_all requería modificar múltiples vistas.

## Arquitectura nueva

### Migración: `099_real_hourly_first_architecture.py`

### Capa 1: Vista canónica por viaje — `ops.v_real_trip_fact_v2`

- 1 fila por viaje
- Lee de `ops.v_trips_real_canon_120d` (existente)
- Incluye TODOS los viajes (completados, cancelados, otros)
- Campos nuevos:
  - `trip_hour` (0-23)
  - `trip_outcome_norm` (completed/cancelled/other)
  - `is_completed`, `is_cancelled`
  - `motivo_cancelacion_raw`, `cancel_reason_norm`, `cancel_reason_group`
  - `trip_duration_seconds`, `trip_duration_minutes`
- Reutiliza toda la lógica canónica existente (parks, geo, service type, LOB)

### Capa 2: MV horaria — `ops.mv_real_lob_hour_v2`

Granularidad: fecha + hora + país + ciudad + park + LOB + servicio + segmento + outcome + cancel_reason

Métricas:
- `requested_trips`, `completed_trips`, `cancelled_trips`, `unknown_outcome_trips`
- `gross_revenue`, `margin_total`, `distance_total_km`
- `duration_total_minutes`, `duration_avg_minutes`
- `cancellation_rate`, `completion_rate`

### Capa 3: MV diaria — `ops.mv_real_lob_day_v2`

Lee EXCLUSIVAMENTE de `ops.mv_real_lob_hour_v2`.

### Capa 4: MV semanal — `ops.mv_real_lob_week_v3`

Lee EXCLUSIVAMENTE de `ops.mv_real_lob_hour_v2`.
Contrato compatible con `mv_real_lob_week_v2` anterior: mismas columnas base (trips, revenue, margin_total, distance_total_km, max_trip_ts, is_open) + nuevas (completed_trips, cancelled_trips, duration_total_minutes).

### Capa 5: MV mensual — `ops.mv_real_lob_month_v3`

Lee EXCLUSIVAMENTE de `ops.mv_real_lob_hour_v2`.
Contrato compatible con `mv_real_lob_month_v2` anterior.

## Bootstrap

Script: `backend/scripts/bootstrap_hourly_first.py`

```bash
# Bootstrap completo (hour → day → week → month)
python scripts/bootstrap_hourly_first.py

# Solo una capa
python scripts/bootstrap_hourly_first.py --only-hour
python scripts/bootstrap_hourly_first.py --only-day
python scripts/bootstrap_hourly_first.py --only-week
python scripts/bootstrap_hourly_first.py --only-month

# Dry run
python scripts/bootstrap_hourly_first.py --dry-run
```

Flujo:
1. Hour: bootstrap por sub-bloques de 7 días (staging → MV)
2. Day: DROP + CREATE desde hourly (directo, rápido)
3. Week: DROP + CREATE desde hourly
4. Month: DROP + CREATE desde hourly

## Governance

Script: `backend/scripts/governance_hourly_first.py`

```bash
python scripts/governance_hourly_first.py
python scripts/governance_hourly_first.py --skip-refresh
python scripts/governance_hourly_first.py --refresh-only
```

Flujo:
1. Inspección de artefactos
2. Hour vacía → bootstrap; Hour poblada → REFRESH CONCURRENTLY
3. Reconstruir day/week/month desde hourly
4. Validaciones:
   - `fact_view_ok`: vista canónica consultable
   - `dims_populated`: dimensiones de servicio activas
   - `canonical_no_dupes`: sin duplicados de categoría
   - `hourly/day/week/month_populated`: MVs con datos
   - `cancel_reason_norm_populated`: cancelaciones normalizadas
   - `trip_duration_reasonable`: duraciones en rango esperado
   - `week_no_raw_deps`: week no depende de trips_all
   - `month_no_raw_deps`: month no depende de trips_all

## Refresh operativo

Para refresh diario o periódico:

```bash
python scripts/governance_hourly_first.py
```

Esto:
1. Refresca hourly (CONCURRENTLY si tiene datos)
2. Reconstruye day/week/month desde hourly
3. Valida todo

## Uso operativo (UI y API)

- **UI**: Tab Real → sub-tab **Operativo** (por defecto). Incluye: Hoy/Ayer/Esta semana, Comparativos, Por día, Por hora, Cancelaciones.
- **Endpoints**: `GET /ops/real-operational/snapshot`, `/day-view`, `/hourly-view`, `/cancellations`, `/comparatives/today-vs-yesterday`, `/comparatives/today-vs-same-weekday`, `/comparatives/current-hour-vs-historical`, `/comparatives/this-week-vs-comparable`.
- **Legacy**: Drill y vista diaria antigua bajo sub-tab "Drill y diario (avanzado)". Ver `docs/real_legacy_map.md`.

## Cambio futuro de fuente

Ver: `docs/real_trip_source_contract.md`

Solo se necesita modificar `ops.v_trips_real_canon_120d` para apuntar a la nueva fuente. Las capas downstream (fact → hourly → day → week → month) no se tocan.

## Relación con MVs v2 existentes

Las MVs v2 (`mv_real_lob_week_v2`, `mv_real_lob_month_v2`) **no se eliminan** en la migración 099. Siguen existiendo y alimentando los endpoints actuales. Cuando se quiera migrar el backend/frontend a las MVs v3, se hace gradualmente sin romper nada.

## Nuevas funciones SQL

| Función | Schema | Propósito |
|---------|--------|-----------|
| `canon.normalize_cancel_reason(TEXT)` | canon | Normaliza motivo_cancelacion |
| `canon.cancel_reason_group(TEXT)` | canon | Agrupa motivos en categorías de negocio |
