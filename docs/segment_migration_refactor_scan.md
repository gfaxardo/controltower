# Scan / mapeo previo: segmentación semanal y Migration

Documento obligatorio antes del refactor E2E de segmentación (dormant, casual, pt, ft, elite, legend) y rediseño de la vista Migration. No implementar a ciegas.

## 1. Fuentes de verdad detectadas

| Capa | Fuente | Detalle |
|------|--------|---------|
| **Config** | `ops.driver_segment_config` | `segment_code`, `min_trips_week`, `max_trips_week`, `ordering`, `effective_from` / `effective_to`. Seed en `backend/alembic/versions/065_driver_segment_config_and_mv_rebuild.py`. |
| **Clasificación** | `ops.mv_driver_segments_weekly` | Segmento por JOIN a config; `segment_change_type` con CASE hardcodeado en `067_mv_driver_segments_weekly_join_config.py` (FT=5, PT=4, CASUAL=3, OCCASIONAL=2, DORMANT=1). |
| **Métrica base** | `trips_completed_week` | En `ops.mv_driver_weekly_stats` (origen: `ops.v_driver_lifecycle_trips_completed` → `public.trips_unified`). No existe columna `weekly_trips`; es `trips_completed_week`. |
| **Churn/Reactivation** | `ops.v_driver_weekly_churn_reactivation` + `ops.mv_supply_weekly` | Churned = activos en N-1, 0 viajes en N; Reactivated = 0 en N-1, >0 en N. Independiente de segmentos. |
| **Migration API** | `get_supply_migration()` en `backend/app/services/supply_service.py` | Lee `mv_driver_segments_weekly`; **incluye same-to-same** (segment_change_type = 'stable' → migration_type = 'lateral'). |

## 2. Taxonomía actual vs objetivo

| Actual (065/067) | Rangos | Objetivo | Rangos |
|------------------|--------|----------|--------|
| DORMANT | 0 | dormant | 0 |
| OCCASIONAL | 1–4 | — | (fusionar en casual) |
| CASUAL | 5–19 | casual | 1–29 |
| PT | 20–59 | pt | 30–59 |
| FT | 60+ | ft | 60–119 |
| — | — | elite | 120–179 |
| — | — | legend | 180+ |

## 3. Labels hoy en uso

- **Segmentos:** FT, PT, CASUAL, OCCASIONAL, DORMANT (`supply_definitions.py`, `SupplyView.jsx` SEGMENT_CRITERIA_FALLBACK).
- **Migration types:** upgrade, downgrade, drop, revival, lateral (mapeo en `supply_service.py`).
- **B2B/B2C:** Solo en Real LOB/Drill; no mezclar con segmentación semanal.

## 4. Dónde aparecen segmentos

- **Supply:** Overview (FT_share, PT_share, weak_supply), Composition (tabla por segment_week), Migration (From/To, badges por migration_type), Alerts (segment_week).
- **Driver Lifecycle:** Columna "Mix FT/PT" en serie por periodo; no usa `driver_segment_config`.
- **Endpoints:** `GET /ops/supply/segments/config`, `segments/series`, `composition`, `migration`, `migration/drilldown`; definiciones en `GET /ops/supply/definitions`.

## 5. Contratos actuales

### GET /ops/supply/segments/config

- Respuesta: `{ "data": [ { "segment", "min_trips", "max_trips", "priority" } ] }`.
- Orden actual: `ORDER BY ordering DESC` (mayor priority primero).

### GET /ops/supply/migration

- Respuesta: `{ "data": [ { "week_start", "park_id", "from_segment", "to_segment", "segment_change_type", "migration_type", "drivers_migrated", "drivers_in_from_segment_previous_week", "migration_rate", "week_display" } ], "summary": { "upgrades", "downgrades", "drops", "revivals" } }`.
- Incluye filas con `migration_type === 'lateral'` (same-to-same).

## 6. Archivos a tocar

| Área | Archivos |
|------|----------|
| Backend | Nueva migración Alembic (078), `backend/app/services/supply_service.py`, `backend/app/services/supply_definitions.py` |
| Frontend | `frontend/src/components/SupplyView.jsx`, `frontend/src/components/DriverSupplyGlossary.jsx`, nueva constante `frontend/src/constants/segmentSemantics.js` |
| Docs | Este archivo, entregables finales |

## 7. Riesgos

- **MVs en cascada:** `mv_driver_segments_weekly` → `mv_supply_segments_weekly` → `mv_supply_segment_anomalies_weekly` → `mv_supply_alerts_weekly` → `v_supply_alert_drilldown`. Cualquier cambio en segmentos exige recrear/refresh esta cadena.
- **067:** El CASE para `ord`/`prev_ord` está hardcodeado (solo 5 segmentos). Añadir ELITE/LEGEND requiere nueva migración que use ordering desde `driver_segment_config`.
- **Same-to-same:** La API devuelve lateral; el front debe excluirlas de la tabla principal o moverlas a bloque "Stable/Retained".
- **Compatibilidad:** Cambios de rangos (p. ej. CASUAL 1–29) afectan datos ya materializados hasta el próximo refresh. Estrategia: migración additive (nuevos segmentos + effective_from); no borrar filas en uso.

## 8. Qué puede hacerse sin migración BD

- Leyenda y tooltips en front.
- Filtrado de `migration_type === 'lateral'` en la tabla principal de Migration.
- Reordenación visual y bloque "Stable/Retained" en Migration.
- Constante compartida de segmentos en front (fallback).

## 9. Qué requiere migración BD

- Nuevos segmentos ELITE (120–179) y LEGEND (180+) en `driver_segment_config`.
- Ajuste de FT a max 119 (60–119).
- Recrear `mv_driver_segments_weekly` (y cadena) con `ord`/`prev_ord` desde JOIN a `driver_segment_config` en lugar de CASE fijo.

## 10. Observaciones

- **Occasional vs Casual:** Fusionar 1–29 como "casual" puede hacerse con nueva fila en config (effective_from) y effective_to en OCCASIONAL/CASUAL; opcional en esta fase.
- **Dormant vs Churned:** Dormant = 0 viajes en la semana (segmento). Churned = definición en `v_driver_weekly_churn_reactivation` (activos N-1, 0 en N). No mezclar en UI.
- **Revival:** migration_type "new" en Migration; conceptualmente "vuelta a actividad" o primera semana; dejar explícito en labels/tooltips.
