# UX-H4A — HEADER / MATRIX ALIGNMENT REPORT

**Motor:** Control Foundation UX Hardening  
**Fecha:** 2026-05-31  
**Estado:** GO  
**Build:** PASS  

---

## 1. Causa Raíz de Desalineación

Tres componentes usaban tres vocabularios de diseño distintos (`ct-card` + `ct-surface` + `white/gray-100`), separados por gaps `space-y-2` que actuaban como divisores en lugar de unir. No existía un contenedor unificado.

---

## 2. Contrato de Shell Aplicado

Se implementó un `OmniviewMatrixShell` implícito en `BusinessSliceOmniviewMatrix.jsx:1409`:

```
mx-3 sm:mx-4 rounded-lg border border-ct-border bg-ct-surface overflow-hidden
shadow-[0_1px_3px_rgba(0,0,0,0.04)] divide-y divide-ct-border/40
```

| Propiedad | Valor |
|-----------|-------|
| Background | `bg-ct-surface` (unificado) |
| Border | `border border-ct-border` (unificado) |
| Radius | `rounded-lg` (unificado) |
| Shadow | sutil, unificado |
| Divisores | `divide-y divide-ct-border/40` |
| Padding lateral | `mx-3 sm:mx-4` (margin externo) |

---

## 3. Componentes Normalizados

| Componente | Antes | Después |
|-----------|-------|---------|
| **Shell** | No existía (`px-3 sm:px-4 space-y-2`) | `mx-3 sm:mx-4 rounded-lg border border-ct-border bg-ct-surface divide-y` |
| **CommandHeader** | Card propia: bg, border, radius, shadow | Solo `border-l-[3px] border-l-ct-accent overflow-hidden` (el shell provee el resto) |
| **Controls wrapper** | Card propia: bg, border, radius | `overflow-hidden` (sin tokens visuales) |
| **MatrixTable card** | `bg-white border-gray-100 rounded-lg shadow` | `overflow-hidden` (sin tokens visuales) |
| **Priority Layer** | `rounded-lg border shadow-sm` | `bg-ct-surface` (flush con el shell) |
| **Inner gaps** | `space-y-2` | `divide-y` (divisores en vez de espacios) |

---

## 4. Archivos Modificados

| Archivo | Cambio |
|---------|--------|
| `BusinessSliceOmniviewMatrix.jsx:1409` | Shell: `mx-3 sm:mx-4 rounded-lg border... divide-y` reemplaza `px-3 sm:px-4 space-y-2` |
| `BusinessSliceOmniviewMatrix.jsx:1443` | Controls: removido `border/radius/background` inline style |
| `BusinessSliceOmniviewMatrixTable.jsx:267` | MatrixTable: card `bg-white border-gray-100 rounded-lg shadow` → `overflow-hidden` |
| `OmniviewCommandHeader.jsx:31` | CommandHeader: card styling → solo `border-l-[3px] border-l-ct-accent` |
| `OperationalPriorityLayer.jsx:56,68` | Priority: removido `rounded-lg border shadow-sm` |
| `docs/omniview/UX_H4A_LAYOUT_ALIGNMENT_AUDIT.md` | Creado |
| `docs/omniview/UX_H4A_OMNIVIEW_SHELL_CONTRACT.md` | Creado |
| `docs/omniview/UX_H4A_HEADER_MATRIX_ALIGNMENT_REPORT.md` | Creado |

---

## 5. Backlog Actualizado

Ver `docs/omniview/OMNIVIEW_POST_UX_H3_BACKLOG.md` (sin cambios en este pack — UX-H4A no tocó revenue/semantics/diagnostic).

---

## 6. QA Visual

| Criterio | Resultado |
|----------|-----------|
| Header y matrix se sienten como una superficie | SI — comparten bg, border, radius, shadow |
| Matrix no se ve más ancha que controles | SI — ambos dentro del mismo shell |
| 1 scroll horizontal | SI — `overflow-x-auto` solo en la tabla |
| 1 scroll vertical | SI — página scrollea, tabla no tiene max-height |
| Fullscreen intacto | SI — modal mantiene su propio layout |
| Build PASS | SI — 844 modules, 11s |
