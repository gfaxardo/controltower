# CF-H2 Revenue Reconciliation & Canonical Definition

## Fecha: 2026-05-29

---

## 1. Reconciliación

### Revenue por día
| Fuente | Columna | Certificación |
|--------|---------|---------------|
| `ops.real_business_slice_day_fact` | `revenue_yego_net` | **certified** — ABS(comision) real + proxy vía fact |
| `ops.real_business_slice_day_fact` | `revenue_yego_final` | **certified** — igual que net (vía enriched temp) |
| `ops.v_real_revenue_proxy_audit` | `revenue_yego_real` | **certified** — solo real, sin proxy |
| `ops.v_real_revenue_proxy_audit` | `revenue_yego_final` | **certified** — COALESCE(real, proxy) por viaje |

### Revenue por semana
| Fuente | Columna | Certificación |
|--------|---------|---------------|
| `ops.real_business_slice_week_fact` | `revenue_yego_net` | **certified** — agregado de daily |
| `serving.omniview_projection_daily_fact` (weekly) | `real_revenue` | **certified** — via `_REVENUE_SELECT` |

### Revenue por mes
| Fuente | Columna | Certificación |
|--------|---------|---------------|
| `ops.real_business_slice_month_fact` | `revenue_yego_net` | **certified** — agregado directo de enriched |
| `ops.mv_real_trips_monthly` | `revenue_yego_real` | **certified** — solo real, sin proxy |

---

## 2. Clasificación de fuentes

| Clasificación | Fuentes |
|---------------|---------|
| **certified** | `real_business_slice_*_fact` (todas), `v_real_revenue_proxy_audit`, `mv_real_trips_monthly` |
| **proxy** | `revenue_yego_proxy` en enriched temp (solo como componente de `revenue_yego_final`) |
| **partial** | Ninguna — el sistema siempre tiene real o proxy, nunca parcial |
| **unknown** | Tablas legacy pre-010 (no usadas por Control Tower) |
| **unsafe** | `mv_real_trips_monthly` pre-010 (GMV), plan `projected_revenue` pre-009 |

---

## 3. Definición Canónica de Revenue YEGO

### Revenue YEGO Oficial

```
Revenue YEGO = Comisión cobrada por YEGO al conductor por cada viaje completado.
```

### Fuente primaria
```
comision_empresa_asociada en public.trips_unified
```
Extraída, normalizada y agregada como:
```
revenue_yego_net = NULLIF(comision_empresa_asociada, 0)   — en enriched base
revenue_yego_real = ABS(revenue_yego_net)                 — en enriched temp
```

### Fallback permitido
```
Cuando comision_empresa_asociada ES NULL o = 0:
  revenue_yego_proxy = ticket * resolve_commission_pct(country, city, park, service, date)
  Default commission_pct = 3%
```

### Columna de consumo
```
En UI y API: revenue_yego_net (valor ya ABS + proxy via pipeline)
En proyección: COALESCE(revenue_yego_final, revenue_yego_net) con ABS
```

### Período de vigencia
```
Desde 2025-01-01 hasta presente.
Sin fecha de caducidad.
```

### Reglas de confianza

| Indicador | Significado | Umbral |
|-----------|-------------|--------|
| `revenue_real_coverage_pct` | % de revenue que viene de comision real | >90% = HIGH, 70-90% = MEDIUM, <70% = LOW |
| `revenue_source` | Por viaje: 'real' / 'proxy' / 'missing' | 'real' preferido |
| `commission_pct_applied` | Tasa usada en proxy (solo proxy trips) | Documentado para auditoría |

### Cómo mostrarlo en UI

- **Nombre**: "Revenue"
- **Formato**: Currency (sin decimales para valores grandes)
- **Delta**: Gap vs Expected (coloreado: green ≥0, amber <0 ≥-10%, danger <-10%)
- **Tooltip**: Mostrar attainment %, expected, gap absoluto
- **Badge de confianza**: Si coverage < 70%, mostrar "Revenue parcialmente estimado"

---

## 4. Revenue para Priority Layer

### ¿Revenue está certificado para RC-1 Priority Layer?

**SI**. Revenue tiene:
- Fuente primaria documentada (`comision_empresa_asociada`)
- Fallback documentado (proxy via commission config)
- Cobertura medible (`revenue_real_coverage_pct`)
- Sin cambios de fórmula por fecha
- Sin ambigüedad GMV vs Revenue

### Regla para Priority Layer
```
Impacto económico de revenue DEBE usar revenue_yego_net del fact (certified).
Si coverage < 70% para el scope, marcar como "revenue parcialmente estimado".
NUNCA usar GMV como revenue.
NUNCA usar trips * ticket como revenue.
```
