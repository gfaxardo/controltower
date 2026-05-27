# RUNTIME RECURSION RISK AUDIT

**Versión:** 1.0.0
**Fecha:** 2026-05-26
**Alcance:** `frontend/src/config/`, `frontend/src/utils/`, `frontend/src/components/omniview/`
**Total archivos auditados:** 35

---

## Resumen

| Clasificación | Cantidad | Detalle |
|---------------|----------|---------|
| **fix_now** | **0** | Ningún patrón circular/recursivo confirmado |
| **risky** | **0** | Ningún near-circular pattern a un cambio de ser circular |
| **watch** | **4** | Inversión arquitectónica (utils → components) — seguro hoy, vulnerable a futuro |
| **safe** | **31** | Sin patrones circulares intra-file ni inter-file |

**Veredicto global:** El grafo de imports es un DAG puro. No hay ciclos.

---

## 1. Intra-file circular calls (función A → B → A)

**Resultado: Ninguno detectado.**

En todos los archivos, el grafo interno de llamadas forma un DAG. Las funciones helper son llamadas por funciones compuestas sin ciclos de retorno.

| Archivo | Cadena interna | Veredicto |
|---------|---------------|-----------|
| `operationalDecisionSeverity.js` | `sortByDecisionPriority` → `getDecisionRank` + `getDecisionSeverity` → `normalizeDecisionSignal` | safe |
| `diagnosticExplanationEngine.js` | `buildDiagnosticExplanation` → `extractDiagnosticFactors` → `extractDominantDiagnosticFactor` | safe |
| `operationalMomentumPriority.js` | `extractMomentumPriorityFromMatrix` → `classifyMomentumRisk` → `detectConsecutiveDecline` | safe |
| `omniviewMatrixUtils.js` | `computeDeltas` → `_comparisonMetaForDelta`, `_isPartialState` | safe |
| `alertingEngine.js` | `buildAlertPayload` → `computePriorityScore` + `classifyAlert` + `mapToAction` | safe |
| `controlTowerNavigationRegistry.js` | `getVisibleTabs()` → `getVisibleNavigation()` | safe |

---

## 2. Inter-file circular imports (X importa Y, Y importa X)

**Resultado: Ninguno detectado.**

Toda relación inter-file es unidireccional y no forma ciclos.

### Watch items — inversión arquitectónica utils → components

Estos archivos en `utils/` importan desde `components/omniview/`. No es circular hoy porque los targets no tienen imports del proyecto, pero si alguien agrega un import de `utils/` en `omniviewMatrixUtils.js` o `projectionMatrixUtils.js`, se formaría un ciclo:

| Archivo | Importa desde | Riesgo |
|---------|--------------|--------|
| `utils/omniviewExport.js` | `../components/omniview/omniviewMatrixUtils.js` | **watch** |
| `utils/omniviewExport.js` | `../components/omniview/projectionMatrixUtils.js` | **watch** |
| `utils/projectionCellDisplayModel.js` | `../components/omniview/omniviewMatrixUtils.js` | **watch** |
| `utils/projectionCellDisplayModel.js` | `../components/omniview/projectionMatrixUtils.js` | **watch** |

**Recomendación:** Mover `omniviewMatrixUtils.js` y `projectionMatrixUtils.js` a `utils/` para romper la inversión, o establecer regla de lint que prohíba imports de `utils/` desde `components/omniview/omniviewMatrixUtils.js`.

---

## 3. Re-export indirection (barrel/index.js)

**Resultado: Ninguno.** No existen archivos `index.js` barrel en los tres directorios. Todos los imports son explícitos desde archivos individuales.

---

## 4. Nota adicional

`components/omniview/rootCauseEngine.js` (línea 21) define su propio array local `PROJECTION_KPIS` en vez de importarlo desde `projectionMatrixUtils.js` donde está la fuente canónica. No es circular pero es riesgo de divergencia.

---

## 5. Conclusión

El codebase está limpio de dependencias circulares. El único riesgo abierto es la inversión arquitectónica `utils → components` (4 archivos en watch), que debe monitorearse en cada code review para evitar que se convierta en un ciclo si se agregan nuevos imports.

**Próxima auditoría:** Cada 2 sprints o al modificar imports entre `utils/` y `components/omniview/`.
