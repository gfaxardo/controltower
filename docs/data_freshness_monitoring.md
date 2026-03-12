# Monitoreo de Freshness & Cobertura

**Proyecto:** YEGO CONTROL TOWER  
**Objetivo:** Saber qué fuente base está vigente, hasta qué fecha llega, si los derivados absorbieron la data, si falta data esperada, y mostrar alertas accionables.

---

## 0. Regla global "Falta data"

**Regla única para todo el sistema:**

- **Solo** mostrar estado **"Falta data"** cuando la **última fecha con data del dataset/objeto derivado** es **menor o igual a `current_date - 2`** (es decir, no llega hasta ayer).
- Si `derived_max_date` es **ayer** → **NO** falta data (estado Fresca o Parcial esperada).
- Si `derived_max_date` es **antes de ayer** o NULL → **SÍ** falta data.

Se aplica en: estado por fila (ej. Real LOB drill), indicador global en UI (banner) y cualquier vista que muestre estado de datos. Detalle y auditoría por vista: [system_views_freshness_audit.md](system_views_freshness_audit.md).

---

## 1. Principios

- **No asumir que `trips_all` es la fuente vigente:** inspeccionar `trips_all`, `trips_2026` (y otras particiones si existen) y la vista canónica `ops.v_trips_real_canon` / `public.trips_unified`.
- **Separar:** (A) freshness de fuente, (B) freshness de objeto derivado, (C) cobertura esperada.
- **Reglas explícitas:** las expectativas (“debería haber data hasta X”) están en `ops.data_freshness_expectations` y documentadas aquí.
- **Auditable:** cada ejecución del chequeo se guarda en `ops.data_freshness_audit`.

---

## 2. Objetos creados

| Objeto | Tipo | Descripción |
|--------|------|-------------|
| `ops.data_freshness_expectations` | tabla | Config por dataset: grain, expected_delay_days, source_object, derived_object, alert_threshold_days. |
| `ops.data_freshness_audit` | tabla | Una fila por dataset por ejecución: source_max_date, derived_max_date, expected_latest_date, lag_days, missing_expected_days, status, alert_reason, checked_at. |

---

## 3. Reglas de expectativa (cobertura)

Definidas en código y en esta doc. **No dejarlas implícitas.**

- **Diario (grain=day):** normalmente se espera data hasta **ayer** (expected_delay_days=1). Si el día actual está abierto, no se considera error; puede marcarse PARTIAL_EXPECTED.
- **Semanal (grain=week):** al menos hasta el **domingo de la última semana cerrada**. La semana actual (lunes–domingo) está abierta → parcial, no error.
- **Mensual (grain=month):** al menos hasta el **último día del mes pasado**. El mes actual está abierto → parcial.

**Estados (status):**

- **OK:** derivado al día con lo esperado; no hay lag respecto a la fuente.
- **PARTIAL_EXPECTED:** el periodo actual está abierto o el retraso es menor al umbral; no se considera error crítico.
- **LAGGING / DERIVED_STALE:** el objeto derivado está atrasado respecto a la fuente (ej. fuente hasta 2026-03-07, derivado hasta 2026-03-02). Acción: ejecutar backfill o REFRESH de la MV/fact.
- **SOURCE_STALE:** la fuente base está atrasada respecto a lo esperado (ej. trips_all cortada). Acción: revisar carga de datos en origen o usar tabla particionada (trips_2026).
- **MISSING_EXPECTED_DATA:** se esperaba data hasta una fecha y no existe o está incompleta (fuente o derivado).

---

## 4. Cómo ejecutar el chequeo

Desde el backend:

```bash
cd backend && python -m scripts.run_data_freshness_audit
```

- Lee `ops.data_freshness_expectations` (active = true).
- Para cada dataset: consulta `source_object` y opcionalmente `derived_object` para obtener MAX(fecha).
- Calcula `expected_latest_date` según grain y expected_delay_days.
- Calcula lag_days, missing_expected_days, status y alert_reason.
- Inserta una fila por dataset en `ops.data_freshness_audit`.

**Performance:** el script usa ventana acotada (`DATA_FRESHNESS_RECENT_DAYS`, default 180) para MAX(fecha), evitando full scan. Para fuentes canónicas (v_trips_real_canon) usa proxy: max(trips_all, trips_2026) sobre tablas base. Recomendación: ejecutar vía cron (ej. cada hora o después del backfill/refresh de MVs).

---

## 5. API / visibilidad

- **GET /ops/data-freshness**  
  Devuelve la auditoría (por defecto última ejecución por dataset).  
  Parámetro: `latest_only` (default true).

- **GET /ops/data-freshness/alerts**  
  Resumen de alertas: lista de datasets con status distinto de OK y mensaje accionable (ej. “La fuente trips_2026 tiene data hasta 2026-03-07, pero real_drill_dim_fact solo hasta 2026-03-02”).

- **GET /ops/data-freshness/expectations**  
  Configuración de expectativas (grain, source/derived, alert_threshold_days) para admin/documentación.

- **GET /ops/data-freshness/global** — Estado global para el banner de UI (fresca | parcial_esperada | atrasada | falta_data | sin_datos). Incluye source_max_date, derived_max_date, lag_days. Regla: Falta data solo si derived_max_date <= today-2. Usado por GlobalFreshnessBanner.

- **GET /ops/data-pipeline-health** — Centro de observabilidad: por dataset source_max_date, derived_max_date, lag_days, expected_latest_date, status, alert_reason, last_checked_at. Parámetro: `latest_only` (default true).

- **POST /ops/pipeline-refresh** — Ejecuta pipeline unificado (backfill Real LOB, refresh driver lifecycle, refresh supply, auditoría). Parámetros opcionales: skip_backfill, skip_driver, skip_supply, skip_audit. Uso: cron o admin. Timeout largo (ej. 1h).

Integración: banner global de frescura en vistas principales (fuente, vista, lag, estado); "Ver salud del pipeline" expande tabla por dataset; detalle con GET /ops/data-freshness/alerts.

---

## 6. Ejemplos de alertas esperadas

1. *“La fuente trips_2026 tiene data hasta 2026-03-07, pero real_drill_dim_fact solo hasta 2026-03-02”*  
   → Status LAGGING; acción: ejecutar backfill Real LOB o revisar pipeline.

2. *“Se esperaba data para 2026-03-08 y no existe en la fuente base”*  
   → Status MISSING_EXPECTED_DATA; acción: revisar carga de viajes en origen.

3. *“El mes actual está abierto; se considera parcial, no error”*  
   → Status PARTIAL_EXPECTED; no requiere acción crítica.

---

## 7. Migración

La migración `072_data_freshness_audit_and_expectations` crea las tablas y la semilla de expectativas para:

- trips_base, trips_2026  
- real_lob, real_lob_drill  
- driver_lifecycle, driver_lifecycle_weekly  
- supply_weekly  

Si una tabla no existe (ej. `trips_2026`), el script de auditoría escribirá error en ese dataset y seguirá con el resto.

---

## 8. Validación rápida (SQL)

- Fuente base más fresca:  
  `SELECT 'trips_all' AS src, MAX(fecha_inicio_viaje)::date FROM public.trips_all UNION ALL SELECT 'trips_2026', MAX(fecha_inicio_viaje)::date FROM public.trips_2026;`
- Comparar con derivado:  
  `SELECT MAX(trip_day) FROM ops.real_rollup_day_fact;`  
  `SELECT MAX(period_start) FROM ops.real_drill_dim_fact;`
- Última auditoría:  
  `SELECT * FROM ops.data_freshness_audit ORDER BY checked_at DESC LIMIT 20;`

---

## 9. Arquitectura final

- **Expectations** (config) → **Script** (run_data_freshness_audit) → **Audit** (tabla) → **API** (GET data-freshness, alerts, expectations; POST data-freshness/run).
- Fuente viva detectada por comparación de max_date en ventana reciente: trips_2026 vs trips_all; la que tiene la fecha más reciente es la viva.

## 10. Cómo interpretar alertas

- **DERIVED_STALE / LAGGING:** el pipeline de derivado (backfill, REFRESH MV) no ha absorbido la data reciente de la fuente. Ejecutar backfill Real LOB o `REFRESH MATERIALIZED VIEW` de Driver Lifecycle / Supply. En la UI (tabla "Ver salud del pipeline") se muestra con fondo ámbar (problema de propagación).
- **SOURCE_STALE:** la tabla fuente (ej. trips_all) está cortada. Más severo: en la UI se muestra con fondo rojo. Para viajes: usar **trips_2026** como fuente viva; **trips_base** (trips_all) está marcada como legacy en expectativas — SOURCE_STALE en trips_base es esperado y no bloquea el estado global del banner (el primario es real_lob_drill).
- **PARTIAL_EXPECTED:** periodo actual (día/semana/mes) aún abierto; no es error.
- **MISSING_EXPECTED_DATA:** faltan días/semanas/meses que ya deberían estar cerrados; revisar carga en origen o pipeline.

## 11. Qué hacer si aparece lag

1. Confirmar con `GET /ops/data-freshness`: ver source_max_date vs derived_max_date.
2. Si derivado atrasado: ejecutar `python -m scripts.backfill_real_lob_mvs` (Real LOB) o refresh de MVs Driver Lifecycle/Supply.
3. Si fuente atrasada: revisar ETL que alimenta trips_all/trips_2026; priorizar trips_2026 para datos recientes.

---

---

## 12. Automatización del audit y del pipeline

- **Solo audit:** `python -m scripts.run_data_freshness_audit` (o `POST /ops/data-freshness/run`). Escribe en `ops.data_freshness_audit`. No refresca derivados.
- **Pipeline completo (recomendado para reparar atrasos):** `python -m scripts.run_pipeline_refresh_and_audit`. Orden: 1) Backfill Real LOB (mes actual + anterior), 2) `ops.refresh_driver_lifecycle_mvs()`, 3) `ops.refresh_supply_alerting_mvs()`, 4) run_data_freshness_audit. Opciones: `--skip-backfill`, `--skip-driver`, `--skip-supply`, `--skip-audit`, `--backfill-months N`.
- **Cron sugerido:** Diario tras carga de viajes, ej. `0 6 * * * cd /path/to/backend && python -m scripts.run_pipeline_refresh_and_audit >> /var/log/ct_pipeline.log 2>&1`.
- **Reejecución manual:** Mismo comando; o `POST /ops/pipeline-refresh` (puede tardar varios minutos).

**Evidencia:** Cada ejecución del audit deja filas en `ops.data_freshness_audit`. La UI muestra la última ejecución en el banner y en "Ver salud del pipeline".

---

## 13. Centro de observabilidad

- **Vista técnica:** GET /ops/data-pipeline-health devuelve la tabla por dataset (dataset_name, source_object, source_max_date, derived_max_date, lag_days, expected_latest_date, status, alert_reason, checked_at).
- **UI:** El banner global (GlobalFreshnessBanner) muestra estado, última fecha en vista, fuente viva y lag; el botón "Ver salud del pipeline" despliega la tabla completa por dataset.
- **Mapa del pipeline:** [data_pipeline_observability_map.md](data_pipeline_observability_map.md) documenta fuente viva real, derivado, mecanismo de refresh y punto de rotura por dataset.

---

*Véase también: [data_freshness_lineage_map.md](data_freshness_lineage_map.md), [data_pipeline_observability_map.md](data_pipeline_observability_map.md), [system_views_freshness_audit.md](system_views_freshness_audit.md).*
