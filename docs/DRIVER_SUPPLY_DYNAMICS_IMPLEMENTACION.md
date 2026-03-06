# Driver Supply Dynamics — Resumen de implementación

## Entregable 1 — Resumen de cambios

### Frontend modificado
- `frontend/src/App.jsx`: tab principal "Supply (Real)" → "Driver Supply Dynamics"
- `frontend/src/components/SupplyView.jsx`: título y descripción; tabs Overview, Composition, Migration, Alerts; overview enriquecido (trips, shares, WoW); Composition con criterio de segmentación y WoW; Migration con resumen y drilldown; Alerts con prioridad High/Medium/Low; modales drilldown (alertas y migración)
- `frontend/src/services/api.js`: comentario; `getSupplyOverviewEnhanced`, `getSupplyComposition`, `getSupplyMigration`, `getSupplyMigrationDrilldown`

### Backend modificado
- `backend/app/services/supply_service.py`: `get_supply_overview_enhanced`, `get_supply_composition`, `get_supply_migration`, `get_supply_migration_drilldown`; helpers `_build_overview_summary`, `_add_wow`, `_wow_pct`, `_wow_pp`, `_alert_priority_label`; en `get_supply_alerts` se añade `priority_label` a cada fila
- `backend/app/routers/ops.py`: GET `/ops/supply/overview-enhanced`, GET `/ops/supply/composition`, GET `/ops/supply/migration`, GET `/ops/supply/migration/drilldown`

### Nuevos endpoints
- `GET /ops/supply/overview-enhanced` — overview con trips, avg_trips_per_driver, FT/PT/weak_supply share; WoW cuando grain=weekly
- `GET /ops/supply/composition` — composición semanal por segmento con WoW (format=csv opcional)
- `GET /ops/supply/migration` — migración from_segment → to_segment con migration_type (format=csv opcional)
- `GET /ops/supply/migration/drilldown` — lista de drivers por park_id, week_start, from_segment, to_segment (format=csv opcional)

### Queries / vistas nuevas
- Ninguna nueva MV ni vista SQL. Cálculos en servicio:
  - Overview: lectura de `ops.mv_supply_weekly`/`monthly` y de `ops.mv_supply_segments_weekly` (agregado por semana) para trips y shares; WoW calculado en Python con LAG implícito (serie ordenada DESC).
  - Composition: `get_supply_segments_series` + WoW en Python por (week, segment).
  - Migration: query directa a `ops.mv_driver_segments_weekly` con GROUP BY week_start, park_id, prev_segment_week, segment_week, segment_change_type.
  - Migration drilldown: query directa a `ops.mv_driver_segments_weekly` con filtros.

### Docs actualizados
- `docs/SUPPLY_RADAR_QA_CHECKLIST.md`: título y tabla Frontend (tabs Composition, Migration, prioridad alertas)
- `docs/CONTROL_TOWER_FRONTEND_MAP.md`: nombre del tab
- `backend/scripts/check_supply_driver_dynamics.py`: script opcional de verificación

---

## Entregable 2 — Decisiones técnicas

- **Reutilizado**: Endpoints existentes `/ops/supply/geo`, `/series`, `/summary`, `/segments/series`, `/alerts`, `/alerts/drilldown`, `/refresh` sin cambios. MVs y vistas SQL sin renombrar. Criterio de segmentación (60/20/5/1/0) sin modificar.
- **Calculado en servicio**: Trips y shares por semana (desde `mv_supply_segments_weekly` agregado por week+park). WoW (drivers_wow_pct, trips_wow_pct, share_wow_pp, etc.) en Python sobre series ordenadas. Agregados de migración (from_segment, to_segment, drivers_migrated, migration_type) con una sola query a `mv_driver_segments_weekly` + mapeo de `segment_change_type` a upgrade/downgrade/drop/revival/lateral.
- **No tocado para compatibilidad**: Rutas `/ops/supply/*` existentes; nombres de funciones y MVs; contrato de respuesta de `/alerts` (solo se añade campo `priority_label`); `activeTab === 'supply'` en App.

---

## Entregable 3 — Resultado funcional

- **Rename**: Tab y título "Driver Supply Dynamics — Radar" implementados.
- **Segmentación visible**: Criterio FT 60+, PT 20–59, Casual 5–19, Occasional 1–4, Dormant 0 en info box en la pestaña Composition.
- **Overview enriquecido**: KPIs trips, avg_trips_per_driver, FT_share, PT_share, weak_supply_share; serie con columnas WoW (drivers_wow_pct, trips_wow_pct) cuando granularidad semanal.
- **WoW**: Implementado en overview (serie) y en Composition (drivers_wow_pct, trips_wow_pct, share_wow_pp).
- **Composition**: Tab con tabla por semana y segmento; export CSV.
- **Migration**: Tab con resumen (upgrades, downgrades, revivals, drops) y tabla from→to con "Ver drivers" y modal drilldown.
- **Alerts mejoradas**: Columna prioridad (High/Medium/Low); baseline vs actual resaltado; drilldown operativo.
- **Drilldowns**: Alertas (conductores downshift/drop) y migración (conductores por from_segment→to_segment) operativos.

---

## Entregable 4 — Riesgos pendientes

- **Para una fase posterior**: Tabla `ops.driver_segment_config`; cambio de criterio de segmentos; estacionalidad avanzada; clasificación de alertas (abrupt_change, sustained_deterioration, atypical_behavior) con lógica de negocio.
- **Depende de definiciones de negocio**: Umbrales de prioridad (actualmente P0/P1→High, P2→Medium, P3→Low); si conviene mostrar DORMANT cuando la MV solo incluye conductores con al menos un viaje.
- **No conviene tocar aún**: Nombres de MVs y vistas; rutas API; criterio 60/20/5/1/0 hasta tener configuración acordada.
