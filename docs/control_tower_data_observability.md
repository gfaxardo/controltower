# Control Tower — Data Observability

Documentación de la capa de auditoría y observabilidad de datos del YEGO Control Tower. El sistema detecta automáticamente pérdida de datos, inconsistencias entre capas, joins defectuosos, duplicaciones, semanas incompletas, MVs stale y divergencias entre vistas.

---

## 1. Arquitectura del sistema

### Fuentes

| Fuente | Descripción | Cobertura |
|--------|-------------|-----------|
| `public.trips_all` | Legacy | 2025 y enero 2026 parcial |
| `public.trips_2026` | Fuente viva | Final enero 2026 → presente |

### Capa canónica

- **`ops.v_trips_canonical`**: Vista unificada de viajes con columnas estándar.
  - Origen: `ops.v_trips_real_canon` (que une `trips_all` &lt; 2026-01-01 y `trips_2026` &gt;= 2026-01-01 con dedup por `id`).
  - Columnas: `trip_id`, `completed_at`, `trip_start_at`, `park_id`, `driver_id`, `pago_corporativo`, `fare_total`, `distance_km`, `condicion`, `source_table`.

### Capa analítica (principales objetos)

- `ops.mv_real_lob_drill` / `ops.real_drill_dim_fact`
- `ops.mv_real_lob` / `ops.real_rollup_day_fact`
- `ops.mv_driver_lifecycle_weekly` / `ops.mv_driver_weekly_stats`
- `ops.mv_supply_weekly`
- `ops.mv_driver_segments_weekly`
- `ops.mv_supply_alerts_weekly`

---

## 2. Vista canónica de viajes

**`ops.v_trips_canonical`**

- Unifica `trips_all` y `trips_2026` sin duplicar por `trip_id` (la deduplicación se hace en `v_trips_real_canon`).
- Expone nombres de columna estándar para auditorías y reportes.

---

## 3. Auditoría de ingestión

**`ops.v_ingestion_audit`**

| Campo   | Descripción                    |
|---------|--------------------------------|
| fuente  | `trips_all` o `trips_2026`     |
| mes     | Mes (date)                     |
| viajes  | Total viajes                   |
| viajes_b2b | Viajes B2B (pago_corporativo) |
| drivers | Conductores distintos          |
| parks   | Parks distintos                 |

**Uso:** Detectar ingestión incompleta, caídas abruptas o duplicaciones por fuente.

---

## 3b. Ventana temporal (performance)

Desde la migración **077**, las vistas de auditoría que leen de la canónica o de Real LOB están limitadas a **últimos 24 meses** (`fecha_inicio_viaje >= current_date - 24 months`). Así se evitan timeouts y full scans sobre toda la historia; la auditoría sigue siendo exacta para operación diaria. Detalle en **docs/audit_layer_performance_hardening.md**.

---

## 4. Auditoría de integridad de viajes

**`ops.v_trip_integrity`**

Compara viajes completados en la capa canónica vs viajes en la capa Real LOB (suma de `trips` en `real_rollup_day_fact` por mes). **Solo últimos 24 meses.**

| Campo           | Descripción                          |
|-----------------|--------------------------------------|
| mes             | Mes                                  |
| viajes_base     | Viajes Completado en canonical       |
| viajes_real_lob | Suma trips en real_rollup_day_fact   |
| loss_pct        | (viajes_base - viajes_real_lob) / viajes_base * 100 |
| status          | OK \| WARNING (loss &gt; 0.1%) \| CRITICAL (loss &gt; 1%) |

**Regla:** Si `loss_pct > 1%` → **CRITICAL**.

---

## 5. Auditoría B2B

**`ops.v_b2b_integrity`**

Compara B2B en canonical vs B2B en Real LOB por mes.

| Campo        | Descripción                    |
|--------------|--------------------------------|
| mes          | Mes                            |
| b2b_base     | Conteo B2B en canonical        |
| b2b_real_lob | Suma b2b_trips en rollup día   |
| diff_pct     | Diferencia porcentual          |

---

## 6. Auditoría de mapping LOB

**`ops.v_lob_mapping_audit`**

Objetivo: detectar viajes sin clasificación LOB (UNCLASSIFIED / sin LOB).

| Campo           | Descripción              |
|-----------------|--------------------------|
| mes             | Mes                      |
| viajes_base     | Viajes completados base  |
| viajes_con_lob  | Con LOB asignado         |
| viajes_sin_lob  | Sin LOB / UNCLASSIFIED   |
| pct_sin_lob     | Porcentaje sin LOB       |

---

## 7. Auditoría de joins críticos

**`ops.v_join_integrity`**

Mide pérdida de filas en joins clave (p. ej. trips → parks).

| Campo       | Descripción                    |
|-------------|--------------------------------|
| join_name   | Nombre del join (p. ej. trips_to_parks) |
| rows_base   | Filas antes del join           |
| rows_joined | Filas después del join         |
| loss_pct    | Porcentaje de filas perdidas   |

---

## 8. Auditoría de duplicados

**`ops.v_duplicate_trips`**

Lista `trip_id` que aparecen más de una vez entre `trips_all` y `trips_2026` (antes de la dedup en canonical).

| Campo    | Descripción        |
|----------|--------------------|
| trip_id  | ID duplicado       |
| count    | Número de apariciones |

---

## 9. Auditoría semanal (WoW)

**`ops.v_weekly_trip_volume`**

Volumen por semana para detectar semanas incompletas o volatilidad artificial.

| Campo      | Descripción   |
|------------|---------------|
| week_start | Inicio semana |
| viajes     | Total viajes  |
| drivers    | Conductores distintos |
| parks      | Parks distintos |

---

## 10. Auditoría de materialized views

**`ops.v_mv_freshness`**

Freshness de las MVs principales: último periodo cargado, lag en horas, estado.

| Campo             | Descripción                          |
|-------------------|--------------------------------------|
| view_name         | Nombre de la MV                      |
| last_period_start | Última fecha de periodo en la MV     |
| lag_hours         | Horas desde ese periodo hasta ahora  |
| status            | OK \| STALE (según umbral ~48h o última semana) |

Vistas incluidas: `mv_real_lob_drill`, `mv_real_lob`, `mv_driver_lifecycle_weekly`, `mv_supply_weekly`, `mv_driver_segments_weekly`.

---

## 11. Auditoría de consistencia entre módulos

**`ops.v_driver_consistency`**

Compara conductores activos por semana según:

- Viajes (canonical completados)
- Driver lifecycle (`mv_driver_weekly_stats`)
- Supply (`mv_supply_weekly`)

| Campo              | Descripción                    |
|--------------------|--------------------------------|
| week               | Semana                         |
| drivers_trips      | Desde trips                    |
| drivers_lifecycle  | Desde lifecycle                |
| drivers_supply     | Desde supply                   |
| diff               | Máxima diferencia entre fuentes |

---

## 12. Reporte global de integridad

**`ops.v_control_tower_integrity_report`**

Una fila por check con estado global.

| Campo     | Descripción                          |
|----------|--------------------------------------|
| check_name | TRIP LOSS, B2B LOSS, LOB MAPPING LOSS, DUPLICATE TRIPS, MV STALE, JOIN LOSS, WEEKLY ANOMALY |
| status   | OK \| WARNING \| CRITICAL            |
| severity | OK \| WARNING \| CRITICAL            |
| details  | JSON con métricas asociadas          |

**Estados:** OK, WARNING, CRITICAL.

---

## 13. Script de auditoría automática

**`backend/scripts/audit_control_tower.py`**

1. Ejecuta las vistas de auditoría (vía consultas que las usan).
2. Escribe resultados en `ops.data_integrity_audit`.
3. Imprime un diagnóstico en consola.

**Uso:**

```bash
cd backend && python -m scripts.audit_control_tower
```

**Ejemplo de salida:**

```
============================================================
CONTROL TOWER DATA AUDIT
============================================================
  Trips integrity........ OK
  LOB mapping............ WARNING (2.1% unmapped)
  B2B classification..... OK
  Driver lifecycle....... OK
  Supply consistency..... OK
  Materialized views..... OK
  Weekly anomalies....... WARNING

Results persisted to ops.data_integrity_audit.
============================================================
```

---

## 14. Persistencia de auditorías

**Tabla `ops.data_integrity_audit`**

Cada ejecución del script inserta una fila por check.

| Campo        | Tipo       | Descripción                |
|-------------|------------|----------------------------|
| id          | serial     | PK                         |
| timestamp   | timestamptz| Momento de la ejecución    |
| check_name  | text       | Nombre del check           |
| status      | text       | OK \| WARNING \| CRITICAL  |
| metric_value| numeric    | Valor numérico (opcional)  |
| details     | text       | Detalle (opcional)         |

Índices: `(timestamp DESC)`, `(check_name, timestamp DESC)`.

---

## 15. Dashboard de observabilidad

En la pestaña **System Health** del Control Tower se muestra:

- **Integridad:** Resumen (OK / WARNING / CRITICAL) y tabla de checks desde `v_control_tower_integrity_report`.
- **Materialized views:** Freshness (vista, último periodo, lag, status) desde `v_mv_freshness`.
- **Ingestión:** Últimos meses por fuente desde `v_ingestion_audit`.
- **Pipeline:** Freshness por dataset (desde `data_freshness_audit` / data-pipeline-health).
- **Acción:** Botón *Ejecutar auditoría* que llama a `POST /ops/integrity-audit/run` (ejecuta el script y actualiza datos).

---

## 16. API

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/ops/integrity-report` | Reporte de integridad (lista de checks). |
| GET | `/ops/system-health` | Estado completo para el dashboard (integridad, MVs, ingestión, última auditoría). |
| POST | `/ops/integrity-audit/run` | Ejecuta el script de auditoría y persiste en `ops.data_integrity_audit`. |

---

## 17. Interpretación de resultados

- **TRIP LOSS CRITICAL:** Pérdida &gt; 1% entre canonical y Real LOB → revisar pipeline Real LOB (filtros, joins, ventana de backfill).
- **LOB MAPPING WARNING:** % sin LOB &gt; 1–2% → revisar `canon.map_real_tipo_servicio_to_lob_group` y tipos de servicio nuevos.
- **DUPLICATE TRIPS (warning de negocio/operación):** El check cuenta `trip_id` que aparecen en **ambas** fuentes (trips_all y trips_2026) en los últimos 24 meses. Es **esperable** si hay solapamiento en la frontera 2026-01-01; la vista canónica ya hace DISTINCT ON (id) con prioridad a trips_2026, por lo que no hay duplicados en la base canónica. WARNING = “hay ids en ambas fuentes”; revisar solo si el número crece (posible carga doble). Ver **docs/audit_layer_performance_hardening.md** (FASE D).
- **MV STALE:** Alguna MV con lag &gt; umbral → ejecutar refresh (backfill Real LOB, refresh driver lifecycle, refresh supply).
- **JOIN LOSS:** Pérdida alta en trips → parks → revisar `park_id` y catálogo `parks`.
- **WEEKLY ANOMALY (warning de negocio):** El script compara **última semana cerrada** vs **anterior semana cerrada** (no la semana actual) para evitar falsos positivos. Si sigue en WARNING, es caída real WoW en semanas completas; revisar operación o eventos. Ver **docs/audit_layer_performance_hardening.md** (FASE E).

---

## 18. Migraciones

- **075**: Vistas de auditoría y tabla `ops.data_integrity_audit`.
- **076**: Tabla `ops.audit_query_performance` (duración y status por check).
- **077**: Ventana de 24 meses en vistas de auditoría (performance; ver **docs/audit_layer_performance_hardening.md**).

Aplicar con:

```bash
cd backend && alembic upgrade head
```
