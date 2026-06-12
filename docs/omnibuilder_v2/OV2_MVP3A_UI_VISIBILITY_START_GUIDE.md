# OV2-MVP.3A — OMNIVIEW V2 START GUIDE

> **Fase:** OV2-MVP.3A — Operational Trial Execution
> **Sub-document:** UI Visibility + Start Guide
> **Fecha:** 2026-06-12

---

## 1. URLS EXACTAS

### Omniview V2 (MVP / Shadow)

```
URL local:    http://localhost:5173/operacion/omniview-v2-shadow
URL relativa: /operacion/omniview-v2-shadow
Componente:   OmniviewV2ShadowPage
Router:        App.jsx → ROUTE_MAP → sub: operacion_omniview_v2_shadow
```

### Omniview V1 (Production)

```
URL local:    http://localhost:5173/operacion/omniview-matrix
URL relativa: /operacion/omniview-matrix
Componente:   BusinessSliceOmniviewMatrix
Router:        App.jsx → ROUTE_MAP → sub: operacion_omniview_matrix
```

---

## 2. NAVIGATION VISIBILITY

### Sidebar (Operacion tab)

| Entry | Label | Visible | Status |
|-------|-------|---------|--------|
| V1 | Omniview Matrix | **YES** (default) | productionReady: true |
| V2 | **Omniview V2 MVP** | **YES** | productionReady: false, MVP/Shadow badge |
| V1 Legacy | Omniview | HIDDEN | legacy view |
| Reports | Reportes | YES | productionReady: true |
| CL PvR | Control Loop Plan vs Real | YES | productionReady: true |

### Registry Entry

```javascript
{
    key: 'operacion_omniview_v2',
    label: 'Omniview V2 MVP',
    tab: 'Operacion',
    component: 'OmniviewV2ShadowPage',
    route: '/operacion/omniview-v2-shadow',
    engine: ENGINE.CONTROL_FOUNDATION,
    phaseStatus: PHASE_STATUS.ACTIVE,
    visibility: VISIBILITY.KEEP_VISIBLE,
    productionReady: false,
    requiresValidation: true,
    reason: 'OV2-MVP.1A — Omniview V2 MVP en shadow mode.',
}
```

---

## 3. FEATURE FLAGS

| Flag | Status | Impact |
|------|--------|--------|
| `VITE_OV2_ALLOW_MATRIX_FALLBACK` | `false` (default) | Matrix fallback adapter disabled in production |
| `VITE_SHOW_DEV_MODULES` | `false` (default) | Not needed — V2 uses KEEP_VISIBLE |
| `V1_LEGACY_MODE` | Not implemented yet | V1 is default, V2 is shadow |
| `productionReady` | `false` | Shows MVP/Shadow badge |

**No feature flags required to access V2.** It's visible unconditionally via `KEEP_VISIBLE`.

---

## 4. PERMISSIONS

No special permissions required. V2 is a public route. No auth guard.

---

## 5. V1 vs V2 DIFFERENCES

| Aspect | V1 (Omniview Matrix) | V2 (Omniview V2 MVP) |
|--------|---------------------|----------------------|
| URL | `/operacion/omniview-matrix` | `/operacion/omniview-v2-shadow` |
| Status | Production (default) | MVP / Shadow |
| Source systems | CT only (implicit) | CT + Yango (selector) |
| Filters | Year, Month, City, Slice, Subfleet | Source, Grain, Date From/To, Country, City, Park, Slice |
| KPIs | 7 (incl. commission, cancel) | 6 (commission shows N/A) |
| Business slices | Matrix rows | Matrix rows |
| Signal colors | Yes (insight thresholds) | Yes (delta direction borders) |
| Source badges | No | Yes (CT/YAN/FALLBACK) |
| Delta arrows | No | Yes (▲▼→) |
| Fullscreen | No | Yes ([F] button + Esc) |
| Status bar | Fixed | Collapsible |
| Plan vs Real | Daily/Weekly/Monthly | Monthly only |
| ECharts reports | Yes | No (P2 backlog) |
| Default route | Yes | No (V1 still default) |

---

## 6. VERIFICATION CHECKLIST

| # | Check | Expected | Status |
|---|-------|----------|--------|
| 1 | Open browser → `localhost:5173` | Control Tower loads | ✓ |
| 2 | Click Operacion tab | Sidebar shows navigation items | ✓ |
| 3 | Find "Omniview V2 MVP" in sidebar | Visible between "Omniview Matrix" and "Control Loop" | ✓ |
| 4 | Click "Omniview V2 MVP" | Navigates to `/operacion/omniview-v2-shadow` | ✓ |
| 5 | V2 page loads | Matrix with filters + status bar | ✓ |
| 6 | V1 still accessible | Click "Omniview Matrix" → V1 loads | ✓ |
| 7 | V1 is default | Navigate to Operacion tab → V1 loads first | ✓ |
| 8 | V2 has MVP banner | Blue banner "OV2 MVP — Shadow Mode" | ✓ |
| 9 | Filters work | Country, City, Park, Slice dropdowns | ✓ |
| 10 | Matrix shows data | Business slices with values | ✓ |

---

## 7. BLOCKERS KNOWN

| # | Blocker | Severity | Status |
|---|---------|----------|--------|
| 1 | Commission % shows N/A | LOW | Data pipeline pending. Not a code bug. |
| 2 | ECharts reports not ported | LOW | P2 backlog. Matrix + filters substitute. |
| 3 | Day/week Plan vs Real not yet | LOW | Monthly works. Day/week pending data pipeline. |
| 4 | SUB_URL fix applied | FIXED | Added `operacion_omniview_v2` → `/operacion/omniview-v2-shadow` |

---

## 8. START TRIAL

### Steps to begin

1. Open browser: `http://localhost:5173`
2. Login if required
3. Click **Operacion** tab in top navigation
4. Click **Omniview V2 MVP** in left sidebar
5. V2 matrix loads. Set filters:
   - Country: Peru
   - City: Lima
   - Grain: Day
   - Date From: yesterday
   - Date To: yesterday
6. Verify data loads. Start using V2 as primary tool.

---

## 9. ANSWERS TO EXPLICIT QUESTIONS

### ¿Cuál es la URL exacta de Omniview V2?

**`/operacion/omniview-v2-shadow`**

### ¿Está visible en la UI?

**Sí** — Aparece en la barra lateral de Operacion como **"Omniview V2 MVP"** con badge MVP/Shadow. Visibility: `KEEP_VISIBLE`.

### ¿V1 sigue visible?

**Sí** — V1 sigue como "Omniview Matrix" en la barra lateral y es la ruta default de Operacion. Sin cambios.

### ¿Podemos iniciar el trial operacional usando esa ruta?

**Sí** — La ruta `/operacion/omniview-v2-shadow` está funcional, visible en navegación, y lista para el trial de 2 semanas. El fix de SUB_URL (que faltaba) fue aplicado para que el click desde el sidebar funcione correctamente.
