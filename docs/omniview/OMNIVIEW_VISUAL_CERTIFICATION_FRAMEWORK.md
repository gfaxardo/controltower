# OMNI-GOV-001 — OMNIVIEW VISUAL CERTIFICATION FRAMEWORK

**Motor:** Omniview Governance  
**Fecha:** 2026-06-03  
**Versión:** 1.0  
**Estado:** FRAMEWORK CREADO — PENDIENTE PRIMERA CERTIFICACIÓN

---

## 1. OBJETIVO

Establecer una capa obligatoria de certificación visual para Omniview. Ningún sprint futuro puede declarar GO sin pasar esta certificación. Los tests de backend y el build de frontend son necesarios pero NO suficientes.

---

## 2. ALCANCE

| Dimensión | Cubierto |
|-----------|----------|
| Daily / Weekly / Monthly | **Sí** |
| Métricas (trips, revenue, drivers, ticket, TPD) | **Sí** |
| Estados (real cerrado, parcial, futuro, sin plan, sin real, blocked, warning) | **Sí** |
| Header + filtros + matriz + freshness banner | **Sí** |
| Compact / Comfortable density | **Sí** |
| Backend / APIs / Datos | **No** (scope exclusivo UI) |
| Plan vs Real (projection mode) | **No** (certificación separada OMNI-PVR-001) |
| Driver views / Supply / otras vistas | **No** (scope Omniview Matrix únicamente) |

---

## 3. MATRIZ DE CERTIFICACIÓN VISUAL

### 3.1 Temporalidad × Métrica × Estado

Para cada celda de la matriz, se define qué esperar.

#### Daily (granularidad: día)

| Métrica | Real cerrado | Parcial actual | Futuro | Sin real | Blocked | Warning |
|---------|-------------|----------------|--------|----------|---------|---------|
| Viajes | Número entero ≥ 0 | Número entero ≥ 0 | — o Proy | — | Número + overlay rojo | Número + overlay ámbar |
| Revenue | Número con 2 decimales | Número con 2 decimales | — o Proy | — | Igual viajes | Igual viajes |
| Conductores | Número entero ≥ 0 | Número entero ≥ 0 | — | — | overlay rojo | overlay ámbar |
| Ticket | Número con 2 decimales | Número con 2 decimales | — | — | overlay rojo | overlay ámbar |
| TPD | Número con 1 decimal | Número con 1 decimal | — | — | overlay rojo | overlay ámbar |

#### Weekly (granularidad: semana ISO)

| Métrica | Real cerrado | Parcial actual | Futuro | Sin real | Blocked | Warning |
|---------|-------------|----------------|--------|----------|---------|---------|
| Viajes | Número entero | Número entero | — o Proy | — | overlay rojo | overlay ámbar |
| Revenue | Número con 2 decimales | Número con 2 decimales | — o Proy | — | overlay rojo | overlay ámbar |
| Conductores | Número entero | Número entero | — | — | overlay rojo | overlay ámbar |
| Ticket | Número con 2 decimales | Número con 2 decimales | — | — | overlay rojo | overlay ámbar |
| TPD | Número con 1 decimal | Número con 1 decimal | — | — | overlay rojo | overlay ámbar |

#### Monthly (granularidad: mes)

| Métrica | Real cerrado | Parcial actual | Futuro | Sin real | Blocked | Warning |
|---------|-------------|----------------|--------|----------|---------|---------|
| Viajes | Número entero | Número entero | — o Proy | — | overlay rojo | overlay ámbar |
| Revenue | Número con 2 decimales | Número con 2 decimales | — o Proy | — | overlay rojo | overlay ámbar |
| Conductores | Número entero | Número entero | — | — | overlay rojo | overlay ámbar |
| Ticket | Número con 2 decimales | Número con 2 decimales | — | — | overlay rojo | overlay ámbar |
| TPD | Número con 1 decimal | Número con 1 decimal | — | — | overlay rojo | overlay ámbar |

### 3.2 Placeholders permitidos

| Placeholder | Cuándo |
|-------------|--------|
| `—` (em dash) | Periodo sin datos reales disponibles (futuro, sin cobertura) |
| `Sin plan` | Proyección sin plan cargado para ese periodo |
| `Proy` | Dato proyectado (no real) — distinguible visualmente del real |
| `~` | Dato parcial (periodo abierto, comparación incompleta) |

### 3.3 Placeholders prohibidos (FAIL automático)

| Placeholder | Severidad |
|-------------|-----------|
| `[object Object]` | **FAIL** |
| `NaN` | **FAIL** |
| `undefined` | **FAIL** |
| `null` | **FAIL** |
| `Infinity` | **FAIL** |
| `-Infinity` | **FAIL** |
| `unknown` sin tooltip explicativo | **FAIL** |
| `0` donde debería ser dato faltante (confusión semántica) | **FAIL** |

---

## 4. REGLAS NO-GO

### 4.1 FAIL — Bloquea GO

| # | Regla | Descripción |
|---|-------|-------------|
| F1 | **Token prohibido visible** | `[object Object]`, `NaN`, `undefined`, `null`, `Infinity` en cualquier parte de la UI |
| F2 | **Matriz vacía > 40% viewport** | Si más del 40% del espacio de la grilla muestra `—` o `Sin plan` sin datos reales ni proyección |
| F3 | **Periodo actual no identificable** | El usuario no puede encontrar HOY / ESTA SEMANA / ESTE MES en < 2 segundos (sin auto-scroll funcional o sin highlight) |
| F4 | **BLOCKED sin explicación** | Banner muestra BLOCKED pero no hay mensaje, remediation, ni tooltip explicando por qué |
| F5 | **Mismatch activo sin remediation** | MONTH_TRIPS_MISMATCH o similar visible en trust banner sin acción sugerida |
| F6 | **Doble scroll no controlado** | Scroll horizontal + vertical compiten o crean barras redundantes |
| F7 | **Métrica sin datos mientras fact tiene datos** | El endpoint/fact table tiene datos para un periodo pero la UI muestra `—` |
| F8 | **Confianza no numérica** | El score de confianza muestra texto no parseable (ej: `[object Object]%`) |
| F9 | **Header corrupto** | Labels de periodo ilegibles, fechas mal formateadas, caracteres rotos |
| F10 | **Freshness banner contradice datos** | Banner dice "Falta data" pero la matriz muestra datos reales (o viceversa) |

### 4.2 WARNING — No bloquea GO pero requiere documentación

| # | Regla | Descripción |
|---|-------|-------------|
| W1 | **"Sin plan" > 30% columnas** | Más del 30% de las columnas de proyección muestran "Sin plan" |
| W2 | **"unknown" sin tooltip** | Algún campo muestra "unknown" sin explicación en hover/tooltip |
| W3 | **Futuro excesivo** | Más de 6 columnas de futuro visibles en daily (deberían comprimirse) |
| W4 | **Inconsistencia cross-métrica** | Una métrica muestra datos y otra `—` para el mismo periodo (sin justificación) |
| W5 | **Densidad sub-óptima** | Compact/comfortable no aplica correctamente a todas las filas |
| W6 | **Temporal tier mal asignado** | LATEST_CLOSED apunta a un mes que no es el último cerrado |

---

## 5. EVIDENCIA VISUAL OBLIGATORIA

Antes de declarar GO en cualquier sprint de Omniview, se requiere:

### 5.1 Screenshots mínimos (15)

| # | Vista | Métrica | Grain |
|---|-------|---------|-------|
| 1 | Matriz | Viajes | Daily |
| 2 | Matriz | Revenue | Daily |
| 3 | Matriz | Conductores | Daily |
| 4 | Matriz | Ticket | Daily |
| 5 | Matriz | TPD | Daily |
| 6 | Matriz | Viajes | Weekly |
| 7 | Matriz | Revenue | Weekly |
| 8 | Matriz | Conductores | Weekly |
| 9 | Matriz | Ticket | Weekly |
| 10 | Matriz | TPD | Weekly |
| 11 | Matriz | Viajes | Monthly |
| 12 | Matriz | Revenue | Monthly |
| 13 | Matriz | Conductores | Monthly |
| 14 | Matriz | Ticket | Monthly |
| 15 | Matriz | TPD | Monthly |

### 5.2 Qué validar en cada screenshot

| Elemento | Check |
|----------|-------|
| Header | Labels de periodo legibles, tier visual correcto |
| Filtros | Grain, país, ciudad, año/mes visibles y funcionales |
| Matriz | Datos numéricos correctos, sin tokens prohibidos |
| Periodo actual | Highlight azul visible, badge presente, auto-scroll funcional |
| Primer viewport | Sin scroll horizontal excesivo, datos visibles sin búsqueda |
| Placeholders | `—` bien aplicado, sin "sin plan" masivo |
| Freshness banner | Status coherente con datos visibles |
| Trust banner | Sin BLOCKED injustificado, remediation presente si aplica |

---

## 6. CHECKLIST ANTES DE GO

```
[ ] Sin tokens prohibidos (F1)
[ ] Matriz > 60% con datos reales o proyección (F2)
[ ] Periodo actual identificable < 2s (F3)
[ ] BLOCKED con explicación si existe (F4)
[ ] Mismatch con remediation si existe (F5)
[ ] Sin doble scroll (F6)
[ ] Métricas coinciden con fact tables (F7)
[ ] Confianza numérica y correcta (F8)
[ ] Header sin corrupción (F9)
[ ] Freshness coherente con datos (F10)
[ ] 15 screenshots capturados (Sección 5.1)
[ ] Cada screenshot validado (Sección 5.2)
[ ] Backlog documentado para WARNINGs
[ ] Build PASS
[ ] Backend health OK
```

---

## 7. CRITERIOS PARA BLOQUEAR DIAGNOSTIC

Diagnostic Engine 2A.3 no puede abrir si:

1. La matriz muestra FAIL en cualquier regla F1-F10
2. El periodo actual no es identificable (F3)
3. La confianza muestra tokens no numéricos (F8)
4. Hay BLOCKED activo sin remediation (F4)
5. El freshness banner contradice los datos visibles (F10)

---

## 8. PLANTILLA DE REPORTE VISUAL

```markdown
# OMNI-VISUAL-XXX — Reporte de Certificación Visual

**Fecha:** YYYY-MM-DD
**Sprint:** XXX
**Auditor:** [nombre]

## Resumen

| Métrica | Valor |
|----------|-------|
| Screenshots capturados | X/15 |
| FAIL | X |
| WARNING | X |
| Veredicto | GO / CONDITIONAL GO / NO GO |

## Evidencia

[15 screenshots con anotaciones]

## Hallazgos

| # | Tipo | Regla | Descripción | Screenshot |
|---|------|-------|-------------|------------|
| 1 | FAIL | F3 | Periodo actual sin highlight | #3 |
| 2 | WARN | W1 | 45% columnas "Sin plan" | #8 |

## Backlog generado

| ID | Descripción | Prioridad |
|----|-------------|-----------|
| OMNI-UX-XXX | ... | P1 |

## Veredicto

[GO / CONDITIONAL GO / NO GO]
```

---

## 9. BACKLOG DETECTADO (SCREENSHOTS ACTUALES)

### OMNI-UX-016 — Confianza [object Object]%
**Severidad:** FAIL (F8)  
**Descripción:** El score de confianza muestra `[object Object]%` en lugar de un número. El frontend está intentando renderizar un objeto como string.  
**Archivo sospechoso:** `DataTrustBadge.jsx` o `OmniviewCommandHeader.jsx` — `confidence.score` no se accede correctamente.

### OMNI-UX-017 — Empty Future Compression
**Severidad:** WARNING (W3)  
**Descripción:** Columnas futuras ocupan espacio excesivo en daily/weekly. Deberían comprimirse para dar prioridad al pasado reciente + periodo actual.  
**Archivo:** `BusinessSliceOmniviewMatrixTable.jsx` — lógica de columnas futuras.

### OMNI-UX-018 — Future Horizon Compression
**Severidad:** WARNING (W3)  
**Descripción:** El horizonte de proyección muestra demasiadas columnas futuras sin datos. Límite recomendado: 6 columnas futuras máximo en daily, 4 en weekly, 3 en monthly.

### OMNI-UX-019 — Fullscreen Density Optimization
**Severidad:** WARNING (W5)  
**Descripción:** En fullscreen/ultrawide, la densidad de información es sub-óptima. Las filas podrían mostrar más datos o el espaciado podría ajustarse.

### OMNI-UX-020 — Cross-Metric Layout Harmonization
**Severidad:** WARNING (W4)  
**Descripción:** Cambiar entre métricas (viajes → revenue → conductores) produce saltos visuales porque los formatos numéricos tienen anchos diferentes. Deberían alinearse.

### OMNI-UX-021 — Temporal Hierarchy Governance
**Severidad:** WARNING (W6)  
**Descripción:** El tier `LATEST_CLOSED` (emerald) a veces destaca más que el periodo actual (blue). La jerarquía visual debe ser: Present Focus > LATEST_CLOSED > CURRENT_PARTIAL > Historical > Future.

### OMNI-UX-022 — Present Focus V2
**Severidad:** WARNING  
**Descripción:** El Present Focus actual (O3) es funcional pero podría mejorarse: indicador de posición en el scroll, animación suave al hacer clic en "Ir a hoy", accesibilidad keyboard.

### OMNI-COV-001 — Metric Coverage Matrix
**Severidad:** INFO  
**Descripción:** Documentar para cada métrica × grain qué cobertura de datos existe. Algunas métricas pueden no tener datos para ciertos grains (ej: TPD en monthly puede requerir agregación diferente).

### OMNI-COV-002 — Serving Coverage Audit
**Severidad:** INFO  
**Descripción:** Auditar qué endpoints de serving tienen cobertura completa vs parcial. Relacionado con el serving integrity guard (CF-H1L.2).

### OMNI-COV-003 — Projection Coverage Audit
**Severidad:** INFO  
**Descripción:** Auditar cobertura de proyección: ¿todos los grains tienen plan cargado? ¿Hay meses sin proyección?

### OMNI-COV-004 — Plan Coverage Audit
**Severidad:** INFO  
**Descripción:** Auditar cobertura del plan: ¿todos los business slices tienen plan? ¿Hay slices huérfanos?

### OMNI-COV-005 — Metric/Temporality Certification
**Severidad:** INFO  
**Descripción:** Certificar que cada métrica funciona correctamente en cada temporalidad. No asumir que si funciona en monthly, funciona en daily.

### OMNI-COV-006 — UI ↔ Serving Reconciliation
**Severidad:** INFO  
**Descripción:** Comparar datos visibles en UI con datos retornados por el endpoint de serving. Deben coincidir. Si no coinciden, es un bug de transformación en el frontend.

### OMNI-ARCH-001 — Universal Grid Specification
**Severidad:** INFO  
**Descripción:** Definir una especificación única de grid para todas las vistas de Omniview. Actualmente Evolution y Projection usan lógicas de render diferentes.

### OMNI-ARCH-002 — Metric Adapter Pattern
**Severidad:** INFO  
**Descripción:** Cada métrica debería tener un adapter que defina formato, color, umbrales, y comportamiento. Evitar lógica dispersa en múltiples componentes.

### OMNI-ARCH-003 — Cross-Metric Consistency Audit
**Severidad:** INFO  
**Descripción:** Auditar que el comportamiento visual sea consistente entre métricas. Mismo periodo, misma ciudad, mismo slice debería verse coherente.

### OMNI-ARCH-004 — Single Rendering Contract
**Severidad:** INFO  
**Descripción:** Unificar el contrato de rendering entre Evolution y Projection. Ambas usan `BusinessSliceOmniviewMatrixCell` pero con paths divergentes.

---

## 10. AUTOMATIZACIÓN FUTURA

### OMNI-QA-001 — Playwright Omniview Visual Certification

**Objetivo:** Automatizar la captura y validación de los 15 screenshots mínimos.

**Diseño propuesto (NO implementar todavía):**

```
playwright-omniview-cert/
├── tests/
│   ├── daily-trips.spec.js
│   ├── daily-revenue.spec.js
│   ├── weekly-trips.spec.js
│   ├── monthly-trips.spec.js
│   └── ... (15 specs)
├── assertions/
│   ├── no-forbidden-tokens.js     # F1
│   ├── current-period-visible.js  # F3
│   ├── confidence-numeric.js      # F8
│   └── grid-coverage.js           # F2
├── fixtures/
│   └── omniview-state.json
└── screenshots/
    └── baseline/                   # reference images for diff
```

**Assertions por test:**
1. Navegar a Omniview con grain + métrica
2. Esperar que la matriz cargue (data rows > 0)
3. Verificar que no hay tokens prohibidos en el DOM
4. Verificar que el periodo actual tiene la clase/atributo de highlight
5. Verificar que el banner de confianza contiene un número
6. Capturar screenshot y comparar con baseline (diff < 1%)
7. Verificar que el freshness banner es coherente

**Integración CI:**
- Ejecutar en cada PR que toque `frontend/src/components/BusinessSliceOmniview*`
- Bloquear merge si hay FAIL de token prohibido (F1, F8)
- Warning si hay diff visual > 1%

---

## 11. VEREDICTO

### GO

Framework creado. Incluye:
- Matriz de certificación 3×5×7 (temporalidad × métrica × estado)
- 10 reglas FAIL, 6 reglas WARNING
- Checklist de 15 items
- 15 screenshots obligatorios
- Plantilla de reporte
- 17 tickets de backlog documentados
- 1 propuesta de automatización (Playwright)

Omniview NO puede declararse cerrado visualmente hasta que:
1. Se capturen los 15 screenshots
2. Se verifiquen las 10 reglas FAIL (0 FAILs)
3. Se documenten los WARNINGs
4. Se complete el checklist

---

## 12. PRÓXIMO PROMPT RECOMENDADO

**OMNI-VISUAL-001 — Primera Certificación Visual de Omniview**

Ejecutar la certificación visual contra el estado actual, capturar los 15 screenshots, ejecutar el checklist, y emitir el primer veredicto GO/CONDITIONAL GO/NO GO con evidencia.

No corregir bugs. Solo documentar el estado real.

---

**END OF FRAMEWORK**
