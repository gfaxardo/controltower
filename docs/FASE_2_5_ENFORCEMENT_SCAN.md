# FASE 2.5 — Enforcement Scan

## 1. Qué enforcement existe hoy

| Mecanismo | Estado |
|-----------|--------|
| `SERVING_REGISTRY` (15 features) | Declarativo; no fuerza nada en runtime |
| `forbidden_sources` en registry entries | Declarado en 5 features; nadie las verifica |
| `GET /ops/diagnostics/serving-sources` | Devuelve freshness parcial; `actual_source` siempre == `preferred_source`; sin compliance_status |
| `stale_threshold_hours` | Campo presente pero nunca se aplica contra `last_refresh_at` |
| `SourceDiagnostic` dataclass | Definido, nunca instanciado |
| Warning en `_fetch_resolved_period_totals` else branch | Un solo `logger.warning` para grain no estándar |
| Docstring fact-first en `business_slice_omniview_service.py` | Documentación, no enforcement |
| `docs/architecture_serving_discipline.md` | Política escrita, sin automatización |

## 2. Qué enforcement falta

- Policy central reutilizable (`ServingPolicy` + `assert_serving_source`)
- Lista central de forbidden sources con enforcement real (excepción en strict mode)
- Declaración programática de policy en cada servicio crítico
- Stale detection computado (threshold vs last_refresh)
- `compliance_status` por feature (COMPLIANT / WARNING / NON_COMPLIANT)
- Trace real de `source_used` vs `preferred_source`
- Script de validación automática de cumplimiento
- Bloqueo hard de fallback silencioso (no solo warning)

## 3. Features sin policy explícita

| Servicio | Tiene policy? | Tiene forbidden_sources? |
|----------|---------------|--------------------------|
| `business_slice_omniview_service` | No (solo docstring) | No |
| `control_loop_plan_vs_real_service` | No (solo docstring) | No |
| `real_lob_service` | No | No |
| `real_lob_service_v2` | No | No |
| `real_lob_v2_data_service` | No | No |
| `real_lob_daily_service` | No | No |
| `business_slice_service` | Parcial (warning log) | No |

## 4. Fuentes prohibidas para serving normal

| Fuente | Razón |
|--------|-------|
| `public.trips_all` | Raw, millones de filas |
| `public.trips_unified` | Raw |
| `ops.v_real_trips_business_slice_resolved` | Grano viaje, scan completo para agregaciones |
| `ops.v_real_trips_enriched_base` | Build-only, grano viaje |
| `ops.v_real_trip_fact_v2` | Trip-level; solo aceptable para audit/quality |

## 5. Features en riesgo de regresión

| Feature | Riesgo | Causa |
|---------|--------|-------|
| Omniview omniview (rollups) | Medio | Funciones legacy `_fetch_resolved_*` aún existen en el archivo |
| Business slice coverage | Alto | 2 queries a `V_RESOLVED` en `get_business_slice_coverage` |
| `_fetch_resolved_period_totals` else branch | Bajo | Fallback a `V_RESOLVED` para grain no estándar, solo warning |
| Territory quality | Alto | Lee `public.trips_all` directamente |

## 6. Endpoints que NO se tocan (contratos públicos)

- `GET /ops/business-slice/monthly` (contrato intacto)
- `GET /ops/business-slice/weekly` (contrato intacto)
- `GET /ops/business-slice/daily` (contrato intacto)
- `GET /ops/business-slice/omniview` (contrato intacto)
- `GET /ops/business-slice/matrix-operational-trust` (contrato intacto)
- `GET /ops/control-loop/plan-vs-real` (contrato intacto)
- `GET /ops/real-lob/*` (contrato intacto)
- `GET /ops/supply/*` (contrato intacto)
- `GET /ops/driver-lifecycle/*` (contrato intacto)
- Todos los endpoints de frontend (sin cambio)
