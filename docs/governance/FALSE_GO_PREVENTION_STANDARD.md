# FALSE GO PREVENTION STANDARD

**Motor:** Omniview Governance — RCA  
**Fecha:** 2026-06-04  
**Investigación:** OMNI-RCA-001  
**Pregunta central:** ¿Por qué Omniview recibió GO cuando todavía no era confiable?

---

## PARTE A — CRONOLOGÍA RECONSTRUIDA

### Hito 1: OMNI-COV-006 — UI/Serving Reconciliation Audit (2026-06-03)

**Archivo:** `docs/omniview/UI_SERVING_RECONCILIATION_AUDIT.md`
**Script:** `backend/scripts/audit_omniview_ui_serving_reconciliation.py`

**Qué validó:**
- Query real a `/ops/business-slice/daily`, `/weekly`, `/monthly`
- Comparación de datos serving vs UI rendering contract
- Field mapping: API → Frontend → Render

**Resultado:** **NO GO — 10 FAIL, 1 WARNING, 5 PASS**

| Grain | Trips | Revenue | Drivers | Ticket | TPD |
|-------|-------|---------|---------|--------|-----|
| Daily | FAIL (25%) | FAIL (0%) | FAIL (25%) | FAIL (25%) | FAIL (25%) |
| Weekly | FAIL (37.5%) | FAIL (0%) | FAIL (37.5%) | FAIL (37.5%) | FAIL (37.5%) |
| Monthly | PASS (100%) | WARNING (50%) | PASS (100%) | PASS (100%) | PASS (100%) |

**Evidencia documentada en el archivo:**
- Línea 94-109: Matriz grain×metric con 10 FAILs
- Línea 233: Veredicto NO GO

**Bugs detectados:**
- B1 (L175): `confidence.[object Object]%` en `BusinessSliceOmniviewMatrix.jsx:1767`
- B2 (L176): Revenue usa `revenue_yego_net` en vez de `revenue_yego_final` en `omniviewMatrixUtils.js:14,664,860`
- B3 (L184): day_fact data loss recurrente
- B4 (L185): week_fact data loss recurrente

**Condiciones para GO (L244-248):**
1. Restaurar day_fact y week_fact (refresh)
2. Corregir B1
3. Corregir B2
4. Re-ejecutar script → 0 FAIL

---

### Hito 2: OMNI-COV-006-FIX — Corrección de Bugs (2026-06-03)

**Qué se corrigió (CÓDIGO):**
- **B1:** `confidence.score` en vez de `confidence` (objeto → propiedad numérica)
  - Archivo: `BusinessSliceOmniviewMatrix.jsx:1767`
- **B2:** `enrichRow()` con COALESCE: `revenue_yego_final ?? revenue_yego_net`
  - Archivo: `omniviewMatrixUtils.js:615-617`

**Qué NO se corrigió (DATOS):**
- B3: day_fact data loss — los datos de Mayo 26-31 seguían ausentes
- B4: week_fact data loss — S18-S22 seguían ausentes
- El COALESCE en el frontend no sirve si AMBOS campos son NULL en el API response

**Qué se hizo con los datos:**
- Probable refresh de serving facts restauró day_fact y week_fact temporalmente
- La reconciliación fue re-ejecutada y dio "14 PASS, 1 WARN, 0 FAIL"
- **El documento original de la auditoría (10 FAILs) NO fue actualizado**
- Persiste en el repo como evidencia de lo que REALMENTE se encontró

---

### Hito 3: OMNI-COV-006-CLOSE — Cierre de Reconciliación (2026-06-03)

**Archivo:** `docs/omniview/OMNIVIEW_HARDENING_CLOSURE.md:27`

| Fase | Estado declarado | Estado real en auditoría |
|------|-----------------|------------------------|
| UI/Serving Reconciliation | **GO — 14 PASS, 1 WARN, 0 FAIL** | NO GO — 10 FAIL, 1 WARN, 5 PASS |

**Brecha:** La reconciliación se declaró GO basándose en una re-ejecución post-data-refresh, no en la auditoría original. La auditoría original que encontró los 10 FAILs sigue en el repo sin modificar.

---

### Hito 4: O4 — Visual Certification Report (2026-06-03)

**Archivo:** `docs/omniview/OMNIVIEW_VISUAL_CERTIFICATION_REPORT.md`

**Qué validó:**
- Matriz grain×metric (L72-88): **14 PASS, 1 WARNING**
- Reglas F1-F10: **0 FAIL**
- Screenshots: **15/15** capturados (referenciados, no verificables en este análisis)
- Build: PASS (4.97s)
- Backend: Operativo en 8001

**Veredicto:** **CONDITIONAL GO**

**Lo que la matriz visual dice (L72-88):**

| Grain | Metric | Serving declarado | UI Esperado | Status O4 |
|-------|--------|-------------------|-------------|-----------|
| Daily | Revenue | **100%** | Números con 2 decimales, COALESCE _final | **PASS** |
| Weekly | Revenue | **100%** | Números con 2 decimales, COALESCE _final | **PASS** |
| Monthly | Revenue | 50% | WARN: revenue_yego_net NULL | **WARNING** |

**Lo que la verdad era (OMNI-COV-006 original):**

| Grain | Metric | Serving real | UI Real | Status real |
|-------|--------|-------------|----------|-------------|
| Daily | Revenue | **0%** | Todo NULL | **FAIL** |
| Weekly | Revenue | **0%** | Todo NULL | **FAIL** |
| Monthly | Revenue | 50% | `_net` NULL | **WARNING** |

**Falsedad en O4:** Las celdas de Daily Revenue y Weekly Revenue se declararon "100% serving, PASS" cuando el script de reconciliación original había encontrado 0% y FAIL. O4 asumió que el fix B2 resolvía el problema de datos, pero B2 solo corrigió el código.

---

### Hito 5: O4.1 — Visual Certification Framework (2026-06-03)

**Archivo:** `docs/omniview/OMNIVIEW_VISUAL_CERTIFICATION_FRAMEWORK.md`

**Qué creó:**
- 10 reglas FAIL (F1-F10)
- 6 reglas WARNING (W1-W6)
- Checklist de 15 items
- 15 screenshots obligatorios

**Qué NO incluyó:**
- Validación de que los datos existen en serving ANTES de validar el render
- Validación de que Revenue tiene datos en todos los grains
- Validación de que el trust es coherente con los datos reales
- Validación de modo único (no Evolution + Vs Proy compitiendo)
- Validación de CLOSED/PARTIAL visibility en celdas
- Cualquier regla semántica (solo tokens y render)

**Supuesto incorrecto:** Que si el código está limpio (sin tokens prohibidos, build OK) y el backend responde, el sistema es operacionalmente confiable.

---

### Hito 6: O5 — Omniview Hardening Closure (2026-06-03)

**Archivo:** `docs/omniview/OMNIVIEW_HARDENING_CLOSURE.md`

**Veredicto:** **CLOSED — GO**

**Evidencia citada (L33-47):**

| Evidencia | Valor declarado |
|-----------|----------------|
| UI/Serving Reconciliation | **14 PASS, 1 WARN, 0 FAIL** |
| DOM Validation | **15/15 PASS** |
| Forbidden tokens | **0** |
| day_fact May 2026 | **645 filas, 817,513 trips** |
| week_fact S18-S22 | **112 filas, 5 semanas** |
| month_fact May 2026 | **23 filas, 817,513 trips** |

**Acción:** Diagnostic Engine 2A.3 desbloqueado.

**Warnings documentados y descartados (L53-58):**

| Warning | Decisión |
|---------|----------|
| Monthly revenue 50% cobertura | "No bloquea (dato existe en `_final`, no en serving view)" |
| Cross-grain data loss | "No bloquea (workaround: secuencia month→week→day)" |
| CT_SCHEDULER_ENABLED=false | "No bloquea (manual refresh)" |

---

### Hito 7: OMNI-P0A — Evidence Over Documents (2026-06-04, hoy)

**Evidencia extraída del sistema corriendo:**

| Grain | Estado real |
|-------|------------|
| Daily | 18 filas, solo Jun 1-3. Revenue: **100% NULL**. Mayo 26-31 ausente. |
| Weekly | **0 filas. FACT_LAYER_EMPTY.** `"No hay datos en ops.real_business_slice_week_fact"` |
| Monthly | 72 filas, Jun 2025-May 2026. Revenue: **92% NULL**. Solo Feb 2026 tiene valor (-88,964.5, negativo). |
| Projection | Solo datos para Colombia. Peru sin plan. KPI freshness: **TODO STALE** (lag 45-73 días). |
| Trust | Oscila entre **BLOCKED (conf 36)** y **SAFE (conf 99)** en minutos. |
| Focus | Bug en `projectionClosedPeriodEngine.js:142`: `allPeriods[length-2]` = Noviembre. |

**Trust score real:** **31/100**

**Conclusión:** El GO emitido el 2026-06-03 era inválido. Los datos citados como evidencia en O5 ya no existen 24 horas después.

---

## PARTE B — ANÁLISIS POR HITO

### OMNI-COV-006 (original)

| Validado | NO validado | Supuesto incorrecto |
|----------|------------|---------------------|
| Endpoints responden | Si los datos persisten entre refrescos | "Los datos son estables" — no lo son |
| Field mapping API→Frontend | Si `completed_revenue_sum` se mapea a `revenue_yego_net` en el payload | "La API expone revenue correctamente" — no lo hace |
| Cobertura de datos por grain | Si el data loss es temporal o permanente | "El refresh resuelve el data loss" — es recurrente |
| 10 FAILs documentados | Que estos FAILs desaparecieran permanentemente | "El fix de código arregla el problema de datos" — no |

### OMNI-COV-006-FIX

| Validado | NO validado | Supuesto incorrecto |
|----------|------------|---------------------|
| B1: `confidence.score` compila | Si el trust es numéricamente correcto | "Score=99 es correcto" — es falso cuando los datos faltan |
| B2: COALESCE en frontend | Si el backend expone `revenue_yego_final` en el campo `revenue_yego_net` | "El COALESCE frontend basta" — el backend no expone `_final` en `revenue_yego_net` |
| Código modificado | Si los datos en day_fact/week_fact realmente existen | "Los datos se restauraron" — temporalmente |

### O4 — Visual Certification

| Validado | NO validado | Supuesto incorrecto |
|----------|------------|---------------------|
| Tokens prohibidos (F1) | Datos reales en celdas de revenue | "100% serving coverage en daily/weekly revenue" — falso |
| Build frontend | Que el revenue en daily/weekly muestra números | "COALESCE _final basta" — el payload no incluye _final |
| Screenshots 15/15 | El contenido semántico de los screenshots | "Los screenshots muestran datos correctos" — muestran celdas vacías |
| 0 FAIL F1-F10 | Que F7 (métrica sin datos) fue correctamente evaluada | "F7 PASS porque B2 está arreglado" — B2 es fix de código, no de datos |

### O5 — Closure

| Validado | NO validado | Supuesto incorrecto |
|----------|------------|---------------------|
| day_fact: 645 filas | Si esas 645 filas cubren todas las fechas de Mayo | "645 filas = daily coverage completo" — no, solo cubre el agregado mensual |
| week_fact: 112 filas | Si 112 filas cubren todas las semanas | "112 filas = weekly coverage completo" — no están todas las semanas |
| Reconciliation: 14 PASS | El resultado de la auditoría ORIGINAL (10 FAIL) | "La mejor ejecución es la verdad" — la peor ejecución es la realidad operativa |
| Diagnostic Engine desbloqueado | Si Control Foundation está realmente estable | "Omniview está listo" — no lo estaba |

---

## PARTE C — CLASIFICACIÓN DE BRECHAS

### BUILD GAP (1 brecha)

**B2 fix sin propagación al payload:**
- `omniviewMatrixUtils.js:615-617`: `const canonicalRev = row.revenue_yego_final != null ? Number(row.revenue_yego_final) : Number(row.revenue_yego_net) || null`
- El COALESCE frontend lee `row.revenue_yego_final` y `row.revenue_yego_net`
- **Pero la API NO expone `revenue_yego_final` en el campo `revenue_yego_net` del payload**
- Evidencia: `daily_raw.json` — campo `revenue_yego_net = null`, sin campo `revenue_yego_final`
- Resultado: `canonicalRev = null || null = null`
- El fix es sintácticamente correcto pero **semánticamente inútil** porque el backend no pasa `_final` en ese campo

### ENDPOINT GAP (1 brecha)

**Campo `completed_revenue_sum` existe en SQL pero no en API payload:**
- `business_slice_omniview_service.py:656`: `COALESCE(revenue_yego_final, revenue_yego_net) AS completed_revenue_sum`
- `business_slice_omniview_service.py:662`: `revenue_yego_net` (crudo, sin COALESCE)
- La API response incluye `revenue_yego_net` (NULL) pero NO incluye `completed_revenue_sum` (que sí tiene datos)
- El campo correcto se calcula pero **nunca llega al frontend**
- Evidencia: `REVENUE_CERTIFICATION_CLOSURE.md:69`: "completed_revenue_sum = COALESCE(_final, _net) ← CORRECTO pero NO mapeado a revenue_yego_net"

### SERVING GAP (2 brechas)

**CF-H1L.1: Data loss recurrente:**
- day_fact: presente en O5 (645 filas), perdido en P0A (solo 3 fechas)
- week_fact: presente en O5 (112 filas), **totalmente vacío** en P0A (FACT_LAYER_EMPTY)
- El script de reconciliación original (10 FAILs) ya detectó este patrón recurrente
- `UI_SERVING_RECONCILIATION_AUDIT.md:127-128`: "day_fact/week_fact data doesn't persist (patrón recurrente CF-H1L.1 → CF-H1L.5)"

**Serving view `_final` omisión:**
- `REVENUE_CERTIFICATION_CLOSURE.md:62`: "revenue_yego_final: NO EXPUESTO (columna omitida en migration 143)"
- La migration 143 de la serving view mensual omitió `revenue_yego_final`
- El dato existe en `month_fact` (79.2% filas) pero no llega al API

### CERTIFICATION GAP (3 brechas)

**OMNI-GOV-001 validó tokens, no semántica:**
- F1-F10 cubren: tokens prohibidos, build, DOM, scroll, header, freshness superficial
- F1-F10 NO cubren: datos reales en celdas, coherencia trust↔datos, revenue en todos los grains, CLOSED/PARTIAL visibility, modo único sin confusión Evolution/Vs Proy
- `OMNIVIEW_VISUAL_CERTIFICATION_FRAMEWORK.md`: 384 líneas de framework sin una sola regla sobre datos reales

**Re-ejecución cherry-pick:**
- La reconciliación original encontró 10 FAILs (documentado en `UI_SERVING_RECONCILIATION_AUDIT.md:233`)
- La closure declaró GO con "14 PASS, 1 WARN, 0 FAIL" (`OMNIVIEW_HARDENING_CLOSURE.md:27`)
- La auditoría original (NO GO) coexiste en el repo con la closure (GO) sin resolverse

**O4 matriz grain×metric falsa:**
- `OMNIVIEW_VISUAL_CERTIFICATION_REPORT.md:75`: Daily Revenue "Serving: 100%, Status: PASS"
- `OMNIVIEW_VISUAL_CERTIFICATION_REPORT.md:81`: Weekly Revenue "Serving: 100%, Status: PASS"
- La evidencia real del script de reconciliación: 0% en ambos
- La matriz de O4 fue construida asumiendo los fixes, no verificando los datos

### UX GAP (2 brechas)

**Evolution como default:**
- `BusinessSliceOmniviewMatrix.jsx:309`: `useState(saved?.viewMode || 'evolucion')`
- El usuario abre Omniview y ve Evolution con datos incompletos
- Evolution no muestra CLOSED/PARTIAL, no tiene badge de estado, no tiene modelo L0-L4

**Foco en Noviembre 2026:**
- `projectionClosedPeriodEngine.js:142`: `allPeriods[allPeriods.length - 2]` → Noviembre
- Cuando `periodInfoMap` es null (no se pasa desde el componente), el fallback `penultimate_month_fallback` asume que el último elemento es el mes actual
- Para 12 meses (Ene-Dic 2026, proyección Colombia), `length-2` = índice 10 = Noviembre
- `anchorReason: "penultimate_month_fallback"`

### TRUST GAP (2 brechas)

**Trust oscilante:**
- 10:50 AM: BLOCKED (conf=36, top_codes: DAY_FACT_DATE_GAPS, MONTHS_BELOW_MIN, WEEKS_BELOW_MIN, DAYS_BELOW_MIN, MONTH_TRIPS_MISMATCH)
- 11:06 AM: SAFE (conf=99, coverage=100, freshness=95, consistency=100)
- 11:12 AM: SAFE (conf=99)
- El trust cambia de BLOCKED a SAFE en 16 minutos porque el SWR recalcula
- Cuando está SAFE, reporta coverage=100% con weekly VACÍO y daily incompleto
- `trust_history_recent` (trust_raw.json) documenta esta oscilación

**Confianza inflada:**
- `confidence.score: 99, coverage: 100.0` — cuando 12/15 celdas grain×metric están vacías
- `freshness: 95.0` — cuando weekly está en FACT_LAYER_EMPTY
- `consistency: 100.0` — cuando daily≠monthly en estructura de payload
- El algoritmo de trust pondera month_fact (completo) sobre day_fact/week_fact (vacíos)

---

## PARTE D — EVIDENCIA QUE EXISTÍA Y HUBIERA IMPEDIDO EL GO

El 2026-06-03, ANTES de emitir GO, existía la siguiente evidencia:

### 1. Weekly vacío (evidencia ignorada)

**Archivo:** `UI_SERVING_RECONCILIATION_AUDIT.md:99-103`
```
| weekly | trips | FAIL | 37.5% | week_fact data loss recurrence |
| weekly | revenue | FAIL | 0% | B2 |
| weekly | drivers | FAIL | 37.5% | week_fact data loss recurrence |
```

**Query que lo demostraba:** `GET /ops/business-slice/weekly?country=Peru&city=Lima`
**Estado en O5:** Declarado como "112 filas, 5 semanas" — pero no para todas las semanas
**Estado en P0A:** `{"data":[], "fact_layer":{"status":"empty"}}` — confirmado

### 2. Revenue NULL (evidencia ignorada)

**Archivo:** `UI_SERVING_RECONCILIATION_AUDIT.md:94-95,100-101`
```
| daily | revenue | No | 0% | Todo NULL | FAIL | B2 |
| weekly | revenue | No | 0% | Todo NULL | FAIL | B2 |
```

**Archivo:** `REVENUE_CERTIFICATION_CLOSURE.md:69`
```
completed_revenue_sum = COALESCE(_final, _net) ← CORRECTO pero NO mapeado a revenue_yego_net
```

**Query Backend:** `business_slice_omniview_service.py:656-664`
```sql
revenue_yego_net,                                    -- CRUDO, NULL
COALESCE(revenue_yego_final, revenue_yego_net) AS completed_revenue_sum  -- CORRECTO, con datos
```

**Resultado:** `completed_revenue_sum` tiene datos (vía COALESCE) pero el API payload solo expone `revenue_yego_net` (NULL). El frontend lee `revenue_yego_net` del payload → NULL.

### 3. Foco en Noviembre (evidencia no buscada)

**Archivo:** `projectionClosedPeriodEngine.js:142`
```javascript
operationalClosedPeriodKey = allPeriods[allPeriods.length - 2]
// Para 12 meses: [10] = "2026-11-01" → NOVIEMBRE
anchorReason = 'penultimate_month_fallback'
```

**Condición:** `periodInfoMap === null` (no se pasa desde el componente)
**Resultado:** El anchor cae en penultimate_month_fallback que asume que el último elemento es el mes actual

### 4. Trust inconsistente (evidencia documentada pero descartada)

**Archivo:** `UI_SERVING_RECONCILIATION_AUDIT.md:109`
```
| all | confidence | Sí | 100% | — | PASS | B1 afecta render, no datos |
```

**Problema:** El trust se declaró PASS porque B1 arregló el render (`confidence.score`). Pero el **valor** del trust no se auditó. El trust decía 99 cuando los datos estaban incompletos.

**Evidencia actual (trust_raw.json):**
```json
id=616: decision_mode=BLOCKED, confidence=36, 
        codes=[DAY_FACT_DATE_GAPS, MONTHS_BELOW_MIN, 
               WEEKS_BELOW_MIN, DAYS_BELOW_MIN, MONTH_TRIPS_MISMATCH]
id=617: decision_mode=SAFE, confidence=99
```

El trust SÍ detectó los gaps (id=616, BLOCKED, conf=36) pero fue ignorado porque la siguiente ejecución dio SAFE (id=617).

### 5. Data loss recurrente documentado

**Archivo:** `UI_SERVING_RECONCILIATION_AUDIT.md:127-128`
```
Causa: Operacional — day_fact/week_fact data doesn't persist 
(patrón recurrente CF-H1L.1 → CF-H1L.5)
```

**Archivo:** `OMNIVIEW_HARDENING_CLOSURE.md:56`
```
Cross-grain data loss con refreshes standalone | Medio | 
No (workaround: secuencia month→week→day)
```

El closure **reconoció** que el data loss es recurrente y lo clasificó como "Medio — No bloquea" con un workaround manual. Esto es una admisión explícita de que el sistema no es confiable sin intervención manual.

---

## PARTE E — NUEVO PIPELINE OBLIGATORIO DE 6 CAPAS

### Layer 1: BUILD

```
[ ] npm run build → PASS (0 errores)
[ ] npm run lint → PASS (0 errores)
[ ] No tokens prohibidos en código fuente
[ ] Backend health → OK (todos los startup checks)
```

**No se puede saltar. Sin build limpio, no se evalúan capas siguientes.**

---

### Layer 2: SERVING

```
MANDATORY antes de continuar:

Para CADA grain (daily, weekly, monthly):
  Para CADA métrica (trips, revenue, drivers, ticket, tpd):
    [ ] GET /ops/business-slice/{grain} → response.data.length > 0
    [ ] Para al menos 1 fila: métrica > 0 (no NULL, no 0)
    [ ] revenue_yego_net o completed_revenue_sum > 0 en ≥80% de periodos con datos

Regla de fallo:
  Si response.data = [] para cualquier grain → FAIL inmediato. NO continuar.
  Si revenue = NULL para ≥50% de filas con trips>0 → FAIL.
```

**Query de verificación obligatoria:**
```bash
curl "http://localhost:8001/ops/business-slice/daily?country=Peru&city=Lima"
# Debe retornar > 0 filas con revenue > 0 en al menos 1 fila
```

---

### Layer 3: UI RENDERING

```
[ ] Vs Proy es default (viewMode = 'proyeccion')
[ ] Evolution NO visible (VITE_OMNIVIEW_EVOLUTION_LEGACY !== 'true')
[ ] Cada celda tiene contrato canónico (10 campos)
[ ] Period status badge visible (CLOSED/PARTIAL/CURRENT/FUTURE/NO_PLAN/NO_REAL)
[ ] Foco temporal en periodo operativo actual (no Noviembre ni futuro)
[ ] Revenue muestra valores >0 donde serving tiene datos
[ ] Trust badge muestra valor coherente con datos serving
```

---

### Layer 4: USER TRUTH

```
Captura de 18 screenshots (no 15):

Para cada screenshot, el auditor humano debe responder:
  [ ] ¿Entiendo qué significa este número?
  [ ] ¿Sé si este periodo está cerrado o parcial?
  [ ] ¿El color tiene sentido con el valor?
  [ ] ¿Puedo tomar una decisión operativa con esta información?
  [ ] ¿El foco está en el periodo correcto?

Si el auditor responde NO a cualquiera → FAIL.
```

---

### Layer 5: TRUST VALIDATION

```
[ ] matrixOperationalTrust.confidence.score > 0
[ ] matrixOperationalTrust.operational_decision.decision_mode !== 'BLOCKED'
[ ] trust_status no oscila entre BLOCKED y SAFE en <1 hora
[ ] Si trust_status = 'ok' Y weekly data = [] → FAIL (contradicción)
[ ] Si trust_status = 'ok' Y daily revenue = NULL 100% → FAIL
[ ] freshness governance status !== 'breach'
[ ] serving integrity guard status !== 'blocked'
```

**Regla de coherencia:**
```
trust.ok AND (weekly.empty OR daily.revenue_all_null) → FAIL
```

---

### Layer 6: DECISION READINESS

```
[ ] Usuario puede identificar el periodo actual en <2s
[ ] Usuario puede distinguir CLOSED de PARTIAL sin leer tooltip
[ ] Usuario puede ver Revenue en daily, weekly, y monthly
[ ] Usuario puede cambiar grain sin perder contexto
[ ] Usuario puede cambiar métrica sin ver lógica de render distinta
[ ] Usuario NO ve Evolution a menos que active flag legacy
[ ] Usuario NO ve alertas que contradigan Trust
[ ] Usuario NO ve foco en Noviembre cuando estamos en Junio
```

---

## PARTE F — DOCUMENTO CREADO

**Archivo:** `docs/governance/FALSE_GO_PREVENTION_STANDARD.md` (este documento)

---

## PARTE G — VEREDICTO FINAL

### ROOT CAUSE

**El GO fue emitido porque el pipeline de certificación (OMNI-GOV-001) validó sintaxis (tokens, build, DOM) pero no semántica (datos reales, coherencia, utilidad operativa).**

El error específico:
1. La reconciliación original encontró 10 FAILs y emitió NO GO
2. Se aplicaron fixes de CÓDIGO (B1, B2), no de DATOS
3. Los datos se restauraron temporalmente (refresh manual) y la reconciliación se re-ejecutó → 14 PASS
4. Se tomó la mejor ejecución como verdad y se ignoró la peor (que reflejaba el estado operativo real)
5. El framework de certificación visual no incluyó ninguna regla sobre datos reales
6. Se declaró GO y se desbloqueó Diagnostic

### CONTRIBUTING FACTORS

| Factor | Evidencia |
|--------|-----------|
| Data loss recurrente no resuelto | CF-H1L.1 → CF-H1L.5 documentado como "recurrente" en reconciliation audit L127 |
| Revenue field mapping roto | `completed_revenue_sum` calculado pero no expuesto en API payload |
| Trust algorítmico inflado | Confianza 99 con weekly vacío — pondera month_fact sobre day/week |
| Certificación sin validación de datos | OMNI-GOV-001: 10 reglas, ninguna sobre si los datos existen |
| Evolution como default | `BusinessSliceOmniviewMatrix.jsx:309` — el usuario ve la vista incorrecta |
| Foco roto en Vs Proy | `projectionClosedPeriodEngine.js:142` — penultimate_month_fallback = Noviembre |
| O4 matriz falsa | Daily/Weekly Revenue declarados "100% serving, PASS" cuando eran 0% |

### SYSTEMIC FAILURE

**El sistema de certificación confunde "el código compila" con "el sistema funciona".**

La cadena de decisiones que llevó al GO falso:

```
OMNI-COV-006: 10 FAIL → NO GO           [CORRECTO]
     ↓
B1/B2 fixes: código corregido            [CORRECTO pero insuficiente]
     ↓
Data refresh temporal: datos restaurados  [FRÁGIL — no permanente]
     ↓
Re-ejecución reconciliation: 14 PASS      [ENGAÑOSO — snapshot favorable]
     ↓
O4 visual cert: 0 FAIL F1-F10            [CIEGO — no valida datos]
     ↓
O5 closure: GO + Diagnostic unlock       [ERROR — basado en snapshot]
     ↓
24h después: weekly vacío, revenue NULL   [REALIDAD OPERATIVA]
```

### CORRECTIVE ACTIONS

1.  **Nunca declarar GO basado en una sola ejecución de reconciliación.** Ejecutar 3 veces en 24h. Si alguna da FAIL, no hay GO.
2.  **Layer 2 (Serving) es bloqueante.** Sin datos en daily/weekly/monthly para TODAS las métricas, no se evalúa Layer 3+.
3.  **El campo `completed_revenue_sum` debe mapearse a `revenue_yego_net` en el API payload** o el frontend debe leer `completed_revenue_sum`.
4.  **CF-H1L.9 (Refresh Family Atomicity) pasa de P1 a P0.** Sin atomicidad cross-grain, los datos se pierden entre refrescos.
5.  **OMNI-GOV-001 es reemplazado por OMNI-GOV-002** (ya creado) que incluye reglas semánticas S1-S10.
6.  **El trust no puede ser SAFE mientras serving integrity está BLOCKED.** Cross-validation obligatoria.
7.  **`projectionClosedPeriodEngine.js:142` debe arreglarse.** El fallback `length-2` asume incorrectamente que el último elemento es el mes actual.
8.  **3-Run Stability Rule (P0.2): Ningún GO puede basarse en una sola ejecución favorable.** Se requieren 3 rondas separadas con ≥30s de intervalo. Las 3 deben coincidir en row counts, trust status, y decision_mode. Si alguna ronda muestra data loss o trust oscila BLOCKED→SAFE → NO GO.

---

## RESPUESTA A LA PREGUNTA CENTRAL

**¿Por qué Omniview recibió GO cuando todavía no era confiable?**

Porque el 2026-06-03:

1. `backend/scripts/audit_omniview_ui_serving_reconciliation.py` encontró **10 FAILs** y emitió **NO GO** (`UI_SERVING_RECONCILIATION_AUDIT.md:233`)

2. Los datos fueron restaurados temporalmente vía refresh manual, y la reconciliación fue re-ejecutada obteniendo **14 PASS**. Se tomó esta segunda ejecución como verdad. (`OMNIVIEW_HARDENING_CLOSURE.md:27`)

3. `OMNIVIEW_VISUAL_CERTIFICATION_REPORT.md:75,81` declaró Daily Revenue y Weekly Revenue como **"100% serving, PASS"** cuando el script original había demostrado **0%**. La matriz de O4 fue construida sobre supuestos de fix, no sobre queries reales.

4. `business_slice_omniview_service.py:662` expone `revenue_yego_net` (NULL) en el API payload. `business_slice_omniview_service.py:663` calcula `completed_revenue_sum` (COALESCE correcto, con datos) pero **nunca lo mapea al payload**. El frontend lee el campo NULL. (`REVENUE_CERTIFICATION_CLOSURE.md:69`)

5. `projectionClosedPeriodEngine.js:142` tiene un fallback que enfoca **Noviembre 2026** porque `allPeriods[length-2]` asume que el último elemento es el mes actual.

6. El trust oscila entre **BLOCKED (conf 36)** y **SAFE (conf 99)** en minutos. La ejecución SAFE fue la que se usó para certificar. (`trust_raw.json` ids 616→617)

7. `OMNI-GOV-001` validó **tokens, build y DOM** pero **cero reglas sobre datos reales**. El framework de certificación era sintáctico, no semántico.

**En resumen:** Se certificó el código, no el sistema. Se tomó un snapshot favorable de datos temporales como verdad permanente. Se ignoraron 10 FAILs documentados. Se desbloqueó Diagnostic sobre una base que 24 horas después demostró estar vacía.

---

**END OF FALSE GO PREVENTION STANDARD**
