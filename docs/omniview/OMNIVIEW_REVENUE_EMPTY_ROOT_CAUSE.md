# OMNI-P0 — REVENUE EMPTY GRID ROOT CAUSE

**Motor:** Omniview Governance — P0 Recovery
**Fecha:** 2026-06-04
**Estado:** ROOT CAUSE IDENTIFICADA — PENDIENTE FIX DE DATOS

---

## 1. PREGUNTAS Y RESPUESTAS

### 1.1 ¿Revenue tiene datos en serving?

**Respuesta: Depende del grain.**

| Grain | ¿Datos en serving? | ¿Qué campo? |
|-------|-------------------|-------------|
| Daily | **NO** — 0% cobertura | `revenue_yego_net` NULL, `revenue_yego_final` NULL (day_fact data loss) |
| Weekly | **NO** — 0% cobertura | `revenue_yego_net` NULL, `revenue_yego_final` NULL (week_fact data loss) |
| Monthly | **PARCIAL** — 50% | `revenue_yego_net` NULL en meses sin commission real; `revenue_yego_final` existe en `month_fact` pero no siempre en serving view |

**Evidencia**: `UI_SERVING_RECONCILIATION_AUDIT.md` línea 92-109. Datos confirmados con `day_fact` (645 filas, 817K trips en Mayo agregado) pero day_fact solo tiene Jun 1-2 post data loss.

### 1.2 ¿Revenue tiene plan?

**Respuesta: Depende de si el usuario cargó un plan.**

Vs Proy carga plan desde `/ops/business-slice/omniview-projection` con `planVersion`. Si el usuario no ha cargado un plan para el periodo/grain/métrica, la celda muestra "Sin plan".

Esto es **expected behavior**, no un bug.

### 1.3 ¿Revenue tiene proyección?

**Respuesta: Depende de si hay proyección activa.**

La proyección en Vs Proy se construye a partir del plan + datos reales. Si no hay plan, no hay attainment. Si no hay real, no hay comparación.

### 1.4 ¿La UI usa `revenue_yego_final`?

**Respuesta: Sí, con COALESCE en ambos lados.**

| Capa | Ubicación | Lógica |
|------|-----------|--------|
| Backend | `business_slice_omniview_service.py:656` | `COALESCE(revenue_yego_final, revenue_yego_net)` en fact queries |
| Backend | `business_slice_omniview_service.py:718` | `COALESCE(revenue_yego_final, revenue_yego_net, 0)` en rollups |
| Frontend | `omniviewMatrixUtils.js:615-617` | `revenue_yego_final ?? revenue_yego_net` en `enrichRow()` |

### 1.5 ¿Hay COALESCE correcto?

**Respuesta: Sí, el COALESCE es correcto. El problema no es de código, es de datos.**

El COALESCE funciona correctamente cuando los datos existen. El problema es que:
- En day_fact/week_fact, **ambos campos son NULL** porque los datos se perdieron.
- En monthly, `revenue_yego_final` existe en `month_fact` pero no siempre en la serving view que lee el frontend.

### 1.6 ¿Por qué algunas celdas aparecen vacías?

**Respuesta: Tres causas independientes:**

1. **Data loss en day_fact/week_fact (P0)**: Los datos de Mayo 2026 en day_fact y S18-S22 en week_fact desaparecieron. Sin datos en las fact tables, el COALESCE no tiene nada que coalescer. Resultado: NULL → `—` en UI.

2. **`revenue_yego_net` NULL en monthly histórico (P1)**: En meses donde no hubo `comision_empresa_asociada` (commission real), `revenue_yego_net` es NULL. El backend intenta `COALESCE(revenue_yego_final, revenue_yego_net)` (L656) y también hace LEFT JOIN con `month_fact` (L799-809), pero si `month_fact` no tiene la fila correspondiente, `revenue_yego_final` también es NULL.

3. **Sin plan cargado (expected)**: Si el usuario no cargó plan para el periodo, Vs Proy muestra "Sin plan" o `—`.

### 1.7 ¿Es expected empty o bug?

| Caso | Clasificación |
|------|---------------|
| Revenue vacío en daily (data loss) | **BUG P0** — datos deberían existir |
| Revenue vacío en weekly (data loss) | **BUG P0** — datos deberían existir |
| Revenue vacío en monthly sin commission | **BUG P1** — `_final` debería estar disponible |
| Revenue vacío en periodo futuro sin plan | **Expected empty** — sin datos ni plan |
| Revenue vacío en periodo con plan pero sin real | **Expected empty** — sin dato real todavía |

---

## 2. CADENA CAUSAL COMPLETA

```
Raw DB: comision_empresa_asociada
    ↓
Enriched Base: revenue_yego_net = NULLIF(comision_empresa_asociada, 0)
    ↓ (si es NULL → se calcula proxy)
Enriched Base: revenue_yego_proxy = ticket * commission_pct
    ↓
Enriched Base: revenue_yego_final = COALESCE(revenue_yego_real, revenue_yego_proxy)
    ↓
Fact Tables: day_fact, week_fact, month_fact
    ↓
    ├─ day_fact: DATA LOSS → revenue_yego_net=NULL, revenue_yego_final=NULL
    ├─ week_fact: DATA LOSS → revenue_yego_net=NULL, revenue_yego_final=NULL
    └─ month_fact: revenue_yego_final existe (79.2% filas) pero no siempre en serving
    ↓
Serving Layer: COALESCE(revenue_yego_final, revenue_yego_net) → NULL si ambos NULL
    ↓
API Response: completed_revenue_sum = NULL
    ↓
Frontend: enrichRow() → canonicalRev = NULL → muestra "—"
```

---

## 3. FLUJO DE CORRECCIÓN

### Paso 1: Restaurar datos (P0)

Ejecutar refresh de day_fact y week_fact para recuperar datos de Mayo-Junio 2026.

```
→ day_fact debe tener datos Mayo 26 - Junio 4
→ week_fact debe tener datos S18 - S23
→ Verificar que revenue_yego_final tiene valores >0 en day_fact y week_fact
```

### Paso 2: Verificar serving (P1)

Después del refresh, verificar que el endpoint `/ops/business-slice/daily` y `/ops/business-slice/weekly` retornan `completed_revenue_sum > 0`.

### Paso 3: Verificar UI (P1)

Abrir Vs Proy en daily/weekly con métrica Revenue. Verificar que las celdas muestran valores numéricos, no `—`.

### Paso 4: Monthly revenue (P1)

Verificar que `ops.real_business_slice_month_fact` tiene `revenue_yego_final` para todos los meses, y que el LEFT JOIN en `business_slice_omniview_service.py:799` está funcionando.

---

## 4. CONCLUSIÓN

**Root cause primaria**: Data loss en day_fact y week_fact (CF-H1L.1 recurrente). No es un bug de código. El COALESCE es correcto. Los datos simplemente no están en las fact tables.

**Root cause secundaria**: `revenue_yego_final` en monthly serving view no se expone consistentemente (gap de 50%).

**No es un problema de**: selección de campo, lógica de COALESCE, renderizado frontend, o formato de número.

---

**END OF REVENUE ROOT CAUSE**
