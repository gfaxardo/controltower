# OV2-MVP.1B — OPERATIONAL SIGNAL LAYER REPORT

> **Fase:** OV2-MVP.1B — Operational Signal Layer
> **Motor:** Control Foundation
> **Fecha:** 2026-06-12
> **Contexto:** OV2-MVP.1A Core Parity → Signal Layer
> **Clasificación:** `OV2_SIGNAL_LAYER_CERTIFIED`

---

## 1. EXECUTIVE SUMMARY

Capa visual-operativa de señales implementada en Omniview V2. **Signal colors, delta arrows, source badges, trust badges, fallback indicators visibles directamente en cells.** Commission KPI auditado (columna existe, valores NULL → muestra "N/A"). Signal contract documentado con 5 categorías de señales.

**Resultado: GO para OV2-MVP.2 UX Hardening.**

---

## 2. GOVERNANCE VALIDATION

| Rule | Status |
|------|--------|
| No Diagnostic Engine | **PASS** |
| No Forecast | **PASS** |
| No Suggestion | **PASS** |
| No Source Promotion | **PASS** |
| No V1 deprecation | **PASS** |
| No tocar V1 | **PASS** |
| No Root Cause | **PASS** |
| No ECharts reports | **PASS** |

---

## 3. COMMISSION KPI AUDIT

### 3.1 Findings

| Aspect | Result |
|--------|--------|
| Column `commission_pct` in `day_fact` | **EXISTS** (numeric) |
| Column `commission_pct` in `week_fact` | **EXISTS** (numeric) |
| Column `commission_pct` in `month_fact` | **EXISTS** (numeric) |
| Values populated | **FAIL** — all NULL |
| Root cause | Data pipeline doesn't compute `commission_pct` |

### 3.2 Fix Applied

| Before | After |
|--------|-------|
| `COALESCE(AVG(commission_pct), 0)` → **shows "0.0%"** (misleading) | `AVG(commission_pct)` → **returns NULL** → frontend shows "N/A" with `NOT_AVAILABLE` badge |

---

## 4. SIGNAL CONTRACT

5 signal categories documented in `OV2_MVP1B_SIGNAL_CONTRACT.md`:

| Category | Signals | Visual Elements |
|----------|---------|----------------|
| **Delta** | UP, DOWN, FLAT, NO_COMPARISON | ▲ green / ▼ red / → gray |
| **Health** | HEALTHY, WARNING, STALE, MISSING, FALLBACK_USED, NOT_CERTIFIED | Border colors + badges |
| **Plan** | AHEAD, ON_TRACK, BEHIND, NO_PLAN | Double arrows + attainment % |
| **Source** | CT_BRIDGE, YANGO_API, SHARED, FALLBACK_CT, NOT_AVAILABLE | Source badge in cell corner |
| **Trust** | OK, WARN, BLOCKED | Implicit in cell_status + canonical_ready |

---

## 5. MATRIX CELL SIGNALS

### 5.1 Changes

| Component | Change |
|-----------|--------|
| `MatrixCell.jsx` | Signal color function (`_signalColor`), delta direction (`_deltaDirection`), source badge, fallback badge, N/A handling |
| `CellDelta.jsx` | Arrow icons: ▲ (UP, green), ▼ (DOWN, red), → (FLAT, gray) with colored text |
| `CellBadge.jsx` | Extended types: CT_BRIDGE, YANGO_API, FALLBACK, STALE, MISSING, HEALTHY, NOT_AVAILABLE |
| `MatrixVisualSystem.css` | Delta direction colors: `ov2-cell--delta-up/down/flat`, delta arrow colors |

### 5.2 Cell Rendering Order

```
[CT/YAN badge]  [FALLBACK badge]   (top-right corner)
[Value (bold)]                     (center-right)
[PARTIAL badge]  [EST badge]       (additional badges)
[▲/▼ delta%]                       (bottom-left, if comparison available)
```

### 5.3 Signal Color Logic

| Condition | Border Color | Background |
|-----------|-------------|------------|
| Delta UP | Green (#16a34a) | White |
| Delta DOWN | Red (#dc2626) | White |
| Delta FLAT | Gray (#9ca3af) | White |
| WARNING (non-canonical) | Amber | Amber bg |
| BLOCKED / NULL | Red | Blocked bg |
| NOT_COMPARABLE (future) | None | Muted bg |

---

## 6. EXECUTION CONTEXT UI

### 6.1 Model

```
Real → always visible
Plan → inline (same cell/row, not separate screen)
Gap → plan - real
Attainment% → real / plan * 100
Plan Status → AVAILABLE | MISSING (badge)
```

### 6.2 Current State

- **Backend**: `/ops/omniview-v2/plan-real/monthly` exists and returns real + plan data
- **Frontend**: Plan vs Real mode button exists; switches to monthly plan matrix
- **Missing**: Day/week plan-real endpoints, inline cell rendering of Real + Plan + Gap + Attainment% in same cell

### 6.3 NOT IMPLEMENTED (intentionally)

- Projection Mode (separado) — **CANCELED**, not MVP scope
- Day/week plan-real — pending data pipeline, not a signal layer task
- Gap/Attainment% in cells — requires plan data at cell grain, pending

---

## 7. STICKY HEADERS

### 7.1 Verification

| Check | Status | Evidence |
|-------|--------|----------|
| `ov2-header-cell--sticky` CSS class | **EXISTS** | `position: sticky; left: 0; z-index: var(--ov2-z-sticky-col)` |
| `ov2-row-label` CSS class | **EXISTS** | `position: sticky; left: 0;` for first column |
| JS scroll sync (header ↔ body) | **EXISTS** | `handleBodyScroll` updates `scrollLeft` state, header translates |
| No double-scroll regression | **PASS** | Outer `overflow: hidden`, body `overflow: auto` verified in MVP.1A |

---

## 8. STATUS BAR EXTENSION

Status bar from MVP.1A shows:
- Operating date + freshness status (FRESH / STALE / CRITICAL)
- Max available date + has_today_data
- Coverage %
- Canonical ready (Yes/No)
- Fallback active (ACTIVE / None)
- Source system + Grain

Extended view (expand button):
- All of the above in detail view

---

## 9. FILES MODIFIED

| File | Change |
|------|--------|
| `docs/omnibuilder_v2/OV2_MVP1B_COMMISSION_KPI_AUDIT.md` | Commission audit: column exists, values NULL, fix applied |
| `docs/omnibuilder_v2/OV2_MVP1B_SIGNAL_CONTRACT.md` | 5-category signal contract with colors, icons, conditions |
| `backend/app/repositories/omniview_v2_matrix_repository.py` | Removed COALESCE from `commission_pct` → returns NULL |
| `backend/app/services/omniview_v2_matrix_view_model_service.py` | `commission_pct` formatter: shows "N/A" when value is None |
| `frontend/.../components/matrix/MatrixCell.jsx` | Signal colors, source badge, fallback badge, delta direction, N/A handling |
| `frontend/.../components/matrix/CellDelta.jsx` | Arrow icons (▲▼→) with green/red/gray colors |
| `frontend/.../components/matrix/CellBadge.jsx` | Extended types: CT_BRIDGE, YANGO_API, FALLBACK, STALE, MISSING, HEALTHY, NOT_AVAILABLE |
| `frontend/.../design/MatrixVisualSystem.css` | Delta direction colors, delta arrow styles |

---

## 10. GO / NO-GO

### GO for OV2-MVP.2 UX Hardening: **GO**

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | commission_pct no muestra 0 falso | **PASS** | Returns NULL → shows "N/A" |
| 2 | Signal contract documented | **PASS** | `OV2_MVP1B_SIGNAL_CONTRACT.md` |
| 3 | Cells muestran signal colors | **PASS** | Delta direction borders + cell status colors |
| 4 | Delta arrows visibles | **PASS** | ▲▼→ with green/red/gray |
| 5 | Source badges visibles | **PASS** | CT/YAN/FALLBACK in corner |
| 6 | Execution context sin Projection Mode | **PASS** | Model defined, no separate mode created |
| 7 | Real visible sin Plan | **PASS** | Real always visible in matrix cells |
| 8 | Sticky headers verificados | **PASS** | CSS + JS scroll sync |
| 9 | No double-scroll | **PASS** | Verified in MVP.1A, maintained |
| 10 | V1 intacto | **PASS** | 0 V1 changes |
| 11 | No nuevos motores | **PASS** | Diagnostic/Forecast/Suggestion/Decision/Action remain BLOCKED |

### Classification

**`OV2_SIGNAL_LAYER_CERTIFIED`** — Operational signals visibles en cells. Delta arrows, source badges, trust indicators implementados. Commission audit completado. 0 V1 changes.

---

## 11. BACKLOG UPDATED

| Estado | Fase | Descripción |
|--------|------|-------------|
| **ACTIVE** | **OV2-MVP.1B** | Operational Signal Layer (this document) |
| READY NEXT | **OV2-MVP.2** | UX Hardening |
| BACKGROUND | OV2-MVP.3 | Operational Acceptance |
| BACKGROUND | OV2-MVP.4 | V1 Deprecation Readiness |
| BACKGROUND | CF-H2E.2A | Rate Limit & Throughput Governance |
| BLOCKED | CF-H2H | Omniview Source Promotion |

---

## 12. ANSWER TO EXPLICIT QUESTION

**¿Estamos listos para abrir OV2-MVP.2 UX Hardening?**

**Sí — GO.**

Operational Signal Layer completada:
- Commission auditado: columna existe, valores NULL → "N/A" en vez de 0 falso
- Signal contract documentado: 5 categorías con colores e íconos
- MatrixCell: signal colors, source badges, fallback badges, delta direction
- CellDelta: arrow icons ▲▼→ con green/red/gray
- CellBadge: 10+ tipos de badges
- CSS: delta direction colors, delta arrow styles
- Sticky headers verificados (CSS + JS)
- 8 archivos modificados
- 0 V1 changes, 0 runtime pesado, 0 secrets

OV2-MVP.2 puede enfocarse en ECharts reports, control loop PvR, fullscreen toggle, park filter, y full projection mode integration.

---

## 13. FIRMA

| Campo | Valor |
|-------|-------|
| **Implementado por** | OV2-MVP.1B Operational Signal Layer |
| **Fecha** | 2026-06-12 |
| **Motor** | Control Foundation |
| **Clasificación** | `OV2_SIGNAL_LAYER_CERTIFIED` |
| **Veredicto** | **GO for OV2-MVP.2 UX Hardening** |
| **Próxima fase** | OV2-MVP.2 — ECharts reports, control loop PvR, fullscreen, park filter |
