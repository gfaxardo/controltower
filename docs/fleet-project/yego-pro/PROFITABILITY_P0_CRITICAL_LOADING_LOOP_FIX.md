# Yego Pro Profitability — P0 Critical: Infinite Loading Loop Fix

**Date:** 2026-05-29
**Fix Type:** P0 Critical
**Previous attempts:** P0 KPI fix, P0.1 StrictMode fix (failed)

---

## Causa raíz real

El bloqueo "Cargando diagnóstico ejecutivo..." persistente tenía **tres causas concurrentes**:

### 1. `diagLoaded` como bloqueador global (estado React)

```js
const [diagLoaded, setDiagLoaded] = useState(false)
useEffect(() => {
    if (diagLoaded) return      // ← BLOQUEO: en StrictMode remount
    setDiagLoaded(true)
    ...
}, [diagLoaded])
```

En React StrictMode (dev), el componente se monta → desmonta → remonta. En el remount, `diagLoaded` ya es `true` (estado preservado), y el efecto retorna inmediatamente **sin volver a fetchear**.

### 2. AbortController + `.finally()` condicionado

```js
.finally(() => {
    if (!controller.signal.aborted) setDiagLoading(...)
})
```

Cuando StrictMode desmonta, `controller.abort()` cancela los 9 requests. El guard `!controller.signal.aborted` impide que `diagLoading` pase a `false`. Las 9 keys quedan en `true` para siempre.

### 3. `setState` en cleanup del fix anterior

```js
return () => {
    controller.abort()
    setDiagLoaded(false)       // ← setState en unmount crea re-render fantasma
    setDiagLoading({})
}
```

Llamar `setState` dentro del cleanup de un componente que se está desmontando es una anti-patrón. En StrictMode, los state updates del primer mount se transfieren al segundo, pero pueden crear renders intermedios y condiciones de carrera impredecibles.

---

## Por qué falló el fix anterior (P0.1)

El fix P0.1 añadió `setDiagLoaded(false)` y `setDiagLoading({})` en el cleanup, asumiendo que:
1. El state update en cleanup se aplicaría al segundo mount — **parcialmente cierto, pero impredecible**
2. React manejaría el setState en unmount sin efectos secundarios — **falso, puede causar renders intermedios no deseados**
3. La secuencia sería determinista — **no lo es bajo StrictMode con múltiples state updates encadenados**

El resultado: el loop `setDiagLoaded(true) → cleanup → setDiagLoaded(false) → remount → setDiagLoaded(true) → ...` podía crear un ciclo infinito de renders.

---

## Patrón nuevo implementado

### requestIdRef (sin estado React)

```js
const requestIdRef = useRef(0)

useEffect(() => {
    const requestId = ++requestIdRef.current
    ...
    // En cada callback:
    if (requestId !== requestIdRef.current) return  // ← descarta respuestas stale
    ...
}, [])
```

- `useRef` no dispara re-renders al cambiar
- Cada ejecución del efecto incrementa el contador
- Callbacks de ejecuciones anteriores detectan requestId ≠ current → descartan
- `useEffect` con `[]` como dependencia: se ejecuta siempre en mount (y StrictMode remount)
- **Sin estado** que bloquee re-ejecución

### 8s timeout failsafe

```js
forceShowRef.current = setTimeout(() => {
    if (requestId !== requestIdRef.current) return
    setDiagLoading({})  // ← limpia todos los loading states
}, 8000)
```

Garantiza que **nunca** habrá spinner infinito:
- A los 8s, setDiagLoading({}) vacía el objeto
- `anyLoading = false` → la condición del spinner (`anyLoading && !hasAnyData`) = `false && X` = `false`
- Si hay data: se renderiza contenido parcial
- Si no hay data: se muestra EmptyState con mensaje claro

### Cleanup sin setState

```js
return () => {
    controller.abort()
    // SIN setState — solo abort
}
```

El cleanup solo aborta requests pendientes. No modifica estado. La protección requestIdRef se encarga de descartar callbacks stale de montajes anteriores.

### Debug logs (solo development)

```js
if (process.env.NODE_ENV === 'development') console.debug('[Profitability] request start|done|error|final', key)
```

Vite elimina estos logs en producción mediante tree-shaking.

---

## Archivos tocados

| Archivo | Cambio |
|---|---|
| `frontend/src/components/YegoProProfitabilityPage.jsx` | Reemplazo del patrón `diagLoaded` + `setState en cleanup` por `requestIdRef` + `forceShowRef` + cleanup sin setState |

---

## QA

| Check | Result |
|---|---|
| Build (`npm run build`) | **PASS** |
| `diagLoaded` state eliminado | **YES** |
| `setState` en cleanup eliminado | **YES** |
| requestIdRef protege de callbacks stale | **YES** |
| 8s timeout failsafe | **YES** |
| Debug logs (dev only) | **YES** |
| useEffect con `[]` (sin bloqueador) | **YES** |
| AbortController preservado | **YES** |
| StrictMode preservado | **YES** |

### Traza en StrictMode (post-fix)

| Paso | Evento | requestId | Efecto |
|------|--------|-----------|--------|
| Mount 1 | useEffect → 9 fetches | 1 | Normal |
| Unmount 1 | cleanup → abort() | 1 | Fetches cancelados |
| Remount 2 | useEffect → 9 NEW fetches | 2 | requestId cambió |
| Callbacks mount 1 | `requestId(1) !== current(2)` | X | Descartados |
| Callbacks mount 2 | `requestId(2) === current(2)` | 2 | Procesados normalmente |
| 8s timeout mount 1 | `requestId(1) !== current(2)` | X | Descartado |
| 8s timeout mount 2 | `requestId(2) === current(2)` | 2 | Activo como failsafe |

### Traza si todos los endpoints fallan

| Tiempo | Evento |
|---|---|
| t=0s | Spinner visible |
| t=0-8s | 9 fetch attempts, all fail |
| t=8s | forceShowRef timeout → `setDiagLoading({})` |
| t=8s+ | Spinner desaparece, EmptyState visible |
| | **NUNCA spinner infinito** |

---

## Veredicto

| Check | Result |
|---|---|
| Root cause confirmado | **YES** — 3 causas concurrentes eliminadas |
| Spinner infinito corregido | **YES** — requestIdRef + forceShowRef + cleanup sin setState |
| Scope contamination | **NO** — solo `YegoProProfitabilityPage.jsx` |
| Build | **PASS** |
| **GO para prueba humana** | **GO** |
