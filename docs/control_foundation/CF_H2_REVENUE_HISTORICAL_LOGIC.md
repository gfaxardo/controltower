# CF-H2 Revenue Historical Logic

## Fecha: 2026-05-29

---

## Timeline de revenue

| Período | Fórmula | Significado | Confianza |
|---------|---------|-------------|-----------|
| Pre-010 (histórico) | `SUM(precio_yango_pro)` | GMV, no revenue real | **UNSAFE** — no es revenue |
| 010-119 (transición) | `ABS(comision_empresa_asociada)` | Revenue real, sin proxy | **HIGH** — pero viajes sin comision = NULL |
| 120+ (actual) | `COALESCE(ABS(comision), ticket * commission_pct)` | Revenue real + proxy fallback | **CERTIFIED** — mejor disponible |

---

## Migraciones clave

| # | Nombre | Cambio |
|---|--------|--------|
| 003 | plan_trips_monthly | Introduce `projected_revenue = trips * ticket` (GMV bug) |
| 008 | consolidate_real_monthly | `revenue_real_proxy = SUM(precio_yango_pro)` (GMV) |
| 009 | fix_revenue_plan_input | Corrige plan: `projected_revenue` deja de ser GMV |
| 010 | fix_real_revenue_gmv_take_rate | Corrige real: `revenue_yego_real = ABS(comision_empresa_asociada)` |
| 111 | business_slice_phase1 | `revenue_yego_net = NULLIF(comision_empresa_asociada, 0)` — estable desde aquí |
| 118 | enriched_base_trips_2025_2026 | Cambio de fuente: trips_2025/2026 (misma fórmula) |
| 120 | revenue_proxy_config_and_layer | Introduce proxy layer: `revenue_yego_final = COALESCE(real, proxy)` |
| 121 | consolidate_hourly_first | Propaga proxy a pipeline v2 |
| 122 | revenue_hardening_nan_guard | NaN guards (sin cambio de fórmula) |
| 126 | business_slice_trips_unified_trust | Unifica a `trips_unified` (misma fórmula) |

---

## ¿Cambia la fórmula por fecha?

**NO**. Desde migración 111, la fórmula de `revenue_yego_net` es:
```sql
NULLIF(c.comision_empresa_asociada, 0)::numeric
```

Lo que SÍ cambia es:
- **Tabla fuente**: `trips_2025` vs `trips_2026` vs `trips_unified` (partición por año)
- **Cobertura real vs proxy**: Depende de si `comision_empresa_asociada` tiene datos en el source

---

## Campos que alimentan el proxy

| Campo | Fuente | Uso |
|-------|--------|-----|
| `ticket` | `precio_yango_pro` en trips_unified | Base para proxy revenue |
| `commission_pct` | `ops.yego_commission_proxy_config` vía `ops.resolve_commission_pct()` | Multiplicador del proxy |
| Default commission | 3% (hardcoded en `COALESCE(..., 0.03)`) | Fallback si no hay config |

---

## Confianza por período

| Período | Revenue | Confianza | Proxy % esperado |
|---------|---------|-----------|-----------------|
| 2021-2024 | GMV o NULL | UNSAFE | N/A (no se usa en Control Tower) |
| 2025 actual | Revenue real + proxy | HIGH | Depende de cobertura de comision_empresa_asociada |
| 2026 actual | Revenue real + proxy | HIGH | Misma fórmula |

---

## ¿Hay "enriquecimiento parcial"?

El término "enriquecimiento parcial" no existe en el código. El sistema usa:

1. **Enriched base** (`ops.v_real_trips_enriched_base`): JOINs con dim_park y drivers
2. **Revenue_real**: Cuando `comision_empresa_asociada` existe (NO NULL, NO 0)
3. **Revenue_proxy**: Cuando NO existe comision → estimado con `ticket * commission_pct`

El `revenue_real_coverage_pct` mide qué % viene de real vs proxy. No hay estados intermedios.

---

## Conclusión

Revenue tiene una definición clara y estable:
- **Desde 111+**: `comision_empresa_asociada` (commission YEGO)
- **Desde 120+**: Con fallback proxy documentado
- **Sin cambios de fórmula por fecha** (solo cambios de tabla fuente)
- **GMV está explícitamente separado** desde 010

No hay ambigüedad histórica para el período actual cubierto por Control Tower (2025-2026).
