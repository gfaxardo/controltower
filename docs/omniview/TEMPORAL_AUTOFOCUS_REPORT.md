# TEMPORAL AUTO-FOCUS & PRESENT PERIOD AUTHORITY — FINAL REPORT

**Date**: 2026-05-25
**Motor**: Control Foundation (GO)
**Phase**: 1H.4 — Operational Maturity Governance Layer
**Sub-phase**: Temporal Auto-Focus Hardening
**Status**: **COMPLETED — GO**

---

## 1. ESTADO: GO ✅

Temporal Auto-Focus + Present Period Authority está implementado, verificado y listo.

---

## 2. WHAT WAS DONE

### 2.1 Auto-Scroll Operacional

**Problema**: La matrix no aterrizaba en el presente. El usuario debía hacer scroll horizontal manual para encontrar HOY.

**Solución**:
- `scrollToCurrentPeriod()` usa ahora `requestAnimationFrame` doble en lugar de `setTimeout(300ms)` para timing preciso post-render
- La columna destino se calcula con `calculateScrollTarget()` del nuevo engine centralizado
- El ancho de columna ahora es modal-aware (`78px` evolution / `100px` projection en comfortable, `58px` / `78px` en compact)
- El botón "Ir a hoy/semana/mes actual" ahora está disponible en ambos modos (Evolución y Proyección)

**Archivos modificados**:
- `BusinessSliceOmniviewMatrix.jsx:1051-1077`

### 2.2 User Navigation Respect

**Problema**: El auto-scroll se re-disparaba con cada cambio de filtro (ciudad, businessSlice, focusedKpi), peleando con la navegación del usuario.

**Solución**:
- `autoScrollAppliedRef` ahora SOLO se resetea en cambios de `grain` y `viewMode` (contexto crítico temporal)
- Cambios de ciudad, businessSlice, focusedKpi, año, mes NO disparan re-scroll
- El usuario puede navegar libremente sin fightback

**Archivos modificados**:
- `BusinessSliceOmniviewMatrix.jsx:1085`

### 2.3 Current Period Visual Authority

**Problema**: El periodo actual no dominaba visualmente. Las fuentes eran iguales para todos los periodos. El background era demasiado sutil (`bg-blue-50/20`).

**Solución — Header**:
- Fondo actual: `bg-blue-950/90` (sin cambios)
- Glow: de `shadow-[inset_0_0_12px_rgba(59,130,246,0.15)]` a `shadow-[inset_0_0_16px_rgba(59,130,246,0.25)]` (+67% intensidad)
- Fuente primaria: `text-[15px]` (comfortable) / `text-[12px]` (compact) vs `text-[13px]` / `text-[10px]` normal
- Fuente secundaria: `text-[12px]` (comfortable) / `text-[11px]` (compact) vs `text-[10px]` normal
- Badge HOY: `text-[10px]` + `px-1.5 py-0.5` + `shadow-sm` vs `text-[8px]` + `px-1 py-px` anterior
- KPI header: `text-[13px]` + `text-blue-100` vs `text-[11px]` normal

**Solución — Celdas**:
- Valor principal: `text-[16px] font-extrabold` vs `text-[14px] font-semibold` normal (+2px, extra-bold)
- Delta: `text-[12px]` vs `text-[11px]` normal (+1px)
- Fondo: `bg-blue-50/40 ring-1 ring-inset ring-blue-400/30 shadow-[inset_0_0_20px_rgba(59,130,246,0.08)]` vs `bg-blue-50/20` anterior
- Momentum en periodo actual: `font-bold` adicional

**Solución — TotalsRow**:
- Fondo periodo actual: `rgb(219,234,254)` (blue tinted) con `ring-1 ring-inset ring-blue-400/30`
- Valor: `text-[18px] font-bold text-blue-900` vs `text-[14px] font-bold text-slate-700` normal
- Delta: `text-[13px]` vs `text-[11px]` normal

**Archivos modificados**:
- `BusinessSliceOmniviewMatrixHeader.jsx`
- `BusinessSliceOmniviewMatrixCell.jsx`
- `BusinessSliceOmniviewMatrixTable.jsx` (TotalsRow)

### 2.4 Current Period Focus Engine

**Problema**: La lógica de periodo actual estaba dispersa en `omniviewMatrixUtils.js` sin una API centralizada para scroll target y prioridad visual.

**Solución**: Nuevo archivo `frontend/src/utils/currentPeriodFocusEngine.js` con:
- `resolveCurrentPeriodKey(grain)` — hoy / lunes ISO / mes actual
- `resolveOperationalDay(grain, allPeriods)` — fallback al último día con datos
- `resolveCurrentPeriodIndex(allPeriods, grain)` — índice en array de periodos
- `isCurrentPeriod(pk, grain)` — chequeo directo
- `getCurrentPeriodBadge(grain)` — "HOY" / "SEMANA ACTUAL" / "MES ACTUAL"
- `calculateScrollTarget(idx, colW, fixedW, viewportW)` — cálculo de destino de scroll
- `getCurrentPeriodVisualPriority(grain)` — flags de prioridad visual
- `isPeriodNear(grain, pk, currentKey, allPeriods)` — periodos cercanos
- `isPeriodDistant(grain, pk, currentKey, allPeriods)` — periodos distantes
- `shouldAutoScrollReset(prevGrain, nextGrain, prevVM, nextVM)` — guard de reset

**Archivo creado**:
- `frontend/src/utils/currentPeriodFocusEngine.js`

---

## 3. HOW AUTO-FOCUS WORKS

```
1. Component mounts
2. Data fetches → rows.length > 0, loading = false
3. useEffect fires:
   - Guard: autoScrollAppliedRef.current === false? → YES
   - requestAnimationFrame #1 → requestAnimationFrame #2 → scrollToCurrentPeriod()
   - autoScrollAppliedRef.current = true
4. scrollToCurrentPeriod():
   - resolveCurrentPeriodIndex(allPeriods, grain) → idx
   - calculateScrollTarget(idx, colW, fixedW, viewportW) → targetLeft
   - container.scrollTo({ left: targetLeft, behavior: 'smooth' })
5. autoScrollAppliedRef stays true until grain or viewMode changes
6. User navigates freely without fightback
```

---

## 4. WHAT CHANGED VISUALLY

| Element | Before | After |
|---------|--------|-------|
| Current period header bg | `bg-blue-950/90` | `bg-blue-950/90` (sin cambio) |
| Current period header glow | `shadow-[inset_0_0_12px_rgba(59,130,246,0.15)]` | `shadow-[inset_0_0_16px_rgba(59,130,246,0.25)]` |
| Header primary font (current) | `text-[13px]` | `text-[15px]` |
| Header badge | `text-[8px] bg-blue-500` | `text-[10px] bg-blue-500 shadow-sm` |
| Cell main value (current) | `text-[14px] font-semibold` | `text-[16px] font-extrabold` |
| Cell background (current) | `bg-blue-50/20` | `bg-blue-50/40 ring-1 ring-blue-400/30 shadow` |
| Cell delta (current) | `text-[11px]` | `text-[12px]` |
| TotalsRow bg (current) | Zebra stripe (same as others) | `rgb(219,234,254)` + ring |
| TotalsRow value (current) | `text-[14px]` | `text-[18px] text-blue-900` |
| KPI header (current) | Same as others | Larger + `text-blue-100` |

---

## 5. RISKS

### Mitigated

| Risk | Mitigation |
|------|-----------|
| Auto-scroll fights user | Only fires on grain/viewMode changes — filter changes don't trigger |
| Scroll loops | Single-shot: `autoScrollAppliedRef` guard + `requestAnimationFrame` |
| Re-render cascades | No state changes during scroll; `currentPeriodKey` is useMemo'd |
| Performance | 813 modules (was 812, +1 new file), build time stable (4.37s vs 9.71s) |
| Virtualization break | No virtualization change — all columns rendered in DOM |
| Sticky break | Pure CSS sticky — no interaction with scroll JS |
| Weekday focus conflict | No conflict — weekday focus filters columns, auto-scroll adjusts to filtered set |

### Accepted (not blocking)

| Risk | Reason |
|------|--------|
| Slight scroll target mismatch if colW differs from actual | Table uses fixed colW via `<col>` width — deterministic, no runtime variation |
| Projection auto-scroll uses evolution allPeriods | Both matrices share same allPeriods for same grain/filters |

---

## 6. PERFORMANCE IMPACT

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Modules | 812 | 813 | +1 |
| Build time | 9.71s | 4.37s | Faster (cold vs warm cache variance) |
| JS bundle | 1,804.58 kB | 1,806.04 kB | +1.46 kB |
| CSS | 89.83 kB | 92.05 kB | +2.22 kB (Tailwind generates new utility classes) |
| Runtime | No change | No change | Auto-scroll is one-time, non-blocking |
| Re-renders | No change | No change | No new state or effect triggers in render cycle |

---

## 7. FILES CREATED

| File | Purpose |
|------|---------|
| `frontend/src/utils/currentPeriodFocusEngine.js` | Centralized temporal focus engine |
| `docs/omniview/TEMPORAL_AUTOFOCUS_PRECHECK.md` | GO/NO-GO pre-check |
| `docs/omniview/TEMPORAL_RENDER_AUDIT.md` | Render path audit |
| `docs/omniview/TEMPORAL_FIRST2S_TEST.md` | First 2 seconds operational test |
| `docs/omniview/TEMPORAL_AUTOFOCUS_QA.md` | Full QA checklist (61 checks) |
| `docs/omniview/TEMPORAL_AUTOFOCUS_REPORT.md` | This report |

---

## 8. FILES MODIFIED

| File | Changes |
|------|---------|
| `BusinessSliceOmniviewMatrix.jsx` | Import engine, `requestAnimationFrame` scroll timing, modal-aware colW, `autoScrollAppliedRef` guards narrowed to grain/viewMode, button visible in both modes |
| `BusinessSliceOmniviewMatrixHeader.jsx` | `CURRENT_PERIOD_GLOW` constant, larger fonts for current period, bigger badge, KPI row enhancement |
| `BusinessSliceOmniviewMatrixCell.jsx` | +2px font size for current period, `font-extrabold`, stronger background with ring + shadow |
| `BusinessSliceOmniviewMatrixTable.jsx` | TotalsRow: `currentPeriodKey` prop, blue-tinted background, larger text + ring for current period |

---

## 9. BUILD EVIDENCE

```
> npm run build
✓ 813 modules transformed.
✓ built in 4.37s
```

---

## 10. UX FINDINGS

### Expected operator experience:

1. **Abre Omniview** → La columna HOY (o semana/mes actual) está centrada en pantalla.
2. **Primera mirada**: El badge "HOY" destaca, la columna tiene glow azul, las fuentes son más grandes.
3. **El ojo aterriza**: Inmediatamente en el valor del periodo actual (fuente extra-bold, 16px).
4. **Navega a histórico**: Hace scroll manual sin que el sistema lo "jale" de vuelta.
5. **Cambia de grain**: De daily a weekly → auto-scroll recentra en la semana actual.
6. **Cambia a Proyección**: Auto-scroll recentra (nuevo modo operativo).

### Deterioration visibility:

- La celda del periodo actual tiene mayor peso visual → cualquier deterioro (rojo, alerta) es más visible.
- El momentum (DoD/WoW/MoM) en el periodo actual usa `font-bold` adicional → más contraste.
- El TotalsRow resalta el total del periodo actual con fondo azul y texto azul oscuro.

---

## 11. CRITERIA COMPLIANCE

### GO Criteria

| Criterion | Status |
|-----------|--------|
| Matrix aterriza cerca del presente | ✅ Auto-scroll al load |
| HOY domina visualmente | ✅ +2px fuente, extra-bold, glow, ring |
| Current period tiene autoridad | ✅ Header + Cell + TotalsRow todos reforzados |
| Fuentes actuales más visibles | ✅ 16px vs 14px, 15px vs 13px |
| No scroll manual obligatorio | ✅ Auto-scroll al load |
| No runtime pesado | ✅ requestAnimationFrame one-shot |
| No regressions | ✅ 61 QA checks passing |
| Virtualization intacta | ✅ Sin cambios |
| Build PASS | ✅ 813 modules, 4.37s |

### NO-GO Risks: NONE TRIGGERED

| Risk | Status |
|------|--------|
| Scroll infinito | ❌ No aplica — single-shot |
| Scroll agresivo | ❌ No aplica — smooth, native |
| Re-render severo | ❌ No aplica — sin state changes |
| Virtualization rota | ❌ No aplica — sin cambios |
| Sticky roto | ❌ No aplica — sin cambios |
| Fuentes gigantes globales | ❌ No aplica — solo periodo actual |
| Matrix inestable | ❌ No aplica — sin cambios estructurales |
| Usuario pierde control | ❌ No aplica — navegación respetada |

---

## 12. RECOMMENDATION

**RELEASE READY.**

Omniview ahora aterriza automáticamente en el presente operacional, da autoridad visual clara al periodo actual, y respeta la navegación del usuario. El comportamiento es el de un verdadero radar operacional en tiempo real.
