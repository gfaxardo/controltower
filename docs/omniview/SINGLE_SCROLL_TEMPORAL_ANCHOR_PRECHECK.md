# SINGLE SCROLL + TEMPORAL ANCHOR — PRECHECK GO / NO-GO

**Date**: 2026-05-25
**Phase**: 1H.4 — Operational Maturity Governance Layer
**Motor**: Control Foundation
**Foco**: Omniview Vs Proyección

---

## 1. ACTIVE PHASE

| Field | Value |
|---|---|
| Motor | Control Foundation |
| Phase | 1H.4 |
| Status | ACTIVE |
| Allowed | Scroll governance, viewport anchoring, UX hardening |
| Forbidden | New engines, AI loops, backend changes, Evolution changes |

## 2. READY NEXT

Diagnostic Engine — Phase 2A.3 (blocked).

## 3. SCROLL OWNERS DETECTADOS

| # | Línea | Owner | Overflow | Scroll Context |
|---|---|---|---|---|
| 1 | Matrix.jsx:1283 | Root wrapper | `overflow-x-hidden` | CLIP |
| 2 | Table.jsx:256 | Table outer | `overflow: clip` | CLIP |
| 3 | **Table.jsx:270** | **Scroll container** | **`overflow-x-auto overflow-y-auto`** | **SCROLL X+Y** |
| 4 | Matrix.jsx:1763 | Fullscreen (Evol) | `overflow-y-auto` | SCROLL Y |
| 5 | **Matrix.jsx:1874** | **Fullscreen (Proj)** | **`overflow-y-auto`** | **SCROLL Y** |

### DOBLE SCROLL ROOT CAUSE

**Fullscreen projection (línea 1874)**: El overlay tiene `overflow-y-auto` Y la tabla embebida tiene `overflow-y-auto` con `maxHeight`. Ambos crean scroll context vertical. La solución: el overlay fullscreen NO debe tener `overflow-y-auto` — la tabla es el scroll owner único.

**No-fullscreen**: Si `maxHeight` no acierta el espacio disponible, la página genera una barra vertical extra. Ajustar `maxHeight` para que el contenedor de tabla sea el dueño vertical único.

## 4. WIRING VERIFICATION

| Target | Vivo | Modo |
|---|---|---|
| `BusinessSliceOmniviewMatrix` | ✅ | Proyección + Evolución |
| `BusinessSliceOmniviewMatrixTable` | ✅ | Componente compartido |
| `scrollContainerRef` | ✅ | Pasa de Matrix → Table |
| `projectionViewportFocusEngine` | ✅ | Centrado de viewport |
| `currentPeriodFocusEngine` | ✅ | Índice/scroll target |

Zero changes to Evolution wiring.

## 5. RISKS

| Risk | Severity | Mitigation |
|---|---|---|
| Fullscreen overlay overflow | HIGH | Eliminar `overflow-y-auto` del overlay |
| Sticky en fullscreen | LOW | Sticky elements dependen del scroll container maestro, que se mantiene |
| maxHeight calc incorrecto | MEDIUM | Ajustar a `calc(100vh - 220px)` más conservador |
| Zoom transform overflow | LOW | `overflow: clip` ya previene |

## VERDICT: **GO**

Proceed to PASO 1 — Single Scroll Ownership Map.
