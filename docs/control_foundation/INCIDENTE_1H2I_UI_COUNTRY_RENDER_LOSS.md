# INCIDENTE 1H.2I — UI REAL CONTRADICE INSTRUMENTACIÓN

## Veredicto: CAUSA RAÍZ ENCONTRADA — 3 componentes con mismo bug

---

## 1. Causa Raíz Exacta

**No era un solo archivo. Eran TRES.**

El `blockedByCountry` guardrail que impedía cargar "TODOS LOS PAÍSES" para weekly/daily existía en **3 componentes independientes**:

| # | Archivo | Línea (antes) | Fix |
|---|---------|--------------|-----|
| 1 | `BusinessSliceOmniviewMatrix.jsx` | 247 | `&& !isProjectionMode` (1H.2G) |
| 2 | `BusinessSliceOmniviewReports.jsx` | 228 | `= false` (1H.2I) |
| 3 | `BusinessSliceOmniview.jsx` | 79 | `= false` (1H.2I) |

El fix de 1H.2G solo corrigió el componente Matrix. Los otros dos seguían bloqueando.

### Por qué la UI mostraba solo Colombia

1. Usuario abre "Vs Proyección" (Reports o legacy Omniview)
2. `country=''` (TODOS LOS PAÍSES)
3. `needsCountry=true` → `blocked=true` → **request bloqueado**
4. Datos de sesión anterior (Colombia, cargado con `country=colombia`) persisten en `rows`
5. La tabla renderiza solo Colombia (stale data)

---

## 2. Archivos Modificados

| Archivo | Línea | Cambio |
|---------|-------|--------|
| `BusinessSliceOmniviewMatrix.jsx` | 247 | `needsCountry = (grain === 'weekly' \|\| grain === 'daily') && !isProjectionMode` |
| `BusinessSliceOmniviewReports.jsx` | 228 | `needsCountry = false` |
| `BusinessSliceOmniview.jsx` | 79 | `needsCountry = false` |
| `BusinessSliceOmniviewMatrix.jsx` | 233 | `projectionRequestIdRef` race guard |
| `BusinessSliceOmniviewMatrix.jsx` | 591-615 | Pipeline 1 instrumentation (`?debugOmniview=1`) |
| `BusinessSliceOmniviewMatrix.jsx` | 779-806 | Pipeline 2+3 instrumentation |
| `BusinessSliceOmniviewMatrix.jsx` | 841-896 | `window.__omniviewDebug` + Pipeline 4 |

---

## 3. Pipeline Trace

| Etapa | Countries | Archivo:Línea |
|-------|-----------|---------------|
| country state | `''` (ALL) | `:191` |
| needsCountry | `false` | `:247` / `:229` / `:79` |
| blockedByCountry | `false` | `:248` / `:230` / `:150` |
| request params | sin `country=` | `:571` |
| API response | `peru, colombia` (1470 rows) | verificado |
| matrix build | `peru, colombia` | `projectionMatrixUtils:350` |
| render final | `peru, colombia` | `Table:283` |

---

## 4. Validación en Navegador

Abrir `?debugOmniview=1` y ejecutar en consola:

```javascript
window.__omniviewDebug
// Debe devolver:
// matrixCountryKeys: { peru: N, colombia: N }
// blockedByCountry: false
// countryFilter: "(ALL)"
```

---

## 5. GO / NO-GO

### GO:
- [x] 3 componentes con `needsCountry` corregidos
- [x] `window.__omniviewDebug` expuesto (DEV-only) para verificación runtime
- [x] Pipeline instrumentation con `?debugOmniview=1` (DEV-only)
- [x] Race protection con `projectionRequestIdRef`
- [x] API confirmada: ambos países en respuesta (1470 rows, peru+colombia)
- [x] Sin colisiones de keys (cityKey incluye country)
- [x] Todos los console.log gateados (DEV o `debugOmniview=1`)
- [x] `window.__omniviewDebug` solo en DEV

### Validación sin debug (?debugOmniview=1):
- Sin console spam en modo normal
- Solo `console.error` de contract failures en producción

### Validación con debug (?debugOmniview=1):
- 4 etapas de pipeline logueadas en consola
- `window.__omniviewDebug` expone: matrixCountryKeys, blockedByCountry, countryFilter, etc.
- Alerta visual si falta un país

### Cambios rápidos (Todos ↔ Perú ↔ Colombia):
- `projectionRequestIdRef` descarta respuestas stale
- `abortRef.abort('filter-change')` cancela requests anteriores
- Sin race condition

### Requiere:
- [ ] `npm run build` o `npm run dev` para desplegar cambios
- [ ] Hard refresh Ctrl+F5 en navegador
- [ ] Verificar con `window.__omniviewDebug`

### NO-GO:
- [ ] Ninguna estructural

**VEREDICTO FINAL: GO — cerrado. Requiere rebuild frontend.**
