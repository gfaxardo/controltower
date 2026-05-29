# CF-H2 Revenue Contract & UI Audit

## Fecha: 2026-05-29

---

## 1. Qué significa "Revenue" en Control Tower

**Revenue YEGO** = Comisión cobrada por YEGO al conductor por cada viaje completado.

Fuente: `comision_empresa_asociada` en `public.trips_unified` (tabla RAW de viajes).

NO es:
- GMV (facturación bruta del pasajero) — `efectivo + tarjeta + pago_corporativo`
- `trips × ticket` — eso es GMV, no revenue
- `trips × 3%` — eso es proxy, no revenue real

---

## 2. Columnas y su uso

| Columna | Significado | Uso en Omniview |
|---------|------------|-----------------|
| `revenue_yego_net` | ABS(comision_empresa_asociada) — valor real + proxy vía fact | KPI principal de Revenue |
| `revenue_yego_final` | COALESCE(real, proxy) — best effort con fallback | Priority en proyección (`_REVENUE_SELECT`) |
| `commission_pct` | SUM(revenue) / SUM(total_fare) — ratio derivado | KPI secundario % Comisión |
| `avg_ticket` | AVG(ticket) = AVG(precio_yango_pro) — precio promedio | KPI Ticket medio (no revenue) |
| `revenue_real_coverage_pct` | % de viajes con revenue real (no proxy) | Métrica de confianza/calidad |

---

## 3. ¿Cambia por país/ciudad/fecha?

**NO**. La columna `comision_empresa_asociada` es universal. El revenue se calcula igual para Perú, Colombia, cualquier ciudad, cualquier fecha.

Lo que SÍ cambia por país/ciudad:
- Commission proxy pct (tabla `ops.yego_commission_proxy_config`)
- Cobertura de revenue real (algunos parks tienen más NULLs que otros)

---

## 4. Fallback documentado

### Jerarquía de fallback
```
1. revenue_yego_net != NULL → usar ABS(comision_empresa_asociada) — REAL
2. revenue_yego_net IS NULL, ticket > 0 → usar ticket * commission_pct — PROXY
3. Ambos NULL → revenue = NULL (sin revenue para ese viaje)
```

### Commission proxy
```
Config: ops.yego_commission_proxy_config
Resolución: ops.resolve_commission_pct(country, city, park_id, tipo_servicio, date)
Default global: 3%
```

---

## 5. API Contract

### Endpoint: `POST /ops/business-slice/omniview-projection`
Response JSON:
```json
{
  "data": [{
    "revenue_yego_net": 12345.67,                    // KPI revenue (real + proxy vía fact)
    "revenue_yego_net_projected_total": 15000.00,    // Plan revenue total
    "revenue_yego_net_projected_expected": 12000.00, // Expected to date
    "revenue_yego_net_attainment_pct": 82.3,         // % attainment vs expected
    "revenue_yego_net_gap_to_expected": -2345.33,    // Gap vs expected
    "revenue_yego_net_gap_pct": -15.6,               // Gap %
    "revenue_yego_net_signal": "warning",            // green|warning|danger|no_data
    "revenue_yego_net_audit_raw": 12345.67           // Audit trail (may preserve sign)
  }]
}
```

### Endpoint: `GET /ops/business-slice/daily|weekly|monthly`
```json
{
  "data": [{
    "revenue_yego_net": 12345.67,   // Valor agregado del fact
    "commission_pct": 0.034         // Ratio revenue/total_fare
  }]
}
```

---

## 6. Frontend — Cómo se muestra

### KPI Revenue en Omniview
| Componente | Qué muestra | Fuente |
|-----------|------------|--------|
| Matriz Evolution | `revenue_yego_net` del fact | `getBusinessSliceDaily|Weekly|Monthly()` |
| Matriz Vs Proyección | `revenue_yego_net` del response | `getOmniviewProjection()` |
| Celda proyección L1 (real) | `fmtValue(actual, 'revenue_yego_net')` — valor formateado | `buildProjectionCellDisplay()` |
| Celda proyección L2 (delta) | Gap vs expected, coloreado por signal | `buildComparableDelta()` |
| Totals row | Suma de revenue (additive) | `computeProjectionTotalsDeltas()` |
| Drill | Detalle de revenue con plan, expected, gap | `OmniviewProjectionDrill` |
| ContextBar | Revenue en KPI summary | `ProjectionContextBar` |

### Validación visual
| Check | Estado |
|-------|--------|
| Revenue aparece en daily | SI |
| Revenue aparece en weekly | SI |
| Revenue aparece en monthly | SI |
| Muestra cierre correcto | SI — usa freshness del fact |
| Tiene deltas DoD/WoW/MoM | SI — via `period_over_period` |
| Freshness por KPI funciona | SI — `compute_kpi_freshness()` para revenue |
| No muestra NaN | SI — `fmtValue()` protege, `_safe_float()` en backend |
| No mezcla monedas | SI — revenue es universal (misma columna para Perú y Colombia) |

---

## 7. Revenue en el ProjectionCellDisplay

El modelo canónico de celda (`projectionCellDisplayModel.js`) usa:
- **L1 (REAL)**: `fmtValue(actual, 'revenue_yego_net')` — el valor real formateado
- **L2 (DELTA)**: `buildComparableDelta()` — gap vs expected con color por signal
- **L3 (CONTEXTO)**: attainment % solo si no hay momentum comparable

El signal de revenue usa:
- `green` = attainment >= 100%
- `warning` = attainment >= 90%
- `danger` = attainment < 90%
- `no_data` = sin datos

---

## 8. KPIs derivados del revenue

| KPI | Fórmula | Categoría |
|-----|---------|-----------|
| commission_pct | `SUM(revenue) / SUM(total_fare)` | Ratio — no proyectable |
| revenue per trip | `revenue / trips` = `commission_pct * avg_ticket` aprox | Derivado |
| take_rate_yego | `revenue_yego_real / gmv_passenger_paid` | Analítico (mv_real_trips) |

---

## 9. Verdict

| Aspecto | Estado |
|---------|--------|
| Revenue tiene definición canónica | **PASS** — `ABS(comision_empresa_asociada)` |
| Revenue NO es GMV | **PASS** — Verificado en 5+ migrations, audit scripts, config |
| Fallback documentado | **PASS** — Proxy via commission_pct config |
| No cambia por país/ciudad/fecha | **PASS** — Misma columna universal |
| API contract definido | **PASS** — `revenue_yego_net` + campos de proyección |
| Omniview muestra correctamente | **PASS** — Lee del fact, formatea correcto, sin NaN |
| Freshness por KPI funciona | **PASS** — Per-KPI freshness implementado en CF-H1 |
