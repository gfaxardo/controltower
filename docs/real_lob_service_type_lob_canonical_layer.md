# Capa canónica service_type → LOB (Real LOB)

## Estado actual detectado (auditoría)

- **Heads en repo:** `070_canonical_service_type_lob` (y `071_real_service_type_unmapped_monitor` si existe). Cadena: … → 068 → 069 → 070 [→ 071].
- **Revisión en BD (alembic_version):** Puede estar en una revisión **fantasma** (ej. `073_normalize_expres_to_express`) que ya no existe en `backend/alembic/versions/`, lo que provoca `Can't locate revision identified by '073_...'`.
- **Migraciones presentes en repo:** 001…069, 070, 071 (070 = capa canónica; 071 = vista unmapped monitor). No existe archivo 073 en el repo.
- **Objetos de la capa canónica:** Creados por la migración 070 al aplicar `alembic upgrade head`. Si 070 no se ha aplicado por el bloqueo de Alembic, no existirán en BD: `canon.dim_real_service_type_lob`, `canon.normalize_real_tipo_servicio`, `ops.v_real_trips_service_lob_resolved`, y `ops.v_real_trips_with_lob_v2` (wrapper).
- **Riesgos de inconsistencia:** (1) BD con version_num fantasma impide aplicar 070/071. (2) Si hubiera objetos creados a mano (dim/función/vista) sin migración, el historial Alembic no reflejaría el estado real.

---

## Resolución del problema de Alembic

**Causa:** La tabla `alembic_version` tiene `version_num` apuntando a una revisión que ya no existe en el repo (ej. `073_normalize_expres_to_express`).

**Estrategia (recomendada):** Alinear la BD al historial del repo sin recuperar la migración perdida:

1. **Inspección:**  
   `python -m scripts.alembic_inspect_and_fix`  
   Muestra el contenido actual de `alembic_version`.

2. **Reparación:**  
   `python -m scripts.alembic_inspect_and_fix --fix`  
   - Hace `UPDATE alembic_version SET version_num = '069_real_lob_residual_diagnostic'`.  
   - Ejecuta `alembic upgrade head` (aplica 070 y 071).

3. **Solo stamp (sin upgrade):**  
   `python -m scripts.alembic_inspect_and_fix --stamp 069_real_lob_residual_diagnostic`  
   Útil si quieres solo alinear la versión y ejecutar `alembic upgrade head` manualmente después.

**Evidencia before/after:** Ejecutar antes `alembic_inspect_and_fix` (sin --fix) y anotar `alembic_version`. Después de `--fix`, ejecutar `alembic current`, `alembic heads`, `alembic history` y comprobar que `alembic upgrade head` no devuelve error.

---

## Fuente de verdad oficial (map vs dim)

- **Fuente canónica única (editar y consumir):** `canon.dim_real_service_type_lob`.  
  - Todos los consumidores (vista resuelta, backfill, drill) usan esta tabla (y la función `canon.normalize_real_tipo_servicio`).  
  - Cualquier nuevo mapping debe insertarse/actualizarse aquí.

- **Legacy / compatibilidad:** `canon.map_real_tipo_servicio_to_lob_group`.  
  - Se mantiene por si algún proceso externo la lee; **no** es fuente de verdad.  
  - La migración 070 puebla `dim` desde `map` una vez; a partir de ahí solo se edita `dim`.  
  - Scripts como `insert_envios_mapping.py` y `run_real_lob_gap_diagnosis.py` escriben en **dim**; escribir también en map es opcional y solo por compatibilidad.

- **Resumen:** Una sola fuente canónica activa = `canon.dim_real_service_type_lob`. La otra tabla queda como legacy explícito; no hay ambigüedad: se edita y se consume la dim.

---

## Problema que resuelve

- **Joins repetidos e inconsistencias:** La normalización de `tipo_servicio` y el mapping a LOB estaban duplicados en varias vistas (064, 050, 053, 047, backfill, etc.), con riesgo de divergencia.
- **Sin única fuente de verdad:** `canon.map_real_tipo_servicio_to_lob_group` era la tabla de mapping pero la lógica de normalización (CASE) vivía en cada objeto.
- **Mantenibilidad:** Cualquier cambio en variantes (ej. nuevo tipo o acento) obligaba a tocar N sitios.
- **Auditoría:** No había una capa explícita que expusiera `tipo_servicio_raw → tipo_servicio_norm → lob_group` por viaje.

Esta capa canónica centraliza en un solo lugar la normalización y el mapping, y expone una vista por viaje con trazabilidad completa.

---

## Diseño final

### Principios respetados

- No cambiar la taxonomía de negocio actual.
- No inventar LOBs nuevos.
- No mezclar Plan y Real.
- Trazabilidad completa: `tipo_servicio_raw → tipo_servicio_norm → lob_group_resolved`.
- Capa auditable y fácil de refrescar.

### Objetos creados (migraciones 070 y 071)

| Objeto | Tipo | Descripción |
|--------|------|-------------|
| `canon.dim_real_service_type_lob` | Tabla | Dimensión canónica: `service_type_norm` (PK), `lob_group`, `mapping_source`, `is_active`, `notes`, `updated_at`. |
| `canon.normalize_real_tipo_servicio(raw text)` | Función | Normalización única raw → clave para lookup en la dim. |
| `ops.v_real_trips_service_lob_resolved` | Vista | Por viaje: country, city, park, fecha, **tipo_servicio_raw**, **tipo_servicio_norm**, **lob_group_resolved**, **is_unclassified**, segment_tag, revenue, etc. |
| `ops.v_real_trips_with_lob_v2` | Vista | Wrapper sobre la capa resuelta; mantiene contrato (`real_tipo_servicio_norm`, `lob_group`) para drill y backfill. |
| `ops.v_real_service_type_unmapped_monitor` | Vista | Observabilidad: no mapeados últimos 90 días (trips, first_seen_date, last_seen_date). Ver `docs/real_lob_service_type_unmapped_monitor.md`. |

### Lógica

1. **Raw → normalizado:** `canon.normalize_real_tipo_servicio(tipo_servicio)` (economico/económico→economico, confort/comfort→confort, mensajería, express, tuk-tuk, len>30→UNCLASSIFIED, else LOWER(TRIM)).
2. **Normalizado → LOB:** Lookup en `canon.dim_real_service_type_lob` por `service_type_norm` con `is_active = true`.
3. **Sin fila en dim:** `lob_group_resolved = 'UNCLASSIFIED'`, `is_unclassified = true`.

### Pipeline antes / después

**Antes**

- Varias vistas y el backfill repetían un CASE de normalización y un `LEFT JOIN canon.map_real_tipo_servicio_to_lob_group`.
- Cualquier nuevo mapping o variante obligaba a tocar múltiples archivos.

**Después**

- Una función `canon.normalize_real_tipo_servicio` y una tabla `canon.dim_real_service_type_lob`.
- `ops.v_real_trips_with_lob_v2` y el backfill consumen la capa resuelta (vista o función + dim).
- Nuevos mappings: solo insertar/actualizar en `canon.dim_real_service_type_lob` (y opcionalmente en `map_*` por compatibilidad).

---

## Objetos que siguen existiendo y cuáles consumen la capa

- **`canon.map_real_tipo_servicio_to_lob_group`:** Sigue existiendo; se pobló `dim` desde aquí en la migración. **Fuente de verdad desde 070:** `canon.dim_real_service_type_lob`. Los scripts que añaden mappings deben actualizar la dim (y opcionalmente map por legado).
- **`ops.v_trips_real_canon`:** Sin cambios; sigue siendo la fuente de viajes reales.
- **`ops.v_real_trips_with_lob_v2`:** **Consume** la capa: es un SELECT sobre `ops.v_real_trips_service_lob_resolved` con alias.
- **Backfill** `backend/scripts/backfill_real_lob_mvs.py`: **Consume** `canon.normalize_real_tipo_servicio` y `canon.dim_real_service_type_lob` para drill_dim y rollup_day.
- **Drill UI:** Sigue leyendo `ops.mv_real_drill_dim_agg` (vista sobre `real_drill_dim_fact`); los datos se rellenan por el backfill que ya usa la capa canónica.
- **Diagnóstico** `run_real_lob_gap_diagnosis.py`: Al añadir mappings, escribe en **dim** y en map.

---

## Cómo se audita

- **Por viaje:** Consultar `ops.v_real_trips_service_lob_resolved` y revisar `tipo_servicio_raw`, `tipo_servicio_norm`, `lob_group_resolved`, `is_unclassified`.
- **Mapping vigente:** `SELECT * FROM canon.dim_real_service_type_lob WHERE is_active = true ORDER BY service_type_norm;`
- **Histórico / notas:** Columnas `mapping_source`, `notes`, `updated_at` en `canon.dim_real_service_type_lob`.

---

## Cómo se refresca

- **Dimensión:** Inserts/updates manuales o vía scripts (ej. `insert_envios_mapping.py`, `run_real_lob_gap_diagnosis.py`). No hay refresh automático; es tabla de referencia.
- **Vista resuelta:** No requiere refresh; es vista que calcula sobre `v_trips_real_canon` + dim.
- **Datos del drill:** `python -m scripts.backfill_real_lob_mvs --from YYYY-MM-01 --to YYYY-MM-01` para repoblar `real_drill_dim_fact` y `real_rollup_day_fact` usando ya la capa canónica.

---

## Validaciones SQL clave

```sql
-- A) service_type vs LOB residual (desde fact del drill; columnas: breakdown, dimension_key, trips)
SELECT
  breakdown,
  dimension_key AS breakdown_value,
  SUM(trips) AS trips
FROM ops.real_drill_dim_fact
WHERE breakdown IN ('service_type','lob')
  AND dimension_key = 'UNCLASSIFIED'
GROUP BY breakdown, dimension_key
ORDER BY 1, 2;

-- B) Top tipos no mapeados desde la vista resuelta
SELECT tipo_servicio_norm, COUNT(*) AS trips
FROM ops.v_real_trips_service_lob_resolved
WHERE is_unclassified = true
GROUP BY tipo_servicio_norm
ORDER BY trips DESC
LIMIT 100;

-- C) Mapeados activos (dim canónica)
SELECT * FROM canon.dim_real_service_type_lob WHERE is_active = true ORDER BY service_type_norm;

-- D) Conteo mapeados vs no mapeados (desde capa resuelta, últimos 90 días)
SELECT
  CASE WHEN lob_group_resolved = 'UNCLASSIFIED' THEN 'unclassified' ELSE 'classified' END AS status,
  COUNT(*) AS trips
FROM ops.v_real_trips_service_lob_resolved
WHERE fecha_inicio_viaje::date >= current_date - 90
GROUP BY 1;
```

## Cómo detectar nuevos service_type no mapeados

- **Vista de monitoreo:** `ops.v_real_service_type_unmapped_monitor` (creada en migración 071).  
  Agregado por (tipo_servicio_raw, tipo_servicio_norm) últimos 90 días, solo filas con `is_unclassified = true`. Columnas: tipo_servicio_raw, tipo_servicio_norm, trips, first_seen_date, last_seen_date, sample_lob_resolved, is_unclassified.
- **Uso:** Consultar con `ORDER BY trips DESC` para priorizar candidatos a mapping; separar basura marginal (pocos viajes, texto que no es tipo de servicio) de candidatos reales. Documentación detallada: `docs/real_lob_service_type_unmapped_monitor.md`.

---

## Riesgos residuales

- **Scripts que solo leen `map_*`:** Si algún proceso sigue insertando solo en `map_real_tipo_servicio_to_lob_group` y no en `dim_real_service_type_lob`, esos mappings no afectarán a la vista ni al backfill (que usan la dim). Solución: documentar y hacer que todos los inserts de mapping actualicen la dim.
- **Downgrade 070:** Restaura `v_real_trips_with_lob_v2` con CASE + map; el backfill en ese caso debe volver a usar map (revertir cambios en el script si se hace downgrade).

---

## Resumen de archivos modificados / creados

| Acción | Archivo |
|--------|---------|
| Creado | `backend/alembic/versions/070_canonical_service_type_lob_layer.py` |
| Modificado | `backend/scripts/backfill_real_lob_mvs.py` (usa `canon.normalize_real_tipo_servicio` y `canon.dim_real_service_type_lob`) |
| Modificado | `backend/scripts/insert_envios_mapping.py` (inserta en dim; map opcional) |
| Modificado | `backend/scripts/run_real_lob_gap_diagnosis.py` (inserta en dim al añadir mappings) |
| Creado | `docs/real_lob_service_type_lob_canonical_layer.md` (este documento) |

---

## Aplicación y backfill

1. Aplicar migración: `alembic upgrade head` (o `alembic upgrade 070_canonical_service_type_lob`).  
   **Nota:** Si aparece `Can't locate revision identified by '073_...'`, la BD tiene una revisión que ya no está en el repo; hay que alinear el historial (p. ej. marcar manualmente la revisión actual en `alembic_version` o recuperar el archivo de la migración 073) antes de aplicar 070.
2. (Opcional) Repoblar un rango reciente para validar:  
   `python -m scripts.backfill_real_lob_mvs --from 2025-01-01 --to 2025-03-01`
3. Validar con las consultas SQL anteriores y comprobar que el drill UI (mensual/semanal, desglose LOB, tipo de servicio, park) sigue funcionando.

---

## Resumen ejecutivo (Fase F)

### Objetos creados

| Objeto | Descripción |
|--------|-------------|
| `canon.dim_real_service_type_lob` | Tabla dimensión: service_type_norm (PK), lob_group, mapping_source, is_active, notes, updated_at |
| `canon.normalize_real_tipo_servicio(text)` | Función SQL de normalización raw → norm |
| `ops.v_real_trips_service_lob_resolved` | Vista por viaje con tipo_servicio_raw, tipo_servicio_norm, lob_group_resolved, is_unclassified |

### Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `backend/alembic/versions/070_canonical_service_type_lob_layer.py` | **Nuevo:** migración que crea dim, función, vista resuelta y redefine v_real_trips_with_lob_v2 |
| `backend/scripts/backfill_real_lob_mvs.py` | Usa `canon.normalize_real_tipo_servicio` y `canon.dim_real_service_type_lob` en lugar de CASE + map |
| `backend/scripts/insert_envios_mapping.py` | Inserta en `dim_real_service_type_lob`; map opcional por compatibilidad |
| `backend/scripts/run_real_lob_gap_diagnosis.py` | Al añadir mappings, escribe también en `dim_real_service_type_lob` |
| `docs/real_lob_service_type_lob_canonical_layer.md` | **Nuevo:** documentación de la capa canónica |

### Migración

- **Archivo:** `070_canonical_service_type_lob_layer.py` (down_revision: 069_real_lob_residual_diagnostic).
- **Aplicación:** `alembic upgrade head` cuando el historial de Alembic esté alineado con el repo (si la BD referencia una revisión 073 que no existe, hay que resolverlo antes).

### Backfill / refresh

- Tras aplicar 070, el backfill (`backfill_real_lob_mvs.py`) ya usa la capa canónica; no es obligatorio re-ejecutarlo salvo para repoblar un rango y validar.

### Validaciones SQL clave

- Conteo mapeados vs unclassified: `SELECT ... FROM ops.v_real_trips_service_lob_resolved WHERE ... GROUP BY status`.
- Top unclassified: `SELECT tipo_servicio_norm, COUNT(*) ... WHERE is_unclassified = true ...`.
- Listado de mapping vigente: `SELECT * FROM canon.dim_real_service_type_lob WHERE is_active = true`.

### Comparación antes/después

- **Antes:** CASE de normalización y `LEFT JOIN canon.map_real_tipo_servicio_to_lob_group` repetidos en 064, 050, 053, 047, backfill, etc.
- **Después:** Una función, una tabla dim y una vista resuelta; `v_real_trips_with_lob_v2` y backfill consumen esa capa. No debe aumentar UNCLASSIFIED si la dim se pobló correctamente desde map.

### Drill UI

- Sin cambios de contrato: el drill sigue leyendo `ops.mv_real_drill_dim_agg` (vista sobre `real_drill_dim_fact`). Los datos se rellenan por el backfill que ya usa la capa canónica. Comprobar tras aplicar 070 y (opcional) backfill: mensual, semanal, desglose LOB, desglose tipo de servicio, park.

### Veredicto

**LISTO PARA CERRAR** (tras aplicar reparación Alembic y migraciones)

- La capa canónica está implementada y documentada; el pipeline Real LOB (vista + backfill) consume la dim como única fuente.
- Reparación Alembic: ejecutar `python -m scripts.alembic_inspect_and_fix --fix` si la BD tiene revisión fantasma (073); luego `alembic current` / `alembic upgrade head` deben ser coherentes.
- Tras aplicar 070 y 071, ejecutar validaciones SQL (A–D) y revisar drill UI (mensual, semanal, LOB, tipo de servicio, park). Monitor de no mapeados: `ops.v_real_service_type_unmapped_monitor`.

---

## Resumen ejecutivo (entregable final)

1. **Estado inicial detectado:** BD con `alembic_version` posiblemente en revisión fantasma (073); repo con heads 069→070→071; migración 070 no aplicada si Alembic fallaba.
2. **Resolución Alembic:** Script `scripts/alembic_inspect_and_fix.py`: inspección sin args; `--fix` hace stamp a 069 y ejecuta `alembic upgrade head`; `--stamp REV` solo actualiza `alembic_version`.
3. **Objetos canónicos finales:** `canon.dim_real_service_type_lob`, `canon.normalize_real_tipo_servicio`, `ops.v_real_trips_service_lob_resolved`, `ops.v_real_trips_with_lob_v2` (wrapper), `ops.v_real_service_type_unmapped_monitor`.
4. **Qué consume el backfill:** `canon.normalize_real_tipo_servicio` y `canon.dim_real_service_type_lob` (ya integrado en `backfill_real_lob_mvs.py`).
5. **Qué consume el drill:** `ops.mv_real_drill_dim_agg` (vista sobre `real_drill_dim_fact`); los datos los rellena el backfill que usa la capa canónica; breakdown service_type y LOB salen de la misma resolución.
6. **Validación SQL:** Ejecutar consultas A–D de la sección "Validaciones SQL clave"; documentar resultados (conteo UNCLASSIFIED, top unmapped, filas en dim).
7. **Resultado visual/UI:** Comprobar mensual, semanal, desglose LOB, desglose tipo de servicio, park; que no aparezca LOW_VOLUME donde no corresponda y que la cabecera y el residual tengan sentido.
8. **Monitor unmapped:** `ops.v_real_service_type_unmapped_monitor` (071); ver `docs/real_lob_service_type_unmapped_monitor.md`.
9. **Archivos modificados/creados:** `backend/scripts/alembic_inspect_and_fix.py`, `backend/alembic/versions/071_real_service_type_unmapped_monitor.py`, `docs/real_lob_service_type_unmapped_monitor.md`; actualizado `docs/real_lob_service_type_lob_canonical_layer.md`; `insert_envios_mapping.py` escribe solo en dim.
10. **Comandos ejecutados (recomendados):** `python -m scripts.alembic_inspect_and_fix --fix` (si había bloqueo); `alembic current`; `alembic heads`; `alembic upgrade head`; (opcional) backfill de un rango; validaciones SQL A–D.
11. **Veredicto final:** LISTO PARA CERRAR una vez Alembic alineado, 070 y 071 aplicadas, validaciones y drill UI comprobados.
