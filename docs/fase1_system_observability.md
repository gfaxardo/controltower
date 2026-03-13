# FASE 1 — SYSTEM OBSERVABILITY E2E

## 1. Objetivo de la fase

Construir una capa de **observabilidad integral** del sistema para que Control Tower pueda responder:

- Qué datasets/vistas/MVs alimentan cada módulo
- Cuándo fue el último refresh real de cada artefacto crítico
- Qué tan fresca o stale está la data
- Qué scripts/funciones/pipelines refrescan cada componente
- Qué dependencias existen entre tablas, views, MVs, endpoints y pantallas
- Dónde hay puntos ciegos, duplicidad o riesgo operativo

**Principio:** todo aditivo; no reemplazar lógica existente ni romper contratos.

---

## 2. Artefactos creados

### 2.1 Base de datos (migración 092)

| Artefacto | Tipo | Descripción |
|-----------|------|-------------|
| `ops.observability_artifact_registry` | Tabla | Catálogo de artefactos (nombre, tipo, módulo, schema, refresh_owner, source_kind, active_flag, notes). |
| `ops.observability_refresh_log` | Tabla | Log de cada ejecución de refresh (artifact_name, started_at, finished_at, status, trigger_type, script_name, error_message). |
| `ops.v_observability_module_status` | Vista | Por módulo: artifact_count, with_refresh_count, latest_refresh_at, all_fresh, observability_coverage_pct. |
| `ops.v_observability_freshness` | Vista | Señales de frescura: artifact_name, latest_refresh_at, source (observability_refresh_log o supply_refresh_log). |
| `ops.v_observability_artifact_lineage` | Vista | Lineage: artefactos activos (artifact_name, module_name, refresh_owner, notes). |

### 2.2 Backend

| Artefacto | Ubicación | Descripción |
|-----------|-----------|-------------|
| `observability_service.py` | `app/services/` | get_observability_overview, get_observability_modules, get_observability_artifacts, get_observability_lineage, get_observability_freshness, log_refresh. |
| `observability.py` (router) | `app/routers/` | GET /ops/observability/overview, /modules, /artifacts, /lineage, /freshness. |
| Instrumentación en `refresh_real_lob_mvs_v2.py` | `scripts/` | Llamadas a log_refresh al inicio (running) y fin (ok/error) por MV. |

### 2.3 Frontend

| Artefacto | Ubicación | Descripción |
|-----------|-----------|-------------|
| API | `api.js` | getObservabilityOverview, getObservabilityModules, getObservabilityArtifacts, getObservabilityLineage, getObservabilityFreshness. |
| UI | `SystemHealthView.jsx` | Secciones: Observabilidad por módulo, Artefactos críticos, Riesgos detectados (stale/sin cobertura). |

### 2.4 Documentación e inventario

| Artefacto | Ubicación | Descripción |
|-----------|-----------|-------------|
| Inventario JSON | `docs/observability_inventory.json` | Lista de artefactos con tipo, módulo, upstream/downstream, refresh_mechanism, observability_gap. |
| Lineage | `docs/observability_data_lineage.md` | Flujos por módulo y dependencias. |
| Runbook | `docs/observability_runbook.md` | Cómo leer la UI, interpretar freshness, instrumentar nuevos módulos. |

---

## 3. Modelo de observabilidad

1. **Registry:** id, artifact_name, artifact_type, module_name, schema_name, refresh_owner, source_kind, active_flag, notes.
2. **Refresh log:** artifact_name, refresh_started_at, refresh_finished_at, refresh_status, rows_affected_if_known, trigger_type, script_name, error_message_if_any.
3. **Module status (vista):** module_name, latest_refresh_at, freshness_status (derivado), observability_coverage_pct, all_fresh.

Supply sigue usando `ops.supply_refresh_log`; la vista de módulos integra ese log para el módulo Supply Dynamics. Real LOB y Driver Lifecycle pueden escribir en `observability_refresh_log` vía `log_refresh()`.

---

## 4. Cobertura por módulo

| Módulo | Registrado en registry | Refresh con trazabilidad | Comentario |
|--------|------------------------|---------------------------|------------|
| Real LOB | Sí (mv_real_lob_*_v2, real_drill_dim_fact) | Sí (script instrumentado) | refresh_real_lob_mvs_v2.py escribe en observability_refresh_log. |
| Driver Lifecycle | Sí (mv_driver_lifecycle_base, mv_driver_weekly_stats) | No (pendiente instrumentar script) | Log manual o wrapper recomendado. |
| Supply Dynamics | Sí (mv_driver_segments_weekly, mv_supply_segments_weekly, supply_alerting_mvs) | Sí (supply_refresh_log) | run_supply_refresh_pipeline.py ya registra. |
| Ingestion | Sí (bi.ingestion_status) | N/A (ETL externo) | Estado vía /ingestion/status. |
| System Health | Sí (data_freshness_audit, data_integrity_audit) | Sí (scripts de auditoría) | run_data_freshness_audit, audit_control_tower. |

---

## 5. Flujo de datos por módulo

Ver `docs/observability_data_lineage.md` para flujos fuente → transformación → MV/view → endpoint → frontend.

---

## 6. Cómo leer la nueva UI

- **Diagnósticos → System Health:** al cargar, se pide además `getObservabilityOverview` y `getObservabilityArtifacts`.
- **Observabilidad por módulo:** tabla con módulo, número de artefactos, cuántos tienen refresh registrado, último refresh, cobertura %, estado (fresh / stale/unknown).
- **Artefactos críticos:** tabla artefacto, tipo, módulo, último refresh, origen (script/función).
- **Riesgos detectados:** lista cuando algún módulo está stale o con cobertura &lt; 100%.

---

## 7. Cómo interpretar freshness / staleness

- **fresh:** último refresh (o señal equivalente, p. ej. supply_refresh_log) dentro de las últimas 36 h.
- **stale:** último refresh anterior a 36 h o ausente.
- **unknown:** sin ninguna señal de refresh (no hay fila en observability_refresh_log ni supply_refresh_log para ese módulo/artefacto).

---

## 8. Cómo instrumentar nuevos módulos en el futuro

1. Añadir filas en `ops.observability_artifact_registry` (vía migración o INSERT manual) con artifact_name, artifact_type, module_name, refresh_owner, source_kind.
2. En el script o función que hace el refresh, al inicio: `log_refresh(artifact_name, status="running", script_name="...", trigger_type="script")`.
3. Al finalizar: `log_refresh(artifact_name, status="ok", script_name="...")` o `status="error"` con error_message.
4. Opcional: para módulos con log propio (como Supply), la vista `v_observability_module_status` puede extenderse para mapear ese log al artifact_name o módulo correspondiente.

---

## 9. Riesgos pendientes

- Driver Lifecycle: script de refresh no instrumentado aún; depende de que se añada log_refresh o un wrapper.
- Algunos artefactos (Behavioral Alerts, Fleet Leakage, Plan vs Real) no tienen fila en observability_refresh_log; su frescura se infiere de MVs compartidas (p. ej. mv_driver_segments_weekly) o de data_freshness_audit.
- Cron/scheduler de refreshes no está definido en el repo; si existe externamente, documentar en runbook.

---

## 10. Siguientes pasos recomendados

1. Aplicar migración 092 en entornos target.
2. Instrumentar `refresh_driver_lifecycle.py` (o el script que invoque refresh_driver_lifecycle_mvs) con log_refresh.
3. Documentar en runbook los cron/jobs que ejecutan refresh_real_lob_mvs_v2, run_supply_refresh_pipeline y refresh_driver_lifecycle.
4. Revisar módulos sin cobertura (Behavioral Alerts, Fleet Leakage, Action Engine) y decidir si se añaden al registry y a algún refresh log existente o nuevo.
