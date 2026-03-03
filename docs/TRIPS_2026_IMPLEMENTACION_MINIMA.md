# Implementación mínima y segura: incorporar trips_2026 sin tablas gigantes

**Objetivo:** Usar una tabla `trips_2026` (datos 2026+) junto con `trips_all` (histórico) sin duplicar datos ni crear tablas gigantes, y con impacto controlado en MVs y rendimiento.

---

## 1. Diferencia VIEW vs TABLE vs MATERIALIZED VIEW

| Concepto | Qué es | Almacenamiento | Cuándo se calcula | Uso típico |
|----------|--------|----------------|-------------------|------------|
| **TABLE** | Datos físicos en disco | Sí: todos los datos | En escritura (INSERT/UPDATE) | Fuente de verdad, datos crudos (ej. `trips_all`, `trips_2026`). |
| **VIEW** | Definición de una consulta (query guardada) | No: no guarda filas | En cada SELECT | Unificar fuentes (UNION), simplificar consultas, una sola “entrada” para muchas MVs. |
| **MATERIALIZED VIEW (MV)** | Resultado precalculado de una consulta, guardado como tabla | Sí: guarda el resultado de la query | En REFRESH (manual o programado) | Agregados pesados (mensual, semanal, LOB) para no escanear la tabla base en cada request. |

- **TABLE:** crece con los datos; si juntas todo en una sola tabla, puede volverse gigante.
- **VIEW:** no crece; cada consulta que la use ejecuta la query subyacente (aquí, UNION ALL).
- **MV:** crece con el resultado agregado (pocas filas por mes/semana/park), no con el detalle de viajes; es el lugar donde conviene seguir leyendo desde **una sola fuente lógica** (la VIEW unificada).

---

## 2. Opciones evaluadas

### A) Crear VIEW `public.trips_unified` (UNION ALL trips_all + trips_2026)

- **Idea:** Una sola vista que expone `trips_all` ∪ `trips_2026` con la misma estructura de columnas.
- **Ventajas:**
  - Un único punto de cambio: todas las MVs y vistas siguen leyendo de **una fuente** (`trips_unified`).
  - No hace falta tocar cada MV ni cada migración que hoy referencia `trips_all`.
  - Cero almacenamiento extra; no se duplican filas.
  - Implementación mínima y reversible (DROP VIEW y volver a `trips_all`).
- **Inconvenientes:**
  - Cada REFRESH de las MVs que lean de `trips_unified` ejecutará el UNION ALL; el planificador puede empujar filtros (p. ej. por `fecha_inicio_viaje`) a cada rama y usar índices por fecha en ambas tablas.

### B) Cambiar cada MV para leer de `trips_2026` según fecha

- **Idea:** En cada definición de MV, sustituir `FROM public.trips_all` por algo como  
  `FROM (SELECT * FROM trips_all WHERE fecha_inicio_viaje < '2026-01-01' UNION ALL SELECT * FROM trips_2026 WHERE fecha_inicio_viaje >= '2026-01-01') t`.
- **Ventajas:**
  - Lógica de corte por fecha explícita en cada MV.
- **Inconvenientes:**
  - Hay muchas migraciones y vistas que referencian `trips_all` (mv_real_trips_monthly, mv_real_trips_monthly_v2, mv_real_trips_weekly, v_real_*, v_plan_vs_real_*, LOB, drill, etc.). Cambiar “cada MV” implica muchas ediciones, más riesgo de error y más esfuerzo de pruebas.
  - Duplicación de la misma expresión UNION en cada sitio.
  - No evita escanear ambas tablas cuando el REFRESH necesita todo el rango; el comportamiento de rendimiento es similar a leer de una VIEW que haga ese UNION, pero con más superficie de cambio.

---

## 3. Impacto en rendimiento y mitigación

- **Impacto:** Las MVs que hoy hacen full scan (o scan por mes/semana) sobre `trips_all` pasarán a leer de `trips_unified`. El coste añadido es el de un UNION ALL (concatenar dos resultados) y, sobre todo, el de escanear **dos tablas** en lugar de una. Si `trips_all` ya es grande y `trips_2026` crece con el tiempo, los REFRESH pueden tardar más.
- **Mitigación recomendada:**
  1. **Índices en ambas tablas** para los filtros que usan las MVs:
     - `(fecha_inicio_viaje)` para cortes por mes/semana.
     - `(condicion, fecha_inicio_viaje)` para el filtro típico `condicion = 'Completado'`.
     - Opcional: `(park_id, tipo_servicio, fecha_inicio_viaje)` para agregados por park/LOB (como en 038 y 023).
     - Opcional para driver lifecycle: `(conductor_id, fecha_inicio_viaje)` o `(conductor_id, COALESCE(fecha_finalizacion, fecha_inicio_viaje))`.
  2. **Refreshes en ventana de bajo uso** y, si hace falta, subir `statement_timeout` / `lock_timeout` para los REFRESH (como ya se hace en driver lifecycle).
  3. **No crear tablas gigantes:** mantener el criterio claro: histórico en `trips_all`, 2026+ en `trips_2026`, y la vista unificada solo como capa de unión.

Con índices adecuados, el planificador puede limitar cada rama del UNION a los rangos de fecha que pida la query (por ejemplo solo 2026 en `trips_2026` y solo histórico en `trips_all`), reduciendo el impacto.

---

## 4. Recomendación final (una sola)

**Recomendación: opción A — crear la VIEW `public.trips_unified` (UNION ALL) y que todas las MVs/vistas que hoy leen de `trips_all` pasen a leer de `trips_unified`.**

- Implementación mínima y en un solo lugar.
- No se crean tablas nuevas grandes; solo una vista.
- Riesgo acotado y fácil de revertir.
- El cambio en el código existente se reduce a: reemplazar `public.trips_all` por `public.trips_unified` en las definiciones que alimentan el “real” (en migraciones nuevas o en un script de reemplazo aplicado a las MVs/vistas clave), o bien crear primero la vista y migrar por fases (primero vistas, luego MVs) según convenga.

A continuación se da el SQL exacto para la vista y los índices sugeridos.

---

## 5. SQL exacto

### 5.1 Requisito previo

- `trips_2026` existe en `public` con **las mismas columnas** que `trips_all` (mismos nombres y tipos), para que el `SELECT *` del UNION ALL sea válido.
- Criterio de corte recomendado:
  - `trips_all`: solo filas con `fecha_inicio_viaje < '2026-01-01'` (o sin datos 2026).
  - `trips_2026`: solo filas con `fecha_inicio_viaje >= '2026-01-01'`.

Si en tu entorno `trips_all` ya contiene 2026, primero habría que dejar de cargar 2026 ahí y cargar solo en `trips_2026` (o mover datos 2026 de `trips_all` a `trips_2026` y luego borrar esos rangos de `trips_all`).

### 5.2 Crear la VIEW unificada

```sql
-- Crear vista unificada: una sola fuente lógica para todo el real
CREATE OR REPLACE VIEW public.trips_unified AS
SELECT * FROM public.trips_all
UNION ALL
SELECT * FROM public.trips_2026;

COMMENT ON VIEW public.trips_unified IS
'Unión lógica de trips_all (histórico) y trips_2026 (2026+). Mismas columnas en ambas tablas. Usar como fuente en MVs/vistas de real.';
```

### 5.3 Índices recomendados (mitigación de rendimiento)

Ejecutar **después** de crear la vista, en ventana de bajo uso. Para tablas muy grandes, usar `CREATE INDEX CONCURRENTLY` y aumentar timeout si hace falta.

```sql
-- trips_all: filtros por fecha y condicion (usados por MVs real)
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_trips_all_fecha_inicio
ON public.trips_all (fecha_inicio_viaje);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_trips_all_condicion_fecha
ON public.trips_all (condicion, fecha_inicio_viaje)
WHERE condicion = 'Completado';

-- Opcional: agregados por park/LOB (plan vs real, LOB hunt)
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_trips_all_realkey_month
ON public.trips_all (park_id, tipo_servicio, (DATE_TRUNC('month', fecha_inicio_viaje)::DATE));

-- trips_2026: mismos criterios
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_trips_2026_fecha_inicio
ON public.trips_2026 (fecha_inicio_viaje);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_trips_2026_condicion_fecha
ON public.trips_2026 (condicion, fecha_inicio_viaje)
WHERE condicion = 'Completado';

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_trips_2026_realkey_month
ON public.trips_2026 (park_id, tipo_servicio, (DATE_TRUNC('month', fecha_inicio_viaje)::DATE));
```

### 5.4 Uso en MVs/vistas

Donde hoy tengas:

```sql
FROM public.trips_all t
```

cámbialo a:

```sql
FROM public.trips_unified t
```

Ejemplo para una MV (el cambio es solo el nombre de la tabla fuente):

```sql
-- Antes (ejemplo conceptual)
FROM public.trips_all t
WHERE t.condicion = 'Completado' AND t.fecha_inicio_viaje IS NOT NULL

-- Después
FROM public.trips_unified t
WHERE t.condicion = 'Completado' AND t.fecha_inicio_viaje IS NOT NULL
```

Puedes aplicar este reemplazo en:

- Las definiciones de MVs que lean de `trips_all` (mv_real_trips_monthly, mv_real_trips_monthly_v2, mv_real_trips_weekly, mv_real_rollup_day, mv_real_lob_*, etc.).
- Las vistas que referencian `trips_all` (v_real_universe_*, v_real_trips_*, v_plan_vs_real_*, vistas LOB/drill que usen trips).

La forma más limpia es hacerlo en **nuevas migraciones de Alembic** que recreen o alteren solo la definición de cada MV/vista para usar `trips_unified`, en lugar de editar migraciones ya aplicadas.

### 5.5 Comprobar que la vista devuelve el mismo esquema

```sql
-- Comprobar columnas (debe coincidir con trips_all / trips_2026)
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'trips_unified'
ORDER BY ordinal_position;
```

---

## 6. Resumen

| Qué | Cómo |
|-----|------|
| **Unificación de fuentes** | VIEW `public.trips_unified` = `trips_all` UNION ALL `trips_2026` |
| **Evitar tablas gigantes** | No se copian datos; cada tabla mantiene su rango (histórico vs 2026+) |
| **Rendimiento** | Índices por `fecha_inicio_viaje` y `(condicion, fecha_inicio_viaje)` en ambas tablas; opcional park/tipo_servicio/mes |
| **Cambio en código** | Sustituir `FROM public.trips_all` por `FROM public.trips_unified` en MVs y vistas de real (idealmente en nuevas migraciones) |

Con esto se incorpora `trips_2026` de forma mínima y segura, sin crear tablas gigantes y con una única recomendación: **VIEW unificada + índices + uso de `trips_unified` en las definiciones de real.**
