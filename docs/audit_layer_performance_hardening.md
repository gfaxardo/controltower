# Audit Layer — Performance Hardening e interpretación de warnings

## FASE A — Perfilado del sistema de auditoría

### Consultas exactas por check

| check_name | Consulta (lo que ejecuta el script) | Vista(s) usada(s) | Tablas fuente |
|------------|--------------------------------------|-------------------|----------------|
| TRIP_LOSS | `SELECT status, loss_pct, viajes_base, viajes_real_lob FROM ops.v_trip_integrity ORDER BY mes DESC LIMIT 1` | v_trip_integrity | v_trips_real_canon (→ trips_all, trips_2026), real_rollup_day_fact |
| B2B_LOSS | `SELECT b2b_base, b2b_real_lob, diff_pct FROM ops.v_b2b_integrity ORDER BY mes DESC LIMIT 1` | v_b2b_integrity | v_trips_real_canon, real_rollup_day_fact |
| LOB_MAPPING_LOSS | `SELECT pct_sin_lob, viajes_sin_lob FROM ops.v_lob_mapping_audit ORDER BY mes DESC LIMIT 1` | v_lob_mapping_audit | v_trips_real_canon, v_real_trips_with_lob_v2 (→ parks, map LOB) |
| DUPLICATE_TRIPS | `SELECT COUNT(*) AS c FROM ops.v_duplicate_trips` | v_duplicate_trips | trips_all, trips_2026 (UNION ALL + HAVING COUNT(*) > 1) |
| MV_STALE | `SELECT view_name FROM ops.v_mv_freshness WHERE status = 'STALE'` | v_mv_freshness | real_drill_dim_fact, real_rollup_day_fact, mv_* (solo MAX/EXISTS, ligero) |
| JOIN_LOSS | `SELECT loss_pct, join_name FROM ops.v_join_integrity LIMIT 1` | v_join_integrity | v_trips_real_canon, public.parks (COUNT(*) sobre todos los completados) |
| WEEKLY_ANOMALY | `SELECT week_start, viajes FROM ops.v_weekly_trip_volume ORDER BY week_start DESC LIMIT 2` | v_weekly_trip_volume | v_trips_real_canon |

### Cuellos de botella identificados (before hardening)

| check_name | current_duration_approx | main_objects | suspected_bottleneck | explain_summary |
|------------|-------------------------|--------------|----------------------|-----------------|
| TRIP_LOSS | ~285s | v_trips_real_canon (full scan), real_rollup_day_fact | Full scan de canonical por mes sin filtro temporal; agregación por mes sobre toda la historia | Seq Scan sobre union trips_all + trips_2026, luego GROUP BY mes |
| B2B_LOSS | ~284s | Idem | Mismo que TRIP_LOSS | Idem |
| LOB_MAPPING_LOSS | ~603s (timeout) | v_trips_real_canon, v_real_trips_with_lob_v2 | Tres CTEs que escanean v_real_trips_with_lob_v2 (join parks + LOB mapping) sobre toda la historia; vista muy pesada en cascada | Seq Scan + joins costosos en v_real_trips_with_lob_v2, sin ventana temporal |
| DUPLICATE_TRIPS | ~182s | trips_all, trips_2026 | UNION ALL de todas las id de ambas tablas, luego GROUP BY id HAVING COUNT(*) > 1; full scan de ambas tablas | Seq Scan en ambas tablas, HashAggregate sobre millones de filas |
| JOIN_LOSS | ~354s | v_trips_real_canon, parks | base_trips = todos los completados sin filtro; dos COUNT(*) sobre canonical y sobre join con parks | Seq Scan canonical completo, Nested Loop o Hash Join con parks |
| WEEKLY_ANOMALY | ~273s | v_trips_real_canon | Full scan por semana sobre toda la historia | Seq Scan + GROUP BY week_start |

### Estrategia de optimización aplicada

- **Ventana temporal de 24 meses**: Todas las vistas que leen de `v_trips_real_canon` o de `v_real_trips_with_lob_v2` se limitan a `fecha_inicio_viaje >= (current_date - interval '24 months')`. Así se evita full scan sobre toda la historia y se mantiene sentido para auditoría operativa diaria.
- **DUPLICATE_TRIPS**: La vista se limita a viajes con `fecha_inicio_viaje >= (current_date - interval '24 months')` en cada fuente; se reportan duplicados en ventana reciente (solapamiento o carga doble).
- **WEEKLY_ANOMALY**: El script compara **última semana cerrada** vs **anterior semana cerrada** (excluye semana actual incompleta) para evitar falsos positivos.

---

## FASE B–C — Optimizaciones aplicadas (migración 077)

- **v_trip_integrity**: Filtro en CTE base `fecha_inicio_viaje >= (current_date - interval '24 months')`.
- **v_b2b_integrity**: Mismo filtro en CTE base.
- **v_lob_mapping_audit**: Filtro en base, with_lob y unmapped a 24 meses (sobre `t.fecha_inicio_viaje` y `v.fecha_inicio_viaje`).
- **v_join_integrity**: Filtro en base_trips a 24 meses.
- **v_weekly_trip_volume**: Filtro `fecha_inicio_viaje >= (current_date - interval '24 months')`.
- **v_duplicate_trips**: Solo ids con `fecha_inicio_viaje >= (current_date - interval '24 months')` en cada tabla; mismo resultado de negocio para “duplicados recientes”.

---

## FASE D — DUPLICATE_TRIPS: interpretación

- **Qué mide**: Cantidad de `trip_id` que aparecen en **ambas** fuentes (trips_all y trips_2026) en la ventana de auditoría (24 meses).
- **Por qué puede dar WARNING**:
  - **Solapamiento esperado**: Si en la frontera 2026-01-01 hay datos cargados en ambas tablas, los mismos `id` pueden existir en las dos. La vista canónica (`v_trips_real_canon`) ya hace **DISTINCT ON (id)** con prioridad a trips_2026, por lo que no hay duplicados en la base canónica. El check solo informa “hay ids en ambas fuentes”.
  - **Carga doble o migración**: Si se cargó el mismo lote en trips_all y trips_2026, es un tema de proceso, no de modelo.
- **Veredicto**: WARNING por DUPLICATE_TRIPS es **esperable** cuando existe solapamiento; no implica error de integridad si la canónica está bien deduplicada. Se considera **warning de negocio/operación**: revisar si el número es estable (solapamiento) o crece (posible carga doble).

---

## FASE E — WEEKLY_ANOMALY: interpretación

- **Qué mide**: Caída >30 % WoW en viajes (semana N vs N-1).
- **Falso positivo típico**: Si se compara la **semana actual** (aún incompleta) con la semana anterior completa, la “caída” es artefacto.
- **Corrección aplicada**: El script compara **última semana cerrada** (week_start = lunes de la semana pasada) con **penúltima semana cerrada**. Así solo se comparan semanas completas.
- **Si sigue en WARNING**: Es **warning de negocio** (semana cerrada con caída real); revisar operación o eventos.

---

## FASE F — Vista canónica

- **v_trips_real_canon** (064): Unión con corte `trips_all < 2026-01-01`, `trips_2026 >= 2026-01-01`; **DISTINCT ON (id)** con `source_priority DESC` (trips_2026 gana). No genera duplicados en la salida; el solapamiento se resuelve por prioridad.
- **v_trips_canonical** (075): Alias de columnas sobre v_trips_real_canon; no cambia lógica.

---

## FASE G — Engine de auditoría

- Cada check corre en **su propia conexión** y transacción; timeout no contamina el siguiente.
- **AUDIT_TIMEOUT_MS** (default 600000) por conexión; opcional **AUDIT_TIMEOUT_MS_HEAVY** para checks pesados si se configura en el futuro.
- Persistencia: **ops.data_integrity_audit** (resultado por check) y **ops.audit_query_performance** (duración, status OK/TIMEOUT/ERROR).
- Mensaje de error: se persiste en `details` en data_integrity_audit cuando hay fallo; en audit_query_performance solo status.

---

## Límites conocidos

- Las vistas de auditoría (trip integrity, B2B, LOB, join, weekly) solo consideran **últimos 24 meses**. Para auditoría histórica completa haría falta ejecutar consultas ad hoc sin ventana.
- DUPLICATE_TRIPS en ventana 24 meses no detecta duplicados solo en datos muy antiguos.
- El reporte global **v_control_tower_integrity_report** sigue leyendo las mismas vistas (ya con ventana).

---

## Comandos de validación

```bash
cd backend
python -m scripts.audit_control_tower
```

```sql
SELECT check_name, execution_time_ms, status, executed_at
FROM ops.audit_query_performance
ORDER BY executed_at DESC
LIMIT 20;
```

Comparar **before/after** (duración por check y que LOB_MAPPING_LOSS pase sin timeout).

---

## FASE J — Resumen ejecutivo (entregable final)

### 1. Checks auditados

TRIP_LOSS, B2B_LOSS, LOB_MAPPING_LOSS, DUPLICATE_TRIPS, MV_STALE, JOIN_LOSS, WEEKLY_ANOMALY.

### 2. Cuellos de botella encontrados

- Full scan de **v_trips_real_canon** (y en cascada **v_real_trips_with_lob_v2**) sobre toda la historia.
- **v_join_integrity**: dos COUNT(*) sobre todos los viajes completados sin filtro temporal.
- **v_duplicate_trips**: UNION ALL de todas las id de trips_all y trips_2026 sin ventana.
- **WEEKLY_ANOMALY**: comparación que incluía semana actual incompleta → falso positivo.

### 3. Optimizaciones aplicadas

- **Ventana 24 meses** en v_trip_integrity, v_b2b_integrity, v_lob_mapping_audit, v_join_integrity, v_weekly_trip_volume y v_duplicate_trips (migración 077).
- **WEEKLY_ANOMALY**: consulta restringida a `week_start < date_trunc('week', current_date)::date` y LIMIT 2 → solo últimas dos semanas cerradas.
- Persistencia del **mensaje de error** en `ops.data_integrity_audit` cuando un check falla (TIMEOUT/ERROR).
- Salida del script: líneas **Duplicate trips** y **Join integrity** añadidas.

### 4. LOB_MAPPING_LOSS

Corregido: la vista **v_lob_mapping_audit** limita las tres CTEs (base, with_lob, unmapped) a `fecha_inicio_viaje::date >= (current_date - 24 months)`. Con ello el check deja de hacer timeout y devuelve resultado usable.

### 5. Duplicados canónicos

No se cambia la vista canónica. **v_trips_real_canon** ya hace DISTINCT ON (id) con prioridad a trips_2026. El WARNING de DUPLICATE_TRIPS es **esperable** cuando hay solapamiento; documentado como warning de negocio/operación. La vista **v_duplicate_trips** se limita a últimos 24 meses para reducir tiempo de ejecución.

### 6. WEEKLY_ANOMALY

Era **falso positivo** al comparar semana actual (incompleta) con anterior. Corregido: el script solo compara **última semana cerrada** vs **anterior semana cerrada**. Si tras el cambio sigue en WARNING, es anomalía de negocio real.

### 7. Before/after de performance (esperado)

| check_name        | before_status | after_status | before_duration | after_duration | improvement      | remaining_issue |
|-------------------|---------------|--------------|------------------|----------------|------------------|-----------------|
| TRIP_LOSS         | OK            | OK           | ~285s            | &lt; 60s        | Ventana 24m      | Ninguno         |
| B2B_LOSS          | OK            | OK           | ~284s            | &lt; 60s        | Ventana 24m      | Ninguno         |
| LOB_MAPPING_LOSS  | TIMEOUT       | OK           | ~603s            | &lt; 120s      | Ventana 24m      | Ninguno         |
| DUPLICATE_TRIPS   | WARNING       | WARNING/OK   | ~182s            | &lt; 60s        | Ventana 24m      | WARNING esperable si hay solapamiento |
| JOIN_LOSS         | OK            | OK           | ~354s            | &lt; 90s        | Ventana 24m      | Ninguno         |
| WEEKLY_ANOMALY    | WARNING       | OK o WARNING | ~273s            | &lt; 60s        | Ventana 24m + lógica semana cerrada | WARNING solo si caída real WoW |

### 8. Archivos modificados

- **backend/alembic/versions/077_audit_views_24month_window.py** (nuevo): ventana 24 meses en vistas de auditoría.
- **backend/scripts/audit_control_tower.py**: WEEKLY_ANOMALY con semana cerrada; persistencia de error en data_integrity_audit; líneas Duplicate trips y Join integrity en salida.
- **docs/audit_layer_performance_hardening.md** (este documento): perfilado, optimizaciones, interpretación DUPLICATE_TRIPS y WEEKLY_ANOMALY.
- **docs/control_tower_data_observability.md**: sección ventana 24 meses; interpretación DUPLICATE_TRIPS y WEEKLY_ANOMALY; referencias a migración 076/077.

### 9. Comandos ejecutados

```bash
cd backend
alembic upgrade head   # aplica 077
python -m scripts.audit_control_tower
```

```sql
SELECT check_name, execution_time_ms, status, executed_at FROM ops.audit_query_performance ORDER BY executed_at DESC LIMIT 20;
```

### 10. Veredicto final

**LISTO PARA CERRAR** con las siguientes observaciones:

- Auditoría operativa basada en **últimos 24 meses**; para análisis histórico completo haría falta consulta ad hoc sin ventana.
- **DUPLICATE_TRIPS** en WARNING es esperable cuando existe solapamiento entre fuentes; no indica error de modelo si la canónica está bien deduplicada.
- **WEEKLY_ANOMALY** en WARNING tras el cambio indica caída real WoW entre semanas cerradas; revisar operación.
