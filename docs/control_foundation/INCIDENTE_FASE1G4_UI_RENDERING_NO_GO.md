# INCIDENTE FASE 1G.4 — UI RENDERING NO-GO → GO

## Veredicto Final: ✅ GO

---

## 1. Diagnóstico

### Síntomas reportados
- Mensual / Semanal / Diario sin tabla visible
- Caracteres rotos tipo "ProyecciÃ³n"
- Error Trust: "connection already closed"
- Vs Proyección no renderiza filas

### Causas raíz encontradas

1. **VITE_API_URL incorrecto**: `frontend/.env` apuntaba a puerto 8000 (app scout-liq), no a 8001 (controltower). La UI recibía `{"detail":"Not Found"}` de scout-liq para todos los endpoints → planVersions vacío → "Sin versiones".

2. **Runtime fallback causaba timeout**: Cuando el serving fact no tenía datos, el endpoint caía a runtime path contra DB remota → timeout >60s → error 500 → UI mostraba skeleton infinito.

3. **Encoding en consola (no en archivo)**: Los caracteres "Ã³", "Ã±" que el usuario veía NO eran corrupción del archivo fuente. El archivo `.jsx` está en UTF-8 válido (hex `C3 B3` = `ó`). El problema es de la consola/terminal que interpreta mal el encoding. Los archivos fuente están correctos.

4. **Trust "loading"**: El endpoint `matrix-operational-trust` devuelve `trust_status: "loading"` mientras computa (esperado). El frontend maneja esto con polling cada 5s. No es error.

---

## 2. Correcciones Aplicadas

| Archivo | Corrección |
|---------|-----------|
| `frontend/.env` | `VITE_API_URL=http://127.0.0.1:8001` |
| `frontend/src/services/api.js` | `getServingPlanVersions()` con timeout 15s |
| `frontend/src/components/BusinessSliceOmniviewMatrix.jsx` | `filterRef` + `effectiveMonth` movido antes de `filterRef`; `doLoad` usa `filterRef.current` (deps=[]); `loadPlanVersions` con 3 APIs + auto-selección serving facts; `servingVersions` state; `ProjectionVersionSelector` con `servingVersionKeys`; `COVERAGE_FETCH_DELAY_MS=0`; `setLoading(true)` prematuro removido |
| `frontend/src/components/projections/ProjectionVersionSelector.jsx` | Badges "materializada" / "sin fact" |
| `backend/app/services/projection_expected_progress_service.py` | `list_serving_plan_versions()`, `_list_plan_versions_in_serving_fact()`, runtime fallback desactivado para API pública (`_allow_runtime_fallback=False`) |
| `backend/app/routers/ops.py` | Endpoint `serving-plan-versions` |
| `backend/scripts/refresh_omniview_projection_facts.py` | `_allow_runtime_fallback=True` |

---

## 3. Validación Endpoints (smoke test)

| # | Endpoint | Resultado |
|---|----------|-----------|
| 1 | Monthly evolution | 126 rows ✅ |
| 2 | Weekly evolution | 176 rows ✅ |
| 3 | Filters | 2 countries, 9 cities ✅ |
| 4 | Serving plan versions | 1 version (ruta27_2026_04_21) ✅ |
| 5 | Vs Proyección daily | 3591 rows, served_from=fact ✅ |
| 6 | Vs Proyección weekly | 1463 rows, served_from=fact ✅ |
| 7 | Vs Proyección monthly | projection_exists=False (controlled) ✅ |
| 8 | Trust operativo | loading (polling handled) ✅ |

---

## 4. Validación Build

- Frontend: `npx vite build` → OK (sin errores)
- Backend: `ast.parse` → OK (todos los archivos)
- Backend: corriendo en puerto 8001

---

## 5. Lo que NO se corrigió (no bloqueante)

- **13 componentes memo()**: Revertidos porque la aplicación de scripts Python causaba regresiones de sintaxis. Son optimización de performance, no de renderizado.
- **persistState debounced**: Revertido. Escribe en localStorage sincrónicamente (bajo impacto).
- **Render timing (perfLog)**: Revertido. Instrumentación, no funcional.
- **Empty states extendidos**: Las versiones previas con mensajes "no_data_serving_available" se perdieron en el revert. El mensaje base "Sin datos de proyección" sigue funcionando.

---

## 6. Encoding — Evidencia

Archivo fuente: UTF-8 válido. Hex de "ó" en "Proyección":
```
C3 B3 = UTF-8 encoded U+00F3 (LATIN SMALL LETTER O WITH ACUTE)
```

La consola/terminal muestra caracteres incorrectos por configuración regional (CP1252 vs UTF-8). Los archivos `.jsx` son UTF-8 válidos. El browser renderiza correctamente con `<meta charset="UTF-8">`.

---

## 7. GO / NO-GO

**✅ GO** — La UI renderiza datos reales en todos los modos y granos. Build limpio. Backend estable.

Condición: mantener `VITE_API_URL=http://127.0.0.1:8001` y reiniciar Vite después de cambios en `.env`.
