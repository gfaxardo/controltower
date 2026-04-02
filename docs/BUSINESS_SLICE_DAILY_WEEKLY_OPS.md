# Business Slice Daily/Weekly — Guia Operativa

## Arquitectura de datos

```
trips_2025 / trips_2026
       |
       v
ops.v_real_trips_enriched_base  (vista, NO materializada)
       |
       v  (materializa en TEMP TABLE por mes)
business_slice_incremental_load.py
       |
       +---> ops.real_business_slice_month_fact  (grano mensual)
       +---> ops.real_business_slice_day_fact    (grano diario)
       +---> ops.real_business_slice_week_fact   (rollup de day_fact)
```

## Tablas fact

| Tabla | Grano | Clave unica |
|-------|-------|-------------|
| `ops.real_business_slice_month_fact` | mes + country + city + slice + fleet | `month` |
| `ops.real_business_slice_day_fact` | dia + country + city + slice + fleet | `trip_date` |
| `ops.real_business_slice_week_fact` | semana + country + city + slice + fleet | `week_start` |

### Columnas principales

`trips_completed`, `trips_cancelled`, `active_drivers`, `avg_ticket`,
`commission_pct`, `trips_per_driver`, `revenue_yego_net`, `cancel_rate_pct`

## Poblar / Refrescar datos

### Un solo mes (month + day + week)

```bash
cd backend
python -m scripts.refresh_business_slice_mvs --month 2026-03
```

### Backfill por rango (solo day + week)

```bash
python -m scripts.backfill_business_slice_daily --from-date 2026-01 --to-date 2026-03
```

### Backfill completo (month + day + week)

```bash
python -m scripts.backfill_business_slice_daily --from-date 2026-01 --to-date 2026-03 --with-month
```

### Backfill con dry-run

```bash
python -m scripts.backfill_business_slice_daily --from-date 2026-01 --to-date 2026-03 --dry-run
```

### Solo day (sin week)

```bash
python -m scripts.backfill_business_slice_daily --from-date 2026-03 --to-date 2026-03 --no-week
```

### Backfill legacy (solo month_fact, sin day/week)

```bash
python -m scripts.refresh_business_slice_mvs --backfill-from 2025-01 --backfill-to 2025-12 --no-daily
```

## Tiempos esperados

| Operacion | Tiempo estimado |
|-----------|-----------------|
| Materializar enriched base (1 mes) | 15-40 min |
| Resolver + agregar day_fact (1 mes) | 5-15 min por chunk |
| Week rollup | < 1 min |
| Total por mes | 20-60 min |

## Endpoints

| Endpoint | Fuente principal | Fallback |
|----------|-----------------|----------|
| `GET /ops/business-slice/daily` | `ops.real_business_slice_day_fact` | `ops.v_real_trips_business_slice_resolved` (lento, usa `get_db_drill`) |
| `GET /ops/business-slice/weekly` | `ops.real_business_slice_week_fact` | `ops.v_real_trips_business_slice_resolved` (lento, usa `get_db_drill`) |

### Cuando cae a fallback

El endpoint verifica si la fact table tiene datos **para el rango de fechas solicitado** (year/month).
Si no hay datos en el rango pedido, cae a fallback con un log WARNING:

```
day_fact sin datos para year=2026 month=3 -- fallback a vista resolved (lento)
```

## Diagnostico: revenue_yego_net NULL

### Causa raiz

`revenue_yego_net` viene de `comision_empresa_asociada` en las tablas fuente
(`trips_2025` / `trips_2026`). Si esa columna es NULL o 0 en los viajes,
revenue sera NULL en la fact.

**Ejemplo real:** Para marzo 2026, solo 1 de 3.9M viajes tenia `comision_empresa_asociada` no nula.
Esto es un tema de INGESTION upstream, no del loader.

### Como verificar

```sql
-- Verificar si la fuente tiene comision para un mes:
SELECT count(*) AS total,
       count(comision_empresa_asociada) AS has_comision,
       count(*) FILTER (WHERE comision_empresa_asociada != 0) AS nonzero
FROM public.trips_2026
WHERE fecha_inicio_viaje >= '2026-03-01' AND fecha_inicio_viaje < '2026-04-01';

-- Verificar revenue en la fact:
SELECT trip_date, count(*) AS rows,
       count(revenue_yego_net) AS rev_ok,
       count(*) - count(revenue_yego_net) AS rev_null
FROM ops.real_business_slice_day_fact
WHERE trip_date >= '2026-03-01'
GROUP BY trip_date ORDER BY trip_date;
```

### Cuando re-poblar

Si `comision_empresa_asociada` se actualiza upstream (por ejemplo via Yango Pro reporting),
re-ejecutar el refresh para ese mes:

```bash
python -m scripts.refresh_business_slice_mvs --month 2026-03
```

## Validacion

```bash
python -m scripts._validate_day_fact
python -m scripts._test_endpoint_performance
```

## Cobertura actual

| Periodo | month_fact | day_fact | week_fact |
|---------|-----------|---------|----------|
| 2025-01 a 2025-12 | SI | NO (requiere backfill) | NO |
| 2026-01 a 2026-03 | SI | SI (post backfill) | SI |

**Nota:** Los meses de 2025 usan `trips_2025` que tiene `comision_empresa_asociada = NULL`
para todos los registros (0 filas con comision). Revenue sera NULL para todo 2025.
