# Runbook — Observabilidad Control Tower (Fase 1)

## Cómo comprobar que funciona

1. **Backend:** Tras aplicar migración 092, reiniciar API. Llamar a `GET /ops/observability/overview`. Debe devolver 200 y un JSON con `modules` (lista) y `recent_refreshes_7d`.
2. **Frontend:** Ir a **Diagnósticos → System Health**. Debe mostrarse la sección **Observabilidad por módulo** con al menos los módulos registrados en el registry (Real LOB, Driver Lifecycle, Supply Dynamics, Ingestion, System Health). Si la migración no está aplicada, la sección no aparece o aparece vacía sin error.
3. **Refresh log:** Ejecutar `python -m scripts.refresh_real_lob_mvs_v2` (en backend/). Luego `GET /ops/observability/freshness` o revisar en UI **Artefactos críticos** que `ops.mv_real_lob_month_v2` y `ops.mv_real_lob_week_v2` tengan **Último refresh** reciente.

---

## Dónde mirar

| Qué | Dónde |
|-----|--------|
| Estado por módulo | Diagnósticos → System Health → tabla "Observabilidad por módulo". |
| Último refresh por artefacto | Misma pantalla → "Artefactos críticos"; columna "Último refresh". |
| Riesgos (stale / sin cobertura) | Misma pantalla → recuadro ámbar "Riesgos detectados". |
| API directa | GET /ops/observability/overview, /ops/observability/artifacts, /ops/observability/freshness. |
| Log de Supply | GET /ops/supply/freshness (last_refresh desde ops.supply_refresh_log). |
| Log de Real LOB | ops.observability_refresh_log (tras ejecutar refresh_real_lob_mvs_v2). |

---

## Cómo verificar si un módulo está stale

1. En **Observabilidad por módulo**, revisar la columna **Estado**: si es "stale/unknown", el módulo no tiene refreshes recientes (o no hay trazabilidad).
2. En **Artefactos críticos**, filtrar por ese módulo y ver si **Último refresh** está vacío o es una fecha antigua (> 36 h).
3. Para Supply: además usar **GET /ops/supply/freshness** (status: fresh/stale/unknown).
4. Para freshness global: **GET /ops/data-freshness/global** (banner) o tabla "Pipeline (freshness por dataset)" en System Health.

---

## Cómo validar si un script dejó log

1. **Real LOB:** Después de `python -m scripts.refresh_real_lob_mvs_v2`, consultar `SELECT * FROM ops.observability_refresh_log WHERE artifact_name LIKE 'ops.mv_real_lob%' ORDER BY refresh_started_at DESC LIMIT 4;` Debe haber filas con refresh_status = 'ok' y refresh_finished_at reciente.
2. **Supply:** Después de `python -m scripts.run_supply_refresh_pipeline` o POST /ops/supply/refresh, consultar `SELECT * FROM ops.supply_refresh_log ORDER BY started_at DESC LIMIT 1;` status = 'ok', finished_at not null.
3. **Driver Lifecycle:** Hoy no escribe en observability_refresh_log; cuando se instrumente, mismo patrón que Real LOB.

---

## Checklist de validación manual

- [ ] Migración 092 aplicada (existen ops.observability_artifact_registry y ops.observability_refresh_log).
- [ ] GET /ops/observability/overview devuelve modules con al menos Real LOB, Supply Dynamics, Ingestion, System Health.
- [ ] System Health muestra sección "Observabilidad por módulo" y "Artefactos críticos".
- [ ] Tras ejecutar refresh_real_lob_mvs_v2, en Artefactos críticos aparece "Último refresh" para ops.mv_real_lob_month_v2 y ops.mv_real_lob_week_v2.
- [ ] Supply muestra "Último refresh" y estado fresh cuando run_supply_refresh_pipeline se ejecutó recientemente.
- [ ] GET /ops/system-health sigue respondiendo 200 (regresión).

---

## Añadir un nuevo artefacto al registry

```sql
INSERT INTO ops.observability_artifact_registry
(artifact_name, artifact_type, module_name, schema_name, refresh_owner, source_kind, active_flag, notes)
VALUES
('ops.mi_nueva_mv', 'materialized_view', 'Mi Módulo', 'ops', 'mi_script_refresh.py', 'script', true, 'Descripción breve')
ON CONFLICT (artifact_name) DO NOTHING;
```

Luego, en el script que refresca, al inicio y al final:

```python
from app.services.observability_service import log_refresh

log_refresh("ops.mi_nueva_mv", status="running", script_name="mi_script_refresh.py", trigger_type="script")
# ... hacer REFRESH ...
log_refresh("ops.mi_nueva_mv", status="ok", script_name="mi_script_refresh.py", trigger_type="script")
```
