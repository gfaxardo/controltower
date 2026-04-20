# FASE 3.5 — Semántica Canónica de Omniview Matrix

**Fecha:** 2026-04-16  
**Alcance:** Todo Omniview Matrix — todos los KPIs, todos los arcos temporales (diario, semanal, mensual)

---

## 1. Problema Raíz

La versión anterior de Omniview Matrix mezclaba distintas semánticas para el mismo concepto:

| Problema                              | Impacto operativo                                                        |
|---------------------------------------|--------------------------------------------------------------------------|
| `attainment_pct` podía ser negativo   | Revenue negativo en algunas ciudades generaba "-823%" como "avance"      |
| Sin campo `comparison_basis` explícito | Usuarios no sabían si el % comparaba vs full period o vs expected-to-date |
| Sin `gap_pct` canónico                | Solo existía `gap_to_expected` (absoluto); el % de diferencia no estaba disponible |
| Fórmulas distintas en totals vs celdas | La fila TOTAL usaba avance no-canónico (permitía negativos)              |

---

## 2. Definiciones Canónicas

### 2.1 Avance %

```
avance_pct = actual / expected_base × 100
```

**Regla crítica:** `avance_pct` **NUNCA es negativo**.  
- Si `actual < 0` (ej: revenue negativo) → `avance_pct = None`  
- Si `expected_base ≤ 0` → `avance_pct = None`

### 2.2 Gap Absoluto

```
gap_abs = actual − expected_base
```

Puede ser negativo (indica déficit frente a lo esperado).

### 2.3 Gap %

```
gap_pct = (actual − expected_base) / expected_base × 100
```

**Sí puede ser negativo.** Representa qué tan por encima o por debajo del expected está la ejecución real.

> **Distinción clave:** Si ves `avance_pct = —` pero `gap_pct = -183%`, significa que el valor real es negativo (ej: devoluciones o ajustes contables). El `gap_pct` te da la señal real del problema.

### 2.4 Base Esperada (`expected_base`)

La base que se usa para calcular avance y gap depende del arco temporal:

| Grain    | Período cerrado             | Período en curso                    |
|----------|-----------------------------|--------------------------------------|
| Monthly  | `plan_full_month`           | `expected_to_date_month` (curva estacional × plan) |
| Weekly   | `plan_full_week`            | `expected_to_date_week` (curva × plan) |
| Daily    | `plan_day` (siempre full_day) | N/A                                 |

---

## 3. `comparison_basis` — Campo Explícito

Cada celda del backend ahora expone `{kpi}_comparison_basis` indicando qué base se usó:

| Valor                    | Significado                                               |
|--------------------------|-----------------------------------------------------------|
| `full_month`             | Período mensual cerrado; se usa el plan total del mes     |
| `expected_to_date_month` | Mes en curso; se usa la fracción esperada según curva estacional |
| `full_week`              | Semana cerrada; se usa el plan total de la semana         |
| `expected_to_date_week`  | Semana en curso; se usa la fracción esperada              |
| `full_day`               | Granularidad diaria; el plan del día es la base           |
| `unknown`                | Fila sin plan (missing_plan); no hay base calculable      |

---

## 4. Campos por Celda (API Response)

Cada fila de la respuesta de `/ops/business-slice/omniview-projection` ahora incluye por cada KPI proyectable (`trips_completed`, `revenue_yego_net`, `active_drivers`):

| Campo                         | Tipo        | Descripción                                                |
|-------------------------------|-------------|------------------------------------------------------------|
| `{kpi}`                       | float\|null | Valor real acumulado al corte                              |
| `{kpi}_projected_total`       | float\|null | Plan total del período completo                           |
| `{kpi}_projected_expected`    | float\|null | Expected al corte (curva estacional × plan)               |
| `{kpi}_attainment_pct`        | float\|null | **Avance % — NUNCA negativo** (null si actual < 0)        |
| `{kpi}_gap_to_expected`       | float\|null | Gap absoluto (puede ser negativo)                         |
| `{kpi}_gap_pct`               | float\|null | **NUEVO** Gap % (puede ser negativo)                      |
| `{kpi}_gap_to_full`           | float\|null | Diferencia vs plan total del período                      |
| `{kpi}_completion_pct`        | float\|null | % de ejecución vs plan total (sin ajuste de curva)        |
| `{kpi}_signal`                | string      | `green` / `warning` / `danger` / `no_data`                |
| `{kpi}_comparison_basis`      | string      | **NUEVO** Base de comparación canónica                    |
| `{kpi}_curve_method`          | string\|null | Método de curva estacional usado                          |
| `{kpi}_curve_confidence`      | string\|null | Confianza en la curva                                     |
| `{kpi}_fallback_level`        | int\|null   | Nivel de fallback usado                                   |
| `{kpi}_expected_ratio`        | float\|null | Ratio al corte (0.0–1.0)                                  |

---

## 5. Casos Especiales

| Situación                              | `avance_pct` | `gap_pct`  | `comparison_status` |
|----------------------------------------|--------------|------------|---------------------|
| Ambos actual y plan presentes          | ≥ 0 %        | cualquiera | `comparable`        |
| actual negativo (revenue con ajuste)   | `null`       | < 0 %      | `comparable`        |
| expected_base = 0 o null              | `null`       | `null`     | `not_comparable`    |
| actual = null, plan > 0               | `null`       | `null`     | `no_execution_yet`  |
| actual existe, plan = null             | `null`       | `null`     | `missing_plan`      |
| Sin datos de ningún tipo              | `null`       | `null`     | `no_data`           |

---

## 6. Módulo Canónico Backend

**Archivo:** `backend/app/services/omniview_semantics_service.py`

Funciones expuestas:

```python
resolve_comparison_basis(is_full_period: bool, grain: str) -> str
```
Determina el `comparison_basis` según si el período ya cerró y el tipo de granularidad.

```python
compute_canonical_metrics(
    actual: Optional[float],
    expected_base: Optional[float],
    plan_full: Optional[float],
    comparison_basis: str,
) -> Dict[str, Any]
```
Retorna `{ avance_pct, gap_abs, gap_pct, comparison_status }` siguiendo las reglas canónicas.

```python
resolve_signal(avance_pct: Optional[float], actual: Optional[float]) -> str
```
Semáforo basado en avance %, con fallback a `danger` si actual < 0.

---

## 7. Cambios en el Frontend

### 7.1 `projectionMatrixUtils.js`
- **`buildProjectionMatrix`**: Lee los nuevos campos `{kpi}_gap_pct` y `{kpi}_comparison_basis` del raw response.
- **Totals**: Usa fórmula canónica (avance no puede ser negativo; si actual < 0 → `danger`).
- **`computeProjectionDeltas`**: Pasa `gap_pct` y `comparison_basis` al delta de cada celda.
- **`computeProjectionTotalsDeltas`**: Pasa `gap_pct` al delta de la fila Total.
- **`buildProjectionCellTooltip`**: Muestra `Base: <comparison_basis>`, `Avance %`, `Gap %` y nota si actual es negativo.
- **Nuevas utilidades**: `describeBasis()`, `fmtGapPct()`, `COMPARISON_BASIS_LABELS`.

### 7.2 `BusinessSliceOmniviewMatrixCell.jsx`
- **Avance % nunca negativo**: Si `actual < 0`, la celda muestra `—` en Avance y en su lugar muestra el `gap_pct` (con label contextual en el tooltip).
- **Revenue negativo**: Se muestra en rojo con señal `danger` y badge de alerta.
- **Gap % como fallback**: Cuando `avance_pct = null` por valor negativo, se muestra `gap_pct` en la fila 3 con estilo apropiado.

---

## 8. Archivos Modificados

| Archivo | Tipo de cambio |
|---------|---------------|
| `backend/app/services/omniview_semantics_service.py` | **Nuevo** — módulo canónico |
| `backend/app/services/projection_expected_progress_service.py` | Integración de semántica canónica en builders monthly/weekly/daily |
| `frontend/src/components/omniview/projectionMatrixUtils.js` | Campos canónicos, tooltip, totals, helpers |
| `frontend/src/components/BusinessSliceOmniviewMatrixCell.jsx` | Renderizado canónico, manejo de actual negativo |

---

## 9. QA — Validaciones

### 9.1 Avance % nunca negativo

| Caso | Resultado esperado |
|------|--------------------|
| Lima trips: actual=18K, expected=20K | avance_pct = 90.0% (warning) |
| Bogotá revenue: actual=-5237, expected=80K | avance_pct = null, gap_pct = -106.5%, signal = danger |
| Cali trips: actual=0, plan=5K | avance_pct = 0.0%, signal = danger |

### 9.2 comparison_basis

| Mes | Estado | comparison_basis esperado |
|-----|--------|--------------------------|
| Enero 2026 | Cerrado | `full_month` |
| Abril 2026 | En curso (día 16) | `expected_to_date_month` |
| Semana Mar 30 - Abr 5 | Cerrada | `full_week` |
| Semana Abr 14-20 | En curso | `expected_to_date_week` |
| Cualquier día diario | — | `full_day` |

### 9.3 Fila TOTAL

La fila TOTAL usa exactamente la misma semántica canónica:
- avance_pct = suma_actual / suma_expected_base × 100 (solo si suma_actual ≥ 0)
- Si el total sumado es negativo → avance = null, signal = danger

### 9.4 Tooltip

El tooltip de cada celda ahora muestra explícitamente:
- `Base: Plan mes completo (período cerrado)` o equivalente
- `Avance %:` el valor (nunca negativo)
- `Gap %:` el valor (puede ser negativo)
- Nota si el valor real es negativo

---

## 10. Restricciones y Principios

- ✅ NO cambia el storage — ningún dato de BD fue modificado
- ✅ Completamente aditivo — los nuevos campos son adicionales al contrato existente
- ✅ Compatible con modelo REAL-FIRST de FASE 3.4
- ✅ Mantiene sanitización JSON global (sin NaN/Infinity)
- ✅ La semántica es única para todos los KPIs y arcos temporales
- ✅ No inventa expected donde no existe base confiable

---

## 11. Veredicto

**GO** — La semántica canónica está implementada y es consistente en backend y frontend.  

La distinción explícita entre **Avance %** (siempre ≥ 0) y **Gap %** (puede ser negativo) elimina la ambigüedad operativa y permite interpretación correcta de todos los escenarios incluyendo valores de revenue negativos.
