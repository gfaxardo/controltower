# RUNTIME RECURSION POSTMORTEM

**Versión:** 1.0.0
**Fecha:** 2026-05-26
**Severidad:** CRÍTICA
**Categoría:** Runtime Architecture Bug
**Archivo afectado:** `frontend/src/config/operationalMaturityRegistry.js`

---

## 1. Resumen ejecutivo

El deployment de la capa de gobernanza de madurez operacional (1H.4) introdujo un bug de recursión mutua entre dos funciones públicas del registry: `isProductionReady()` y `getCapabilityMeta()`. El bug no fue detectado por `npm run build` (Vite no lanza error en ciclos de runtime JS puro), pero rompió completamente la aplicación en navegador con `Maximum call stack size exceeded`. Pantalla en blanco. Cero funcionalidad.

---

## 2. Síntoma

- **Error en consola del navegador:** `Uncaught RangeError: Maximum call stack size exceeded`
- **Stack trace:** alternaba entre `isProductionReady` y `getCapabilityMeta`
- **Estado de la app:** página en blanco, sin renderizado
- **`npm run build`:** PASS (sin errores ni warnings)
- **`npm run dev`:** PASS (Vite dev server arranca sin errores)

---

## 3. Impacto

- **Usuarios afectados:** todos (aplicación inutilizable)
- **Duración del incidente:** desde commit `30dcb52` (Fase 1H.4 Maturity Governance Layer) hasta commit `1f18ca5` (fix)
- **Funcionalidad perdida:** 100% de la SPA — no se renderizaba ningún componente
- **Detección:** manual, al abrir la app en navegador tras deploy

---

## 4. Causa raíz

### Recursión mutua entre dos funciones del mismo módulo:

```
isProductionReady(moduleKey)
  → llama a getCapabilityMeta(moduleKey)
    → en su return, computaba productionReady:
      → isProductionReady(moduleKey)
        → llama a getCapabilityMeta(moduleKey)
          → ...
```

### Código original (roto):

**`getCapabilityMeta()` (línea ~572):**
```js
productionReady: isProductionReady(moduleKey),
```

**`isProductionReady()` (línea ~588):**
```js
export function isProductionReady(moduleKey) {
  const meta = getCapabilityMeta(moduleKey)
  ...
}
```

`getCapabilityMeta` usaba `isProductionReady` para computar el campo `productionReady`, y `isProductionReady` llamaba a `getCapabilityMeta` para obtener la metadata. Ciclo infinito.

---

## 5. Por qué build no lo detectó

Vite (ESBuild + Rollup) no realiza análisis estático de ciclos de llamadas JavaScript. La recursión mutua es un problema de ejecución, no de sintaxis ni de tipos. El bundler solo verifica que las dependencias de módulos se puedan resolver, no que las funciones internas de un módulo formen ciclos válidos.

**Lección:** `npm run build` verde NO garantiza que la app funcione en runtime.

---

## 6. Qué se investigó incorrectamente

Durante la diagnosis inicial se sospechó de:
- Componentes de Omniview renderizando infinitamente
- React re-renders por dependencias de useEffect mal declaradas
- Problemas de Vite HMR en desarrollo

**Error de diagnóstico:** se asumió que el bug era del componente visual (Omniview) cuando era una dependencia de arquitectura runtime global (el registry de gobernanza).

---

## 7. Fix aplicado

### Commit: `1f18ca5`

Se eliminó la llamada circular. `getCapabilityMeta()` ahora computa `productionReady` inline en vez de delegar en `isProductionReady()`.

### Código corregido (`getCapabilityMeta`, línea 572):

```js
productionReady: entry.maturity === MATURITY.STABLE
  || entry.maturity === MATURITY.ACTIVE
  || (entry.maturity === MATURITY.HARDENING && entry.engine === ENGINE_OWNER.CONTROL_FOUNDATION),
```

`isProductionReady()` sigue existiendo como helper público y continúa delegando en `getCapabilityMeta()`. Esto es seguro porque `getCapabilityMeta()` ya no llama de vuelta a `isProductionReady()`. El ciclo se rompió unilateralmente desde `getCapabilityMeta`:

```js
// isProductionReady → getCapabilityMeta → (lee registry, sin más llamadas)  ← DAG, seguro
export function isProductionReady(moduleKey) {
  const meta = getCapabilityMeta(moduleKey)
  if (!meta) return false
  if (meta.maturity === MATURITY.STABLE || meta.maturity === MATURITY.ACTIVE) return true
  if (meta.maturity === MATURITY.HARDENING && meta.engine === ENGINE_OWNER.CONTROL_FOUNDATION) return true
  return false
}
```

---

## 8. Patrón prohibido

### REGLA DE ORO

```
helper A → helper B → helper A  ← PROHIBIDO
```

En el registry de madurez operacional:

```
getCapabilityMeta() → isProductionReady() → getCapabilityMeta()  ← PROHIBIDO
```

### Reglas específicas:

1. **`getCapabilityMeta()` NO puede llamar a helpers públicos que a su vez llamen a `getCapabilityMeta()`.**
2. **Los helpers públicos del registry (`isProductionReady`, `getMaturity`, `getCapabilityMeta`, `isModuleVisible`, etc.) no pueden formar ciclos de llamadas.**
3. **Si un helper necesita un dato que otro helper computa, debe duplicar la lógica inline O extraerla a una función interna privada que ambos consuman sin circularidad.**
4. **Toda función pública del registry debe resolver su resultado consultando directamente `OPERATIONAL_MATURITY_REGISTRY`, nunca delegando en otra función pública del mismo módulo que a su vez lea el registry para el mismo módulo.**

### Anti-patrones detectados por esta regla:

| Anti-patrón | Descripción |
|---|---|
| `registry helper → capability meta → registry helper` | La recursión de este bug |
| `metadata resolver → status checker → metadata resolver` | Mismo patrón con otros nombres |
| `index re-export circular` | Módulo A re-exporta B, B re-exporta A |

---

## 9. Cómo prevenir regresión

### Guardrailes técnicos:

1. **Script de QA:** `npm run qa:maturity-registry` — ejecuta todas las funciones públicas del registry contra módulos conocidos y detecta stack overflow.
2. **Auditoría de circularidad:** revisión periódica de `frontend/src/config/`, `frontend/src/utils/`, `frontend/src/components/omniview/` buscando patrones de llamadas circulares.
3. **Regla de linting mental:** toda función pública del registry debe leer de `OPERATIONAL_MATURITY_REGISTRY` directamente, sin delegar en otra función pública.

### Gobernanza:

- **Code review:** cualquier PR que modifique el registry debe validar que no se introduzcan ciclos de llamadas entre funciones públicas.
- **Pre-merge check:** ejecutar `npm run qa:maturity-registry` antes de mergear.

---

## 10. Checklist futuro

Al modificar `operationalMaturityRegistry.js` o cualquier archivo del registry:

- [ ] ¿Alguna función pública nueva llama a otra función pública del mismo módulo?
- [ ] ¿Esa otra función pública llama de vuelta (directa o indirectamente)?
- [ ] ¿Se ejecutó `npm run qa:maturity-registry` y pasó?
- [ ] ¿Se ejecutó `npm run build` y pasó?
- [ ] ¿Se probó la app en navegador (no solo build)?
- [ ] ¿Se verificó que `getCapabilityMeta()` no llame a `isProductionReady()` ni viceversa?

---

**Cierre técnico:** Bug resuelto. Guardrail establecido. No regresión.

**Próxima revisión:** Cada modificación del registry de madurez operacional.
