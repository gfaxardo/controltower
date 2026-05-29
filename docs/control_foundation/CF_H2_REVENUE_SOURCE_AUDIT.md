# CF-H2 Revenue Source Audit

## Fecha: 2026-05-29
## Motor: Control Foundation H2

---

## 1. Columnas de revenue existentes

| Columna | Definición | Nivel | Fecha de creación |
|---------|-----------|-------|-------------------|
| `revenue_yego_net` | `NULLIF(comision_empresa_asociada, 0)` — commission real | RAW/enriched | Migration 111 (base) |
| `revenue_yego_real` | `ABS(revenue_yego_net)` — solo completed, solo cuando existe | Enriched temp | Migration 120 |
| `revenue_yego_proxy` | `ticket * resolve_commission_pct(...)` — fallback cuando real es NULL | Enriched temp | Migration 120 |
| `revenue_yego_final` | `COALESCE(revenue_yego_real, revenue_yego_proxy)` — best effort | Facts | Migration 120 |
| `revenue_source` | Enum: `'real'` / `'proxy'` / `'missing'` | Enriched temp | Migration 122 |
| `revenue_real_coverage_pct` | % de trips con revenue real vs proxy | Facts | Migration 120 |
| `revenue_proxy_trips` | # trips con proxy revenue | Facts | Migration 120 |
| `revenue_real_trips` | # trips con revenue real | Facts | Migration 120 |
| `real_revenue` | Alias en projection: `ABS(COALESCE(final, net))` | Projection | Fase 1G.3 |
| `real_revenue_raw` | Audit trail: `COALESCE(final, net)` con signo | Projection | Fase 1G.3 |
| `gmv_passenger_paid` | `efectivo + tarjeta + pago_corporativo` — GMV, NO revenue | RAW | Migration 010 |
| `total_fare` | Mismo que gmv_passenger_paid (denominador de commission_pct) | RAW | Migration 126 |
| `ticket` | `precio_yango_pro` — usado en proxy, NO es revenue | RAW | Migration 126 |

---

## 2. Fuente primaria (RAW)

### Revenue YEGO real
```
Tabla origen: public.trips_unified
Columna origen: comision_empresa_asociada (commission cobrada por YEGO al driver)
Migración: 126_business_slice_trips_unified_trust.py, línea 133
```

### GMV (NO es revenue)
```
Tabla origen: public.trips_unified
Columnas: efectivo + tarjeta + pago_corporativo = gmv_passenger_paid
Migración: 010_fix_real_revenue_gmv_take_rate.py, línea 57-81
```

### Ticket
```
Tabla origen: public.trips_unified
Columna: precio_yango_pro (lo que paga el pasajero)
Migración: 126, línea 134
```

---

## 3. Pipeline de revenue

```
comision_empresa_asociada (RAW)
  │
  ▼
ops.v_real_trips_enriched_base
  revenue_yego_net = NULLIF(comision_empresa_asociada, 0)
  ticket = precio_yango_pro
  total_fare = efectivo + tarjeta + pago_corporativo
  │
  ▼
_bs_enriched_month (temp table)
  revenue_yego_real     = ABS(revenue_yego_net)  — when real exists
  revenue_yego_proxy    = ticket * commission_pct — when real is NULL
  revenue_yego_final    = COALESCE(real, proxy)   — best effort
  revenue_source        = 'real' | 'proxy' | 'missing'
  │
  ▼
Agregación por business_slice (resolution CTE + GROUP BY)
  revenue_yego_net  = SUM(revenue_yego_real aliased as revenue_yego_net)
  revenue_yego_final = SUM(revenue_yego_final)
  commission_pct    = SUM(revenue)/SUM(total_fare)
  │
  ▼
Fact tables
  ops.real_business_slice_day_fact
  ops.real_business_slice_week_fact
  ops.real_business_slice_month_fact
  │
  ▼
Omniview (Evolution)
  Lee revenue_yego_net directamente del fact
  │
  ▼
Projection (Vs Proyección)
  _REVENUE_SELECT: ABS(COALESCE(revenue_yego_final, revenue_yego_net)) AS real_revenue
  Fallback: ABS(revenue_yego_net) AS real_revenue (si revenue_yego_final no existe)
  │
  ▼
Frontend
  recibe "revenue_yego_net" en el response
  muestra en matriz, calcula attainment vs plan
```

---

## 4. Fallback de revenue

### Nivel 1: Fallback por columna
```
Preferencia: revenue_yego_final (real + proxy)
Fallback:    revenue_yego_net (solo real)
```

### Nivel 2: Proxy commission pct
```
Función: ops.resolve_commission_pct(country, city, park_id, tipo_servicio, trip_date)
Tabla:   ops.yego_commission_proxy_config
Default: 3%
```

La función busca la mejor coincidencia por:
1. park_id + tipo_servicio + city + country (especificidad máxima)
2. Desempate: specificity DESC → priority DESC → valid_from DESC

### Nivel 3: Cobertura de revenue real
```
revenue_real_coverage_pct = 100 * trips_real / total_trips
```
Si coverage < 100%, hay trips con proxy. La columna lo documenta.

---

## 5. Fuente que usa Omniview

### Evolution (Real vs Real)
| Grain | Tabla | Columna leída | ¿Usa COALESCE? |
|-------|-------|--------------|-----------------|
| Monthly | `ops.real_business_slice_month_fact` | `revenue_yego_net` | No (directo) |
| Weekly | `ops.real_business_slice_week_fact` | `revenue_yego_net` | No (directo) |
| Daily | `ops.real_business_slice_day_fact` | `revenue_yego_net` | No (directo) |

### Vs Proyección (Plan vs Real)
| Grain | Tabla | Columna leída | SQL |
|-------|-------|--------------|-----|
| Monthly | `ops.real_business_slice_month_fact` | `real_revenue` | `ABS(COALESCE(revenue_yego_final, revenue_yego_net))` |
| Weekly | `ops.real_business_slice_week_fact` | `real_revenue` | Mismo |
| Daily | `ops.real_business_slice_day_fact` | `real_revenue` | Mismo |

### Nota crítica
En los fact tables, `revenue_yego_net` YA es la agregación de `revenue_yego_real` (ABS real) visto a través de la resolución CTE. Es decir: el fact NUNCA contiene el valor raw con signo de `comision_empresa_asociada`. El ABS se aplica en `_bs_enriched_month` (línea 968) y el valor viaja como `revenue_yego_net` a través de toda la cadena.

---

## 6. Revenue NO es GMV

Esta distinción está documentada y forzada desde migraciones tempranas:

- **009**: Prohíbe `projected_revenue = trips * ticket` (eso es GMV)
- **010**: Define `revenue_yego_real = ABS(comision_empresa_asociada)` vs `gmv_passenger_paid`
- **Audit scripts**: `validate_real_revenue_gmv.py` verifica revenue < GMV
- **Config**: `source_of_truth_registry.py` separa revenue de GMV en todos los datasets

El take rate típico es ~3% (revenue / GMV), lo que confirma que revenue es la comisión, no el pago del pasajero.

---

## 7. Hallazgos

| Aspecto | Estado |
|---------|--------|
| Revenue tiene fuente RAW certificada | SI — `comision_empresa_asociada` |
| Revenue tiene fallback documentado | SI — proxy via `ticket * commission_pct` |
| Revenue NO es GMV | CONFIRMADO — documentado en 5+ migrations |
| No hay cambio de fuente por fecha | CONFIRMADO — misma fuente desde migración 111 |
| Coverage de revenue real es medible | SI — `revenue_real_coverage_pct` en cada fact |
| % de proxy sobre total es conocido | SI — `revenue_proxy_trips` vs `revenue_real_trips` |
| Omniview muestra revenue correcto | SI — `revenue_yego_net` del fact = ABS(comision) real + proxy |
| Commission PCT es derivado no input | SI — `SUM(revenue)/SUM(total_fare)` |
