# Freshness & Coverage Control — Cierre de fase

**Proyecto:** YEGO CONTROL TOWER  
**Fecha:** 2026-03-09

---

## 1. Fuentes reales detectadas

| Fuente | Tipo | Columna temporal | Vigencia |
|--------|------|------------------|----------|
| `public.trips_all` | table | `fecha_inicio_viaje` | Histórico; puede estar cortada (ej. hasta ene). **No asumir vigente.** |
| `public.trips_2026` | table | `fecha_inicio_viaje` | Partición 2026; suele ser la más fresca para 2026. |
| `public.trips_unified` | view | `fecha_inicio_viaje` | UNION trips_all (< 2026-01-01) + trips_2026 (>= 2026-01-01). |
| `ops.v_trips_real_canon` | view | `fecha_inicio_viaje` | Canónica Real LOB: mismo corte + columnas mínimas + source_table. |

---

## 2. Fuente vigente real

- **Para Real LOB:** la unión lógica en `ops.v_trips_real_canon` (trips_all + trips_2026 con corte por fecha). La fuente “vigente” para fechas recientes es la que contiene esos datos (típicamente `trips_2026` para >= 2026-01-01).
- **Para Driver Lifecycle:** `public.trips_unified` (ya no se asume solo trips_all).

---

## 3. Datasets derivados auditados

- **trips_base** — solo fuente (trips_all).
- **trips_2026** — solo fuente (trips_2026).
- **real_lob** — fuente: v_trips_real_canon; derivado: real_rollup_day_fact (trip_day).
- **real_lob_drill** — fuente: v_trips_real_canon; derivado: real_drill_dim_fact (period_start).
- **driver_lifecycle** — fuente: v_driver_lifecycle_trips_completed; derivado: mv_driver_lifecycle_base (last_completed_ts).
- **driver_lifecycle_weekly** — fuente: mv_driver_lifecycle_base; derivado: mv_driver_weekly_stats (week_start).
- **supply_weekly** — fuente: mv_driver_weekly_stats; derivado: mv_supply_segments_weekly (week_start).

---

## 4. Reglas de expectativa definidas

- **Diario:** data hasta ayer (expected_delay_days = 1).
- **Semanal:** hasta el domingo de la última semana cerrada; semana actual = parcial.
- **Mensual:** hasta el último día del mes pasado; mes actual = parcial.
- **Estados:** OK, PARTIAL_EXPECTED, LAGGING, MISSING_EXPECTED_DATA (documentados en `docs/data_freshness_monitoring.md`).

---

## 5. Objetos creados

| Objeto | Descripción |
|--------|-------------|
| `ops.data_freshness_expectations` | Tabla de config: dataset_name, grain, expected_delay_days, source_object, derived_object, alert_threshold_days. |
| `ops.data_freshness_audit` | Tabla de auditoría: una fila por dataset por ejecución (source_max_date, derived_max_date, expected_latest_date, lag_days, status, alert_reason, checked_at). |
| Migración `072_data_freshness_audit_and_expectations` | Crea las tablas y semilla de expectativas. |

---

## 6. Alertas detectadas

Las alertas se generan al ejecutar el script de auditoría o el endpoint POST `/ops/data-freshness/run`. Ejemplos de mensajes:

- *"La fuente trips_2026 tiene data hasta 2026-03-07, pero real_drill_dim_fact solo hasta 2026-03-02"* (LAGGING).
- *"Se esperaba data para 2026-03-08 y no existe en la fuente base"* (MISSING_EXPECTED_DATA).
- *"El mes actual está abierto; se considera parcial, no error"* (PARTIAL_EXPECTED).

---

## 7. Archivos modificados / creados

| Archivo | Acción |
|---------|--------|
| `docs/data_freshness_lineage_map.md` | Creado — lineage fuentes → canónica → derivados. |
| `docs/data_freshness_monitoring.md` | Creado — reglas, objetos, API, validación. |
| `docs/data_freshness_cierre_fase.md` | Creado — este resumen. |
| `backend/alembic/versions/072_data_freshness_audit_and_expectations.py` | Creado — migración. |
| `backend/scripts/run_data_freshness_audit.py` | Creado — script que escribe en data_freshness_audit. |
| `backend/scripts/sql/validate_data_freshness.sql` | Creado — validación SQL. |
| `backend/app/services/data_freshness_service.py` | Creado — get_freshness_audit, get_freshness_alerts, get_freshness_expectations. |
| `backend/app/routers/ops.py` | Modificado — endpoints GET/POST data-freshness y POST data-freshness/run. |

---

## 8. Comandos ejecutados

```bash
cd backend
python -m alembic upgrade 072_data_freshness_audit
python -m scripts.run_data_freshness_audit
```

Para validación SQL (contra la DB):

```bash
psql -f backend/scripts/sql/validate_data_freshness.sql
```

API:

- `GET /ops/data-freshness` — auditoría (última por dataset).
- `GET /ops/data-freshness/alerts` — resumen de alertas.
- `GET /ops/data-freshness/expectations` — config.
- `POST /ops/data-freshness/run` — ejecuta el chequeo y escribe en audit.

---

## 9. Veredicto final

**LISTO PARA CERRAR** (con observaciones menores)

- **Cumplido:** Ya no se asume que trips_all es la fuente vigente; queda documentada la fuente base por dataset; se mide freshness de fuente y derivado por separado; se mide cobertura esperada; se pueden detectar faltantes; existe salida auditable (tabla + API); documentación en lineage map y monitoring.
- **Observaciones:**
  1. El script `run_data_freshness_audit` puede tardar en entornos con tablas muy grandes (trips_all, v_trips_real_canon). Recomendable ejecutarlo con `statement_timeout` alto o en ventana de bajo uso.
  2. Integración en UI: consumir `GET /ops/data-freshness/alerts` en dashboard o admin para mostrar indicador de datos atrasados (pendiente de implementar en frontend si se desea).
  3. Si en un entorno no existe `trips_2026`, el dataset trips_2026 en expectations fallará al consultar; el script sigue con el resto y registra el error para ese dataset.
