# Cadena REAL canónica — Declaración oficial

**Control Tower — Única fuente de verdad para datos REAL (viajes/completados/margen).**

---

## Cadena canónica (hourly-first)

```
v_trips_real_canon_120d
  → v_real_trip_fact_v2
  → mv_real_lob_hour_v2 / mv_real_lob_day_v2
  → real_rollup_day_fact (vista sobre day_v2)
  → real_drill_dim_fact / mv_real_drill_dim_agg (day/week/month desde misma cadena)
  → agregados week/month derivados de la misma cadena
```

**Regla de gobierno (OBLIGATORIA):**

- **NEW REAL CONSUMERS MUST USE CANONICAL HOURLY-FIRST ONLY.**
- No añadir nuevos consumidores a legacy: `mv_real_trips_monthly`, `mv_real_trips_weekly`, `mv_real_trips_by_lob_*`, `v_real_metrics_monthly`, vistas plan-vs-real que lean de esas MVs.
- Cualquier feature o pantalla nueva que necesite datos REAL debe leer de la cadena canónica (vía `GET /ops/real/monthly?source=canonical` cuando exista paridad, o desde `real_drill_dim_fact` / `real_rollup_day_fact` / `mv_real_lob_day_v2` según grano). Consultar `CONTROL_TOWER_REAL_GOVERNANCE_STATUS.md` y `CONTROL_TOWER_REAL_CANONICALIZATION_PLAN.md`.

---

## Objetos que forman parte de la cadena

| Objeto | Grano | Uso |
|--------|-------|-----|
| ops.v_trips_real_canon_120d | viaje | Canon 120d, entrada a la cadena |
| ops.v_real_trip_fact_v2 | viaje | Fact horario normalizado |
| ops.mv_real_lob_hour_v2 | hour | Operativo por hora |
| ops.mv_real_lob_day_v2 | day | Operativo por día |
| ops.real_rollup_day_fact | day | Vista sobre day_v2; comparativos, drill |
| ops.real_drill_dim_fact / ops.mv_real_drill_dim_agg | day/week/month | Drill PRO, agregados por periodo |
| ops.mv_real_monthly_canonical_hist | month, country | Resumen mensual histórico (v_trips_real_canon, sin 120d) |
| ops.v_real_universe_by_park_realkey_canon | month, country, city, park_id, real_tipo_servicio | Real agregado para Plan vs Real (desde v_trips_real_canon; revenue = ABS(comision)) |
| ops.v_plan_vs_real_realkey_canonical | idem legacy | Plan vs Real mensual con real canónica (mismo contrato que v_plan_vs_real_realkey_final) |
| ops.v_real_data_coverage | — | Cobertura y freshness |

---

## Objetos legacy (no canónicos)

No deben tener **nuevos** consumidores. Migrar consumidores existentes y luego deprecar/eliminar.

- ops.mv_real_trips_monthly  
- ops.mv_real_trips_weekly  
- ops.mv_real_trips_by_lob_month / ops.mv_real_trips_by_lob_week  
- ops.v_real_metrics_monthly (cuando se alimente de mv_real_trips_monthly)  
- Vistas plan-vs-real que tomen real de las MVs anteriores  

Ver `CONTROL_TOWER_REAL_CANONICALIZATION_PLAN.md` para inventario y plan de erradicación.

---

## Modelo de conductores (drivers)

- **Drivers core:** Se calculan desde **viajes** (quién operó, cuántos conductores únicos). Fuente: cadena canónica de viajes (`v_real_trip_fact_v2` o agregados derivados). No usar segmentación para este concepto.
- **Drivers segmentados:** Se calculan desde **segmentación** (cómo operó: activos vs cancel-only, etc.). No son intercambiables con drivers core.
- Grano por vista (Resumen mensual = driver–month–country; semanal = driver–week–country; drill LOB/Park/service_type = driver–period–country–dimensión). Detalle en **`docs/REAL_DRIVER_GOVERNANCE.md`**.

---

## Fuente canónica mensual para Resumen

### Canónica mensual histórica (recomendada para Resumen)

- **Objeto:** `ops.mv_real_monthly_canonical_hist`.
- **Fuente base:** `ops.v_trips_real_canon` (trips_all &lt; 2026 + trips_2026 ≥ 2026), **sin ventana 120d**. Cobertura histórica completa.
- **Grano:** month_start, country. Métricas: trips (completados), margin_total (revenue), active_drivers_core (COUNT DISTINCT conductor_id completados).
- **Consumidor:** `canonical_real_monthly_service.get_real_monthly_canonical()` lee solo de esta MV. Refresco: `scripts/refresh_real_monthly_canonical_hist.py` (tras cambios en trips_all/trips_2026).

### Cadena 120d (operativa / drill reciente)

- **Trips/revenue (ventana reciente):** `ops.real_drill_dim_fact` (period_grain = 'month', breakdown = 'lob'), poblada desde `mv_real_lob_month_v3` por `populate_real_drill_from_hourly_chain`. Limitada a 120d.
- **Drivers core (ventana reciente):** `v_real_trip_fact_v2` (lee de `v_trips_real_canon_120d`). Solo meses dentro de 120d.
- **Uso:** Drill PRO, real diario, comparativos recientes. **No** usar para Resumen mensual con año completo histórico; usar `mv_real_monthly_canonical_hist`.

---

## Plan vs Real mensual (real canónica)

- **Objeto:** `ops.v_plan_vs_real_realkey_canonical` (real desde `ops.v_real_universe_by_park_realkey_canon` → `ops.v_trips_real_canon`).
- **Activación:** `GET /ops/plan-vs-real/monthly?source=canonical` y `GET /ops/plan-vs-real/alerts?source=canonical`. Sin parámetro = legacy (`v_plan_vs_real_realkey_final`).
- **Consistencia:** Misma definición REAL que Resumen (trips completados, revenue = ABS(comision_empresa_asociada)), mismo filtro país (pe/co). Grano Plan vs Real: (country, city, park_id, real_tipo_servicio, period_date).
- **Paridad:** Ejecutar `python -m scripts.validate_plan_vs_real_parity` antes de activar canónica por defecto en UI.
