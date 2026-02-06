# PASO 2 E2E - Homologación LOB PLAN ↔ REAL — Salida

## Reglas de negocio (respetadas)

- **LOB REAL madre** = `trips_all.tipo_servicio` (lob_base). No se redefine.
- **B2B** = `pago_corporativo` (market_type). No redefine lob_base.
- **Homologación** solo alinea “dialectos” de naming; no crea LOB nuevas desde real.

---

## 0) PRECHECK (estructura y datos)

- **Vistas 2C+** (ya creadas por migraciones 020, 021, 022):
  - `ops.v_real_lob_base` — LOB base desde trips_all + regla madre.
  - `ops.v_real_lob_resolution` — Resolución con homologación.
  - `ops.v_real_tipo_servicio_universe` — Agregado por country, city, tipo_servicio (usa dim_park + fecha_inicio_viaje).
- **trips_all**: existencia verificada; columnas clave `fecha_inicio_viaje`, `tipo_servicio`.  
  Conteo 2025/2026 omitido en E2E si la tabla es muy grande (ejecutar a mano con timeout alto si se necesita).

---

## 1) UNIVERSO REAL (canon operativo)

- La vista **ops.v_real_tipo_servicio_universe** ya está definida en la migración 021 (usa `trips_all` + `dim.dim_park`, `fecha_inicio_viaje`, `condicion = 'Completado'`).
- Si tu esquema tiene `trips_all` con columnas `country`, `city`, `trip_date`, puedes reemplazar por la definición literal del super prompt (ver comentario en `backend/sql/paso2_homologacion_lob_e2e.sql`).
- **Reporte**: Top 50 `real_tipo_servicio` por `trips_count` (global y por país) se genera en el script `run_paso2_homologacion_e2e.py` (sección 1). En entornos con `trips_all` muy grande puede haber timeout; en ese caso aumentar `statement_timeout` en el servidor.

---

## 2) STAGING PLAN CSV

- **Schema + tabla**: `staging.plan_projection_raw` (creada en 021) con columnas:  
  `plan_raw_id`, `country`, `city`, `lob_name`, `period_date`, `trips_plan`, `revenue_plan`, `raw_row` (JSONB), `loaded_at`.
- **Loader**: `backend/scripts/load_plan_projection_csv.py`
  - Detecta headers del CSV.
  - Mapea a: country, city, lob_name, period_date, trips_plan, revenue_plan.
  - Guarda la fila completa en `raw_row`.
  - Log: filas cargadas, fechas min/max, nulos por columna.
- **Uso**: `python scripts/load_plan_projection_csv.py <ruta_csv>`

---

## 3) UNIVERSO PLAN (raw)

- Vista **ops.v_plan_lob_universe_raw** (021): agrupa por country, city, `TRIM(LOWER(lob_name))` con SUM(trips_plan), SUM(revenue_plan), MIN/MAX(period_date).
- Reportes: Top 50 `plan_lob_name` por trips_plan y conteo de distintos en el script E2E (sección 3).

---

## 4) TABLA DE HOMOLOGACIÓN (puente auditable)

- **ops.lob_homologation** (021): homologation_id, country, city, real_tipo_servicio, plan_lob_name, confidence (high/medium/low), notes, created_at, UNIQUE(country, city, real_tipo_servicio, plan_lob_name).

---

## 5) SUGERENCIAS (sin autodecisión)

- Vista **ops.v_lob_homologation_suggestions** (021): match exacto → high; contains → low. Incluye already_homologated y filtro para no duplicar.

---

## 6) INSERCIÓN CONTROLADA (solo matches exactos)

- El script E2E y el SQL `paso2_homologacion_lob_e2e.sql` insertan en `ops.lob_homologation` **solo** los registros con `suggested_confidence = 'high'` (match exacto), con `ON CONFLICT DO NOTHING`.

---

## 7) GAP REPORTS

- **Real sin homologación**: ver consulta 7.1 en el super prompt; implementada en el script (sección 6) y en comentarios en `paso2_homologacion_lob_e2e.sql`. También existe la vista **ops.v_real_lob_without_homologation** (021).
- **Plan sin homologación**: consulta 7.2 en el script y en SQL. Vista **ops.v_plan_lob_without_homologation** (021).

---

## 8) SALIDA — RESUMEN EJECUTIVO (8 bullets)

Al ejecutar `python scripts/run_paso2_homologacion_e2e.py` (o el SQL manual), el resumen debe incluir:

1. **Total real_tipo_servicio distintos** — Conteo desde `ops.v_real_tipo_servicio_universe`.
2. **Total plan_lob_name distintos** — Conteo desde `ops.v_plan_lob_universe_raw` (o 0 si staging vacío).
3. **Homologaciones high creadas** — Filas insertadas en esta ejecución (solo matches exactos).
4. **Top 20 gaps REAL** — Listado en sección 6 del script.
5. **Top 20 gaps PLAN** — Listado en sección 6 del script.
6. **Recomendación próximos 10 mappings manuales** — Sugerencias con `suggested_confidence = 'low'` ordenadas por impacto (trips_real, plan_trips), sección 7 del script.
7. **No se crea lob_catalog del plan** si el plan no está limpio (no implementado en este paso).
8. **Lógica madre** (LOB = tipo_servicio, B2B = pago_corporativo) no tocada.

---

## Cómo ejecutar

1. **Precheck + reportes + insert + gaps + resumen**:  
   `cd backend` → `python scripts/run_paso2_homologacion_e2e.py`  
   (Si hay timeout: en la sesión SQL ejecutar `SET statement_timeout = '300s';` o aumentar en el servidor.)
2. **Cargar CSV de proyección a staging**:  
   `python scripts/load_plan_projection_csv.py <ruta_csv>`
3. **Solo SQL (inserción exacta + estructura)**:  
   Ejecutar `backend/sql/paso2_homologacion_lob_e2e.sql` en tu cliente PostgreSQL (con timeout alto si aplica).
