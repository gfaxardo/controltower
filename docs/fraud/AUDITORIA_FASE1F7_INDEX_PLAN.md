# AUDITORIA FASE 1F-7 — INDEX PLAN

**Fecha**: 2026-05-20
**Estado**: **COMPLETO**

---

## 1. Indices creados (Migration 150)

### fraud.trip_risk_features

| Indice | Columnas | Proposito |
|---|---|---|
| `idx_trf_origin_cluster` | (origin_cluster_key, computed_at) | coordinated_origin |
| `idx_trf_route_signature` | (route_signature, computed_at) | repeated_route |
| `idx_trf_driver_route` | (driver_id, route_signature, computed_at) | behavioral profile |
| `idx_trf_driver_origin` | (driver_id, origin_cluster_key, computed_at) | behavioral profile |
| `idx_trf_park_origin` | (park_id, origin_cluster_key, computed_at) | park concentration |

### fraud.driver_risk_snapshot

| Indice | Columnas | Proposito |
|---|---|---|
| `idx_drs_profile_class` | (behavioral_profile_class) | filtering |
| `idx_drs_confidence` | (behavioral_confidence_score) | ranking |

### fraud.trip_behavior_feature_cache

| Indice | Columnas | Proposito |
|---|---|---|
| `idx_tbfc_trip_dt` | (trip_datetime) | date range |
| `idx_tbfc_driver` | (driver_id) | driver lookup |
| `idx_tbfc_origin_cluster` | (origin_cluster_key) | coordinated origin |
| `idx_tbfc_route_signature` | (route_signature) | repeated route |
| `idx_tbfc_park` | (park_id) | park filter |

## 2. Indices NO creados (justificacion)

| Tabla | Por que NO |
|---|---|
| `public.trips_2026` | Tabla productiva, 16M+ filas. Indices funcionales sobre `direccion` son costosos. Se prefiere usar `trip_behavior_feature_cache` pre-computado. |

## 3. Veredicto

**GO** — 11 indices creados en esquema `fraud`. Sin impacto en tablas productivas.
