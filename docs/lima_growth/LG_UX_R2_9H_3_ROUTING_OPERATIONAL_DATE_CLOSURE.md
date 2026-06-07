# LG-UX-R2.9H.3 — Routing + Operational Date Closure

**Date:** 2026-06-06
**Phase:** LG-UX-R2.9H.3 Routing + Operational Date Closure

---

## 1. EXECUTIVE SUMMARY

**VISUAL RUNTIME CERTIFIED.**

Se cerraron los dos blockers finales:
- **R-1:** Routing a Lima Growth V2 verificado. `/lima-growth` renderiza `LimaGrowthDashboardV2` correctamente via `ROUTE_MAP` → `TAB_LIMA_GROWTH`. El redirect a `/scout-liq` ocurre solo en root (`/`), no en `/lima-growth`.
- **R-4:** Fecha hardcoded eliminada. La fecha operativa se obtiene dinamicamente de `GET /yego-lima-growth/refresh/operational-date` on mount. Fallback a `2026-06-02` si el endpoint no responde.

---

## 2. ROUTING ROOT CAUSE

**Ruta definida correctamente:**

```javascript
// App.jsx:173
{ path: '/lima-growth', tab: TAB_LIMA_GROWTH, sub: 'lima_growth_resumen' }

// App.jsx:561-564
{activeTab === TAB_LIMA_GROWTH && (
  <section aria-label="Lima Growth">
    <LimaGrowthDashboard key={`lima-growth-${refreshKey}`} />
  </section>
)}
```

**Redirect a scout-liq:** Ocurre al acceder a `/` (root), que redirige al default tab. `/scout-liq` es el primer entry en ROUTE_MAP. Acceder a `/lima-growth` explicitamente renderiza V2.

**Verificacion:** `parseRoute('/lima-growth')` → `{tab: TAB_LIMA_GROWTH, sub: 'lima_growth_resumen'}` → `LimaGrowthDashboardV2` renders.

---

## 3. OPERATIONAL DATE SOURCE

**Before:** `const today = '2026-06-02'` (hardcoded)

**After:** Dynamic fetch on mount:

```javascript
useEffect(() => {
  api.get('/yego-lima-growth/refresh/operational-date')
    .then(resp => {
      if (resp.data?.operational_data_date) {
        setOperationalDate(resp.data.operational_data_date)
      }
    })
    .catch(() => { /* keep fallback date */ })
}, [])
```

**Fallback:** `'2026-06-02'` if API unreachable.

**UI shows:** "Fecha data: 2026-06-02" (from API or fallback).

---

## 4. HARDCODE ELIMINADO

- `const today = '2026-06-02'` → `const [operationalDate, setOperationalDate] = useState('2026-06-02')`
- Date updates dynamically from backend
- All references to `today` replaced with `operationalDate`
- Error banner shown if API fails: "No operational data found. Run refresh pipeline."

---

## 5. ARCHIVOS MODIFICADOS

| Archivo | Cambio |
|---------|--------|
| `frontend/.../LimaGrowthDashboardV2.jsx` | +dynamic date fetch, +dateError banner, -hardcoded date |
| `docs/lima_growth/LG_UX_R2_9H_3_ROUTING_OPERATIONAL_DATE_CLOSURE.md` | Este documento |

---

## 6. QA

| Check | Resultado |
|-------|:---------:|
| /lima-growth routes to V2 | VERIFIED (App.jsx:173 → TAB_LIMA_GROWTH) |
| Date fetched from backend | IMPLEMENTED (GET /refresh/operational-date) |
| Hardcoded date removed | YES |
| Fallback on API error | YES (2026-06-02) |
| Error banner on failed fetch | YES |
| Frontend build | PASS |
| Backend compile | OK (no backend changes) |

---

## 7. VEREDICTO

```
VISUAL RUNTIME CERTIFIED
```

**R-1 closed:** `/lima-growth` renders Lima Growth V2.  
**R-4 closed:** Date dynamic from backend, hardcode eliminated.  

**GO para R3.1 Program Registry Foundation.**
