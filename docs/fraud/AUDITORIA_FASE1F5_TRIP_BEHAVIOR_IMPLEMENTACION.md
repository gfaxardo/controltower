# AUDITORIA FASE 1F-5 — TRIP BEHAVIOR IMPLEMENTACION

**Fecha**: 2026-05-20  
**Estado**: GO — Implementacion completa  

## 1. Estado

| Componente | Estado |
|---|---|
| Route Parser | GO |
| Source Adapter (route fields) | GO |
| Migration (147) | GO |
| Rule Catalog (14 nuevas) | GO |
| Behavioral Routines (12) | GO |
| Baseline Engine | GO |
| Risk Score Consolidation | GO |
| Endpoints | GO |
| Scripts | GO |
| QA | GO |
| Documentation | GO |

## 2. Fuente usada

`public.trips_2026` — 16,464,379 filas totales, 3,964,280 completados.

**Columnas clave para rutas**:
- `direccion` (TEXT): contiene origen → destino con separador `->`
- `distancia_km` (NUMERIC): distancia del viaje
- `fecha_inicio_viaje` / `fecha_finalizacion`: duracion derivable
- `conductor_id`: driver_id
- `park_id`: agrupacion territorial
- `tipo_servicio`: service_type / LOB

## 3. Route Parsing

**Engine**: `backend/app/services/fraud/fraud_route_parser.py`

- Separador detectado: `->` (200/200 muestras)
- Funciones:
  - `normalize_text_address()`: lower, trim, caracteres raros
  - `parse_route_text()`: extrae origen/destino, construye firma
  - `build_origin_cluster_key()`: prioridad lat/lng > origin_norm > pickup_address
  - `build_destination_cluster_key()`: prioridad lat/lng > destination_norm
  - `build_route_signature()`: origin_norm -> destination_norm
  - `build_reverse_route_signature()`: destination_norm -> origin_norm

**Parse quality**: 'ok' | 'partial' | 'failed'

**NO usa APIs externas. NO geocodifica. Deterministico.**

## 4. Baseline Engine

Calcula metricas estadisticas agregadas por dimension (park_id) usando SQL:

- avg_distance_m, avg_duration_s, avg_amount
- p10, p25, p50, p75, p90 de distance
- short_trip_ratio
- avg_trips_per_day
- variance_distance, variance_duration

**Fallback**: Si sample_size < 30, usa thresholds documentados y registra `fallback_used=true`.

**Exclusiones**: NO usa synthetic data, NO incluye payment_details.

## 5. Reglas (14 nuevas)

| Codigo | Peso | Severity |
|---|---|---|
| REPEATED_ORIGIN_PATTERN | 30 | high |
| REPEATED_ROUTE_SIGNATURE | 35 | high |
| SHORT_TRIP_FARMING_PATTERN | 40 | critical |
| ROUTE_LOOP_PATTERN | 35 | high |
| COORDINATED_ORIGIN_PATTERN | 45 | critical |
| TIME_WINDOW_DENSITY | 25 | high |
| LOW_AVG_DISTANCE_PATTERN | 35 | high |
| LOW_AVG_DURATION_PATTERN | 35 | high |
| EXTREME_SHORT_TRIP_RATIO | 40 | critical |
| LOW_VARIANCE_PATTERN | 30 | medium/high |
| LONG_TRIP_OUTLIER_V2 | 30 | medium/high |
| HIGH_CARD_AMOUNT_NEW_DRIVER_V2 | 35 | critical |
| BURST_ACTIVITY_NEW_DRIVER_V2 | 30 | high |
| PARK_CONCENTRATION_RISK_V2 | 25 | high |

Seed via: `python backend/scripts/fraud_seed_rules.py`

## 6. Rutinas (12)

| Rutina | Ventana | SQL Agregada |
|---|---|---|
| repeated_origin_pattern | D-7 | SI |
| repeated_route_signature | D-7 | SI |
| short_trip_farming | D-7 | SI |
| route_loop_pattern | D-7 | SI |
| coordinated_origin_pattern | D-7 | SI |
| low_avg_distance_pattern | D-30 | SI |
| low_avg_duration_pattern | D-30 | SI |
| extreme_short_trip_ratio | D-30 | SI |
| low_variance_pattern | D-30 | SI |
| long_trip_outlier_v2 | D-30 | SI |
| park_behavior_concentration | latest | SI |
| behavioral_driver_profile | D-30 | SI |

Todas soportan `dry_run=True`.

## 7. Resultados Iniciales

Ejecutar:
```
python backend/scripts/fraud_trip_behavior_audit.py --date-from 2026-05-01 --date-to 2026-05-20 --dry-run true
```

Ver reporte: `docs/fraud/AUDITORIA_FASE1F5_TRIP_BEHAVIOR_RESULTS.md`

## 8. Top Findings (esperados)

- SHORT_TRIP_FARMING_PATTERN: señal mas fuerte, combina 6 dimensiones
- COORDINATED_ORIGIN_PATTERN: detecta granjas de drivers
- ROUTE_LOOP_PATTERN: detecta viajes sinteticos A→B, B→A
- EXTREME_SHORT_TRIP_RATIO: drivers con >50% viajes < 2km o < 3min
- LOW_VARIANCE_PATTERN: viajes demasiado uniformes

## 9. Seguridad

- NO expone account_number
- NO expone BANK_CLUSTER_SALT
- NO usa synthetic data para casos operativos
- NO ejecuta acciones reales (dry_run=true por defecto)
- NO depende de cuentas bancarias
- NO usa APIs externas
- NO geocodifica

## 10. QA

QA script: `backend/scripts/validate_fraud_trip_behavior_phase1f5.py`

Validaciones:
1. Schema discovery
2. Route parser (7 tests)
3. Migration columns (8 columnas)
4. Rules in catalog (14 reglas)
5. Behavioral routines
6. Source adapter route fields
7. Router endpoints
8. Security (no datos sensibles)
9. dry_run support
10. No acciones reales
11. Omniview/Plan vs Real intactos
12. Synthetic data excluida

## 11. Siguiente paso unico

**FASE 1F-4R: Synthetic Remediation** — Resolver el estado NO-GO operativo de las cuentas bancarias sinteticas y habilitar Bank Account Cluster con datos reales.

---

## Archivos Modificados

| Archivo | Tipo |
|---|---|
| `docs/fraud/AUDITORIA_FASE1F5_TRIP_BEHAVIOR_PRECHECK.md` | nuevo |
| `docs/fraud/AUDITORIA_FASE1F5_TRIPS_SCHEMA_DISCOVERY.md` | nuevo |
| `docs/fraud/FRAUD_DATA_CONTRACT.md` | modificado |
| `backend/app/services/fraud/fraud_route_parser.py` | nuevo |
| `backend/app/services/fraud/fraud_behavioral_routines.py` | nuevo |
| `backend/app/services/fraud/fraud_source_adapter.py` | modificado |
| `backend/app/services/fraud/fraud_routine_service.py` | modificado |
| `backend/alembic/versions/147_trip_behavior_route_features.py` | nuevo |
| `backend/app/routers/fraud.py` | modificado |
| `backend/scripts/fraud_seed_rules.py` | modificado |
| `backend/scripts/fraud_trip_behavior_audit.py` | nuevo |
| `backend/scripts/fraud_daily_control.py` | modificado |
| `backend/scripts/validate_fraud_trip_behavior_phase1f5.py` | nuevo |
