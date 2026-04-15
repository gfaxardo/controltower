# FASE 3.2 — Root Cause Engine: Scan y Especificación

## Objetivo

Motor de descomposición determinístico que explica automáticamente las desviaciones vs proyección en Omniview Matrix. Opera completamente en frontend, sin nuevos endpoints ni cambios de backend.

---

## Fuente de Datos

El motor consume lo que ya está disponible en `selection` cuando el usuario hace click en una celda de proyección:

| Campo | Origen | Contenido |
|-------|--------|-----------|
| `selection.raw` | Fila del endpoint `/omniview-projection` | Valores actuales de los 3 KPIs + metadatos de curva |
| `selection.periodDeltas` | `computeProjectionDeltas()` en frontend | Objeto por KPI con `value`, `projected_expected`, `projected_total`, gaps, signal, curva |

Los 3 KPIs proyectables disponibles siempre: `trips_completed`, `revenue_yego_net`, `active_drivers`.

---

## KPIs Soportados

### Primarios (con descomposición)

| KPI | Descomposición |
|-----|----------------|
| `trips_completed` | Drivers × Trips_per_Driver |
| `revenue_yego_net` | Trips × Avg_Ticket |
| `active_drivers` | Gap directo (sin sub-descomposición) |

### Derivados en Runtime

| KPI Derivado | Fórmula Actual | Fórmula Esperado |
|--------------|----------------|------------------|
| `avg_ticket` | `revenue_actual / trips_actual` | `revenue_expected / trips_expected` |
| `trips_per_driver` | `trips_actual / drivers_actual` | `trips_expected / drivers_expected` |

---

## Modelo de Descomposición

### 1. Revenue (multiplicativo, suma exacta)

```
gap_total = revenue_actual - revenue_expected

ticket_expected = revenue_expected / trips_expected   # ratio implícito del plan
ticket_actual   = revenue_actual / trips_actual       # ratio real

factor_trips  = (trips_actual - trips_expected) × ticket_expected   # efecto volumen
factor_ticket = trips_actual × (ticket_actual - ticket_expected)    # efecto precio/mix

VERIFICACIÓN: factor_trips + factor_ticket = gap_total  (exacto)
```

**Interpretación económica:**
- `factor_trips`: cuánto del gap de revenue se explica por haber tenido más/menos viajes de los esperados (al precio esperado)
- `factor_ticket`: cuánto del gap se explica por el ticket real distinto al esperado (sobre el volumen real)

### 2. Trips (multiplicativo, suma exacta)

```
gap_total = trips_actual - trips_expected

tpd_expected = trips_expected / drivers_expected   # productividad esperada
tpd_actual   = trips_actual / drivers_actual       # productividad real

factor_drivers      = (drivers_actual - drivers_expected) × tpd_expected   # efecto supply
factor_productivity = drivers_actual × (tpd_actual - tpd_expected)         # efecto eficiencia

VERIFICACIÓN: factor_drivers + factor_productivity = gap_total  (exacto)
```

**Interpretación:**
- `factor_drivers`: cuántos viajes se perdieron/ganaron por tener más/menos conductores (a la productividad esperada)
- `factor_productivity`: cuántos viajes se perdieron/ganaron porque cada conductor hizo más/menos viajes de los esperados

### 3. Active Drivers (directo)

```
gap_total = drivers_actual - drivers_expected

# No hay sub-descomposición (no tenemos churn/activación en los facts disponibles)
# Se muestra contexto adicional: trips_per_driver actual vs esperado como indicador de eficiencia
```

---

## Limitaciones

1. **Avg ticket esperado es inferido, no de plan directo:** El plan de proyección (Control Loop) solo tiene columnas para trips, revenue y drivers. El `avg_ticket_expected` se deriva dividiendo `revenue_expected / trips_expected`. Si el plan tiene un mix de precios muy diferente al real, esta aproximación puede no capturarlo con precisión.

2. **Drivers sin descomposición en churn/activación:** Para descomponer el gap de drivers en "nuevos conductores" vs "conductores perdidos (churn)" se necesitaría acceso a datos de cohorte de conductores, que no están en los facts de business slice actuales.

3. **División por cero:** Si `trips_expected = 0` o `drivers_expected = 0`, el motor devuelve `is_complete: false` y no intenta la descomposición. Se muestra el gap bruto sin factores.

4. **KPIs no proyectables:** `avg_ticket`, `commission_pct`, `cancel_rate_pct`, `trips_per_driver` no tienen proyección propia en el sistema. Cuando el usuario hace click en una celda con estos KPIs, el motor puede mostrar solo el gap bruto o un mensaje de no soportado.

5. **Multigrano:** El motor es agnóstico al grano (monthly/weekly/daily) porque opera sobre `projected_expected` que el backend ya ajusta según la curva estacional y el ratio del período. No requiere lógica adicional por grano.

6. **Residual numérico:** Por aritmética de punto flotante puede haber un residual de ~0.01% entre suma de factores y gap total. Se muestra explícitamente si supera 0.1% del gap.

---

## Salida del Motor

```javascript
{
  gap_total: -300,                  // revenue_actual - revenue_expected
  is_complete: true,                // false si no se puede descomponer
  kpi_key: 'revenue_yego_net',
  factors: [
    {
      key: 'trips',
      label: 'Volumen (trips)',
      impact: -180,                 // absoluto en la unidad del KPI
      pct: 60,                      // % del gap total (en valor absoluto)
      direction: 'negative',        // 'positive' | 'negative' | 'neutral'
    },
    {
      key: 'ticket',
      label: 'Ticket promedio',
      impact: -120,
      pct: 40,
      direction: 'negative',
    },
  ],
  main_driver: {
    key: 'trips',
    label: 'Volumen (trips)',
    impact: -180,
    pct: 60,
  },
  recommendation: 'Revisar demanda o asignación de volumen',
  meta: {
    ticket_actual: 8.5,
    ticket_expected: 9.2,
    tpd_actual: null,
    tpd_expected: null,
  }
}
```

---

## Integración

El motor vive en:
```
frontend/src/components/omniview/rootCauseEngine.js
```

Se integra en el drill panel existente (`OmniviewProjectionDrill.jsx`) como una sección adicional `RootCauseSection`, posicionada entre "Breakdown por KPI" y "Historial Plan vs Real".

No requiere cambios en:
- Backend
- `BusinessSliceOmniviewMatrix.jsx`
- `BusinessSliceOmniviewMatrixTable.jsx`
- `projection_expected_progress_service.py`

---

## Go/No-Go

| Check | Criterio |
|-------|----------|
| Suma exacta Revenue | `factor_trips + factor_ticket ≈ gap_revenue` (delta < 0.1%) |
| Suma exacta Trips | `factor_drivers + factor_productivity = gap_trips` (exacto) |
| Drivers funciona | Muestra gap directo + contexto |
| Multigrano | Funciona igual en monthly/weekly/daily |
| División por cero | `is_complete: false` cuando expected = 0 |
| Sin regresión | Modo evolución no afectado |
| Integración drill | Sección visible al hacer click en celda de proyección |
