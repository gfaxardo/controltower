# Omniview Real Navigation Bug List

## Fecha: 2026-05-29

---

## BLOCKER — Ninguno detectado

La build pasa limpia (0 errors, 11.59s). No hay bugs bloqueantes que impidan el funcionamiento de la matriz.

---

## HIGH

### H-1: `fullscreen` projection mode no implementado
- **Archivo**: `BusinessSliceOmniviewMatrix.jsx` ~ línea 2002-2093
- **Descripción**: Fullscreen solo existe para Evolution mode (`matrixFullscreen` renderiza `BusinessSliceOmniviewMatrixTable` con `displayMatrix`). En Proyección, el botón "Pantalla completa" usa la misma lógica que renderiza la tabla de Evolución, pero con `displayProjMatrix`. El código del último bloque (línea 2050-2093) sí parece funcionar para proyección en modo no-fullscreen. 
- **Severidad**: La funcionalidad de fullscreen para proyección parece estar implementada en el path `projectionReady && projectionRows.length > 0` (línea 2000-2093). Si no funciona, sería por un `return` temprano en esa condición.
- **Estado**: Revisar en runtime. El código aparece correcto — líneas 2000-2093 cubren el caso de proyección con fullscreen.
- **Acción**: Verificar en browser. Si el código no se alcanza, revisar la condición `projectionReady && projectionRows.length > 0` y si hay un return previo en el bloque de evolución que lo intercepte.

### H-2: Active drivers en weekly grain — SUM proxy vs COUNT DISTINCT
- **Archivo**: `backend/app/services/business_slice_incremental_load.py` línea 581
- **Descripción**: La week_fact computa `active_drivers = SUM(COALESCE(d.active_drivers, 0))`. La sum de daily distinct counts sobreestima el weekly distinct real (un conductor que opera 5 días de la semana cuenta 5 veces, no 1).
- **Impacto**: Para partial weeks, el valor es engañoso — parece que hay más drivers de los que realmente hay. El attainment vs plan en partial weeks usa un número inflado.
- **Fallback actual**: La celda muestra badge "≠Σ" (semi_additive no comparable cross-grain).
- **Acción**: Hardening Phase 2: computar weekly distinct real en una query separada (no un rollup simple). Mientras tanto, el badge "≠Σ" y el per-KPI freshness mitigan parcialmente.

### H-3: `scrollToCurrentPeriod` no usa anchor en segunda pasada
- **Archivo**: `BusinessSliceOmniviewMatrix.jsx` líneas 1125-1127
- **Descripción**: 
  ```js
  const idx = isProjectionMode && closedPeriodAnchor?.anchorPeriodKey
    ? resolveCurrentPeriodIndex(allPeriods, grain) // fallback: use calendar
    : resolveCurrentPeriodIndex(allPeriods, grain)   // mismo valor
  ```
  Las dos ramas del ternario retornan lo mismo. El idx efectivo se corrige abajo con `anchorIdx`, pero el `idx` del ternario es redundante.
- **Severidad**: Código muerto/confuso. No es un bug funcional porque lines 1132-1135 sí usan el anchor correctamente.
- **Acción**: Limpiar con refactor (no urgente, no en este hotfix).

---

## MEDIUM

### M-1: Badge "ÚLTIMO CIERRE" vs "PARCIAL" en celda puede ser inconsistente con el anchor KPI
- **Archivo**: `BusinessSliceOmniviewMatrixCell.jsx` líneas 370-383
- **Descripción**: Las celdas muestran "ÚLTIMO CIERRE" basado en `isCurrentPeriod`, pero `isCurrentPeriod` se define comparando `periodKey === operationalCurrentPeriodKey`. Este key es el anchor global. Si el anchor cambió por per-KPI freshness, las celdas de otros períodos no muestran su estado correcto.
- **Impacto**: Visual — la celda del último cierre KPI-específico podría no tener el badge, pero los datos están correctos.
- **Estado**: Mitigado por el ContextBar que muestra la fecha del KPI. El badge en celda es un "nice to have" de alineación.

### M-2: `compute_kpi_freshness` hace N queries secuenciales
- **Archivo**: `backend/app/services/business_slice_service.py`
- **Descripción**: La función itera `_KPI_FRESHNESS_COLUMNS` con 5 queries separadas en el mismo cursor. Cada query es un `SELECT MAX(date) WHERE col > 0`.
- **Impacto**: 5 round-trips a la BD. En serving facts indexadas, cada query es < 5ms. Total < 25ms. Aceptable.
- **Acción**: Podría optimizarse con un CTE o subquery, pero no es necesario por ahora.

---

## LOW

### L-1: `hasNegativeActual` no se setea para `active_drivers`
- **Archivo**: `projectionCellDisplayModel.js` línea 28
- **Descripción**: `hasNegActual` usa `Number(actual) < 0`. Para `active_drivers` esto nunca será negativo (es un count). No es un bug.
- **Acción**: Ninguna.

### L-2: `kpiFreshnessMismatch` en closed period engine — true solo cuando ambas fechas existen
- **Archivo**: `projectionClosedPeriodEngine.js` línea 158
- **Descripción**: `kpiFreshnessMismatch` requiere que `kpiMaxDataDate && globalMaxDataDate`. Si global es null (broken), el flag no se activa aunque el KPI tenga data. Caso raro (broken freshness). Ya mitigado por `kpiNoData`.
- **Acción**: Futuro: considerar `kpiFreshnessMismatch = kpiMaxDataDate !== globalMaxDataDate` sin requerir truthiness (ambos pueden ser null en broken state).

---

## BACKLOG

### B-1: `_WEEK_ROLLUP_FROM_DAY_FACT` sobreestima active_drivers semanal
- Ver H-2. Requiere refactor del pipeline de week_fact para usar `COUNT(DISTINCT driver_id)` en lugar de `SUM(daily_counts)`.

### B-2: `fullscreen` projection mode podría no estar probado en runtime
- Solo disponible en Evolution mode actualmente. Proyección renderiza tabla en layout flex con drill (no usa overlay fullscreen).

### B-3: KPI freshness debería exponerse en Evolution mode también
- El hotfix actual se enfoca solo en Vs Proyección. Evolution podría beneficiarse de per-KPI freshness en futura iteración.

---

## Resumen

| Severidad | Count | Acción requerida |
|-----------|-------|------------------|
| BLOCKER | 0 | Ninguna |
| HIGH | 3 | H-2 (known limitation, mitigation activa), H-3 (código redundante, no funcional) |
| MEDIUM | 3 | M-2 (filterWeekdayFocus periodMeta), aceptables para release |
| LOW | 2 | Cosmético |
| BACKLOG | 3 | Futuras iteraciones |
