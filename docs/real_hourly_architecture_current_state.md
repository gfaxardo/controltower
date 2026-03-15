# Real Hourly Architecture — Estado Actual (Pre-migración 099)

## Cadena actual

```
public.trips_all (<2026) + public.trips_2026 (>=2026)
  │
  ├─ ops.v_trips_real_canon (064)
  │    └─ DISTINCT ON(id) sobre UNION de ambas tablas
  │    └─ Columnas: id, park_id, tipo_servicio, fecha_inicio_viaje,
  │       fecha_finalizacion, comision_empresa_asociada, pago_corporativo,
  │       distancia_km, condicion, conductor_id, source_table
  │
  ├─ ops.v_trips_real_canon_120d (098)
  │    └─ Mismo contrato, filtro 120d en cada rama del UNION (index-friendly)
  │
  ├─ ops.v_real_trips_service_lob_resolved (090) / _120d (098)
  │    └─ JOIN con parks, normalización geo, normalize_real_tipo_servicio
  │    └─ JOIN con canon.dim_service_type → canon.dim_lob_group
  │    └─ FILTRO: condicion = 'Completado' (solo completados)
  │
  ├─ ops.v_real_trips_with_lob_v2 (064/090) / _120d (098)
  │    └─ Wrapper: real_tipo_servicio_norm, lob_group, segment_tag
  │
  └─ MVs agregadas:
       ├─ ops.mv_real_lob_month_v2 (098) → FROM v_real_trips_with_lob_v2_120d
       ├─ ops.mv_real_lob_week_v2 (098) → FROM v_real_trips_with_lob_v2_120d
       ├─ ops.mv_real_trips_monthly (005) → FROM trips_all directo
       ├─ ops.real_drill_dim_fact (064) → FROM v_trips_real_canon
       └─ ops.real_rollup_day_fact (064) → FROM v_trips_real_canon
```

## Qué se conserva

| Artefacto | Acción | Razón |
|-----------|--------|-------|
| `ops.v_trips_real_canon_120d` | Se conserva | Es la capa de entrada index-friendly. Solo la fact_v2 la lee. |
| `canon.dim_service_type` | Se conserva | Normalización de tipos de servicio |
| `canon.dim_lob_group` | Se conserva | Agrupación LOB |
| `canon.normalize_real_tipo_servicio()` | Se conserva | Función de normalización reutilizada |
| Lógica de geo (parks, city, country) | Se reutiliza | Copiada a v_real_trip_fact_v2 |
| Lógica de segment_tag (B2B/B2C) | Se reutiliza | Mismo patrón |
| Índices en trips_all/trips_2026 | Se conservan | Necesarios para el scan de 120d |
| MVs v2 (week/month) | Se conservan | No se rompen endpoints actuales |

## Qué se reemplaza

| Artefacto anterior | Reemplazo | Razón |
|-------------------|-----------|-------|
| `v_real_trips_service_lob_resolved` como base de MV | `v_real_trip_fact_v2` | Incluye todos los viajes, no solo completados |
| `mv_real_lob_month_v2` como MV directa de vista pesada | `mv_real_lob_month_v3` derivada de hourly | Desacoplada |
| `mv_real_lob_week_v2` como MV directa de vista pesada | `mv_real_lob_week_v3` derivada de hourly | Desacoplada |
| Bootstrap por sub-bloques de 15 días | Bootstrap por sub-bloques de 7 días | Más granular, más seguro |
| Governance old (`close_real_lob_governance.py`) | `governance_hourly_first.py` | Valida nueva cadena |

## Dependencias que se respetan

1. **Backend services**: Los endpoints existentes siguen leyendo de MVs v2. No se rompen.
2. **Frontend**: No se modifica. Los componentes siguen consumiendo los mismos endpoints.
3. **Real vs Proyección**: `ops.v_real_metrics_monthly` lee de `mv_real_trips_monthly` (005). No se toca.
4. **Drill**: `real_drill_dim_fact` y `real_rollup_day_fact` siguen existiendo. No se tocan.
5. **Freshness**: `v_real_freshness_trips` sigue leyendo de `v_trips_real_canon`. No se toca.

## Qué se agrega (nuevo)

| Artefacto | Tipo | Propósito |
|-----------|------|-----------|
| `ops.v_real_trip_fact_v2` | VIEW | Capa canónica por viaje, source-agnostic |
| `ops.mv_real_lob_hour_v2` | MV | Agregación horaria, base para todo |
| `ops.mv_real_lob_day_v2` | MV | Agregación diaria desde hourly |
| `ops.mv_real_lob_week_v3` | MV | Agregación semanal desde hourly |
| `ops.mv_real_lob_month_v3` | MV | Agregación mensual desde hourly |
| `canon.normalize_cancel_reason()` | FUNCTION | Normaliza motivo de cancelación |
| `canon.cancel_reason_group()` | FUNCTION | Agrupa motivos en categorías |
| `bootstrap_hourly_first.py` | SCRIPT | Bootstrap hour → day → week → month |
| `governance_hourly_first.py` | SCRIPT | Governance nueva cadena |
