# FASE_VALIDATION_FIX — KPI Validation Fix & Decision Readiness

**Fecha:** 2026-04-20  
**Proyecto:** YEGO Control Tower  
**Fase:** Cierre operacional de confiabilidad para decisión ejecutiva

---

## 1. Problema conceptual original

### 1.1 Falsos FAIL por semanas ISO

El validador anterior (`validate_kpi_grain_consistency.py` v1) comparaba:

```
monthly_value  vs  SUM(weekly_fact semanas ISO que tocan el mes)
```

Esto generaba **falsos FAIL** porque:
- Una semana ISO (lun–dom) puede cruzar el límite de dos meses calendarios.
- La suma de semanas ISO completas (`weekly_sum_full_iso`) incluye días del mes anterior o siguiente.
- Para meses que empiezan en miércoles o terminan en viernes (caso frecuente), la diferencia puede ser de 3–7 días de actividad "extra" en la suma semanal.
- Resultado: `SUM(weekly_ISO) > monthly_calendario` sin que exista ningún bug de datos.

**Evidencia antes del fix (v1, ejemplo real):**

| kpi             | month   | monthly | weekly_sum_full_iso | status |
|-----------------|---------|---------|---------------------|--------|
| trips_completed | 2026-04 | 18,450  | 19,120              | FAIL   |
| revenue_yego_net| 2026-04 | 145,200 | 151,800             | FAIL   |

La diferencia era exactamente los viajes del 30 y 31 de marzo (días de semanas que caían en el rango ISO pero fuera del mes de abril).

### 1.2 Decision Readiness incompleta

Aunque el contrato KPI ya existía (`kpi_aggregation_rules.py`), faltaban:
1. Campos explícitos de decision readiness por dimensión de uso.
2. Blindaje en el alerting engine para que KPIs `scope_only` no disparen alertas aditivas cross-grain.
3. UI que explique al usuario cuándo puede y cuándo no puede comparar granos.

---

## 2. Por qué `weekly_sum_full_iso` genera falsos FAIL

### Diagrama conceptual

```
Mes de abril 2026 (calendario):    01-abr ─────────────── 30-abr
Semana ISO semana 14:  Lun 30-mar ─── Dom 05-abr   ← incluye 30 y 31 mar
Semana ISO semana 18:  Lun 27-abr ─── Dom 03-may   ← incluye 01 y 02 may

SUM(weekly_full_iso de sem 14..18) 
= trips_del_30_mar + trips_del_31_mar + trips_del_01_abr .. + trips_del_30_abr + trips_del_01_may + trips_del_02_may

SUM > monthly_calendario_abril ← por definición, no es bug
```

### Regla canónica correcta (v2)

```
OBLIGATORIO: monthly_value ≈ SUM(day_fact) WHERE trip_date IN [01-abr, 30-abr]
             (tolerancia: ≤1% relativo O ≤1 unidad absoluta)

COMPLEMENTARIO: monthly_value ≈ SUM(week_fact * fracción_días_en_mes)
                (weekly_sum_intersect — genera warning si diverge >2%, no fail)

INFORMATIVO: SUM(week_fact ISO completas) → campo weekly_sum_full_iso
             Solo se reporta; NUNCA es criterio de FAIL.
```

---

## 3. Fix implementado

### 3.1 `validate_kpi_grain_consistency.py` v2

**Cambios principales:**
- Se eliminó `_eval_additive` que comparaba contra `weekly_sum_full_iso`.
- Se creó `_load_week_facts_intersection()`: carga cada semana individualmente y pondera sus valores por la fracción de días dentro del mes (`fraction = días_en_mes / 7`).
- Nueva `_eval_additive(monthly, daily_sum_in_month, weekly_sum_full_iso, weekly_sum_intersect)`:
  - FAIL solo si `|monthly - daily_sum_in_month|` supera tolerancias.
  - WARNING si `weekly_sum_intersect` diverge >2% (tolerancia doble).
  - `weekly_sum_full_iso` siempre presente en el CSV como campo informativo.
- El CSV output incluye ahora 4 campos separados: `daily_sum_in_month`, `weekly_sum_full_iso`, `weekly_sum_intersect`, `validation_basis`.

### 3.2 Evidencia QA — Before vs After

| Mes     | Antes (v1) FAIL | Después (v2) FAIL | Warnings v2 |
|---------|-----------------|-------------------|-------------|
| Apr 2026| 37 FAIL         | **0 FAIL**        | 7 warnings  |
| Feb 2026| N/A (nuevo test)| **0 FAIL**        | 3 warnings  |
| Dec 2025| N/A (nuevo test)| **0 FAIL**        | 5 warnings  |

Los warnings restantes se deben a semanas con muy pocas días dentro del mes (< 3 días) donde la interpolación es aproximada — **esperado y no accionable**.

---

## 4. Contrato KPI — Decision Readiness

### 4.1 Tabla de KPIs por status

| KPI               | Tipo             | Cross-grain  | Drift Alerts | Priority Scoring | Status           |
|-------------------|------------------|:------------:|:------------:|:----------------:|------------------|
| `trips_completed` | additive         | ✅           | ✅           | ✅               | **decision_ready** |
| `revenue_yego_net`| additive         | ✅           | ✅           | ✅               | **decision_ready** |
| `trips_cancelled` | additive         | ✅           | ✅           | ❌               | decision_ready (componente) |
| `active_drivers`  | semi_additive_distinct | ❌     | ✅ (scope)   | ✅ (scope)       | **scope_only** |
| `avg_ticket`      | non_additive_ratio | ✅ (fórmula) | ❌           | ❌               | **formula_only** |
| `commission_pct`  | non_additive_ratio | ✅ (fórmula) | ❌           | ❌               | **formula_only** |
| `cancel_rate_pct` | non_additive_ratio | ✅ (fórmula) | ❌           | ❌               | **formula_only** |
| `trips_per_driver`| derived_ratio    | ❌           | ❌           | ❌               | **restricted** |

### 4.2 Reglas de uso por tipo

**`decision_ready` (trips_completed, revenue_yego_net):**
- Comparar vs plan mensual: `monthly_real vs plan_mensual` ✅
- Comparar daily acumulado vs plan: `SUM(daily_in_month) vs expected_to_date` ✅
- Gatillar alertas `gap_abs`, `gap_pct`, `underperformance` ✅
- **NO** usar `SUM(weekly_ISO_full)` — puede incluir días de otro mes ❌

**`scope_only` (active_drivers):**
- Comparar vs plan del mismo scope: `monthly_real vs plan_mensual_drivers` ✅
- Gatillar alertas de brecha vs plan del mismo scope ✅
- **NO** comparar suma de semanales contra mensual ❌
- **NO** sumar semanas o días entre sí ❌
- Interpretar: "¿cuántos drivers únicos del mes vs los esperados para el mes?"

**`formula_only` (avg_ticket, commission_pct, cancel_rate_pct):**
- Comparar el ratio recomputado del periodo vs plan del mismo periodo ✅
- Detectar tendencias por scope ✅
- **NO** gatillar alertas de gap aditivo entre granos ❌
- **NO** promediar ratios entre periodos ❌

**`restricted` (trips_per_driver):**
- Usar solo como métrica informativa de productividad ✅
- **NO** en ningún cálculo cross-grain ❌
- **NO** en alertas aditivas ❌
- **NO** en priority scoring ❌

---

## 5. Correcciones en alerts / priority / drift

### 5.1 Backend (`projection_expected_progress_service.py`)

El backend ya tenía `ADDITIVE_PROJECTABLE_KPIS` que excluía `active_drivers` de las verificaciones de conservación (rollup). **Sin cambios requeridos** — era correcto.

### 5.2 Frontend — `alertingEngine.js`

**Cambios implementados:**
1. Añadida constante `NON_ADDITIVE_KPIS_EXCLUDED_FROM_ALERTS` (documentación explícita de por qué ciertos KPIs no entran en el alerting).
2. Añadida constante `SCOPE_ONLY_ATTENUATOR = { active_drivers: 0.80 }`:
   - El `gap_component` de `active_drivers` se atenúa 20% para que un gap de igual magnitud relativa no produzca el mismo score que un KPI aditivo puro.
   - Motivo: un gap de distinct count no tiene la misma urgencia que un gap de viajes aditivos.
3. El score breakdown ahora incluye `scope_attenuator` para trazabilidad.
4. Si `kpiKey` está en `NON_ADDITIVE_KPIS_EXCLUDED_FROM_ALERTS`, el score devuelve 0 con nota explicativa.
5. `buildAlertPayload` añade `trust_note` específica para `active_drivers`:
   > "Drivers únicos (scope_only): brecha vs plan del mismo scope. No comparar contra suma de semanas o días — son distintos scopes."

### 5.3 Frontend — `projectionMatrixUtils.js`

**Cambios:**
1. `KPI_CONTRACT_FALLBACK` ampliado con 5 nuevos campos por KPI: `allowed_for_cross_grain_decision`, `allowed_for_drift_alerts`, `allowed_for_priority_scoring`, `decision_status`, `decision_note`.
2. Nuevos helpers exportados:
   - `getKpiDecisionStatus()`: devuelve `decision_ready | scope_only | formula_only | restricted`.
   - `getKpiDecisionNote()`: devuelve la nota de uso correcto.
   - `getKpiDecisionBadge()`: devuelve badge con color semántico.
   - `isKpiAllowedForDriftAlerts()`: guardrail para lógica de alertas.

### 5.4 Frontend — `OmniviewProjectionDrill.jsx`

La sección `KpiContractSection` ahora muestra:
- Badge de **tipo de KPI** (Aditivo, Distinct, Ratio, Derivado) — ya existía.
- Badge de **Decision Readiness** (Decision Ready, Scope Only, Formula Only, Restricted) — nuevo.
- Fila "Alertas aditivas: No aplica — leer por scope" para KPIs con `allowed_for_drift_alerts = false`.
- Nota de decision readiness en bloque italic con borde lateral para destacarla visualmente.

---

## 6. Nuevos endpoints operativos

### `GET /ops/decision-readiness`

Devuelve el contrato de decision readiness por KPI derivado directamente del `kpi_aggregation_rules.py`. Sin parámetros de filtro — es estático.

```json
{
  "summary": {
    "decision_ready": ["trips_completed", "revenue_yego_net"],
    "scope_only": ["active_drivers"],
    "formula_only": ["commission_pct", "avg_ticket", "cancel_rate_pct"],
    "restricted": ["trips_per_driver"]
  },
  "rows": [...]
}
```

Soporta `?format=csv` para exportar.

### `GET /ops/kpi-consistency-audit` (actualizado a v2)

Ahora usa el validador v2. Incluye campos `daily_sum_in_month`, `weekly_sum_full_iso`, `weekly_sum_intersect`, `validation_basis` en el output.

---

## 7. Evidencia QA

### Archivos generados en `docs/evidence/fase_kpi_rollup/`

| Archivo | Descripción |
|---------|-------------|
| `kpi_consistency_v2_apr2026.csv` | Validación v2 abril 2026: 0 FAIL, 7 warnings |
| `kpi_consistency_v2_feb2026.csv` | Validación v2 febrero 2026: 0 FAIL, 3 warnings |
| `kpi_consistency_v2_dec2025.csv` | Validación v2 diciembre 2025: 0 FAIL, 5 warnings |
| `decision_readiness.csv`         | Report de decision readiness por KPI |
| `endpoint_decision_readiness.json`| Respuesta JSON del endpoint |
| `endpoint_decision_readiness.csv` | CSV del endpoint |
| `endpoint_kpi_consistency_v2_apr2026.csv` | CSV del endpoint de auditoría v2 |

### Verificación de active_drivers (caso prueba Feb 2026)

```
kpi: active_drivers
month: 2026-02
status: expected_non_comparable
note: Distinct count: monthly NO equivale a SUM(weekly|daily); rango vs daily_max verificado.
validation_basis: daily_in_month+max_scope
```

`active_drivers` queda formalmente `expected_non_comparable` — NO genera FAIL. ✅

### Verificación de trips_per_driver

```
kpi: trips_per_driver
status: expected_non_comparable
note: Derivado de drivers únicos: validado por fórmula scope-by-scope, no por suma.
validation_basis: formula_internal
```

`trips_per_driver` nunca genera alertas aditivas. ✅

---

## 8. Riesgos remanentes

### 8.1 Riesgo BAJO — Warnings de intersección semanal

Los 3–7 warnings por mes se deben a semanas con muy pocos días dentro del mes (ejemplo: semana que solo aporta 1–2 días). La ponderación (1/7 o 2/7) genera un `weekly_sum_intersect` pequeño que puede divergir del mensual si hay patrones de demanda muy distintos al inicio/fin del mes.

**Acción recomendada:** ninguna en el corto plazo. Son metodológicamente esperados.

### 8.2 Riesgo MEDIO — `active_drivers` en weekly/daily grain

Cuando el usuario visualiza Omniview en grain `weekly` o `daily`, el KPI `active_drivers` proyectado sigue siendo `scope_only`. La UI ya muestra la nota, pero el usuario podría intentar sumar visualmente los valores semanales.

**Acción recomendada:** en el futuro, desactivar el modo de comparación aditiva en la UI para `active_drivers` en grain weekly/daily.

### 8.3 Riesgo BAJO — `trips_per_driver` en UI

El KPI `trips_per_driver` está en `OMNIVIEW_MATRIX_VISIBLE_KPIS` pero no en `PROJECTION_KPIS`. Aparece en la matriz pero sin proyección ni alertas. El badge "Restricted" en el drill lo comunica, pero podría confundir si el usuario intenta compararlo entre granos.

**Acción recomendada:** considerar removerlo de la vista principal o añadir una nota permanente en la celda (no solo en el drill).

### 8.4 Riesgo BAJO — Revalidación mensual requerida

El validador v2 debe ejecutarse mensualmente (o post-refresh de `month_fact`) para confirmar que no aparecen nuevos FAILs. Idealmente integrar a un job automático.

**Acción recomendada:** añadir al scheduler de `run_business_slice_real_refresh_job` una llamada al validador al final del proceso.

---

## 9. Veredicto final

```
╔══════════════════════════════════════════════════════════════╗
║         YEGO CONTROL TOWER — DECISION READINESS              ║
║                                                              ║
║  VEREDICTO GLOBAL: ✅ DECISION READY (con restricciones)    ║
║                                                              ║
║  KPIs aditivos (trips, revenue):                             ║
║    → DECISION READY sin restricciones                       ║
║    → Validación v2 confirma 0 falsos FAIL                   ║
║                                                              ║
║  active_drivers:                                             ║
║    → SCOPE_ONLY — solo comparar mismo scope                 ║
║    → Alertas de brecha permitidas vs plan del mismo scope   ║
║    → Atenuador 0.80 en priority_score aplicado              ║
║                                                              ║
║  Ratios (avg_ticket, commission, cancel_rate):               ║
║    → FORMULA_ONLY — comparar por fórmula recomputada        ║
║    → Sin alertas aditivas cross-grain                        ║
║                                                              ║
║  trips_per_driver:                                           ║
║    → RESTRICTED — solo lectura informativa                  ║
║                                                              ║
║  Falsos FAIL eliminados: 37 → 0 (Apr 2026)                  ║
║  Alertas falsas de active_drivers: mitigadas con 0.80×     ║
║  UI: badges de decision readiness visibles en drill         ║
╚══════════════════════════════════════════════════════════════╝
```
