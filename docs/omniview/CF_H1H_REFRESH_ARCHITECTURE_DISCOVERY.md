# CF-H1H — REFRESH ARCHITECTURE DISCOVERY REPORT

**Motor:** Control Foundation  
**Fecha:** 2026-05-31  
**Estado:** DISCOVERY COMPLETED — NO IMPLEMENTATION  

---

## 1. ARQUITECTURA ACTUAL

```
RAW (trips_2026: 16.4M rows, trips_2025: 47.9M rows)
  │
  ▼  ops.v_real_trips_enriched_base (VIEW)
  │  ├── UNION ALL trips_2025 + trips_2026
  │  ├── DISTINCT ON (id) → barrera de optimización
  │  ├── LEFT JOIN dim_park
  │  └── LEFT JOIN drivers
  │
  ▼  CREATE TEMP TABLE _bs_enriched_month
  │  (FULL SCAN de 65.4M filas, sort por id, dedup)
  │  Tiempo: ~15-40 min por mes
  │
  ├──▼ day_fact    (INSERT ... FROM _bs_enriched_month GROUP BY trip_date)
  │     21 rows/día, 3 segundos
  │
  ├──▼ week_fact   (INSERT ... FROM _bs_enriched_month GROUP BY week_start)
  │     21 rows/semana, 2 segundos
  │     ⚠ Mismo full scan que day_fact — RE-scan de la vista si no existe temp table
  │
  └──▼ month_fact  (INSERT ... FROM _bs_enriched_month GROUP BY month)
        23 rows/mes, 2 segundos
        ⚠ RE-materializa enriched (otro full scan)
```

**El problema:** Para producir 21 filas en week_fact, se escanean 65.4M filas de RAW. El costo de materializar `_bs_enriched_month` es **1000× mayor** que todo el resto del pipeline combinado.

---

## 2. VOLUMETRÍA REAL

| Nivel | Filas | Escaneo actual |
|-------|-------|---------------|
| RAW 1 día | ~93K trips | — |
| RAW 30 días | ~3.1M trips | — |
| RAW 1 mes (mayo) | ~2.98M trips | — |
| RAW año completo (trips_2026) | 16.4M | **Seq Scan** |
| RAW 2025+2026 (DISTINCT ON) | **65.4M** | **Seq Scan + Sort** |
| day_fact 1 día | 21 rows | 3s |
| week_fact 1 semana | ~21 rows | 2s (tras materializar) |
| month_fact 1 mes | 23 rows | 2s (tras materializar) |

---

## 3. DEPENDENCIAS REALES

### ¿week_fact y month_fact pueden derivarse de day_fact?

| Métrica | Derivar de day_fact | Nota |
|---------|---------------------|------|
| trips_completed | **SÍ** | SUM(daily) = correcto |
| trips_cancelled | **SÍ** | SUM(daily) = correcto |
| revenue_yego_net | **SÍ** | SUM(daily) = correcto |
| revenue_yego_final | **SÍ** | SUM(daily) = correcto |
| avg_ticket | **SÍ** | Weighted avg: SUM(ticket_sum) / SUM(ticket_count) |
| commission_pct | **SÍ** | Weighted avg |
| cancel_rate_pct | **SÍ** | SUM(cancel) / SUM(total) |
| **active_drivers** | **NO** | `SUM(daily distinct)` duplica conductores que trabajan varios días |
| **precio_km, tiempo_km** | **NO** | No están en day_fact (solo en month_fact) |
| **completados_por_hora** | **NO** | No están en day_fact |

**Conclusión:** El 90% de las métricas pueden derivarse de day_fact. Solo `active_drivers` requiere RAW (COUNT DISTINCT driver_id en la ventana). Las columnas extras de month_fact (`precio_km`, `tiempo_km`) pueden derivarse del RAW con una query ligera.

---

## 4. ESTRATEGIA INCREMENTAL RECOMENDADA

### Fase 1 — Incremental Day Fact (costo: ~3s/día)

```sql
-- Bypassea la vista. Va directo a trips_2026 con filtro eficiente.
-- Usa ix_trips_2026_fecha_inicio_viaje.
INSERT INTO ops.real_business_slice_day_fact
SELECT trip_date, country, city, ...
FROM (
  SELECT fecha_inicio_viaje::date AS trip_date, ...
  FROM public.trips_2026
  WHERE fecha_inicio_viaje >= '2026-05-30'::timestamptz  -- ← usa índice
    AND fecha_inicio_viaje <  '2026-05-31'::timestamptz
  -- ... business slice resolution ...
) r
GROUP BY trip_date, country, city, ...
ON CONFLICT DO UPDATE
```

**Costo:** ~93K filas/día scaneadas vía índice. ~3 segundos.

### Fase 2 — Incremental Week Fact (costo: ~4s/semana)

```sql
-- 90% desde day_fact (sin RAW)
INSERT INTO ops.real_business_slice_week_fact
SELECT
  date_trunc('week', d.trip_date)::date AS week_start,
  d.country, d.city, d.business_slice_name, ...
  SUM(d.trips_completed) AS trips_completed,
  SUM(d.trips_cancelled) AS trips_cancelled,
  SUM(d.revenue_yego_net) AS revenue_yego_net,
  -- Active drivers: COUNT DISTINCT desde RAW (solo la ventana semanal)
  (SELECT COUNT(DISTINCT conductor_id)
   FROM public.trips_2026
   WHERE fecha_inicio_viaje::date >= week_start
     AND fecha_inicio_viaje::date < week_start + 7
     AND condicion = 'Completado'
     AND country = d.country AND city = d.city
  ) AS active_drivers,
  ...
FROM ops.real_business_slice_day_fact d
WHERE d.trip_date >= week_start AND d.trip_date < week_start + 7
GROUP BY week_start, country, city, ...
```

**Costo:** Lectura de ~147 filas de day_fact (21 × 7) + 1 COUNT DISTINCT en RAW acotado a 1 semana (~650K filas con índice). ~4 segundos.

### Fase 3 — Incremental Month Fact (costo: ~5s/mes)

Mismo patrón que week_fact, pero con ventana mensual. COUNT DISTINCT sobre ~3M filas (último mes). ~5 segundos.

### Fase 4 — Proyección Serving Fact (sin cambios)

La proyección ya lee de day_fact/week_fact/month_fact. Si estos están frescos, la proyección también lo estará.

---

## 5. REBUILD SCOPE

Para una nueva fecha como 2026-05-30:

| Operación | Scope necesario | Scope actual |
|-----------|----------------|-------------|
| day_fact | Solo 2026-05-30 (93K filas) | Mes completo (2.98M filas) via enriched → 65.4M scan |
| week_fact | Solo la semana que contiene 2026-05-30 (~21 filas) | Dos meses → 2× enriched scan |
| month_fact | Solo mayo 2026 (23 filas) | Mes completo → enriched scan |

**Con incremental: ~10 segundos total. Actual: ~30-60 minutos.**

---

## 6. COMPARACIÓN DE COSTOS

| Estrategia | Filas escaneadas | Tiempo estimado | Problema |
|-----------|-----------------|-----------------|----------|
| **Actual** (`--force`) | 65.4M × 2 meses = 130.8M | 30-60 min | DISTINCT ON + Sort masivo |
| **Actual** (1 mes) | 65.4M | 15-30 min | DISTINCT ON bloquea pushdown |
| **Incremental** (day_fact) | 93K (1 día) | 3s | Necesita bypass de vista |
| **Incremental** (week_fact) | ~150 day_fact rows + 650K RAW | 4s | Necesita ROLLUP + COUNT DISTINCT |
| **Incremental** (month_fact) | ~600 day_fact rows + 3M RAW | 5s | Mismo patrón |
| **Incremental total** (daily refresh) | ~3.8M filas | ~12s | 100× más rápido |

---

## 7. RIESGOS

| Riesgo | Severidad | Mitigación |
|--------|-----------|------------|
| `active_drivers` incorrecto en ROLLUP | Alta | COUNT DISTINCT desde RAW con filtro de fecha, no SUM de day_fact |
| `precio_km`/`tiempo_km` faltantes en month_fact | Media | Query ligera adicional a RAW acotada al mes |
| ON CONFLICT en week_fact | Baja | Usar DELETE + INSERT como month_fact actual |
| El ROLLUP cubre todo el mes/semana aunque solo 1 día cambió | Baja | El costo es trivial comparado con el actual |
| Cambiar el pipeline rompe projection serving | Media | Testear que projection facts sigan derivando correctamente |

---

## 8. ESFUERZO

| Fase | Archivos | Complejidad |
|------|----------|-------------|
| F1: Bypass vista para day_fact | `business_slice_incremental_load.py` — nueva función `_materialize_enriched_direct` | Media |
| F2: ROLLUP day→week | `business_slice_incremental_load.py` — activar `_WEEK_ROLLUP_FROM_DAY_FACT` con fix de active_drivers | Media |
| F3: ROLLUP day→month | `business_slice_incremental_load.py` — nuevo template | Media |
| F4: Nuevo refresh job | `business_slice_real_refresh_job.py` — simplificar scope a últimos N días | Baja |

---

## 9. GO / NO-GO

| Decisión | Veredicto |
|----------|-----------|
| **Seguir usando `--force` con la vista** | **NO-GO** — 65.4M filas por mes es inviable |
| **Implementar bypass de vista** | **GO** — query directa a `trips_2026` con filtro de fecha usa índice y scanea solo lo necesario |
| **Derivar week_fact de day_fact (ROLLUP)** | **GO** — 90% de métricas son sumables, active_drivers se resuelve con COUNT DISTINCT acotado |
| **Derivar month_fact de day_fact (ROLLUP)** | **GO** — mismo patrón, costo trivial |
| **Scope diario (último día)** | **GO** — 93K filas vs 65.4M |
| **Eliminar dependencia de trips_2025** | **GO** — para datos 2026 nunca se necesita 2025 |

---

## 10. ARQUITECTURA RECOMENDADA (DIAGRAMA)

```
RAW trips_2026 (16.4M rows, indexed)
  │
  │  filtro por día/semana/mes (usa índice)
  │  SIN DISTINCT ON, SIN trips_2025
  ▼
┌─────────────────────────────────────────────────────┐
│  _materialize_enriched_direct(start_date, end_date)  │
│  SELECT ... FROM trips_2026                          │
│  WHERE fecha_inicio_viaje >= start                  │
│    AND fecha_inicio_viaje <  end                    │
│  LEFT JOIN dim_park ... LEFT JOIN drivers ...       │
│  (crea TEMP TABLE con solo las filas necesarias)     │
└────────────────────────┬────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
     day_fact        week_fact       month_fact
     (upsert)        (ROLLUP desde   (ROLLUP desde
     GROUP BY        day_fact +      day_fact +
     trip_date       COUNT DISTINCT  COUNT DISTINCT
                     en RAW)         en RAW)
         │               │               │
         └───────────────┼───────────────┘
                         ▼
              serving.omniview_projection
              (projection_expected_progress_service.py)
```

**Tiempo total para refresh diario: ~12 segundos (vs 30-60 minutos actuales).**

**Tiempo total para refresh completo de mayo 2026: ~60 segundos (31 días × 2s de day_fact + ROLLUPs).**
