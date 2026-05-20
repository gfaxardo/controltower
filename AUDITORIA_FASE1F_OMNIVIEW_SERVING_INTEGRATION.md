# Fase 1F — Omniview Serving Integration

**Fecha**: 2026-05-19
**Estado**: **GO** — All validation passed

---

## 1. Cambio implementado

**Un solo cambio**: redirigir `FACT_MONTHLY` en `business_slice_service.py` de la tabla raw a la serving view.

```python
# Antes
FACT_MONTHLY = "ops.real_business_slice_month_fact"

# Después (Fase 1F)
FACT_MONTHLY = "ops.v_real_business_slice_month_serving"
FACT_MONTHLY_RAW = "ops.real_business_slice_month_fact"  # backup
```

Esto hace que **todos los consumidores de Omniview monthly** automáticamente sirvan snapshots para periodos locked y working facts para periodos open. La ruta de escritura/refresh (`business_slice_incremental_load.py`) sigue usando la tabla raw.

---

## 2. Consumidores afectados

| Consumidor | Ahora lee de |
|------------|-------------|
| `business_slice_service.get_business_slice_monthly()` | serving view |
| `business_slice_omniview_service.get_business_slice_omniview()` | serving view |
| `business_slice_real_freshness_service` (FACT_MONTHLY) | serving view |
| `control_loop_plan_vs_real_service` (referencias directas) | raw fact (pendiente) |
| `business_slice_incremental_load.py` (escritura) | raw fact (sin cambio) |

---

## 3. Validación

| Prueba | Resultado |
|--------|-----------|
| FACT_MONTHLY redirect | PASS |
| April serving=snapshot, status=locked_snapshot | PASS |
| May serving=working_fact, status=open | PASS |
| April total 829,118 = raw | PASS |
| May total 472,468 = raw | PASS |
| Bogotá Carga=2801, Delivery=188 | PASS |
| Barranquilla Taxi Moto=12483, Auto=9764, Delivery=1406 | PASS |
| Refresh path unchanged | PASS |
| Omniview service importable | PASS |

---

## 4. Fallback / Last Good

- Si un refresh de un periodo locked falla, la serving view sigue sirviendo el snapshot (porque el snapshot no se modifica).
- Si no hay snapshot, la serving view sirve working_fact con `data_status=locked_no_snapshot`.
- No hay [] silencioso.

---

## 5. Rollback

```python
# Revertir a fact table original:
# En business_slice_service.py, cambiar FACT_MONTHLY de vuelta:
FACT_MONTHLY = "ops.real_business_slice_month_fact"
# La serving view seguirá existiendo pero no será usada.
```

---

## 6. Riesgos pendientes

| Riesgo | Estado |
|--------|--------|
| day/week sin serving views | Fase futura |
| refresh scoped por ciudad | Fase futura |
| resolved view >120s | Índices nocturnos |
| CT_PERIOD_CLOSURE_DRY_RUN=true | Activar en prod |
| control_loop_plan_vs_real_service lee raw | Pendiente, bajo impacto |

---

## 7. Siguiente fase

**Fase 1G — Final Control Foundation Regression / Production Readiness**
