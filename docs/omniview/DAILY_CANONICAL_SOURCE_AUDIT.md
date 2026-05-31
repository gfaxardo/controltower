# DAILY CANONICAL SOURCE AUDIT

**Fecha**: 2026-05-31
**Motor**: Control Foundation
**Gate**: CF-H1E

---

## 1. Resolución de la Contradicción

### Reporte A: FACT_DAILY = 2026-05-29 ✅

Este reporte provino de:
- `check_omniview_serving_freshness.py` (health guard)
- La consulta directa `SELECT MAX(trip_date)` ejecutada después del backfill manual

**Estado**: Correcto. El backfill fue exitoso y la data está presente.

### Reporte B: FACT_DAILY = 2026-04-30

Este reporte provino de:
- La prueba inicial de `get_omniview_freshness_governance()` ejecutada ANTES de que el backfill se aplicara
- En ese momento, FACT_DAILY realmente estaba en April 30

**Estado**: Correcto para ese momento. Representa el estado real previo al backfill.

### Conclusión

**No hay contradicción real.** Ambos reportes son correctos en sus respectivos momentos. El gap temporal entre el backfill y el governance test causó la discrepancia.

---

## 2. Fuente Canónica Daily de Omniview

### **Respuesta única**: `ops.real_business_slice_day_fact`

Esta es la ÚNICA fuente canónica de datos diarios reales para Omniview.

Todas las demás tablas daily derivan de esta o sirven propósitos diferentes:
- `serving.omniview_projection_daily_fact` — caché precomputada (plan + real), no fuente canónica
- `ops.real_rollup_day_fact` — rollup legacy, no usado por Omniview projection

---

## 3. Inventario de Tablas Daily

| Tabla | Max Date | Total | May Rows | Propósito | Consumida por |
|-------|----------|-------|----------|-----------|---------------|
| `ops.real_business_slice_day_fact` | **2026-05-29** | 8,576 | 602 | **CANONICAL** — fuente única de datos reales diarios | `projection_expected_progress_service`, `compute_matrix_data_freshness`, `compute_kpi_freshness`, governance service |
| `serving.omniview_projection_daily_fact` | 2026-05-31 | 868 | 868 | Caché precomputada de proyección (plan + real). Poblada desde la fuente canónica. | `get_omniview_projection()` (cuando usa path `SERVED_FROM_FACT`) |
| `ops.real_rollup_day_fact` | N/A | N/A | N/A | Legacy rollup. No usado por Omniview projection. | Ninguno en la pipeline Omniview |
| `ops.driver_daily_activity_fact` | N/A | N/A | N/A | Driver lifecycle. No relacionado con Omniview. | Driver Lifecycle View |
| `ops.mv_real_rollup_day` | N/A | N/A | N/A | Materialized view de rollup. Pipeline separado. | Real LOB views |

---

## 4. Pipeline Daily — Trazado Completo

```
public.trips_2026 (RAW)
    │
    ▼
ops.v_real_trips_enriched_base (VIEW)
    │ UNION + JOIN dim_park + JOIN drivers
    │
    ▼
LOADER: business_slice_incremental_load.py
    │ DELETE + INSERT per month
    │
    ▼
ops.real_business_slice_day_fact  ◄── FUENTE CANÓNICA
    │
    ├──► compute_matrix_data_freshness()        → banner "Data al X"
    ├──► compute_kpi_freshness()                → per-KPI freshness
    ├──► _load_real_daily()                     → real data for projection
    │
    ▼
projection_expected_progress_service.py
    │ merge plan + real
    │
    ├──► GET /ops/business-slice/omniview-projection (runtime)
    │
    ▼
serving.omniview_projection_daily_fact (CACHÉ)
    │ precomputed: plan + real
    │
    ▼
GET /ops/business-slice/omniview-projection (served_from_fact)
    │
    ▼
Frontend: buildProjectionMatrix() → displayProjMatrix → UI
```

---

## 5. Auditar Governance Service

### ¿Está leyendo la fuente correcta?

**SÍ.** `omniview_freshness_governance_service.py` consulta:

```python
cur.execute(f"SELECT MAX(trip_date) FROM {FACT_DAILY}")
```

Donde `FACT_DAILY = "ops.real_business_slice_day_fact"` (definida en `business_slice_service.py:50`).

Esta es la misma tabla que usa el resto del pipeline. **No está leyendo una fact obsoleta.**

### Estado actual del Governance

| Capa | Max Date | Lag | Status |
|------|----------|-----|--------|
| RAW | 2026-05-29 | 2 | — |
| FACT_DAILY | 2026-05-29 | 2 | WARNING |
| FACT_WEEKLY | 2026-03-23 | 69 | BLOCKED |
| FACT_MONTHLY | 2026-05-01 | — | OK |
| PROJECTION | 2026-05-31 | 0 | OK |

**El status BLOCKED global es correcto**: causado por FACT_WEEKLY que sigue en March 23 (no se aplicó el backfill de semanas a través del pool de conexiones estándar).

---

## 6. Corrección Aplicada

**No se requirió corrección al Governance service.** Lee la fuente correcta.

**No se requirió corrección a Omniview.** La fuente canónica es correcta.

**Se requiere**: Backfill de FACT_WEEKLY para April y May (el backfill anterior no persistió).

---

## 7. Estados Anteriores (Línea de Tiempo)

| Timestamp | FACT_DAILY | Causa |
|-----------|------------|-------|
| Pre-backfill (2026-05-30 ~23:00) | 2026-04-30 | Backend detenido desde finales de abril. APScheduler no corrió. |
| Post-backfill (2026-05-30 ~23:58) | 2026-05-29 | Backfill manual ejecutado (quick_backfill_may2026.py). Datos persistidos correctamente. |
| Actual (2026-05-31 ~00:30) | 2026-05-29 | Datos intactos. 602 filas para Mayo. |

---

## 8. Veredicto

```
FUENTE CANÓNICA DAILY: ops.real_business_slice_day_fact ✓
GOVERNANCE LEE FUENTE CORRECTA: Sí ✓
CONTRADICCIÓN RESUELTA: No hay contradicción, ambos reportes correctos en su momento ✓
CORRECCIÓN REQUERIDA: Ninguna al código ✓
PENDIENTE: Backfill FACT_WEEKLY para April/May ⚠
```

**GO** — Auditoría completada. Fuente canónica identificada. Governance validado.

