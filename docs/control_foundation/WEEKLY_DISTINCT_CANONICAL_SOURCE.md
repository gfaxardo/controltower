# Weekly Distinct Canonical Source — Active Drivers

## Fecha: 2026-05-29

---

## Opciones Evaluadas

### Option A: `COUNT(DISTINCT driver_id)` desde enriched trips (RECOMMENDED)

**Descripción**: El week_fact se puebla desde la misma vista enriched (`_bs_enriched_month`) que month_fact y day_fact, agrupando por `date_trunc('week', trip_date)`.

**Ventajas**:
- Definición canónica: `COUNT(DISTINCT driver_id) FILTER (WHERE completed_flag)`
- Consistente con daily y monthly (misma fórmula)
- No requiere nueva infraestructura
- Auditable: mismo pipeline, distinto GROUP BY

**Desventajas**:
- Performance: requiere escanear la vista enriched en lugar de hacer rollup del day_fact (más lento)
- El day_fact ya no sería suficiente como fuente para week_fact
- Requiere cambiar el orden de refresh: week_fact antes o independiente del day_fact, o desde la misma vista enriched

**Precision**: Exacta (definición canónica)
**Performance**: ~2-5x más lento que el rollup actual (pero aún dentro de lo aceptable — mismo costo que month_fact por chunk)

---

### Option B: `COUNT(DISTINCT driver_id)` desde day_fact si tuviera driver_id

**Descripción**: Añadir columna `driver_id_list` (array) al day_fact para poder hacer `COUNT(DISTINCT)` en el rollup.

**Ventajas**:
- Performance: similar al rollup actual (day_fact ya pre-agregado)
- No requiere re-escanear trips crudos

**Desventajas**:
- Requiere ALTER TABLE en day_fact (cambio de schema)
- Aumenta storage (array de driver_ids por fila)
- Complejidad: `COUNT(DISTINCT unnest(driver_id_array))` en PostgreSQL
- No es canónico: el array puede ser grande para días con muchos drivers

**Precision**: Exacta (si el array está completo)
**Performance**: Similar al actual + overhead de unnest

---

### Option C: `COUNT(DISTINCT driver_id)` desde `ops.v_real_trips_business_slice_resolved`

**Descripción**: Usar la vista resuelta directamente (sin pre-materializar enriched) para el week_fact.

**Ventajas**:
- Definición canónica
- No requiere duplicar lógica de enriquecimiento

**Desventajas**:
- LENTO: La vista resuelta tiene UNION ALL + DISTINCT ON + JOINS. Escaneo completo de la vista por semana.
- La vista no está indexada para agregación semanal
- Riesgo de timeout en producción

**Precision**: Exacta
**Performance**: Inaceptable para UI en vivo. Solo para backfill nocturno.

---

### Option D: Mantener SUM proxy + corregir solo en serving layer

**Descripción**: El week_fact mantiene `SUM(daily_counts)`. Pero el serving fact (`serving.omniview_projection_daily_fact`) para weekly grain usa `COUNT(DISTINCT driver_id)` desde la vista enriched.

**Ventajas**:
- No cambia el week_fact existente
- El serving fact ya se refresca offline (puede tolerar más latencia)
- Omniview lee del serving fact (cuando existe), no del week_fact directamente

**Desventajas**:
- El week_fact sigue siendo incorrecto para Evolution mode y para cualquier consulta directa
- Dos fuentes de verdad: serving fact (correcto) y week_fact (incorrecto)
- Confusión futura: ¿cuál es la fuente canónica?

**Precision**: Exacta para serving fact, incorrecta para week_fact
**Performance**: Sin impacto en week_fact. Serving fact ya es pesado.

---

## Recomendación: Option A

**`COUNT(DISTINCT driver_id) FILTER (WHERE completed_flag)` desde `_bs_enriched_month` en week_fact**

### Razones:
1. Es la definición canónica (misma fórmula que daily y monthly)
2. Elimina la fuente de error de raíz (no parche en el serving layer)
3. Consistente con la arquitectura: month_fact ya hace esto por chunk
4. Auditable: mismo pipeline, mismo código, distinto GROUP BY
5. No requiere cambios de schema ni nuevas tablas

### Implementación:
- Crear `_RESOLVE_AND_AGG_WEEK_FROM_TEMP` (análogo al month_fact y day_fact)
- Agrupar por `date_trunc('week', trip_date)` en lugar de `trip_date` o `trip_month`
- Reemplazar `_WEEK_ROLLUP_FROM_DAY_FACT` por la nueva función
- Ajustar `load_business_slice_week_for_month()` para usar la nueva query
- El day_fact debe seguir refrescándose (para daily grain), pero week_fact ya no depende de él

### Costo de performance estimado:
- month_fact por chunk: ~2-10s dependiendo del tamaño del chunk
- week_fact por chunk: comparable (mismo scan de enriched, mismo número de chunks, distinto GROUP BY)
- Total adicional por refresh: ~mismo costo que month_fact → aceptable para refresh job cada 15 min
