# LG-UX-R2.9G.2 — Visual Certification Mismatch Incident

**Date:** 2026-06-06
**Phase:** LG-UX-R2.9G.2 Visual Certification Mismatch Incident
**Prior certification:** LG-UX-R2.9G.1 — INVALIDATED

---

## 1. EXECUTIVE SUMMARY

La certificacion R2.9G.1 fue invalidada por contradiccion entre reporte Playwright PASS y evidencia de usuario FAIL.

**Causa raiz: DESDOBLAMIENTO DE ENTORNO**

- Frontend usa puerto 5173 (Vite dev)
- Backend usa puerto 8000 (uvicorn)
- El path `/lima-growth` redirige a `/scout-liq`
- La data solo existe para 2026-06-02 (snapshot unico)
- La fecha default del frontend era `new Date()` = 2026-06-06 → todo 0
- Playwright validaba DOM (body length > 50) sin validar contenido real
- API timeouts intermitentes por sesion de backend larga

---

## 2. CAUSA MISMATCH: ANALISIS POR LAYER

### Layer 1: Data

| Fecha | Universe | Eligible | Actionable | Queue |
|-------|:---:|:---:|:---:|:---:|
| 2026-06-02 | 18,475 | 17,917 | 500 | 500 |
| 2026-06-06 | 0 | 0 | 0 | 0 |

Solo existe data para 2026-06-02. No hay scheduler diario generando datos frescos.

### Layer 2: Frontend Date

**Antes (R2.9G.1):** `const today = new Date().toISOString().slice(0, 10)` = `2026-06-06`

Consecuencia: todos los endpoints devuelven 0 para todos los KPIs. Programs vacio, Queue vacio, Action Plan sin acciones.

**Ahora (R2.9G.2):** `const today = '2026-06-02'` (hardcoded a la unica fecha con datos)

### Layer 3: URL Routing

El path `/lima-growth` en Vite dev devuelve el SPA que redirige a `/scout-liq` (default route). Lima Growth V2 se renderiza en `/lima-growth` pero el comportamiento depende del router de React. En produccion, el build esta configurado como SPA con fallback a index.html.

### Layer 4: Playwright Assertions

**R2.9G.1:** Validaba `bodyText.length > 50` → 655 chars = PASS. Pero el contenido era la pagina scout-liq, no Lima Growth V2.

**R2.9G.2:** Valida contenido real con `contains('Capacidad')`, `contains('READY')`, `contains('High Value Recovery')`. Estos fallan en `/scout-liq`.

### Layer 5: API Timeout

El backend (port 8000) acepto algunas llamadas pero eventualmente timeout en 30s. Posibles causas: conexiones agotadas, sesion DB saturada, uvicorn worker lento.

---

## 3. FIXES APLICADOS

| Fix | Archivo | Cambio |
|-----|---------|--------|
| Default date | `LimaGrowthDashboardV2.jsx` | `'2026-06-02'` hardcoded (unica data disponible) |
| R2.9G.1 invalidated | `LG_UX_R2_9G_1_VISUAL_RUNTIME_SMOKE.md` | Veredicto cambiado a NOT CERTIFIED |
| Real assertions | `r2_9g_2_real_smoke.cjs` | Valida contenido semantico, no solo body length |
| Empty state handling | `SharedComponents.jsx` | +remediation, +action props en EmptyState |
| StaleDataBanner | `SharedComponents.jsx` + `LimaGrowthDashboardV2.jsx` | Visible cuando freshness != FRESH |

---

## 4. RESULTADOS POST-FIX

| Check | R2.9G.1 (invalid) | R2.9G.2 (real) |
|-------|:---:|:---:|
| No blank page | PASS (655 chars) | PASS (430 chars) |
| No 500 errors | PASS | PASS |
| No timeout text | PASS | PASS |
| Content assertions | Not tested | 9 FAIL (wrong page) |
| API response | PASS (5/5) | FAIL (timeout) |
| Date correctness | WRONG (2026-06-06) | FIXED (2026-06-02) |

---

## 5. REMAINING ISSUES

| # | Issue | Severity | Status |
|---|-------|:---:|:---:|
| I-1 | Lima Growth V2 not loading at `/lima-growth` (redirects to `/scout-liq`) | HIGH | ABIERTO |
| I-2 | Backend API timeout in Playwright (30s+) | HIGH | ABIERTO |
| I-3 | No scheduler building daily data | MEDIUM | ABIERTO (backlog) |
| I-4 | Playwright API context different from page context | LOW | ABIERTO |
| I-5 | Date hardcoded to 2026-06-02 | LOW | ABIERTO (needs dynamic) |

---

## 6. QA

| Check | Resultado |
|-------|:---------:|
| Frontend build | PASS |
| R2.9G.1 invalidated | YES |
| Date fix applied | YES (2026-06-02) |
| Real assertions implemented | YES |
| Root cause documented | YES |

---

## 7. VEREDICTO

```
VISUAL RUNTIME NOT CERTIFIED
```

**Motivo:**
1. Lima Growth V2 no renderiza bajo `/lima-growth` en dev server (redirige a `/scout-liq`)
2. API timeouts en Playwright (sesion backend larga)
3. La data existe solo para 2026-06-02 (no hay scheduler)
4. Las assertions de contenido real fallan porque la pagina renderizada no es Lima Growth V2

**Requisitos para re-certificacion:**
- Resolver I-1 (routing a Lima Growth V2)
- Resolver I-2 (backend API reliability en Playwright)
- Ejecutar smoke con assertions reales que pasen
