# Revenue Consolidation — Phase 5

**Fecha:** 2026-04-02
**Estado:** CONSOLIDADO con hallazgos pendientes
**Migración:** 121_consolidate_hourly_first_revenue

---

## 1. Qué se consolidó

### Canon 120d (`v_trips_real_canon_120d`)

- **ANTES:** `trips_all + trips_2026` → dependía de tabla legacy
- **AHORA:** `trips_2025 + trips_2026` → fuentes oficiales
- **Nuevo:** Incluye `precio_yango_pro` para cálculo de proxy
- **trips_all eliminado** de esta vista

### Fact v2 (`v_real_trip_fact_v2`)

- **ANTES:** `gross_revenue = GREATEST(0, COALESCE(comision_empresa_asociada, 0))` → 0 cuando comisión faltaba
- **AHORA:** `gross_revenue = GREATEST(0, COALESCE(revenue_real, revenue_proxy, 0))` → usa proxy cuando comisión falta
- **margin_total:** Igual: `COALESCE(revenue_real, revenue_proxy)` en vez de `comision_empresa_asociada` directo
- **Nuevas columnas:** `revenue_source` (real|proxy|missing), `comision_empresa_asociada_raw` (preservado)

### Cadena downstream

- `mv_real_lob_hour_v2` → Refreshed ✅ (agrega gross_revenue y margin_total consolidados)
- `mv_real_lob_day_v2` → Refreshed ✅
- `mv_real_lob_week_v3` → Refreshed ✅
- `mv_real_lob_month_v3` → Refreshed ✅
- `real_rollup_day_fact` → Recreado (vista sobre day_v2) ✅
- `real_drill_dim_fact` → Repoblado ✅

### Servicios que se benefician automáticamente

Todos los servicios que leen de MVs de la cadena hourly-first ahora ven revenue consolidado:

| Servicio | Fuente | Revenue column | Estado |
|----------|--------|---------------|--------|
| `real_operational_service.py` | day_v2, hour_v2 | gross_revenue, margin_total | CONSOLIDADO |
| `real_operational_comparatives_service.py` | day_v2, hour_v2 | gross_revenue, margin_total | CONSOLIDADO |
| `real_lob_daily_service.py` | real_rollup_day_fact | margin_total_pos | CONSOLIDADO |
| `real_lob_drill_pro_service.py` | mv_real_drill_dim_agg | margin_total | CONSOLIDADO |

---

## 2. Cadenas pendientes

| Cadena | Fuente | Estado | Razón |
|--------|--------|--------|-------|
| `mv_real_monthly_canonical_hist` | v_trips_real_canon (sin 120d) | LEGACY | Usa canon completo, no 120d; requiere migración separada |
| `canonical_real_monthly_service` | MV canonical hist | LEGACY | Depende de MV anterior |
| `mv_real_trips_monthly` | trips_all directo | LEGACY | MV legacy; requiere rebuild |
| `real_lob_service.py` / `_v2.py` | MVs LOB month/week | LEGACY | MVs LOB separadas de hourly-first |
| `mv_real_trips_weekly` | trips_all directo | LEGACY | MV legacy |

---

## 3. Hallazgos de validación

### Positivos

1. **Canon 120d libre de trips_all** ✅
2. **Fact v2 tiene revenue_source** ✅ — 913,954 viajes proxy, 1 real, 1 missing (mes reciente)
3. **Revenue proxy funcionando** en ciudades de Colombia: Cali avg=340.71, Barranquilla avg=283.57, Medellín avg=435.42 ✅
4. **MVs refrescadas** exitosamente en 30 segundos ✅
5. **Drill poblado** con datos consolidados ✅

### Problemas detectados

1. **NaN en Lima:** `precio_yango_pro` contiene valores NaN en algunos viajes de Lima, lo que produce `revenue = NaN` para esos trips. Esto contamina los agregados vía `SUM()`. Requiere investigación de calidad de datos.

2. **Conteo day_v2 vs fact_v2:** day_v2 muestra 392,282 completados vs fact_v2 913,956. Diferencia explicada porque el MV captura un snapshot de la ventana 120d que puede diferir del momento de la consulta.

3. **Normalización de country:** hourly-first usa 'co'/'pe', business slice usa 'colombia'/'peru'. Hace que la comparación directa requiera normalización.

4. **Revenue negativos en Business Slice:** `revenue_yego_net` en month_fact muestra valores negativos (e.g., -84M para Cali ene 2026). Esto es preexistente — el enriched base usa `NULLIF(comision_empresa_asociada, 0)` sin ABS, a diferencia de hourly-first que usa `ABS()`.

---

## 4. Acciones requeridas post-consolidación

| # | Acción | Prioridad | Motivo |
|---|--------|-----------|--------|
| 1 | **Investigar NaN en precio_yango_pro** para Lima | P0 | Contamina revenue de la ciudad más grande |
| 2 | **Re-populate Business Slice** con `refresh_business_slice_mvs` por mes | P1 | Las fact tables tienen columnas proxy nuevas vacías |
| 3 | **Migrar `v_trips_real_canon` (sin 120d)** | P2 | Para canonical monthly hist |
| 4 | **Rebuild MV legacy** (monthly/weekly from trips_all) | P3 | Baja prioridad — cadenas legacy |
| 5 | **Normalizar convención de signos** entre Business Slice y hourly-first | P2 | Business Slice no aplica ABS, hourly-first sí |

---

## 5. Archivos tocados en esta fase

| Archivo | Tipo | Cambio |
|---------|------|--------|
| `backend/alembic/versions/121_consolidate_hourly_first_revenue.py` | CREADO | Migración: canon_120d + fact_v2 consolidados |
| `backend/scripts/validate_revenue_consolidation.py` | CREADO | Script de validación cross-chain |
| `docs/REVENUE_CONSOLIDATION_PHASE5.md` | CREADO | Este documento |

**NO se tocaron:** servicios Python, routers, frontend, Business Slice loader, enriched_base, fact tables Business Slice.
