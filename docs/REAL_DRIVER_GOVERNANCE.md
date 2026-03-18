# Gobierno de conductores REAL — Drivers core vs segmentados

**Control Tower — Definición formal del modelo de drivers y grano por vista.**

---

## 1. Dos conceptos no intercambiables

### A. DRIVERS CORE (conductores operativos)

- **Definición:** Conteo de conductores únicos que **operaron** (realizaron al menos un viaje completado en el periodo).
- **Origen:** Siempre desde **viajes** (cadena canónica de viajes), no desde segmentación.
- **Cálculo:** `COUNT(DISTINCT conductor_id)` sobre la fuente de viajes, filtrado por viajes completados, periodo y ámbito (país, etc.).
- **Responden a:** ¿Quién operó? ¿Cuántos conductores únicos produjeron (viajes/revenue) en el periodo?
- **Se pueden sumar:** Solo cuando el grano y el ámbito coinciden (p. ej. mismo periodo y mismo país). No sumar entre periodos ni entre tajadas distintas sin criterio explícito.
- **No se deben sumar:** Entre breakdowns distintos (LOB vs Park vs service_type) sin definir si se desduplica; entre drivers core y drivers segmentados.

### B. DRIVERS SEGMENTADOS (conductores por comportamiento)

- **Definición:** Conteo de conductores clasificados por **comportamiento** (activos vs solo cancelan, etc.) en el periodo.
- **Origen:** Batch de segmentación (p. ej. `v_real_driver_segment_driver_period`, `v_real_driver_segment_agg`).
- **Responden a:** ¿Cómo operó el conductor? Activos vs cancel-only, etc.
- **No son intercambiables** con drivers core: un mismo conductor puede contar en ambos, pero las cifras y el significado son distintos. No usar drivers segmentados para “conductores que operaron” en Resumen.

**Regla obligatoria:** Resumen mensual (y cualquier vista de “conductores activos” operativos) debe usar **solo drivers core** desde viajes. No depender del batch de segmentación para ese KPI.

---

## 2. Grano correcto de drivers core por vista

| Vista / pantalla              | Grano drivers core     | Fuente recomendada (viajes)                    | Notas |
|------------------------------|-------------------------|------------------------------------------------|-------|
| Resumen mensual               | driver–month–country   | `v_real_trip_fact_v2` (o equivalente) por mes | COUNT(DISTINCT conductor_id) por trip_month_start, country |
| Resumen semanal               | driver–week–country     | Misma cadena por week_start                   | Idem por semana |
| Resumen diario                | driver–day–country      | Misma cadena por trip_date                     | Idem por día |
| Drill por LOB                 | driver–period–country–lob | Viajes agregados por period + country + lob_group | Desglose LOB |
| Drill por Park                | driver–period–country–park | Viajes agregados por period + country + park  | Desglose parque |
| Drill por service_type        | driver–period–country–service_type | Viajes por period + country + real_tipo_servicio_norm | Desglose tipo servicio |

- **Qué se puede sumar:** Totales de viajes o revenue en el mismo grano; drivers core solo en el mismo grano y ámbito (evitando doble conteo al cambiar de tajada).
- **Qué NO se puede sumar:** Drivers core de un periodo con otro sin criterio; drivers core con drivers segmentados; filas de distintos breakdowns (lob vs park vs service_type) para un mismo KPI de “conductores” sin definir desduplicación.

---

## 3. Fuente canónica para drivers core (Resumen mensual)

- **Fuente:** `ops.v_real_trip_fact_v2` (cadena canónica de viajes).
- **Filtros:** `is_completed = true`, `conductor_id IS NOT NULL`, mismo año (y opcionalmente mismo país).
- **Agregación:** `GROUP BY trip_month_start` (y country si aplica) → `COUNT(DISTINCT conductor_id) AS active_drivers`.
- **Limitación:** La vista `v_real_trip_fact_v2` depende de `v_trips_real_canon_120d`, por tanto solo incluye viajes en ventana 120d. Los meses fuera de esa ventana no tendrán datos de conductores en esta fuente; es limitación de cobertura, no de lógica.

---

## 4. Referencia cruzada

- Cadena canónica: `docs/REAL_CANONICAL_CHAIN.md`.
- Plan de canonicalización y paridad: `docs/CONTROL_TOWER_REAL_CANONICALIZATION_PLAN.md`.
- Informe Fase 1 y desacoplamiento de conductores: `docs/CONTROL_TOWER_REAL_CANONICALIZATION_PHASE1_REPORT.md`.
