# OMNI-P0-T3 — VS PROY CANONICAL GRID CONTRACT

**Motor:** Omniview P0 Recovery  
**Fecha:** 2026-06-03  
**Estado:** CONTRATO DEFINIDO — PENDIENTE IMPLEMENTACIÓN

---

## 1. PRINCIPIO RECTOR

**Toda celda de Vs Proy debe obedecer el mismo contrato, independientemente de la métrica o grain.**

No se permite que Trips coloree de una forma y Revenue de otra. No se permite que DoD aparezca en daily pero no en weekly. No se permite que una celda muestre -30% sin indicar si es CLOSED o PARTIAL.

---

## 2. CONTRATO DE CELDA CANÓNICO

Cada celda en la grilla de Vs Proy debe exponer:

```json
{
  "real_value": 12345,
  "real_value_formatted": "12,345",
  "plan_value": 13000,
  "plan_value_formatted": "13,000",
  "projection_value": 12350,
  "projection_value_formatted": "12,350",
  "delta_abs": -655,
  "delta_abs_formatted": "-655",
  "delta_pct": -5.04,
  "delta_pct_formatted": "-5.0%",
  "comparison_label": "vs plan mensual",
  "period_status": "PARTIAL",
  "period_status_label": "Parcial (S23 · 3/7 días)",
  "freshness_status": "ok",
  "freshness_detail": "datos hasta 2026-06-03",
  "trust_status": "high",
  "trust_score": 92,
  "display_value": "12,345",
  "display_badge": "~",
  "color_rule": "amber",
  "color_reason": "attainment < 95%",
  "tooltip_reason": "5.0% bajo el plan mensual. 3 de 7 días transcurridos. Proyección: 12,350 esperado.",
  "do_delta": null,
  "wo_delta": { "abs": -120, "pct": -1.0 },
  "mo_delta": null
}
```

### 2.1 Campos requeridos (MANDATORY)

| Campo | Tipo | Obligatorio | Descripción |
|-------|------|-------------|-------------|
| `real_value` | number\|null | Sí | Valor real ejecutado (null si no hay dato) |
| `plan_value` | number\|null | Sí | Valor del plan para ese período |
| `projection_value` | number\|null | Condicional | Valor proyectado/esperado (si aplica) |
| `delta_abs` | number\|null | Condicional | Diferencia absoluta (si hay real y plan) |
| `delta_pct` | number\|null | Condicional | Diferencia porcentual (si hay real y plan) |
| `period_status` | enum | **Sí** | CLOSED \| PARTIAL \| CURRENT \| FUTURE \| NO_PLAN \| NO_REAL |
| `freshness_status` | enum | **Sí** | ok \| stale \| critical \| unknown |
| `trust_status` | enum | **Sí** | high \| medium \| low \| blocked |
| `display_value` | string | **Sí** | Valor formateado para mostrar en celda |
| `color_rule` | enum | **Sí** | green \| amber \| red \| neutral \| empty |
| `tooltip_reason` | string | **Sí** | Explicación legible para el usuario |

### 2.2 Campos opcionales (NICE TO HAVE)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `do_delta` | {abs, pct}\|null | Delta día-contra-día (daily only) |
| `wo_delta` | {abs, pct}\|null | Delta semana-contra-semana |
| `mo_delta` | {abs, pct}\|null | Delta mes-contra-mes |
| `display_badge` | string\|null | Badge visual: "~", "✓", "⚠", "✗" |
| `comparison_label` | string | Etiqueta legible: "vs plan mensual", "vs proyección" |
| `freshness_detail` | string | Detalle de freshness: "datos hasta YYYY-MM-DD" |
| `trust_score` | number\|null | Score de confianza 0-100 |

---

## 3. PERIOD STATUS — ENUM Y REGLAS DE COLOR

| Status | Significado | Color | Cuándo aplica |
|--------|-------------|-------|---------------|
| `CLOSED` | Período cerrado, dato definitivo | Sin badge | Período pasado con datos completos |
| `PARTIAL` | Período en curso, dato incompleto | Amber ~ | Período actual con datos parciales |
| `CURRENT` | Período actual (hoy/esta semana/este mes) | Blue ring | Highlight de presente |
| `FUTURE` | Período futuro, sin datos reales | Gray — | Sin ejecución todavía |
| `NO_PLAN` | Sin plan cargado para este período | Gray "Sin plan" | Plan missing |
| `NO_REAL` | Sin datos reales (pero debería haber) | Red "Sin dato" | Dato esperado pero ausente |

**Regla**: Toda celda con `delta_pct != null` DEBE mostrar `period_status`. Un -30% sin contexto de CLOSED/PARTIAL es inaceptable.

---

## 4. COLOR RULES — CUÁNDO APLICAR CADA COLOR

### 4.1 Reglas base (aplican a TODAS las métricas)

| Condición | Color |
|-----------|-------|
| `period_status === 'FUTURE'` | `empty` (gray, sin datos) |
| `period_status === 'NO_PLAN'` | `empty` (gray, "Sin plan") |
| `period_status === 'NO_REAL'` | `red` (alerta: dato faltante) |
| `real_value === null && period_status !== 'FUTURE'` | `red` (dato esperado ausente) |
| `trust_status === 'blocked'` | `red` (bloqueado) |
| `trust_status === 'low'` | `amber` (precaución) |

### 4.2 Reglas de attainment (Vs Proy — Plan vs Real)

| Condición | Color |
|-----------|-------|
| `attainment_pct >= 100` | `green` (on track o superado) |
| `attainment_pct >= 90 && attainment_pct < 100` | `neutral` (cerca) |
| `attainment_pct >= 75 && attainment_pct < 90` | `amber` (atención) |
| `attainment_pct < 75` | `red` (crítico) |
| `real_value > plan_value * 1.1` | `green` (superado significativamente) |

### 4.3 Reglas de momentum (DoD/WoW/MoM)

| Condición | Color |
|-----------|-------|
| `delta_pct >= 5` (positive direction) | `green` |
| `delta_pct >= 2 && delta_pct < 5` | `neutral` |
| `delta_pct > -2 && delta_pct < 2` | `neutral` |
| `delta_pct <= -2 && delta_pct > -10` | `amber` |
| `delta_pct <= -10` | `red` |

---

## 5. MÉTRICAS CUBIERTAS

| Métrica | KPI Key | Formato | Dirección | Unidad |
|---------|---------|---------|-----------|--------|
| Viajes | `trips_completed` | Entero (1,234) | higher_better | viajes |
| Revenue | `revenue_yego_final` | Decimal 2 (12,345.67) | higher_better | USD/PEN |
| Conductores | `active_drivers` | Entero (2,103) | higher_better | conductores |
| Ticket | `avg_ticket` | Decimal 2 (12.50) | context_dependent | USD/PEN |
| TPD | `trips_per_driver` | Decimal 1 (5.9) | higher_better | viajes/conductor |

**Revenue usa `revenue_yego_final` como fuente canónica. NO `revenue_yego_net`.**

---

## 6. GRAINS CUBIERTOS

| Grain | Período | Comparación primaria | Comparación secundaria |
|-------|---------|---------------------|----------------------|
| Daily | Día | Attainment vs plan diario | DoD (mismo weekday semana anterior) |
| Weekly | Semana ISO | Attainment vs plan semanal | WoW (semana anterior) |
| Monthly | Mes | Attainment vs plan mensual | MoM (mes anterior) |

---

## 7. REGLAS DE RENDERIZADO UNIFORME

1. **Mismo color para misma condición**: attainment 85% → amber en Trips, amber en Revenue, amber en Drivers.
2. **Mismo badge para mismo status**: PARTIAL → "~" en todas las métricas.
3. **Mismo tooltip structure**: "{delta_pct}% {above/below} plan. {days_elapsed} de {total_days} días. Proyección: {projection}."
4. **DoD/WoW/MoM visibles si existen**: no ocultar DoD en daily si el dato existe.
5. **Sin lógica divergente por métrica**: el color de una celda de Revenue no debe calcularse con reglas diferentes a Trips.

---

## 8. IMPLEMENTACIÓN TÉCNICA

### 8.1 Frontend

- `projectionCellDisplayModel.js`: ya tiene `buildProjectionCellDisplay()`. Extender para incluir todos los campos del contrato.
- `BusinessSliceOmniviewMatrixCell.jsx`: unificar rendering cross-métrica usando el contrato.
- `comparableDeltaDisplay.js`: ya existe `buildComparableDelta()`. Asegurar que se aplica a TODAS las métricas.

### 8.2 Backend

- `/ops/business-slice/omniview-projection`: debe exponer `revenue_yego_final` (no `revenue_yego_net`).
- Añadir `period_status` a cada fila de la respuesta.
- Añadir `freshness_status` y `trust_status` por celda.

---

## 9. VERIFICACIÓN DEL CONTRATO

- [ ] Toda celda tiene `period_status`
- [ ] Toda celda con delta tiene `color_rule` consistente cross-métrica
- [ ] Revenue usa `revenue_yego_final`, no `revenue_yego_net`
- [ ] CLOSED es distinguible de PARTIAL visualmente
- [ ] Tooltip explica el porqué del color/número
- [ ] DoD/WoW/MoM visibles donde aplican (no ocultos)

---

**END OF CONTRACT**
