# CF-H2 Revenue Audit Report — Final

## Fecha: 2026-05-29
## Motor: Control Foundation H2 — Revenue Definition & Source Audit

---

## 1. Estado: **GO**

Revenue YEGO está **certificado** para Control Tower y apto para RC-1 Priority Layer.

- Fuente primaria documentada
- Fallback documentado
- GMV explícitamente separado
- Sin cambios de fórmula por fecha (solo cambio de tabla fuente)
- Omniview muestra revenue correctamente
- Freshness por KPI funciona

---

## 2. Fuente Real Encontrada

| Elemento | Valor |
|----------|-------|
| **Columna RAW** | `comision_empresa_asociada` en `public.trips_unified` |
| **Definición** | Comisión cobrada por YEGO al conductor por viaje completado |
| **Fórmula en enriched** | `NULLIF(comision_empresa_asociada, 0)` — elimina ceros |
| **Fórmula en fact** | `SUM(ABS(comision))` — agregado a business slice |
| **Columna en API** | `revenue_yego_net` — el valor agregado del fact |

---

## 3. Fuente Proxy

| Elemento | Valor |
|----------|-------|
| **Cuándo se usa** | Cuando `comision_empresa_asociada` es NULL o 0 |
| **Fórmula** | `ticket * resolve_commission_pct(country, city, park, service, date)` |
| **Config** | `ops.yego_commission_proxy_config` |
| **Default** | 3% |
| **Columna resultante** | `revenue_yego_final = COALESCE(real, proxy)` |

---

## 4. Lógica Histórica por Fecha

| Período | Revenue | Estado |
|---------|---------|--------|
| Pre-010 | GMV (`precio_yango_pro`) | UNSAFE — no usado por Control Tower |
| 010-119 | Commission real sin proxy | OK — legacy |
| 120+ (actual) | Commission real + proxy fallback | **CERTIFIED** |
| Fórmula actual | Estable desde migración 111 | Sin cambios |

No hay _date-based formula switching_. La misma fórmula aplica para 2025 y 2026. Solo cambia la tabla fuente (`trips_2025` vs `trips_2026`) unificadas en `trips_unified`.

---

## 5. Qué Muestra Omniview

| Vista | Grain | Fuente | Columna | Certificación |
|-------|-------|--------|---------|---------------|
| Evolution Daily | Daily | `real_business_slice_day_fact` | `revenue_yego_net` | certified |
| Evolution Weekly | Weekly | `real_business_slice_week_fact` | `revenue_yego_net` | certified |
| Evolution Monthly | Monthly | `real_business_slice_month_fact` | `revenue_yego_net` | certified |
| Vs Proyección Daily | Daily | Fact + `_REVENUE_SELECT` | `real_revenue` | certified |
| Vs Proyección Weekly | Weekly | Fact + `_REVENUE_SELECT` | `real_revenue` | certified |
| Vs Proyección Monthly | Monthly | Fact + `_REVENUE_SELECT` | `real_revenue` | certified |

**Revenue NO es**:
- GMV (`gmv_passenger_paid`)
- `trips * ticket` (GMV bug, corregido en 009)
- `trips * 3%` (proxy simple, sin config)

---

## 6. Riesgos

| Riesgo | Severidad | Mitigación |
|--------|-----------|------------|
| Proxy coverage < 70% en ciertos parks | MEDIUM | `revenue_real_coverage_pct` visible en facts. Marcar en UI si < 70%. |
| Commission config desactualizada | LOW | Tabla `yego_commission_proxy_config`. Actualizable sin deploy. |
| GMV confundido con revenue en nuevos módulos | MEDIUM | Audit scripts de validación. Tests de revenue < GMV. |
| `comision_empresa_asociada` = 0 tratado como NULL | LOW | `NULLIF(col, 0)` es intencional — 0 es "sin datos" para propósito de proxy. |

---

## 7. Fixes Aplicados

**Ninguno requerido**. Revenue está correcto. No hay bugs encontrados en:
- Fórmula de revenue
- Pipeline de datos
- API contract
- Visualización en Omniview

---

## 8. Revenue para RC-1 Priority Layer

| Pregunta | Respuesta |
|----------|-----------|
| ¿Revenue está certificado? | **SI** — fuente, fórmula y pipeline auditados |
| ¿Es apto para Priority Layer? | **SI** — con condición: verificar coverage < 70% marca como estimado |
| ¿Hay riesgo de revenue inventado? | **NO** — `comision_empresa_asociada` es la fuente real |
| ¿Hay riesgo de confusión GMV/revenue? | **NO** — separación forzada desde migración 010 |
| ¿Freshness por KPI funciona? | **SI** — implementado en CF-H1 |

---

## 9. Documentos Generados

| Doc | Contenido |
|-----|-----------|
| `CF_H2_REVENUE_SOURCE_AUDIT.md` | Columnas, pipeline, fallbacks, Omniview |
| `CF_H2_REVENUE_CONTRACT_AUDIT.md` | Data contract, API, frontend display |
| `CF_H2_REVENUE_HISTORICAL_LOGIC.md` | Timeline de migraciones, cambios de fórmula |
| `CF_H2_REVENUE_CANONICAL_DEFINITION.md` | Definición oficial, reconciliación, clasificación |
| `CF_H2_REVENUE_AUDIT_REPORT.md` | Este reporte |

---

## 10. Build & QA

| Check | Estado |
|-------|--------|
| Backend syntax | PASS (múltiples archivos verificados en CF-H1) |
| Frontend build | PASS (11.52s, verificado en CF-H1) |
| Revenue en Omniview daily | PASS |
| Revenue en Omniview weekly | PASS |
| Revenue en Omniview monthly | PASS |
| Sin falso cierre | PASS (per-KPI freshness) |
| Sin moneda mezclada | PASS (misma columna para Perú y Colombia) |
| Sin revenue inventado | PASS (fuente real certificada) |
