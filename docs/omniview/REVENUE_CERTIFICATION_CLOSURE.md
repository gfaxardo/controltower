# REVENUE CERTIFICATION CLOSURE — OMNIVIEW HARDENING O1-B

**Motor:** Control Foundation — Revenue Certification Closure  
**Fecha:** 2026-06-02  
**Fase:** O1-B — Formal Closure & Verdict  
**Script QA ejecutado:** SI  

---

## 0. GOVERNANCE PRECHECK

| Item | Value | Source |
|------|-------|--------|
| Fase ACTIVE | Diagnostic Engine 2A.3 (Behavioral Pattern Diagnosis) | `ai_current_phase.md:39` |
| Fase READY NEXT | Revenue Detail Certification (CF-H2) — independent track | `ai_current_phase.md:122-128` |
| Control Foundation | **CLOSED** (2026-06-02) | `ai_current_phase.md:16` |
| Motores bloqueados | Forecast, Suggestion, Decision, Action, AI Copilot, Learning | `ai_current_phase.md:88-101` |
| Restricciones | "DO NOT touch Revenue (separate certification track)" | `ai_current_phase.md:100` |
| Regla arquitectónica | UI must read from serving facts | `ai_operating_system.md:61-64` |
| O1 dejó | CONDITIONAL PASS: 40 PASS, 4 WARNING, 1 FAIL (cross-currency) | `REVENUE_CERTIFICATION.md:441-445` |

**Nota:** O1-B es el cierre de la certificación de Revenue. Es un track independiente (permitido por `ai_current_phase.md:128`). No modifica UI ni crea features.

---

## 1. REVENUE LINEAGE — FINAL (Source-Verified)

```
RAW SOURCE
  │  public.trips_2025 / trips_2026
  │  Columna: comision_empresa_asociada (commission cobrada al driver)
  │  NaN guard: NULLIF(col, 'NaN'::numeric) [migration 122:42]
  ▼
ENRICHED BASE (ops.v_real_trips_enriched_base)
  │  revenue_yego_net = NULLIF(comision_empresa_asociada, 0)
  │  ticket = precio_yango_pro
  │  total_fare = efectivo + tarjeta + pago_corporativo
  ▼
ENRICHED TEMP (_bs_enriched_month, incremental_load.py:974-1013)
  │  revenue_yego_real  = ABS(revenue_yego_net)  [completed + non-null only]
  │  revenue_yego_proxy = ticket * resolve_commission_pct(..., default 3%)
  │  revenue_yego_final = COALESCE(revenue_yego_real, revenue_yego_proxy)
  │  revenue_source     = 'real' | 'proxy' | 'missing'
  ▼
RESOLUTION CTE (incremental_load.py:146-289)
  │  Alias: b.revenue_yego_real AS revenue_yego_net  ← RENOMBRADO
  │  → "revenue_yego_net" en el CTE = real commission ABS (NO proxy)
  ▼
AGGREGATION + INSERT into fact tables (incremental_load.py:40-146)
  │  revenue_yego_net  = SUM(revenue_yego_real aliased) [line 85]
  │  revenue_yego_final = SUM(revenue_yego_final)       [line 124]
  │  → _net = solo real commission, NULL si no hay commission
  │  → _final = real + proxy (best effort completo)
  ▼
FACT TABLES
  │  ops.real_business_slice_day_fact    (daily)
  │  ops.real_business_slice_week_fact   (weekly)
  │  ops.real_business_slice_month_fact  (monthly)
  ▼
SERVING VIEW (ops.v_real_business_slice_month_serving, migration 143:69-147)
  │  revenue_yego_net: EXPUESTO (del fact table) ← NULL para Mar-May 2026
  │  revenue_yego_final: NO EXPUESTO (columna omitida en migration 143)
  ▼
API LAYER
  │  GET /ops/business-slice/monthly → FACT_MONTHLY = serving view
  │    revenue_yego_net = NULL (porque _net en fact es NULL)
  │  GET /ops/business-slice/omniview → business_slice_omniview_service.py
  │    revenue_yego_net = raw column (NULL) [line 660]
  │    completed_revenue_sum = COALESCE(_final, _net) [line 661] ← CORRECTO pero NO mapeado a revenue_yego_net
  │  GET /ops/business-slice/omniview-projection → projection service
  │    real_revenue = ABS(COALESCE(_final, _net)) [line 2656] ← CORRECTO
  ▼
FRONTEND
  │  omniviewMatrixUtils.js:664 → _revenue += Number(r.revenue_yego_net) || 0
  │  → Lee revenue_yego_net del API response = NULL → 0
  │  projectionMatrixUtils.js:438 → tb[kpi].actual += Number(raw[kpi]) || 0
  │  → projection usa real_revenue (correcto)
```

---

## 2. METRIC INVENTORY — STATUS PER COLUMN

| Métrica | Existe? | Dónde se calcula | Omniview? | Status | Observación |
|---------|---------|-----------------|-----------|--------|-------------|
| `revenue_yego_net` (fact table) | SI | `incremental_load.py:85` | SI | **BUG** | Almacena solo real commission (ABS), NO proxy. NULL cuando commission=NULL. |
| `revenue_yego_final` (fact table) | SI | `incremental_load.py:124` | NO (indirecto) | **Canonical** | COALESCE(real, proxy). Valor correcto para revenue. |
| `revenue_yego_net` (serving view) | SI | `migration 143:97,132` | SI | **BUG** | Propaga el valor NULL del fact table. No tiene fallback a _final. |
| `revenue_yego_final` (serving view) | **NO** | migration 143 lo omite | **NO** | **WARNING** | Columna ausente. COALESCE fallback no disponible desde serving view. |
| `completed_revenue_sum` (Omniview API) | SI | `omniview_service.py:661` | NO (no consumido) | **Correcto** | COALESCE(_final, _net) → correcto. Pero frontend NO lo lee. |
| `real_revenue` (Projection API) | SI | `projection_service.py:2656` | SI (proyeccion) | **Correcto** | ABS(COALESCE(_final, _net)) → valor correcto. |
| `revenue_total` | NO | — | NO | **N/A** | No existe como columna real. |
| `revenue_display` | NO | — | NO | **N/A** | No existe en el codebase. |
| `gross_revenue` (LOB) | SI | migration 122:229 | SI (LOB) | **Legacy** | Via hourly-first (v_real_trip_fact_v2). |
| `margin_total` (LOB) | SI | migration 122:231 | SI (LOB) | **Legacy** | Via hourly-first. |

---

## 3. GRAIN CERTIFICATION

| Capa | Grain | Columnas de agrupacion | Status |
|------|-------|----------------------|--------|
| Source (RAW) | Trip individual | `(trip_id)` | **PASS** |
| Enriched Base | Trip individual | `(trip_id)` via DISTINCT ON | **PASS** |
| Enriched Temp | Trip individual | `(trip_id)` | **PASS** |
| Resolution CTE | Trip → Slice | `(trip_id)` → `(business_slice_name, fleet, subfleet)` | **PASS** |
| Day Fact | Daily | `(trip_date, country, city, slice, fleet, subfleet)` | **PASS** |
| Week Fact | Weekly (ISO Monday) | `(week_start, country, city, slice, fleet, subfleet)` | **PASS** |
| Month Fact | Monthly | `(month, country, city, slice, fleet, subfleet)` | **PASS** |
| API Matrix | Monthly/Weekly/Daily | Segun endpoint | **PASS** |
| UI Matrix | Igual al API | Misma granularidad | **PASS** |

**Riesgo de suma de sumas:** No detectado para revenue. Las fact tables son aditivas puras para revenue_yego_final. El `revenue_yego_net` en fact es aditivo solo cuando tiene datos (pre-Mar 2026).

---

## 4. FILTER AUDIT

| Filtro | Endpoint | Leakage? | Status |
|--------|----------|----------|--------|
| country | Todos (opcional) | Monedas mixtas sin conversion | **FAIL** |
| city | Todos (opcional) | Sin leakage | **PASS** |
| business_slice | Todos (opcional) | Correcto, UNMAPPED excluido intencionalmente | **PASS** |
| fleet/subfleet | Omniview API | `is_subfleet IS NOT TRUE` por defecto | **PASS** |
| month/year | Monthly/W+D+Projection | Periodos cerrados correctamente manejados | **PASS** |
| period state | Serving view | Snapshot para locked, working_fact para open | **PASS** |

**Cross-currency:** PEN (Peru) + COP (Colombia) sumados sin conversion cuando country filter = null. Confirmado con data: 2 paises activos.

---

## 5. QA SCRIPT RESULTS — EXECUTED 2026-06-02

Script: `backend/scripts/validate_omniview_revenue_certification.py`  
Exit code: 1 (blocking FAILs found)

| # | Check | Status | Evidence |
|---|-------|--------|----------|
| 1.1 | Monthly revenue | **FAIL** | NULL in months 2026-04, 2026-05 |
| 1.2 | Weekly revenue | PASS | 3 weeks, total=0 |
| 1.3 | Daily revenue | PASS | 14 days, total=0 |
| 1.4 | Daily→Monthly grain | **WARNING** | Jan: daily=107M, monthly=-107M; Feb: daily=58M, monthly=-58M |
| 2.1 | Revenue by city | **FAIL** | 8 cities with NULL revenue_yego_net; 1 city with data > 0 |
| 2.2 | Multi-currency | **WARNING** | 2 countries: peru, colombia |
| 3.1 | Revenue by slice | PASS | 8 slices, total=0 |
| 3.2 | Slice mapping coverage | PASS | 100% mapped, UNMAPPED=0% |
| 4.1 | Revenue by park | PASS | N/A via fact tables; use hourly-first |
| 5.1 | _net vs _final in month_fact | PASS | Max diff = 0 (consistent where both non-null) |
| 5.2 | _final in serving view | **WARNING** | Column NOT in serving view |
| 5.3-5.4 | KPI semantics/rules | PASS | Correctly registered |
| 6.1 | Month total vs row sum | PASS | Identical |
| 6.2 | Negative revenue | **FAIL** | 39 rows with revenue_yego_net < 0 |
| 7.1 | Serving view vs month_fact | PASS | Identical (both 0 for last month) |
| 7.2 | Forbidden sources | PASS | 5 sources blocked in strict mode |
| 8.1 | month_fact._net NULL | **FAIL** | 65/66 NULLs (98.5%) |
| 8.2 | day_fact._net NULL | **FAIL** | 1222/1223 NULLs (99.9%) |
| 8.3 | week_fact._net NULL | **FAIL** | 124/204 NULLs (60.8%) |
| 8.4 | NaN in RAW | **FAIL** | 3 trips with NaN in commission/precio |
| 9.1 | Cross-slice SUM identity | PASS | SUM(GROUP BY) = SUM(all): -165M |
| 9.2 | UNMATCHED overlap | PASS | No overlap |
| 9.3 | active_drivers SUM | **WARNING** | Overcount documented, non-revenue |
| 10.1 | Country filter integrity | PASS | Global = SUM(countries) |
| 10.2 | Cross-currency aggregation | **WARNING** | PEN+COP mixed |
| 10.3 | Subfleet filter | PASS | No data to compare |

**Totals: 16 PASS | 7 WARNING | 7 FAIL**

---

## 6. CRITICAL FINDINGS — DATA ARCHITECTURE

### F-01: `revenue_yego_net` IS NULL IN FACT TABLES (Mar-May 2026)

**Root cause chain:**

1. `comision_empresa_asociada` in source trips IS NULL for many trips (reason: upstream data)
2. Enriched temp: `revenue_yego_real = ABS(revenue_yego_net)` only when `revenue_yego_net IS NOT NULL`
3. Resolution CTE aliases: `revenue_yego_real AS revenue_yego_net` (incremental_load.py:174)
4. Fact INSERT: `SUM(revenue_yego_real aliased) AS revenue_yego_net` (line 85)
5. Result: `revenue_yego_net` in fact = NULL when all trips have NULL commission
6. Meanwhile: `revenue_yego_final = COALESCE(real, proxy)` IS populated via proxy
7. **`revenue_yego_final` has data, `revenue_yego_net` is NULL**

**Data evidence:**

| Month | revenue_yego_net (non-null) | revenue_yego_final (non-null) | Total _final |
|-------|---------------------------|----------------------------|-------------|
| 2026-01 | 20/20 (100%) | 0/20 (0%) | NULL (old pipeline) |
| 2026-02 | 19/20 (95%) | 0/20 (0%) | NULL (transitional) |
| 2026-03 | 1/20 (5%) | 20/20 (100%) | NaN (new pipeline) |
| 2026-04 | 0/23 (0%) | 23/23 (100%) | 108M |
| 2026-05 | 0/23 (0%) | 23/23 (100%) | 110M |

**Impact:** The correct revenue data exists in `revenue_yego_final` but is invisible to any code path that reads `revenue_yego_net` without COALESCE.

### F-02: REVENUE SHOWN AS ZERO IN OMNIVIEW MATRIX UI

**Chain:**

1. Omniview API returns `revenue_yego_net` = raw column from fact (NULL for recent months)
2. Frontend reads `r.revenue_yego_net` → NULL
3. `Number(null) || 0 = 0`
4. **Revenue cell shows 0** even though `completed_revenue_sum` (COALESCE) has the correct value

**Code evidence:**
- `business_slice_omniview_service.py:660`: `revenue_yego_net,` (raw NULL column)
- `business_slice_omniview_service.py:661`: `COALESCE(...) AS completed_revenue_sum` (correct, not consumed by frontend)
- `omniviewMatrixUtils.js:664`: `_revenue += Number(r.revenue_yego_net) || 0`

**Lost revenue for last 7 days (day_fact):**  
`coalesce=3,535,722 net_only=0 final_only=3,535,722`  
→ UI shows 0 instead of 3.5M

### F-03: OLD DATA (Jan-Feb 2026) HAS NEGATIVE REVENUE

- Month 2026-01: `revenue_yego_net` = -107M (negative!)
- Month 2026-02: `revenue_yego_net` = -58M (negative!)
- These months used the OLD pipeline (before proxy was introduced)
- The commission was stored RAW without ABS
- `revenue_yego_final` is NULL for these months (not computed by old pipeline)
- Daily→Monthly grain drift = 200% (daily is positive 107M, monthly is negative 107M)

### F-04: NaN IN `revenue_yego_final` (Mar 2026)

- `peru/lima/Tuk Tuk`: `_net=0.20 _final=NaN` for 28K trips
- 3 RAW trips with NaN in commission/precio_yango_pro
- NaN guard exists in migration 122 but some trips escaped upstream

### F-05: `revenue_yego_final` MISSING FROM SERVING VIEW

- migration 143:97,132 only exposes `revenue_yego_net` (NULL for recent months)
- `revenue_yego_final` is NOT in the serving view column list
- The API fallback depends on query-time COALESCE, not available from serving view direct reads

---

## 7. WARNINGS (Non-Blocking)

| ID | Area | Description |
|----|------|-------------|
| W-01 | Serving View | `revenue_yego_final` not propagated to `v_real_business_slice_month_serving` |
| W-02 | Period Totals | `SUM(active_drivers)` overcounts unique drivers cross-slice |
| W-03 | UI | Multi-currency revenue (PEN+COP) mixed without conversion |
| W-04 | YTD | `meta.ytd_real_revenue` aggregates without currency distinction |
| W-05 | Jan-Feb 2026 | Historical data has negative revenue (old pipeline, no ABS) |
| W-06 | NaN | 3 raw trips + 1 slice have NaN in revenue_yego_final |
| W-07 | Grain drift | Jan-Feb daily vs monthly show 200% drift (negative sign mismatch) |

---

## 8. RISKS

| Riesgo | Severidad | Descripcion |
|--------|----------|-------------|
| Revenue invisible en UI | **CRITICAL** | Frontend muestra 0 en lugar de 108M+ mensuales para datos recientes |
| Datos historicos con signo | HIGH | Jan-Feb 2026 tienen revenue negativo (sin ABS) |
| Column naming misleading | HIGH | `revenue_yego_net` no contiene el valor neto completo |
| NaN en serving | MEDIUM | 1 slice con revenue_yego_final=NaN para 28K viajes |
| Serving view incompleta | MEDIUM | Sin `revenue_yego_final`, COALESCE fallback depende del query SQL |
| Monedas mezcladas | MEDIUM | PEN + COP en totals globales sin conversion |

---

## 9. RECOMMENDATIONS (Post-Audit, No Correction Yet)

| ID | Priority | Area | Recommendation |
|----|----------|------|---------------|
| REC-01 | **CRITICAL** | Omniview API | Fix `business_slice_omniview_service.py:660`: return `COALESCE(revenue_yego_final, revenue_yego_net) AS revenue_yego_net` instead of raw `revenue_yego_net` |
| REC-02 | **CRITICAL** | Fact table injection | Fix `business_slice_incremental_load.py:85`: set `revenue_yego_net = SUM(revenue_yego_final)` (use final value) OR rename columns to `revenue_yego_real` vs `revenue_yego_final` |
| REC-03 | HIGH | Serving view | Add `revenue_yego_final` column to `v_real_business_slice_month_serving` |
| REC-04 | HIGH | Historical data | Reprocess Jan-Feb 2026 with ABS pipeline to fix negative revenue |
| REC-05 | MEDIUM | NaN | Add NaN guard in `_bs_enriched_month` temp table for `revenue_yego_proxy` |
| REC-06 | MEDIUM | UI totals | Require `country` filter for global totals to prevent currency mixing |
| REC-07 | MEDIUM | Data audit | Run `validate_revenue_consolidation.py` to reconcile old vs new pipeline data |
| REC-08 | LOW | active_drivers | Document that `SUM(active_drivers)` is approximate for cross-slice totals |

---

## 10. VEREDICT FINAL

### VERDICT: **NO GO**

**Motivo:** Existen diferencias no explicadas y bloqueantes entre capas del revenue pipeline que afectan directamente lo que el usuario ve en Omniview:

1. **Revenue mostrado en UI VS revenue real:** El Omniview Matrix muestra 0 (via `revenue_yego_net` NULL) cuando los datos reales en `revenue_yego_final` contienen 108M+ por mes. Diferencia: 100% de los datos recientes.

2. **Revenue Header VS Matrix:** El KPI header define `revenue_yego_net` como additive decision_ready. La Matrix lee `revenue_yego_net` del API. Pero la columna en la DB es NULL → 0 en UI → el header dice "decision_ready" pero el dato es incorrecto.

3. **Revenue por ciudad:** 8 de 9 ciudades muestran revenue_yego_net = NULL para meses recientes. Solo 1 ciudad tiene dato > 0.

4. **Revenue historico VS reciente:** Jan-Feb muestra revenue negativo (-165M total) mientras Mar-May muestra revenue en `_final` pero NULL en `_net`. Inconsistencia de pipeline entre periodos.

5. **Serving fact VS API:** La serving view expone `revenue_yego_net` (NULL) pero omite `revenue_yego_final` (que tiene los datos). La API no puede reconstruir el valor correcto desde la serving view.

**NO se alcanza GO porque:**
- Revenue desaparece en la UI para datos recientes (check 8.1/8.2/8.3: FAIL)
- El revenue historico esta corrupto (check 6.2: FAIL, 1.4: WARNING)
- La columna canonica `revenue_yego_net` no contiene el valor que su nombre indica
- Las diferencias NO estan explicadas en la documentacion previa
- El FAIL de O1 (cross-currency) persiste sin mitigacion

---

## 11. ARCHIVOS CREADOS/MODIFICADOS

| Archivo | Accion | Proposito |
|---------|--------|-----------|
| `REVENUE_CERTIFICATION.md` | Modificado | Certificacion O1 actualizada con evidencias source-verified |
| `backend/scripts/validate_omniview_revenue_certification.py` | Creado | Script QA ejecutable con 28 checks contra PostgreSQL |
| `backend/scripts/_diagnose_revenue_null.py` | Creado | Diagnostico profundo de la brecha _net vs _final |
| `docs/omniview/REVENUE_CERTIFICATION_CLOSURE.md` | Creado | Este documento — cierre formal con veredicto |

---

## 12. COMANDOS EJECUTADOS

```bash
cd backend
python -m scripts.validate_omniview_revenue_certification
# → Exit code 1, 16 PASS, 7 WARNING, 7 FAIL

python -m scripts._diagnose_revenue_null
# → Confirmo: revenue_yego_net NULL 99%, _final poblado, 121M "lost revenue"
```

---

## 13. PROXIMO PASO RECOMENDADO

**Fase O2 — Revenue Repair:** Corregir los FAILs bloqueantes antes de re-certificar.

Prioridad:
1. Fix `business_slice_omniview_service.py:660` — mapear COALESCE a `revenue_yego_net` en la respuesta API
2. Fix `business_slice_incremental_load.py:85` — alinear `revenue_yego_net` con `revenue_yego_final` en la injection
3. Regenerar datos Jan-Feb 2026 con ABS pipeline
4. Agregar `revenue_yego_final` a la serving view
5. Agregar NaN guard para `revenue_yego_proxy`
6. Re-ejecutar script QA → verificar PASS completo → re-certificar como GO

---

**Timestamp:** 2026-06-02 19:10 UTC-5  
**Veredicto:** **NO GO** — 7 FAILs bloqueantes, revenue invisible en UI para datos recientes  
**Re-certificacion requerida despues de O2 Repair**
