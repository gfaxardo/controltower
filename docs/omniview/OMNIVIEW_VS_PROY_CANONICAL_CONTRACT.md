# OMNI-P0 — VS PROY CANONICAL GRID CONTRACT

**Motor:** Omniview Governance — P0 Recovery
**Fecha:** 2026-06-04
**Versión:** 1.0
**Estado:** CONTRATO DEFINIDO — PENDIENTE IMPLEMENTACIÓN UNIFICADA

---

## 1. OBJETIVO

Definir un contrato único de celda para Vs Proy que aplique de forma uniforme a todas las métricas y todos los grains. No se permite que cada métrica renderice con lógica distinta.

---

## 2. CONTRATO DE CELDA (CAMPO OBLIGATORIO)

Toda celda de la grilla Vs Proy DEBE exponer los siguientes campos:

### 2.1 Campos de valor

| Campo | Tipo | Descripción | Obligatorio |
|-------|------|-------------|-------------|
| `real_value` | number \| null | Valor real observado (serving fact) | Sí |
| `plan_value` | number \| null | Valor planeado (projection) | No (puede ser null si no hay plan) |
| `projection_value` | number \| null | Valor proyectado/esperado | No (si no hay proyección activa) |

### 2.2 Campos de delta

| Campo | Tipo | Descripción | Obligatorio |
|-------|------|-------------|-------------|
| `delta_abs` | number \| null | Diferencia absoluta real vs comparable | Sí (si hay real y comparable) |
| `delta_pct` | number \| null | Diferencia porcentual | Sí (si hay real y comparable) |
| `comparison_label` | string \| null | Etiqueta: "DoD", "WoW", "MoM", "vs Plan", "YTD" | Sí (si hay delta) |

### 2.3 Campos de estado

| Campo | Tipo | Valores permitidos | Obligatorio |
|-------|------|-------------------|-------------|
| `period_status` | enum | `CLOSED`, `PARTIAL`, `CURRENT`, `FUTURE`, `NO_PLAN`, `NO_REAL` | **Sí** |
| `freshness_status` | enum | `OK`, `WARNING`, `BLOCKED`, `STALE` | **Sí** |
| `trust_status` | enum | `OK`, `WARNING`, `BLOCKED` | **Sí** |

### 2.4 Campos de presentación (derivados)

| Campo | Tipo | Descripción | Obligatorio |
|-------|------|-------------|-------------|
| `display_value` | string | Valor formateado para UI (con unidades, decimales) | Sí |
| `display_badge` | string \| null | Badge: "CLOSED", "PARCIAL", "ACTUAL", "FUTURO", "SIN PLAN", "SIN DATO" | Sí |
| `color_rule` | object | `{ bg, text, border, severity }` — regla de color | Sí |
| `tooltip_reason` | string | Explicación textual del estado de la celda | Sí |

---

## 3. REGLAS DE RENDER POR PERIOD_STATUS

### 3.1 CLOSED

```
Condición: Periodo finalizado con datos completos.
Display: real_value (dominante, bold)
Badge: "CERRADO" (gris/emerald)
Delta: vs periodo anterior comparable (DoD/WoW/MoM)
Color: según dirección y severidad del delta
Tooltip: "Periodo cerrado. {N} {métrica}. {Delta} vs {periodo_anterior}."
```

### 3.2 PARTIAL

```
Condición: Periodo en curso con datos parciales.
Display: real_value (dominante, bold) + indicador "~"
Badge: "PARCIAL" (ámbar)
Delta: vs equivalente parcial del periodo anterior
Color: según dirección y severidad (con opacidad reducida por parcialidad)
Tooltip: "Periodo parcial. {N} {métrica} hasta {cutoff_date}. Completado vs mismo punto periodo anterior."
```

### 3.3 CURRENT

```
Condición: Día/semana/mes actual (hoy).
Display: real_value (dominante, bold) + ring azul (Present Focus)
Badge: "ACTUAL" (azul)
Delta: vs equivalente parcial del periodo anterior (si aplica)
Color: según dirección y severidad
Tooltip: "Periodo actual. {N} {métrica}. Datos hasta {max_data_date}."
```

### 3.4 FUTURE

```
Condición: Periodo que aún no ha comenzado.
Display: plan_value o projection_value si existen; "—" si no
Badge: "FUTURO" (gris claro) o "PROY" (si hay proyección)
Delta: No aplica
Color: Fondo gris muy claro, texto muted
Tooltip: "Periodo futuro. {Plan/Proyección si existe}. Sin datos reales todavía."
```

### 3.5 NO_PLAN

```
Condición: Periodo sin plan cargado en proyección.
Display: real_value si existe; "—" si no
Badge: "SIN PLAN" (gris)
Delta: vs periodo anterior comparable si hay real
Color: Normal si hay real; gris si no hay real
Tooltip: "Sin plan cargado para este periodo. {Real si existe}."
```

### 3.6 NO_REAL

```
Condición: Periodo pasado pero sin datos reales (data loss, gap).
Display: "—" (em dash) con tooltip
Badge: "SIN DATO" (rojo claro)
Delta: No aplica
Color: Fondo rojo muy claro (#fef2f2), borde rojo
Tooltip: "Sin dato real. Posible gap de serving. Último dato: {max_data_date}."
```

---

## 4. REGLAS DE COLOR (UNIFORME CROSS-MÉTRICA)

### 4.1 Momentum Severity (5 niveles)

Aplica a celdas con delta en periodos CLOSED/PARTIAL/CURRENT.

| Nivel | Condición | Color texto | Color fondo |
|-------|-----------|-------------|-------------|
| **Crítico negativo** | pct ≤ -50% | `#991b1b` | `#fecaca` |
| **Alto negativo** | -50% < pct ≤ -30% | `#dc2626` | `#fee2e2` |
| **Medio negativo** | -30% < pct ≤ -15% | `#ef4444` | `#fef2f2` |
| **Bajo negativo** | -15% < pct ≤ -5% | `#f87171` | `#fff5f5` |
| **Leve negativo** | -5% < pct < 0% | `#fca5a5` | transparent |
| **Neutral** | pct = 0% | `#9ca3af` | transparent |
| **Leve positivo** | 0% < pct < 5% | `#6ee7b7` | transparent |
| **Bajo positivo** | 5% ≤ pct < 15% | `#34d399` | `#f0fdf4` |
| **Medio positivo** | 15% ≤ pct < 30% | `#10b981` | `#dcfce7` |
| **Alto positivo** | 30% ≤ pct < 50% | `#059669` | `#bbf7d0` |
| **Crítico positivo** | pct ≥ 50% | `#047857` | `#86efac` |

### 4.2 KPI con dirección invertida

Las siguientes métricas tienen dirección invertida (más alto = peor):
- `cancel_rate_pct`
- `trips_cancelled`

Para estas métricas, los colores positivo/negativo se invierten.

### 4.3 Periodos sin delta

- FUTURE: gris claro, sin color de severidad
- NO_PLAN: gris, sin color de severidad
- NO_REAL: rojo muy claro (#fef2f2)
- Sin comparable: gris, sin color de severidad

---

## 5. REGLAS DE DoD / WoW / MoM

### 5.1 Qué comparación aplicar

| Grain | Comparación primaria | Label |
|-------|---------------------|-------|
| Daily | Mismo día de la semana anterior (d-7) | DoD |
| Weekly | Misma semana ISO del año anterior | WoW |
| Monthly | Mismo mes del año anterior | MoM |

### 5.2 Cuándo NO aplicar comparación

- Periodo FUTURE: sin datos reales para comparar
- Periodo NO_REAL: sin datos reales para el periodo actual
- Periodo sin periodo anterior comparable (primera fila de datos)
- Periodo con `comparison_status === 'missing_plan'` (solo mostrar real, no delta)

### 5.3 Formato de delta

```
Siempre visible:  "▼ -21% DoD" o "▲ +15% WoW" o "— MoM"
Tooltip:          "Real: 1,234 | Anterior: 1,562 | Delta: -328 (-21.0%) | Comparación: DoD (lunes vs lunes anterior)"
```

---

## 6. MÉTRICAS Y SU CONTRATO DE FORMATO

| Métrica | Key | Unidad | Decimales | Formato display |
|---------|-----|--------|-----------|-----------------|
| Viajes | `trips_completed` | número | 0 | `1,234` |
| Revenue | `revenue_yego_final` | moneda | 2 | `$12,345.67` |
| Conductores | `active_drivers` | número | 0 | `567` |
| Ticket | `avg_ticket` | moneda | 2 | `$8.52` |
| TPD | `trips_per_driver` | número | 1 | `12.3` |

**Regla de revenue**: La fuente canónica para display es `revenue_yego_final`. Si `revenue_yego_final` es NULL, usar `revenue_yego_net`. Si ambos son NULL, mostrar `—` con estado NO_REAL.

---

## 7. GRAINS Y SU CONTRATO

### 7.1 Daily

- **Unidad**: Un día calendario
- **Periodo actual**: `CURRENT` si es hoy; `PARTIAL` si es hoy (día en curso)
- **Comparación**: DoD (mismo weekday semana anterior)
- **Columnas visibles**: 30 días (pasado + presente + futuro limitado)
- **Foco**: Hoy (auto-scroll + ring azul)

### 7.2 Weekly

- **Unidad**: Semana ISO
- **Periodo actual**: `CURRENT`/`PARTIAL` si es la semana actual
- **Comparación**: WoW
- **Columnas visibles**: 12-16 semanas
- **Foco**: Semana actual o última cerrada

### 7.3 Monthly

- **Unidad**: Mes calendario
- **Periodo actual**: `CURRENT`/`PARTIAL` si es el mes actual
- **Comparación**: MoM (mismo mes año anterior)
- **Columnas visibles**: 12-18 meses
- **Foco**: Mes actual o último cerrado

---

## 8. CONTRATO DE TOTALS ROW

El Total row debe mostrar:

| Campo | Descripción |
|-------|-------------|
| `total_real` | Suma de real_value de todas las filas visibles |
| `total_plan` | Suma de plan_value |
| `total_expected` | Suma de projection_value |
| `total_attainment` | total_real / total_plan (porcentaje) |
| `total_gap` | total_real - total_plan (absoluto) |
| `total_delta_pct` | Variación vs periodo anterior (total) |
| `ytd_real` | Acumulado año hasta periodo actual |
| `ytd_expected` | Acumulado esperado año |

---

## 9. VALIDACIÓN DEL CONTRATO

### 9.1 Función de validación requerida

```javascript
function validateCellContract(cell) {
  const errors = [];
  if (cell.period_status === undefined) errors.push('Falta period_status');
  if (cell.display_value === undefined) errors.push('Falta display_value');
  if (cell.display_badge === undefined) errors.push('Falta display_badge');
  if (cell.period_status === 'CLOSED' && cell.real_value === null) {
    errors.push('CLOSED sin real_value');
  }
  if (cell.delta_pct !== null && cell.comparison_label === null) {
    errors.push('Delta sin comparison_label');
  }
  return { valid: errors.length === 0, errors };
}
```

### 9.2 Regla de certificación

Ninguna celda puede escapar al contrato. Si una métrica o grain no cumple el contrato → FAIL de certificación.

---

## 10. IMPLEMENTACIÓN

El contrato se implementa en dos capas:

1. **Backend**: El endpoint de projection serving (`/ops/business-slice/omniview-projection`) debe retornar los campos del contrato para cada celda.
2. **Frontend**: `projectionMatrixUtils.js` → `buildProjectionMatrix()` debe garantizar que cada celda tenga todos los campos del contrato.

**Archivo canónico de validación**: `projectionContractValidation.js` (ya existe, ampliar con este contrato).

---

**END OF CANONICAL GRID CONTRACT**
