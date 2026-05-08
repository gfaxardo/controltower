# Fase 1.5 — Performance hardening (Plan vs Real / Omniview / freshness)

**Alcance:** Control Foundation únicamente. Sin cambios de negocio, sin Suggestion/Decision/Action, sin lógica nueva en frontend.

---

## 1) Perfilado (ranking de cuellos de botella)

| Área | Hallazgo | Impacto |
|------|----------|---------|
| **`GET /ops/plan-vs-real/monthly`** | Filtro `TO_CHAR(period_date, 'YYYY-MM') = %s` sobre columnas de la vista **no sargable** → planner no puede usar bien índices / predicado sobre `period_date`. | Muy alto en meses con mucho volumen en la vista. |
| **`get_alerts_monthly`** | Mismo patrón `TO_CHAR` para `month`. | Alto en misma vista. |
| **Omniview** (`get_business_slice_omniview`) | Ya en **modo fact-first**: `ops.real_business_slice_month_fact` / week / day con `time_column = %s` + filtros; índices existentes (`ix_rbs_month_fact_month`, `ix_mv_bs_monthly_dims_compat` en migración 116). | Medio: 6 round-trips SQL por request (current/prev detail + rollups ×2 periodos); aceptable; optimización mayor = batch/fusion futura (fuera de alcance “sin tocar semántica”). |
| **`GET /ops/data-freshness/global`** | Lectura `ops.data_freshness_audit` + lógica Python; ya O(datasets). | Bajo (~0,6s medido). |
| **YTD / comparativos** | Rutas separadas (`real-lob/comparatives/*`, omniview-projection); no modificados en este cambio. | Según cada servicio; revisar tras medir en prod. |

---

## 2) Trazabilidad breve

| Endpoint | Servicio principal | Fuentes |
|----------|-------------------|---------|
| `/ops/plan-vs-real/monthly` | `plan_vs_real_service.get_plan_vs_real_monthly` | `ops.v_plan_vs_real_realkey_final` o `ops.v_plan_vs_real_realkey_canonical` |
| `/ops/plan-vs-real/alerts` | `get_alerts_monthly` | Mismas vistas |
| `/ops/business-slice/omniview` | `business_slice_omniview_service.get_business_slice_omniview` | `ops.real_business_slice_*_fact` (no resolved en serving) |
| `/ops/data-freshness/global` | `data_freshness_service.get_freshness_global_status` | `ops.data_freshness_audit` |

---

## 3) Estrategia de materialización

- **Plan vs Real:** sigue siendo lectura de **vista** ancha; esta fase **no** añade MV nuevas (cambio no aditivo / alto riesgo sin producto). El arreglo aplicado es **predicado sargable** para permitir mejor plan.
- **Omniview:** ya materializado a nivel **fact mensual/semanal/diario**.

---

## 4) Cambios aplicados (código)

**Archivo:** [`backend/app/services/plan_vs_real_service.py`](../backend/app/services/plan_vs_real_service.py)

- Nueva función **`_period_bounds_yyyy_mm`**: convierte `"YYYY-MM"` en `[ primer día, primer día mes siguiente )`.
- **`get_plan_vs_real_monthly`:** para `month` en forma `YYYY-MM`, filtro  
  `period_date >= %s::date AND period_date < %s::date`  
  en lugar de `TO_CHAR(period_date, 'YYYY-MM') = %s`.
- **Filtro `year`:** solo se aplica si **no** hay rango mensual YYYY-MM (evita redundancia; antes podía solaparse).
- **`get_alerts_monthly`:** mismo criterio sargable para `month`.

**Tests:** [`backend/tests/test_plan_vs_real_canonical.py`](../backend/tests/test_plan_vs_real_canonical.py) — `test_period_bounds_yyyy_mm`, `test_plan_vs_real_monthly_sargable_month_no_to_char`.

**Semántica:** mismo conjunto de filas para un mes civil dado; solo cambia la forma del predicado SQL.

---

## 5) Índices DB

**Ningún índice nuevo en esta fase.** Los facts Omniview ya tienen índices declarados en migraciones previas. Cualquier índice adicional sobre la **vista** Plan vs Real requeriría basetable identificada y `EXPLAIN (ANALYZE, BUFFERS)` en producción (recomendación futura).

---

## 6) Frontend

**Sin cambios obligatorios.** `PlanVsRealView` ya hace una sola llamada a `getPlanVsRealMonthly`; no hay N+1 identificado.

---

## 7) Mediciones (entorno de desarrollo / mismo host que smoke previo)

Ejecución local (Latencia red + PostgreSQL remoto según `.env`):

| Endpoint | Tiempo aproximado | Nota |
|----------|-------------------|------|
| `plan-vs-real/monthly?country=co&month=2026-04` | ~65–70 s (llamada directa Python post-cambio) | La vista sigue siendo el coste dominante; el filtro sargable es **condición necesaria** para que el motor pueda acotar por fecha; medir de nuevo en prod tras **reinicio de uvicorn** si el cliente HTTP devolvió 500 con código antiguo o timeout intermedio. |
| Omniview monthly | ~3,9 s | Bajo target 5 s |
| Omniview weekly | ~3,3 s | Bajo target 5 s |
| `data-freshness/global` | ~0,6 s | Bajo target 2 s |

**Before (referencia conversación previa):** Plan vs Real ~69 s con el mismo patrón de llamada; tras el cambio el orden de magnitud en esta BD sigue alto por coste intrínseco de la vista — **comparación before/after estricta** requiere `EXPLAIN ANALYZE` o medición con y sin parche en la misma sesión y mismo plan cache.

---

## 8) Regresión

- Tests unitarios nuevos pasan.
- Smoke manual: Omniview y freshness OK; si `plan-vs-real` devuelve 500, **reiniciar el proceso uvicorn** para cargar el servicio actualizado y revisar logs.

---

## 9) Riesgos remanentes

1. **Vista Plan vs Real** sin materialización puede seguir superando targets si el optimizador no empuja el predicado hasta tablas base.
2. **Auditoría comercial `trips_2026`** (incidente previo) no es performance; no cubierta aquí.
3. **Seis consultas** en Omniview mensual: mejora futura posible con consolidación solo si se demuestra misma respuesta byte-a-byte.

---

## 10) GO / NO-GO Fase 1.5

| Criterio | Estado |
|----------|--------|
| Mejora material / fundación para planner (sargable) | **GO** |
| Sin cambio de semántica Plan vs Real | **GO** |
| Omniview sin cambios | **GO** |
| Freshness sin cambios | **GO** |
| Sin deuda peligrosa (no cache opaca, no DROP CASCADE) | **GO** |
| Targets numéricos estrictos en Plan vs Real | **PARCIAL** — vista aún pesada; siguiente paso = `EXPLAIN ANALYZE` en prod u opción MV/tabular de soporte **con producto** |

**Veredicto:** **GO** para cerrar **Fase 1.5** en el sentido *stability / predicados / tests*; trabajo **pendiente** para cumplir &lt;8 s P95 en Plan vs Real si la vista no baja solo con predicado.

---

## 11) Recomendaciones siguientes (fuera de este PR)

- `EXPLAIN (ANALYZE, BUFFERS)` sobre la query mensual filtrada por `period_date` + `country`.
- Valorar **tabla/MV de soporte** solo-lectura alineada al contrato realkey (decisión de arquitectura).
- Re-medir `plan-vs-real/monthly` tras despliegue y reinicio de API.
