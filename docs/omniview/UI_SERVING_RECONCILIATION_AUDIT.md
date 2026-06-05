# OMNI-COV-006 — UI ↔ SERVING RECONCILIATION AUDIT

**Motor:** Omniview Governance — Visual Certification  
**Fecha:** 2026-06-03  
**Estado:** COMPLETADO — **NO GO** (FAIL bloqueantes detectados)

---

## 1. GOVERNANCE PRECHECK

| Item | Value |
|------|-------|
| ACTIVE phase | Diagnostic Engine 2A.3 (bloqueado por FAIL visuales) |
| OMNI-GOV-001 vigente | **Sí** |
| Diagnostic bloqueado | **Sí** — hasta que 0 FAIL visuales |
| Scope | Auditoría read-only, sin fixes |

---

## 2. SERVING CONTRACT

### 2.1 Endpoints

| Endpoint | Grain | Usado por |
|----------|-------|-----------|
| `GET /ops/business-slice/daily` | daily | Omniview Matrix |
| `GET /ops/business-slice/weekly` | weekly | Omniview Matrix |
| `GET /ops/business-slice/monthly` | monthly | Omniview Matrix |
| `GET /ops/business-slice/matrix-operational-trust` | all | Banner de confianza |

### 2.2 Field Mapping (API → Frontend)

| Métrica | API field | Frontend KPI key | UI render |
|---------|-----------|-----------------|-----------|
| Viajes | `trips_completed` | `trips_completed` | `fmtValue(delta.value)` |
| Revenue | `revenue_yego_net` | `revenue_yego_net` | `fmtValue(delta.value)` |
| Conductores | `active_drivers` | `active_drivers` | `fmtValue(delta.value)` |
| Ticket | `avg_ticket` | `avg_ticket` | `fmtValue(delta.value)` |
| TPD | `trips_per_driver` | `trips_per_driver` | `fmtValue(delta.value)` |
| Confianza | `operational_decision.confidence` (object) | N/A | `matrixTrust.operational_decision.confidence` |

---

## 3. FRONTEND RENDERING CONTRACT

### 3.1 Data pipeline

```
API response → rows[] → enrichRow() → buildMatrix() → Cell(delta.value) → fmtValue()
```

Todos los campos pasan sin transformación. No hay COALESCE, fallback, ni renaming en el frontend.

### 3.2 Bugs detectados

| # | Bug | Archivo:Línea | Severidad |
|---|-----|--------------|-----------|
| B1 | **Confianza `[object Object]%`** | `BusinessSliceOmniviewMatrix.jsx:1767` | **FAIL (F8)** |
| B2 | **Revenue usa `revenue_yego_net` pero debería usar `revenue_yego_final`** | `omniviewMatrixUtils.js:14,664,860` | **FAIL (F7)** |

### 3.3 B1 — Confianza [object Object]%

**Causa**: `BusinessSliceOmniviewMatrix.jsx:1767`:
```js
Confianza {matrixTrust?.operational_decision?.confidence != null
    ? `${matrixTrust.operational_decision.confidence}%`
    : '—'}
```
`confidence` es un objeto `{score, coverage, freshness, consistency}`. Al interpolarse en template string, JS llama `toString()` → `"[object Object]"`.

**Fix**: `${matrixTrust.operational_decision.confidence.score}%`

### 3.4 B2 — Revenue usa campo incorrecto

**Causa**: Todas las referencias a revenue en el frontend usan `revenue_yego_net`. Pero en las fact tables:
- `revenue_yego_net` = solo comisión real (NULL si no hay commission)
- `revenue_yego_final` = `COALESCE(revenue_yego_real, revenue_yego_proxy)` (best-effort)

**Datos**:
- day_fact: `revenue_yego_net` non-null en 775/8017 filas (9.7%), `revenue_yego_final` en 7498/8017 (93.5%)
- week_fact: `revenue_yego_net` en 981/1229 (79.8%), `revenue_yego_final` en 1221/1229 (99.3%)
- month_fact: `revenue_yego_net` en 41/331 (12.4%), `revenue_yego_final` en 262/331 (79.2%)

**Fix**: Frontend debe usar `revenue_yego_final` en lugar de `revenue_yego_net`, o el backend debe exponer `revenue_yego_final` y el frontend usar COALESCE.

---

## 4. MATRIZ GRAIN × METRIC

### 4.1 Resultados de reconciliación

| Grain | Metric | Serving has data | Coverage | Expected empty | Status | Root cause |
|-------|--------|-----------------|----------|---------------|--------|------------|
| daily | trips | Sí (Jun 1-2) | 25% | May 26-31 (data lost) | **FAIL** | day_fact data loss recurrence |
| daily | revenue | No | 0% | Todo NULL | **FAIL** | B2: usa `_net` en vez de `_final` |
| daily | drivers | Sí (Jun 1-2) | 25% | May 26-31 (data lost) | **FAIL** | day_fact data loss recurrence |
| daily | ticket | Sí (Jun 1-2) | 25% | May 26-31 (data lost) | **FAIL** | day_fact data loss recurrence |
| daily | tpd | Sí (Jun 1-2) | 25% | May 26-31 (data lost) | **FAIL** | day_fact data loss recurrence |
| weekly | trips | Sí (3 weeks) | 37.5% | S18-S22 (data lost) | **FAIL** | week_fact data loss recurrence |
| weekly | revenue | No | 0% | Todo NULL | **FAIL** | B2: usa `_net` en vez de `_final` |
| weekly | drivers | Sí (3 weeks) | 37.5% | S18-S22 (data lost) | **FAIL** | week_fact data loss recurrence |
| weekly | ticket | Sí (3 weeks) | 37.5% | S18-S22 (data lost) | **FAIL** | week_fact data loss recurrence |
| weekly | tpd | Sí (3 weeks) | 37.5% | S18-S22 (data lost) | **FAIL** | week_fact data loss recurrence |
| monthly | trips | Sí | 100% | — | **PASS** | — |
| monthly | revenue | Parcial | 50% | May, Apr (proxy gap) | **WARNING** | `_net` NULL en meses sin commission |
| monthly | drivers | Sí | 100% | — | **PASS** | — |
| monthly | ticket | Sí | 100% | — | **PASS** | — |
| monthly | tpd | Sí | 100% | — | **PASS** | — |
| all | confidence | Sí | 100% | — | **PASS** | B1 afecta render, no datos |

### 4.2 Resumen

| Estado | Count |
|--------|-------|
| PASS | 5 |
| WARNING | 1 |
| FAIL | 10 |

---

## 5. FINDINGS POR MÉTRICA

### Trips
- **Monthly**: 100% OK
- **Weekly**: 37.5% — S18-S22 missing (data loss recurrence)
- **Daily**: 25% — May 26-31 missing (data loss recurrence)
- **Causa**: Operacional — day_fact/week_fact data doesn't persist (patrón recurrente CF-H1L.1 → CF-H1L.5)
- **Capa**: Serving (datos existen en month_fact pero no en day/week)

### Revenue
- **Monthly**: 50% WARNING — `revenue_yego_net` NULL en meses históricos
- **Weekly/Daily**: 0% FAIL — `revenue_yego_net` es NULL en casi todas las filas
- **Causa**: B2 — Frontend lee `revenue_yego_net` (solo real commission) en vez de `revenue_yego_final` (real + proxy)
- **Capa**: **FRONTEND** (field selection incorrecto)

### Drivers
- **Monthly**: 100% OK
- **Weekly/Daily**: Igual que trips (data loss)
- **Causa**: Operacional — data loss

### Ticket
- **Monthly**: 100% OK
- **Weekly/Daily**: Igual que trips (data loss)
- **Causa**: Operacional — data loss

### TPD
- **Monthly**: 100% OK
- **Weekly/Daily**: Igual que trips (data loss)
- **Causa**: Operacional — data loss

---

## 6. FINDINGS POR TEMPORALIDAD

### Daily
- **FAIL masivo**: Solo 2 de 8 días con datos (Jun 1-2). May 26-31 sin datos.
- **Causa**: day_fact data loss. Los datos existen en month_fact (817K trips) pero no en day_fact.
- **Revenue**: 0% porque `revenue_yego_net` es NULL en day_fact.

### Weekly
- **FAIL**: Solo 3 de 8 semanas con datos. S18-S22 missing (patrón recurrente).
- **Causa**: week_fact data loss. El bug de staging fue corregido (CF-H1L.5) pero los datos se pierden entre refrescos.
- **Revenue**: 0% por misma razón que daily.

### Monthly
- **Mayormente OK**: 100% trips, drivers, ticket, TPD. 50% revenue por `_net` NULL.
- **Causa revenue**: `revenue_yego_net` es NULL en la serving view mensual cuando no hay commission real. `revenue_yego_final` existe pero no se expone consistentemente.

---

## 7. BUGS FRONTEND

| Bug | Severidad | Archivo | Línea |
|-----|-----------|---------|-------|
| Confianza `[object Object]%` | **P0** | `BusinessSliceOmniviewMatrix.jsx` | 1767 |
| Revenue usa `_net` en vez de `_final` | **P0** | `omniviewMatrixUtils.js` | 14,664,860 |

---

## 8. BUGS SERVING / COVERAGE

| Bug | Severidad | Descripción |
|-----|-----------|-------------|
| day_fact data loss | **P0** | Datos de Mayo 2026 desaparecen recurrentemente de day_fact |
| week_fact data loss | **P0** | Datos S18-S22 desaparecen recurrentemente (bug de staging corregido, pero recurre) |
| `revenue_yego_final` no expuesto en serving | **P1** | El frontend no puede leer `revenue_yego_final` porque no está en el payload |
| revenue_yego_net NULL en monthly serving | **P1** | 50% de meses históricos sin `revenue_yego_net` en la serving view |

---

## 9. EXPECTED EMPTY CASES

| Caso | Esperado | Estado |
|------|----------|--------|
| Períodos futuros (sin datos) | `—` placeholder | Correcto |
| Períodos sin plan (proyección) | `Sin plan` | Correcto si < 30% columnas |
| Período actual parcial (hoy/semana/mes en curso) | Datos parciales con indicador `~` | Correcto |
| Revenue cuando no hay commission | Debería mostrar `revenue_yego_final` (proxy) | **FAIL** — muestra `_net` NULL |
| Días sin operación (ej: festivo) | `—` | Correcto si realmente 0 viajes |

---

## 10. BACKLOG PRIORIZADO

### P0 — Bloquea GO visual

| ID | Descripción | Capa |
|----|-------------|------|
| OMNI-COV-006-B1 | Confianza `[object Object]%` — fix `confidence.score` | Frontend |
| OMNI-COV-006-B2 | Revenue usa `revenue_yego_net` en vez de `_final` | Frontend + Backend |
| OMNI-COV-006-B3 | day_fact data loss recurrente | Operacional/Scheduler |
| OMNI-COV-006-B4 | week_fact data loss recurrente | Operacional/Scheduler |

### P1 — No bloquea GO pero degrada UX

| ID | Descripción | Capa |
|----|-------------|------|
| OMNI-COV-006-W1 | `revenue_yego_final` no expuesto en API payload | Backend |
| OMNI-COV-006-W2 | Monthly revenue 50% cobertura histórica | Serving |
| OMNI-COV-006-W3 | "Sin plan" masivo en proyección futura | Plan data |

### P2 — Mejoras

| ID | Descripción |
|----|-------------|
| OMNI-COV-006-P2 | Unificar `revenue_yego_net`/`_final` en un solo campo canónico |
| OMNI-COV-006-P2 | Frontend COALESCE fallback para métricas con múltiples fuentes |

---

## 11. VEREDICTO

### NO GO

**Justificación**: 10 FAIL bloqueantes.

| FAIL | Tipo | Capa |
|------|------|------|
| 5 FAIL daily (todas las métricas) | day_fact data loss | Serving |
| 5 FAIL weekly (todas las métricas) | week_fact data loss | Serving |
| Revenue 0% daily/weekly | B2: campo incorrecto | Frontend |
| Confianza `[object Object]%` | B1: acceso incorrecto a objeto | Frontend |

**Condiciones para GO**:
1. Restaurar day_fact y week_fact (refresh)
2. Corregir B1: `confidence.score` en línea 1767
3. Corregir B2: usar `revenue_yego_final` o añadir COALESCE en frontend/API
4. Re-ejecutar este script → 0 FAIL

---

## 12. ARCHIVOS CREADOS/MODIFICADOS

| Archivo | Acción |
|---------|--------|
| `backend/scripts/audit_omniview_ui_serving_reconciliation.py` | **NUEVO** — script read-only de reconciliación |
| `docs/omniview/UI_SERVING_RECONCILIATION_AUDIT.md` | **NUEVO** — este documento |

---

## 13. PRÓXIMO PROMPT RECOMENDADO

**OMNI-COV-006-FIX — Corrección de FAIL bloqueantes**: Corregir B1 (confianza) y B2 (revenue), restaurar day_fact/week_fact, re-ejecutar reconciliación. Sin abrir Diagnostic. Sin tocar KPI layer.

---

**END OF REPORT**
