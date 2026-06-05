# OMNI-P0 — VS PROY DATA COVERAGE MATRIX

**Motor:** Omniview Governance — P0 Recovery
**Fecha:** 2026-06-04
**Estado:** AUDITORÍA COMPLETADA

---

## 1. FUENTES DE DATOS

### 1.1 Endpoints de Vs Proy

| Endpoint | Grain | Datos que sirve |
|----------|-------|-----------------|
| `/ops/business-slice/omniview-projection` | daily, weekly, monthly | Plan + Real + Proyección unificada |
| `/ops/business-slice/omniview-projection/serving-plan-versions` | all | Versiones de plan disponibles |
| `/ops/business-slice/matrix-operational-trust` | all | Trust operacional |

### 1.2 Campo de revenue en Vs Proy

Vs Proy usa `revenue_yego_net` como KPI key (`PROJECTION_KPIS = ['trips_completed', 'revenue_yego_net', 'active_drivers']`), pero el backend aplica `COALESCE(revenue_yego_final, revenue_yego_net)` en queries de fact tables (`business_slice_omniview_service.py:656`).

---

## 2. MATRIZ GRAIN × MÉTRICA — COBERTURA VS PROY

### 2.1 Daily

| Grain | Métrica | Real Coverage | Plan Coverage | Projection Coverage | UI Coverage | Status |
|-------|---------|---------------|---------------|---------------------|-------------|--------|
| Daily | Trips | 25% (solo Jun 1-2) | Depende de plan cargado | Depende de proyección activa | 25% | **FAIL — data loss day_fact** |
| Daily | Revenue | 0% — `_final` NULL en day_fact por data loss | Depende de plan | Depende de proyección | 0% | **FAIL — data loss + campo** |
| Daily | Drivers | 25% (solo Jun 1-2) | Depende de plan | Depende de proyección | 25% | **FAIL — data loss** |
| Daily | Ticket | 25% (solo Jun 1-2) | Depende de plan | Depende de proyección | 25% | **FAIL — data loss** |
| Daily | TPD | 25% (solo Jun 1-2) | Depende de plan | Depende de proyección | 25% | **FAIL — data loss** |

**Root cause**: `day_fact` data loss recurrente. Datos de Mayo 26-31 desaparecen y solo persisten Jun 1-2.

### 2.2 Weekly

| Grain | Métrica | Real Coverage | Plan Coverage | Projection Coverage | UI Coverage | Status |
|-------|---------|---------------|---------------|---------------------|-------------|--------|
| Weekly | Trips | 37.5% (3 de 8 semanas) | Depende de plan | Depende de proyección | 37.5% | **FAIL — data loss week_fact** |
| Weekly | Revenue | 0% — `_final` NULL por data loss | Depende de plan | Depende de proyección | 0% | **FAIL — data loss + campo** |
| Weekly | Drivers | 37.5% | Depende de plan | Depende de proyección | 37.5% | **FAIL — data loss** |
| Weekly | Ticket | 37.5% | Depende de plan | Depende de proyección | 37.5% | **FAIL — data loss** |
| Weekly | TPD | 37.5% | Depende de plan | Depende de proyección | 37.5% | **FAIL — data loss** |

**Root cause**: `week_fact` data loss recurrente. S18-S22 desaparecen. Bug de staging corregido en CF-H1L.5 pero recurre.

### 2.3 Monthly

| Grain | Métrica | Real Coverage | Plan Coverage | Projection Coverage | UI Coverage | Status |
|-------|---------|---------------|---------------|---------------------|-------------|--------|
| Monthly | Trips | **100%** | Depende de plan | Depende de proyección | 100% | **PASS** |
| Monthly | Revenue | **50%** — `_net` NULL en meses sin commission | Depende de plan | Depende de proyección | 50% | **WARNING — `_final` debe exponerse mejor** |
| Monthly | Drivers | **100%** | Depende de plan | Depende de proyección | 100% | **PASS** |
| Monthly | Ticket | **100%** | Depende de plan | Depende de proyección | 100% | **PASS** |
| Monthly | TPD | **100%** | Depende de plan | Depende de proyección | 100% | **PASS** |

**Root cause Revenue 50%**: `revenue_yego_net` es NULL en serving view mensual cuando no hay commission real histórica. `revenue_yego_final` existe en `ops.real_business_slice_month_fact` (`backend:799` LEFT JOIN) pero no se expone consistentemente en el serving layer.

---

## 3. CLASIFICACIÓN DE VACÍOS

### 3.1 Falta de dato real

| Tipo | Métricas | Grains | Causa |
|------|----------|--------|-------|
| **Data loss day_fact** | trips, drivers, ticket, tpd | daily | CF-H1L.1 → CF-H1L.5: day_fact data no persiste. Mayo 26-31 perdido. |
| **Data loss week_fact** | trips, drivers, ticket, tpd | weekly | CF-H1L.5: week_fact data no persiste. S18-S22 perdido. |
| **Revenue `_net` NULL** | revenue | daily, weekly | Data loss + `revenue_yego_net` depende de `comision_empresa_asociada` |
| **Revenue `_final` no expuesto** | revenue | monthly (parcial) | `_final` en `month_fact` pero no en serving view consistente |

### 3.2 Falta de plan

| Condición | Impacto |
|-----------|---------|
| Sin plan cargado | Celdas muestran `—` o "Sin plan" en Vs Proy |
| Plan cargado solo para ciertos meses | Columnas sin plan muestran badge "SIN PLAN" |
| Plan versión incorrecta | Usuario debe seleccionar `planVersion` desde `ProjectionVersionSelector` |

El plan depende del usuario (carga manual). No es bug de sistema.

### 3.3 Falta de proyección

| Condición | Impacto |
|-----------|---------|
| Sin proyección activa | Vs Proy muestra "No hay proyección cargada" (L2168) |
| Proyección sin plan base | Muestra real solamente, sin attainment |

### 3.4 Bug frontend

| Bug | Estado | Impacto en Vs Proy |
|-----|--------|-------------------|
| B1: confidence `[object Object]%` | **FIXED** (confidence.score) | Afectaba trust badge, ya corregido |
| B2: revenue usa `_net` sin `_final` | **PARTIALLY FIXED** | `enrichRow()` en `omniviewMatrixUtils.js:615-617` aplica COALESCE, pero Evolution usa `revenue_yego_net` en `buildMatrix`. Vs Proy hereda el campo del backend que YA aplica COALESCE. El fix es efectivo para Vs Proy cuando los datos existen. |

### 3.5 Bug serving

| Bug | Estado | Impacto |
|-----|--------|---------|
| day_fact data loss | **ACTIVO** | Daily sin datos Mayo 26-31 |
| week_fact data loss | **ACTIVO** | Weekly sin datos S18-S22 |
| `revenue_yego_final` no en serving view mensual | **ACTIVO** | Monthly revenue 50% |
| Cross-grain data loss con refreshes standalone | **CONOCIDO** | Si se refresca solo un grain, se pierden los otros |

### 3.6 Expected empty

| Caso | Correcto? |
|------|-----------|
| Periodos futuros sin datos | Sí — `—` placeholder |
| Periodos sin plan | Sí — "Sin plan" badge |
| Días sin operación real (0 viajes) | Sí — mostrar 0, no `—` |
| Revenue sin commission histórica | **No** — debería mostrar `_final` (proxy) |

---

## 4. RESUMEN DE ESTADO

| Grain | Métricas con datos reales | % Cobertura | Bloquea GO? |
|-------|--------------------------|-------------|-------------|
| Daily | 0/5 completas | 25% max, 0% revenue | **Sí — P0** |
| Weekly | 0/5 completas | 37.5% max, 0% revenue | **Sí — P0** |
| Monthly | 4/5 completas | 100% (4/5), 50% revenue | **No directamente, pero WARNING** |

---

## 5. ACCIONES REQUERIDAS

### P0 — Bloquea GO

| # | Acción | Motor |
|---|--------|-------|
| 1 | Restaurar day_fact: refresh datos Mayo-Junio 2026 | Scheduler/Operaciones |
| 2 | Restaurar week_fact: refresh datos S17-S23 2026 | Scheduler/Operaciones |
| 3 | Verificar que `revenue_yego_final` tiene datos post-refresh | Backend |
| 4 | Re-ejecutar UI/Serving reconciliation → 0 FAIL | QA |

### P1 — No bloquea GO pero necesario

| # | Acción | Motor |
|---|--------|-------|
| 5 | Exponer `revenue_yego_final` consistentemente en serving view mensual | Backend |
| 6 | CF-H1L.9: Refresh Family Atomicity (evitar cross-grain data loss) | Infraestructura |
| 7 | CF-H1L.4: Freshness Confidence Score | Trust |

---

**END OF COVERAGE AUDIT**
