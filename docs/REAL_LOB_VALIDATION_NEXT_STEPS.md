# Real LOB — Siguientes pasos tras validación (run_validate_real_lob_rescue)

## 1. Freshness timeout (paso 5)

**Síntoma:** `Error ejecutando: canceling statement due to statement timeout` en `ops.v_real_freshness_trips`.

**Qué hace el script:**  
- Timeout por defecto **20 min** para todo el script.  
- Para el paso 5 (Freshness) se usa **30 min** solo durante ese `SELECT * FROM ops.v_real_freshness_trips`.

**Si sigue fallando:**

- Aumentar en el script: `FRESHNESS_STATEMENT_TIMEOUT = "45min"` o `"60min"` en `run_validate_real_lob_rescue.py`.
- En BD: la vista hace full scan sobre `ops.v_trips_real_canon` (~55M filas) + JOIN con `parks` y CASE por país. Opciones:
  - **Índice** en la canónica: `(condicion, fecha_inicio_viaje)` si no existe (la migración 064 crea `ix_trips_all_real_lob_refresh` en `trips_all`; comprobar si hay equivalente en `trips_2026`).
  - **MV de freshness**: materializar `last_trip_date` por país y refrescarla tras el backfill (evita full scan en cada validación).

---

## 2. Drill breakdown=lob: filas vs distinct (paso 6)

**Síntoma:** El paso 6 devuelve filas con `rows` > `uniq` (ej.: `rows: 8`, `uniq: 5` para un mismo `period_start`, `country`). Indica que hay más de una fila por el mismo `dimension_key` en ese periodo/país.

**Diagnóstico (duplicados por LOB):**

```sql
-- Ejemplo: periodo y país donde hay diferencia (sustituir por uno de los que salen en paso 6)
SELECT period_start, country, dimension_key, COUNT(*) AS cnt, SUM(trips) AS trips_sum
FROM ops.mv_real_drill_dim_agg
WHERE breakdown = 'lob' AND period_grain = 'month'
  AND period_start = '2025-05-01' AND country = 'pe'
GROUP BY period_start, country, dimension_key
HAVING COUNT(*) > 1
ORDER BY dimension_key;
```

Si hay filas: mismo `dimension_key` aparece varias veces (p. ej. por segmento o granularidad distinta). Revisar cómo se alimenta `mv_real_drill_dim_agg` (agrupación por LOB/segment/period) y si el diseño admite varias filas por `dimension_key` por periodo (en ese caso el paso 6 podría cambiarse para no exigir `rows = uniq`).

---

## 3. Temp usage (paso 2)

**Síntoma:** `temp_files` y `temp_bytes` muy altos (p. ej. 1771 GB).

**Causa habitual:** Sorts/hash que no caben en `work_mem` (p. ej. 4MB) y vuelcan a disco.

**Siguientes pasos:**

- En sesiones de **refresco** (backfill, REFRESH MV): subir `work_mem` y `maintenance_work_mem` solo para esa sesión, por ejemplo:
  - `SET work_mem = '256MB';` (o `512MB` si la RAM lo permite)
  - `SET maintenance_work_mem = '512MB';`
- Ajustar en `postgresql.conf` solo si quieres que afecte a todo el servidor.
- Revisar índices en la canónica y en las tablas base (`trips_all`, `trips_2026`) para filtros y JOINs que usan las MVs (menos filas en memoria → menos temp).

---

## 4. Checklist rápido

| Paso | Acción si falla o hay warning |
|------|-------------------------------|
| 5 Freshness | Aumentar `FRESHNESS_STATEMENT_TIMEOUT`; si persiste, índice en canon o MV de freshness. |
| 6 Drill rows≠uniq | Ejecutar el diagnóstico SQL anterior; decidir si es esperado o corregir la lógica del MV. |
| 2 Temp | Aumentar `work_mem`/`maintenance_work_mem` en sesiones pesadas; revisar índices. |
