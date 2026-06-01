# P4-A — PRESENT ANCHOR HARDENING REPORT

**Motor:** Control Foundation  
**Phase:** 1H.4 ACTIVE  
**Fecha:** 2026-05-31  
**Estado:** PASS  
**Build:** PASS  

---

## 1. Governance Leído

| Documento | Estado |
|-----------|--------|
| `ai_operating_system.md` | Control Foundation GO. Diagnostic ACTIVE (2A.3). Resto BACKLOG. |
| `ai_current_phase.md` | Phase 1H.4 ACTIVE. Omniview hardening ALLOWED (line 62). |

**Bloqueos aplicables:** Ninguno. Present anchor hardening pertenece a Control Foundation / Omniview usability hardening. No toca Diagnostic, Forecast, Suggestion, Decision, Action ni AI Copilot.

---

## 2. Función que Resuelve el Present Focus

**`resolveCurrentPeriodIndex(allPeriods, grain)`** en `currentPeriodFocusEngine.js:49`

1. Obtiene la key del periodo actual vía `resolveCurrentPeriodKey(grain)`
2. Busca `indexOf` exacto en `allPeriods`
3. Si no existe, busca el más cercano hacia atrás (fallback)
4. Si no hay ninguno, retorna `allPeriods.length - 1` (último periodo disponible)

**`calculateScrollTarget(idx, colW, fixedW, viewportW, grain)`** en `currentPeriodFocusEngine.js:73`

- **Daily:** Posiciona el presente al 30% del viewport (`viewportW * 0.30` desde la izquierda) → muestra pasado reciente + presente + futuro inmediato
- **Weekly/Monthly:** Centra el periodo en el viewport

**`scrollToCurrentPeriod()`** en `BusinessSliceOmniviewMatrix.jsx:1149`

- Valida que el container tenga `clientWidth > 0` y `scrollWidth > clientWidth`
- Resuelve qué `allPeriods` usar según modo (evolución vs proyección)
- Si hay anchor cerrado (proyección), usa el anchor; sino, usa el índice resuelto
- Ejecuta `container.scrollTo({ left, behavior: 'smooth' })`

---

## 3. Cómo Evita Pelear con Scroll Manual

| Mecanismo | Función |
|-----------|---------|
| `autoScrollAppliedRef` | Solo se activa una vez por carga de datos |
| `userHasScrolledRef` | Se activa al detectar `wheel`/`touchmove` |
| `shouldAutoScrollReset` | Se reinicia al cambiar grain o viewMode |
| Guard `!autoScrollAppliedRef.current && !userHasScrolledRef.current` | Previene re-scroll agresivo |
| Botón "Ir a hoy" | Resetea `userHasScrolledRef` explícitamente y llama `scrollToCurrentPeriod()` |

---

## 4. Cambios Aplicados

| Archivo | Cambio | Línea |
|---------|--------|-------|
| `utils/currentPeriodFocusEngine.js` | `calculateScrollTarget`: nuevo param `grain`. Daily posiciona al 30% del viewport. | 73 |
| `BusinessSliceOmniviewMatrix.jsx` | `scrollToCurrentPeriod`: container readiness guard, stale closure fix, fallback idx | 1149 |
| `BusinessSliceOmniviewMatrix.jsx` | Auto-scroll useEffect: 150ms timeout retry después de double-RAF | 1177 |
| `BusinessSliceOmniviewMatrix.jsx` | Nuevo ref `scrollTimeoutRef` | 1147 |

---

## 5. Evidencia Visual

### Daily al cargar
- El presente operativo (30 May 2026, o último cierre disponible) queda visible al 30% del viewport
- Se ven días previos (28-29 May aprox.) + presente + días futuros si existen en proyección
- "Ir a hoy" reposiciona al mismo punto

### Weekly al cargar
- Semana actual (S22-2026) centrada en el viewport
- Semanas adyacentes visibles

### Monthly al cargar
- Mes actual (MAYO) centrado en el viewport
- Meses adyacentes visibles

### Scroll
- 1 scrollbar horizontal (tabla)
- 1 scrollbar vertical (página)
- Sticky header intacto
- Columnas fijas intactas
- Shell unificado UX-H4A intacto

---

## 6. Archivos Modificados

| Archivo | Acción |
|---------|--------|
| `frontend/src/utils/currentPeriodFocusEngine.js` | Modificado: `calculateScrollTarget` con soporte por grain |
| `frontend/src/components/BusinessSliceOmniviewMatrix.jsx` | Modificado: `scrollToCurrentPeriod`, auto-scroll efecto, nuevo ref |
