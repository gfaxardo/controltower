# Data Freshness & Coverage Control — Entregable final

**Proyecto:** YEGO CONTROL TOWER  
**Fecha:** 2026-03-09

---

## 1) Datasets auditados

| dataset_name | source_object | derived_object | grain | notes |
|--------------|---------------|----------------|-------|--------|
| trips_base | public.trips_all | — | day | Fuente legacy |
| trips_2026 | public.trips_2026 | — | day | Fuente viva 2026 |
| real_lob | ops.v_trips_real_canon (proxy: trips_all + trips_2026) | ops.real_rollup_day_fact | day | Rollup diario |
| real_lob_drill | ops.v_trips_real_canon (proxy) | ops.real_drill_dim_fact | week | Drill semanal/mensual |
| driver_lifecycle | ops.v_driver_lifecycle_trips_completed | ops.mv_driver_lifecycle_base | day | Viajes completados |
| driver_lifecycle_weekly | ops.mv_driver_lifecycle_base | ops.mv_driver_weekly_stats | week | Semanal |
| supply_weekly | ops.mv_driver_weekly_stats | ops.mv_supply_segments_weekly | week | Supply Dynamics |

---

## 2) Filas reales en ops.data_freshness_audit

**Evidencia ejecutada (2026-03-09):**

```
SELECT COUNT(*) FROM ops.data_freshness_audit;
  -> 7

SELECT * FROM ops.data_freshness_audit ORDER BY checked_at DESC LIMIT 20;
  driver_lifecycle       | source_max=2026-03-09 derived_max=2026-03-05 expected=2026-03-08 | status=DERIVED_STALE
  driver_lifecycle_weekly| source_max=2026-03-05 derived_max=2026-03-02 expected=2026-03-08 | status=DERIVED_STALE
  real_lob               | source_max=2026-03-08 derived_max=2026-03-07 expected=2026-03-08 | status=DERIVED_STALE
  real_lob_drill         | source_max=2026-03-08 derived_max=2026-03-02 expected=2026-03-08 | status=DERIVED_STALE
  supply_weekly          | source_max=2026-03-02 derived_max=2026-03-02 expected=2026-03-08 | status=PARTIAL_EXPECTED
  trips_2026             | source_max=2026-03-08 derived_max=None expected=2026-03-08      | status=OK
  trips_base             | source_max=2026-01-31 derived_max=None expected=2026-03-08      | status=SOURCE_STALE

SELECT dataset_name, MAX(checked_at) FROM ops.data_freshness_audit GROUP BY 1;
  (todos con last_checked = 2026-03-09 12:53:42)
```

---

## 3) Alertas detectadas

| dataset_name | status | alert_reason / mensaje accionable |
|--------------|--------|-----------------------------------|
| trips_base | SOURCE_STALE | Fuente con data hasta 2026-01-31; se esperaba hasta 2026-03-08. Usar trips_2026 para datos recientes. |
| real_lob | DERIVED_STALE | Derivado atrasado 1 día (fuente hasta 2026-03-08, derivado hasta 2026-03-07). Ejecutar backfill si aplica. |
| real_lob_drill | DERIVED_STALE | Derivado atrasado 6 días (fuente hasta 2026-03-08, derivado hasta 2026-03-02). Ejecutar backfill Real LOB. |
| driver_lifecycle | DERIVED_STALE | Derivado atrasado 4 días (fuente hasta 2026-03-09, derivado hasta 2026-03-05). REFRESH mv_driver_lifecycle_base. |
| driver_lifecycle_weekly | DERIVED_STALE | Derivado atrasado 3 días (fuente hasta 2026-03-05, derivado hasta 2026-03-02). REFRESH MVs semanales. |
| supply_weekly | PARTIAL_EXPECTED | Periodo abierto o retraso menor; no error crítico. |

---

## 4) Endpoints funcionando

- **GET /ops/data-freshness** — Devuelve lista de auditoría (última por dataset). Implementado en `app/routers/ops.py` y `app/services/data_freshness_service.py`.
- **GET /ops/data-freshness/alerts** — Devuelve `{ "summary": { "total_datasets", "ok", "alerts_count", "by_status" }, "alerts": [ { "dataset_name", "status", "message", ... } ], "last_checked" }`.
- **GET /ops/data-freshness/expectations** — Devuelve config de expectativas (dataset_name, grain, source_object, derived_object, alert_threshold_days, notes si existe).
- **POST /ops/data-freshness/run** — Ejecuta el script de audit y escribe en `ops.data_freshness_audit`.

Prueba con el backend levantado: `curl http://localhost:8000/ops/data-freshness` y `curl http://localhost:8000/ops/data-freshness/alerts`.

---

## 5) Mejoras de performance aplicadas

- **Ventana acotada:** todas las consultas MAX(fecha) usan `WHERE fecha >= current_date - RECENT_DAYS` (default 180; configurable con `DATA_FRESHNESS_RECENT_DAYS`) para evitar full scan en tablas grandes.
- **Evitar vistas pesadas:** cuando la fuente configurada es `ops.v_trips_real_canon`, el script no consulta la vista; usa `max(MAX(trips_all), MAX(trips_2026))` sobre las tablas base con la misma ventana.
- **Columnas temporales correctas:** cada expectativa tiene source_date_column y derived_date_column; el script usa identificadores escapados (psycopg2.sql.Identifier) para evitar inyección y usar índices.

Documentado en `docs/data_freshness_monitoring.md` (sección 4 y 9).

---

## 6) Archivos modificados / creados

| Archivo | Acción |
|---------|--------|
| docs/data_freshness_lineage_map.md | Actualizado: sección 0 fuente viva, tabla resumen por dataset. |
| docs/data_freshness_monitoring.md | Actualizado: estados SOURCE_STALE/DERIVED_STALE, arquitectura, interpretar alertas, qué hacer si lag. |
| docs/data_freshness_entregable_final.md | Creado: este entregable. |
| backend/alembic/versions/072_data_freshness_audit_and_expectations.py | Ya existía: tablas expectations + audit + semilla. |
| backend/alembic/versions/073_data_freshness_notes_and_status.py | Creado: columna notes en expectations. |
| backend/scripts/run_data_freshness_audit.py | Reescrito: ventana acotada, proxy para canon, status SOURCE_STALE/DERIVED_STALE. |
| backend/scripts/run_freshness_evidence.py | Creado: ejecuta audit + 3 consultas de evidencia. |
| backend/scripts/query_freshness_evidence.py | Creado: solo las 3 consultas de evidencia. |
| backend/app/services/data_freshness_service.py | Actualizado: mensajes DERIVED_STALE/SOURCE_STALE, expectations con notes opcional. |
| backend/app/routers/ops.py | Ya tenía: GET/POST data-freshness y data-freshness/run. |

---

## 7) Comandos ejecutados

```bash
cd backend
python -m alembic upgrade 072_data_freshness_audit
python -m alembic upgrade 073_data_freshness_notes
DATA_FRESHNESS_RECENT_DAYS=90 python -m scripts.run_data_freshness_audit
python -m scripts.query_freshness_evidence
```

Para ejecutar el audit con ventana por defecto (180 días):

```bash
python -m scripts.run_data_freshness_audit
```

---

## Validación de negocio (evidencia)

- **Fuente viva real:** `public.trips_2026` (hasta 2026-03-08 en la ejecución).
- **Hasta qué fecha llega la fuente:** trips_2026 hasta 2026-03-08; trips_all hasta 2026-01-31 (legacy).
- **Hasta qué fecha llega Real LOB:** derivado rollup hasta 2026-03-07; drill hasta 2026-03-02.
- **Hasta qué fecha llega Driver Lifecycle:** derivado base hasta 2026-03-05; weekly hasta 2026-03-02.
- **Datasets en LAGGING/DERIVED_STALE:** real_lob, real_lob_drill, driver_lifecycle, driver_lifecycle_weekly.
- **Datasets en PARTIAL_EXPECTED:** supply_weekly.
- **Dataset en SOURCE_STALE:** trips_base.

---

## Veredicto final

**LISTO PARA CERRAR**

- Implementación completa: tablas, script ligero, endpoints, documentación.
- Ejecución real: audit corrido con evidencia SQL persistida en ops.data_freshness_audit.
- Validación: evidencia de fuente viva (trips_2026), fechas por dataset, alertas accionables.
- Performance: consultas acotadas y proxy para vista canónica; script terminó en ~83 s con RECENT_DAYS=90.
