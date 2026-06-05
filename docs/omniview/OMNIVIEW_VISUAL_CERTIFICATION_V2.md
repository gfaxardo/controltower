# OMNI-GOV-002 — OMNIVIEW VISUAL CERTIFICATION V2 (SEMÁNTICA)

**Motor:** Omniview Governance — P0 Recovery
**Fecha:** 2026-06-04
**Versión:** 2.0
**Estado:** FRAMEWORK DEFINIDO — REEMPLAZA OMNI-GOV-001 PARA CERTIFICACIONES FUTURAS

---

## 1. PROPÓSITO

OMNI-GOV-002 reemplaza y amplía OMNI-GOV-001. La certificación V2 no valida solo tokens y render superficial. Valida **utilidad operativa real y coherencia semántica** de Vs Proy como vista canónica única.

OMNI-GOV-001 queda como subset (reglas F1-F10 se heredan), pero ya no es suficiente por sí solo.

---

## 2. REGLAS HEREDADAS DE OMNI-GOV-001 (F1-F10)

Las 10 reglas FAIL de OMNI-GOV-001 se mantienen como base mínima:

| # | Regla | Heredada |
|---|-------|----------|
| F1 | Token prohibido visible (`[object Object]`, `NaN`, etc.) | Sí |
| F2 | Matriz vacía >40% viewport | Sí |
| F3 | Periodo actual no identificable <2s | Sí |
| F4 | BLOCKED sin explicación | Sí |
| F5 | Mismatch activo sin remediation | Sí |
| F6 | Doble scroll no controlado | Sí |
| F7 | Métrica sin datos mientras fact tiene datos | Sí (ampliada) |
| F8 | Confianza no numérica | Sí |
| F9 | Header corrupto | Sí |
| F10 | Freshness banner contradice datos | Sí (ampliada) |

---

## 3. NUEVAS REGLAS SEMÁNTICAS (S1-S10)

### 3.1 Reglas de Vista Canónica (S1-S3)

| # | Regla | Descripción | Severidad |
|---|-------|-------------|-----------|
| **S1** | **Vs Proy es default** | Al abrir Omniview, el usuario ve Vs Proy (no Evolution). `viewMode` default = `'proyeccion'`. | **FAIL** si no |
| **S2** | **Evolution no visible** | El toggle Evolution/Vs Proy no aparece en UI operacional. Evolution solo accesible con `VITE_OMNIVIEW_EVOLUTION_LEGACY=true`. | **FAIL** si visible |
| **S3** | **Una sola vista certificable** | Solo Vs Proy se certifica. Capturas de Evolution no son evidencia válida. | **FAIL** si se usa Evolution como evidencia |

### 3.2 Reglas de Contrato de Celda (S4-S6)

| # | Regla | Descripción | Severidad |
|---|-------|-------------|-----------|
| **S4** | **Contrato canónico por celda** | Cada celda DEBE tener: `real_value`, `plan_value`, `delta_abs`, `delta_pct`, `comparison_label`, `period_status`, `display_value`, `display_badge`, `color_rule`, `tooltip_reason`. | **FAIL** si falta algún campo |
| **S5** | **Uniformidad cross-métrica** | Todas las métricas (trips, revenue, drivers, ticket, TPD) renderizan con el mismo contrato L0-L4. No puede una métrica mostrar DoD/WoW/MoM y otra no. | **FAIL** si hay divergencia |
| **S6** | **Period status visible** | Cada celda con datos muestra su `period_status` como badge (CLOSED/PARTIAL/CURRENT/FUTURE/NO_PLAN/NO_REAL). No puede mostrarse un delta sin contexto de estado. | **FAIL** si no |

### 3.3 Reglas de Revenue (S7-S8)

| # | Regla | Descripción | Severidad |
|---|-------|-------------|-----------|
| **S7** | **Revenue con datos en todos los grains** | Revenue debe mostrar `revenue_yego_final` con valores >0 en daily, weekly, y monthly para periodos con datos. Si serving tiene datos pero la celda está vacía → FAIL. | **FAIL** |
| **S8** | **Revenue source canónica** | El campo display de revenue usa `revenue_yego_final` (COALESCE con `_net`). No se usa `revenue_yego_net` directamente sin fallback. | **FAIL** si no |

### 3.4 Reglas de Coherencia (S9-S10)

| # | Regla | Descripción | Severidad |
|---|-------|-------------|-----------|
| **S9** | **Trust ↔ Datos coherentes** | Si `matrixOperationalTrust` muestra "OK" pero hay celdas vacías (NO_REAL) en daily/weekly → FAIL. Trust no puede estar OK si los datos están incompletos. | **FAIL** |
| **S10** | **Foco temporal correcto** | El viewport inicial debe mostrar el periodo operativo actual (junio 2026), no periodos históricos (noviembre) ni futuros lejanos. `resolveClosedPeriodAnchor` debe funcionar. | **FAIL** si no |

---

## 4. MATRIZ DE CERTIFICACIÓN V2

### 4.1 Screenshots requeridos (15 → ampliado a 18)

| # | Vista | Métrica | Grain | Validación adicional V2 |
|---|-------|---------|-------|------------------------|
| 1 | Vs Proy | Trips | Daily | S1 (Vs Proy default), S4 (contrato), S6 (status) |
| 2 | Vs Proy | Revenue | Daily | S7 (revenue datos), S8 (source _final) |
| 3 | Vs Proy | Drivers | Daily | S5 (uniformidad) |
| 4 | Vs Proy | Ticket | Daily | S5 |
| 5 | Vs Proy | TPD | Daily | S5 |
| 6 | Vs Proy | Trips | Weekly | S10 (foco temporal) |
| 7 | Vs Proy | Revenue | Weekly | S7, S8 |
| 8 | Vs Proy | Drivers | Weekly | S5 |
| 9 | Vs Proy | Ticket | Weekly | S5 |
| 10 | Vs Proy | TPD | Weekly | S5 |
| 11 | Vs Proy | Trips | Monthly | S10 |
| 12 | Vs Proy | Revenue | Monthly | S7, S8 |
| 13 | Vs Proy | Drivers | Monthly | S5 |
| 14 | Vs Proy | Ticket | Monthly | S5 |
| 15 | Vs Proy | TPD | Monthly | S5 |
| 16 | Vs Proy | Trust + Freshness | — | S9 (trust ↔ datos) |
| 17 | Vs Proy | Alerts panel | — | S9, F5 (mismatch) |
| 18 | Omniview (apertura) | Default view | — | S1, S2 (no Evolution) |

### 4.2 Qué validar en cada screenshot (ampliado)

| Elemento | Check V1 | Check V2 adicional |
|----------|----------|--------------------|
| Header | Labels legibles | ¿Vs Proy es el modo activo? ¿Está Evolution oculto? |
| Filtros | Visibles y funcionales | ¿Plan version selector visible? |
| Matriz | Datos numéricos, sin tokens | ¿Badge de estado en cada celda? ¿Contrato L0-L4 uniforme? |
| Periodo actual | Highlight azul | ¿Foco en junio 2026, no en noviembre? |
| Revenue | — | ¿Valores >0 en daily/weekly/monthly? ¿Source `_final`? |
| Freshness | Coherente con datos | ¿Sin contradicción con trust? |
| Trust | Numérico | ¿Score refleja datos reales? ¿No OK con datos vacíos? |
| Cross-métrica | — | ¿Mismo formato, colores, badges en trips↔revenue↔drivers? |

---

## 5. CHECKLIST V2 ANTES DE GO

```
[ ] S1: Vs Proy es la vista default al abrir
[ ] S2: Evolution NO visible en UI (toggle oculto)
[ ] S3: Certificación usa solo capturas de Vs Proy
[ ] S4: Contrato canónico por celda (10 campos)
[ ] S5: Uniformidad cross-métrica (5 métricas mismo contrato)
[ ] S6: Period status visible en cada celda con datos
[ ] S7: Revenue con datos >0 en daily/weekly/monthly
[ ] S8: Revenue usa revenue_yego_final (no solo _net)
[ ] S9: Trust coherente con datos (no OK con datos vacíos)
[ ] S10: Foco temporal en periodo operativo actual

[ ] F1: Sin tokens prohibidos
[ ] F2: Matriz >60% con datos
[ ] F3: Periodo actual identificable <2s
[ ] F4: BLOCKED con explicación
[ ] F5: Mismatch con remediation (o 0 diff)
[ ] F6: Sin doble scroll
[ ] F7: Métricas coinciden con fact tables
[ ] F8: Confianza numérica
[ ] F9: Header sin corrupción
[ ] F10: Freshness coherente con datos

[ ] 18 screenshots capturados (Sección 4.1)
[ ] Build PASS
[ ] Backend health OK
[ ] day_fact restaurado (sin data loss Mayo 26-Junio 4)
[ ] week_fact restaurado (sin data loss S18-S23)
```

---

## 6. CRITERIOS DE FAIL AUTOMÁTICO (NO GO INMEDIATO)

1. **Evolution visible como modo operativo** (S2)
2. **Revenue vacío en daily/weekly teniendo serving con datos** (S7)
3. **Trust OK + datos incompletos sin explicación** (S9)
4. **Token prohibido en cualquier celda** (F1)
5. **Más de 2 métricas sin contrato S4** (S4/S5)
6. **Foco temporal en periodo no operativo** (S10)

---

## 7. CRITERIOS DE WARNING (NO BLOQUEA GO PERO REQUIERE BACKLOG)

1. "Sin plan" >30% columnas en proyección (W1 heredada)
2. Futuro excesivo sin compresión (W3 heredada)
3. Monthly revenue cobertura <80% (nueva W7)
4. DoD/WoW/MoM no disponible para alguna métrica (nueva W8)
5. TPD/avg_ticket no disponibles en daily (nueva W9)

---

## 8. PLANTILLA DE REPORTE V2

```markdown
# OMNI-VISUAL-V2-XXX — Reporte de Certificación Semántica

**Fecha:** YYYY-MM-DD
**Auditor:** [nombre]
**Vista certificada:** Vs Proy (exclusivamente)

## Resumen

| Métrica | Valor |
|----------|-------|
| Screenshots capturados | X/18 |
| FAIL (F1-F10) | X |
| FAIL (S1-S10) | X |
| WARNING | X |
| Veredicto | GO / CONDITIONAL GO / NO GO |

## Evidencia

[18 screenshots con anotaciones semánticas]

## Hallazgos

| # | Tipo | Regla | Descripción | Screenshot |
|---|------|-------|-------------|------------|
| 1 | FAIL | S2 | Evolution toggle visible | #18 |

## Veredicto

[GO / CONDITIONAL GO / NO GO]

## Condiciones (si CONDITIONAL GO)

[Lista de fixes requeridos antes de GO pleno]
```

---

## 9. RELACIÓN CON OMNI-GOV-001

OMNI-GOV-001 sigue vigente como **subset técnico**. Las reglas F1-F10 se heredan. OMNI-GOV-002 agrega las reglas semánticas S1-S10.

Para certificaciones futuras:
- OMNI-GOV-001 solo → **INSUFICIENTE** (no detecta problemas semánticos)
- OMNI-GOV-002 → **REQUERIDO** para cualquier GO de Omniview

---

**END OF CERTIFICATION V2 FRAMEWORK**
