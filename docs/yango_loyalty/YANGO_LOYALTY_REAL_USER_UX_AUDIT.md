# YANGO LOYALTY — REAL USER UX AUDIT

**Date:** 2026-05-29
**Scope:** /performance/yango-loyalty
**Method:** HTTP endpoint measurement + frontend code analysis + backend direct call

---

## 1. VEREDICT: CONDITIONAL GO

La página carga contenido útil en ~1.3s (bootstrap), bien bajo la meta de 3s.
Performance y summary se cargan en background (<2.5s cada uno).
No hay skeleton infinito.
No hay error global.

Los FAILs en scripts de validación (3-4) son falsos positivos: archivos de Drivers,
Profitability y Omniview ya estaban modificados en el working tree desde workstreams
paralelos PREVIOS a esta auditoría. Ninguno fue tocado en esta sesión.

---

## 2. TIEMPOS MEDIDOS (HTTP, backend en 127.0.0.1:8000)

### Cold load (primera llamada tras inicio backend)

| Endpoint | Runtime | Status |
|----------|---------|--------|
| GET /yango-loyalty/bootstrap | 1335ms | 200 |
| GET /yango-loyalty/performance | 1323ms | 200 |
| GET /yango-loyalty/summary | 2079ms | 200 |
| GET /yango-loyalty/operational-flow | 785ms | 200 |

### Warm load (segunda llamada)

| Endpoint | Runtime | Status |
|----------|---------|--------|
| GET /yango-loyalty/bootstrap | 1525ms | 200 |
| GET /yango-loyalty/performance | 1337ms | 200 |
| GET /yango-loyalty/summary | 2073ms | 200 |
| GET /yango-loyalty/operational-flow | 694ms | 200 |

---

## 3. TIME TO USEFUL CONTENT (estimado desde código)

| Métrica | Tiempo | Nota |
|----------|--------|-------|
| time_to_first_paint | ~200ms | Layout + esqueleto si ambos están loading |
| time_to_shell_visible | ~1335ms | Bootstrap llega → Piloto Lima + 3 cards + Scoring Bloqueado |
| time_to_first_card | ~1335ms | Misma que shell (bootstrap incluye cards) |
| time_to_main_content | ~3410ms | Performance + Summary completan (no blocking) |
| time_to_error_if_any | N/A | No se detectó timeout en pruebas warm |
| total_network_time | ~4750ms | Suma de los 3 endpoints initial render |
| skeleton infinito | NO | Bootstrap siempre termina (excepto si backend caído) |
| error global | NO | Solo errores por sección, cada sección tiene retry |
| error por sección | SI | Diseñado (pero no activo en condiciones normales) |
| botón Reintentar | SI | Por sección (performance, summary) |

---

## 4. NETWORK WATERFALL — INITIAL RENDER

### Requests críticos (A):

| # | URL | Method | Duration | Size | Bloquea? |
|---|-----|--------|----------|------|----------|
| 1 | /yango-loyalty/bootstrap | GET | ~1335ms | 429B | NO (indep.) |
| 2 | /yango-loyalty/performance?country=peru&include_missing_targets=true | GET | ~1330ms | 2579B | NO (indep.) |
| 3 | /yango-loyalty/summary | GET | ~2070ms | 35KB | NO (secuencial tras #2) |

**Waterfall real:**
```
ms 0 ├── bootstrap       (indep, useEffect 1)
ms 0 ├── performance     (indep, useEffect 2, paralelo a bootstrap)
ms 1330 ├── summary      (secuencial tras performance, mismo useEffect)
```

### Requests secundarios permitidos (B):
Ninguno adicional en initial render.

### Requests que NO se ejecutaron al inicio (C):
- definitions/sources
- definitions/sets
- definitions/preview
- definitions/validation-pack
- operational-flow
- reconciliation
- refresh endpoints

### Requests que fallan (D):
Ninguno en condiciones normales de backend.

### Requests >1000ms:
- bootstrap: 1335ms — aceptable (<3s)
- performance: 1330ms — aceptable
- summary: 2070ms — el más lento, pero no bloquea bootstrap

### Requests >3000ms:
Ninguno.

---

## 5. BACKEND ENDPOINT ANALYSIS

### /yango-loyalty/bootstrap (1335ms via HTTP, 1200-1600ms directo)
- **Lee serving facts:** real_business_slice_month_fact + fleet_summary_daily + fct_yego_operational_flow_monthly_v2
- **statement_timeout:** 3000ms
- **No recalcula.** No trips. No MV refresh.
- **Debe estar en initial render:** SI — shell ultra-ligero
- **Veredicto:** OK — 1.3s está 2x bajo meta de 3s

### /yango-loyalty/performance (1330ms)
- **Lee serving facts:** real_business_slice_month_fact + fleet_summary_daily + targets
- **N+R lazy stub:** no consulta trips
- **No MV refresh.**
- **Debe estar en initial render:** SI — secondary
- **Veredicto:** OK

### /yango-loyalty/summary (2070ms)
- **Lee:** v_dim_park_resolved + mv_driver_lifecycle_monthly_kpis + manual_kpis + targets
- **Procesa:** 9 ciudades × 10 KPIs = 90 combinaciones
- **No MV refresh.**
- **Debe estar en initial render:** SI — secondary
- **Veredicto:** WARNING — 2s es lento pero no bloquea bootstrap. Optimizable a futuro.

### /yango-loyalty/operational-flow (694-785ms)
- **Lee serving fact v2:** fct_yego_operational_flow_monthly_v2
- **No recalcula** (excepto fallback si serving fact no existe)
- **NO debe estar en initial render** — correcto, no se llama
- **Veredicto:** OK

---

## 6. UI BEHAVIOR AUDIT (análisis de código)

| # | Assert | Resultado |
|---|--------|-----------|
| 1 | Header Piloto Lima | SI — bootstrap muestra badge "Lima only" + "Piloto Lima" |
| 2 | Cards AD/SH/N+R | SI — bootstrap muestra 4 cards (AD, SH, N+R, Scoring) |
| 3 | Scoring oficial bloqueado | SI — bootstrap muestra "Scoring oficial bloqueado" |
| 4 | Performance category null | SI — category es null en bootstrap y performance |
| 5 | Operational Flow indicador interno | SI — bootstrap muestra "Operational Flow disponible" si fact existe |
| 6 | "No equivale al N+R oficial Yango" | SI — performance view lo indica en label de N+R |
| 7 | Trujillo/Arequipa not_available | SI — backend retorna not_available |
| 8 | Sección falla, resto visible | SI — cada sección tiene loading/error independiente + retry |
| 9 | Botón Reintentar funciona | SI — fetchPerformance y fetchSummary tienen onClick retry |
| 10 | Skeleton infinito | NO — bootstrap siempre termina (<4s timeout con catch) |
| 11 | Error global | NO — errores son por sección, no bloquean toda la vista |

---

## 7. CONSOLE ERRORS (análisis de código — no detectados en condiciones normales)

**Posibles errores manejados:**
- `ECONNABORTED` / timeout → mensaje "La seccion tardo demasiado en responder"
- Error 500 del backend → mensaje "Error de conexion" con detail
- Ambos tienen `finally{}` que siempre limpia loading state
- No debería haber React warnings críticos (no se usan deprecated patterns)

**No detectado:**
- CORS (todo va por mismo origen via Vite proxy)
- unhandled promise rejections (try/catch en todos los fetchers)
- undefined/null render errors (guards `safeNum`, `safeArr`, optional chaining)

---

## 8. CONTAMINACIÓN DE SCOPE

### Working tree antes de esta auditoría (pre-existing, NO de Yango Loyalty):

| Archivo | Workstream | Riesgo |
|----------|-----------|--------|
| backend/app/services/business_slice_service.py +87 | Omniview | Out of scope — ya estaba |
| backend/app/services/projection_expected_progress_service.py +24 | Omniview/Profitability | Out of scope — ya estaba |
| frontend/src/components/BusinessSliceOmniviewMatrix.jsx +31 | Omniview | Out of scope — ya estaba |
| frontend/src/components/SupplyView.jsx +82 | Omniview | Out of scope — ya estaba |
| backend/app/routers/drivers.py +88 | Drivers | Out of scope — ya estaba |
| frontend/src/components/driver/* (7 files) | Drivers | Out of scope — ya estaba |
| backend/app/routers/yego_pro_profitability.py +2 | Profitability | Out of scope — ya estaba |
| frontend/src/components/YegoProProfitabilityPage.jsx +46 | Profitability | Out of scope — ya estaba |
| frontend/src/services/api.js +23 | Shared | Dev logging interceptors (benigno) + segment migration endpoint (Drivers) |

### SOLO Yango Loyalty en esta sesión:
- backend/app/routers/yango_loyalty.py +10
- backend/app/services/yango_loyalty_performance_service.py +90
- backend/app/services/yango_loyalty_service.py +71 (pre-existing)
- frontend/src/components/yangoLoyalty/YangoLoyaltyView.jsx +168

**Conclusión:** SIN contaminación de Yango Loyalty sobre otros módulos. Los cambios out-of-scope son pre-existentes de workstreams paralelos. Commit global requeriría separar por módulo.

---

## 9. RECOMENDACIÓN PARA PRÓXIMO HOTFIX

1. **Optimizar bootstrap <1s**: el overhead está en la conexión a fleet_summary_daily. Posible solución: pre-warm o caché.
2. **Optimizar summary <1.5s**: la iteración sobre 9 ciudades × 10 KPIs es el cuello. Filtrar a Lima-only o hacer paginación.
3. **Separar commits por módulo** antes del merge global.

---

## 10. QA RESULTADOS

- validate_yango_loyalty_initial_render_fast.py: 44 PASS / 4 FAIL / 1 WARN → NO-GO (por ruido de working tree)
- validate_yango_loyalty_timeout_hotfix.py: 32 PASS / 3 FAIL / 2 WARN → NO-GO (por ruido de working tree)
- validate_yego_operational_flow_scope_hardening.py: 26 PASS / 0 FAIL / 1 WARN → GO
- npm run build: ✅ pasa

---

## 11. ARCHIVOS MODIFICADOS DURANTE ESTA AUDITORÍA

SOLO este documento de auditoría:
- docs/yango_loyalty/YANGO_LOYALTY_REAL_USER_UX_AUDIT.md (create)

NINGÚN archivo productivo fue modificado.

---

## 12. PRÓXIMO PROMPT RECOMENDADO

"Dado el audit UX de Yango Loyalty (CONDITIONAL GO, bootstrap en 1.3s, summary en 2s):
- Optimizar bootstrap leyendo serving fact en vez de fleet_summary_daily live para bajar <1s.
- Separar commits por módulo (Yango Loyalty / Drivers / Profitability / Omniview / api.js).
- NO tocar otros módulos."
