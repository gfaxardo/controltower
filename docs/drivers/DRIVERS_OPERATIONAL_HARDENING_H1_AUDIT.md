# DRIVERS OPERATIONAL HARDENING — H1 AUDIT

**Fecha:** 2026-05-26
**Fase activa:** 1H.4 — Operational Maturity Governance Layer
**Sub-fase:** H1 — Drivers Operational Hardening

---

## PURPOSE

Auditar el estado real de cada ruta y componente del módulo Drivers para identificar fallas de loading infinito, bloqueos por filtros, y dependencias en cascada.

**NO es un doc de nuevas features.** Es un snapshot operacional.

---

## 1. MAPEO DE RUTAS

| Ruta | Componente | Estado | Endpoints llamados | Causa probable |
|------|-----------|--------|--------------------|-----------------|
| `/drivers/supply` | SupplyView | **LOADING/BLOCKED** — requiere park obligatorio; sin park muestra mensaje de selección | `GET /ops/supply/geo`, `GET /ops/supply/series`, etc. | Park obligatorio bloquea carga inicial. Si geo falla, parks vacíos → select vacío → bloqueo total |
| `/drivers/action-queues` | DriverActionableLists | **WARNING** — carga OK pero si endpoint falla muestra "No actionable drivers" sin remediation | `GET /drivers/actionable-list` | Falta diferenciar "sin datos" vs "endpoint fallido" vs "lifecycle no disponible" |
| `/drivers/lifecycle` | DriverLifecycleView | **LOADING/BLOCKED** — requiere park obligatorio; sin park muestra "Selecciona un Park" | `GET /ops/driver-lifecycle/parks`, `GET /ops/driver-lifecycle/summary`, `GET /ops/driver-lifecycle/series` | Park obligatorio bloquea. Si parks list vacío → bloqueo total |
| `/drivers/diagnostic` | DriverLifecycleDashboard | **OK** — `finally setLoading(false)`, muestra KPIs y skeleton | `GET /driver-lifecycle/summary`, etc. | Bien construido. Si endpoint falla, muestra error controlado |
| `/drivers/behavior-benchmarking` | DriverBehaviorBenchmarkingDashboard | **OK** — `finally setLoading(false)`, muestra error si falla | `GET /driver-behavior/benchmarking/summary`, etc. | Bien construido |
| `/drivers/behavioral-alerts` | BehavioralAlertsView | **OK** — `finally setLoading(false)` en loadDrivers, park es opcional | `GET /ops/supply/geo`, endpoints de behavioral alerts | Bien construido. Muestra "Pantalla en revisión" banner |
| `/drivers/fleet-leakage` | FleetLeakageView | **OK** — `finally setLoading(false)`, park es opcional | `GET /ops/supply/geo`, leakage endpoints | Bien construido. Muestra "under_review" badge |
| `/drivers/behavioral-patterns` | BehavioralPatternDiagnosisDashboard | **OK** — `finally setLoading(false)` | `GET /behavioral-patterns/*` | Bien construido |
| `/drivers/operational-intelligence` | OperationalBehavioralIntelligenceDashboard | **OK** — `finally setLoading(false)`, 120s timeouts | `GET /operational-intelligence/*` | Timeout alto (120s). Bien construido pero 8 llamadas en paralelo pueden saturar |
| `/drivers/recoverability` | RecoverabilityIntelligenceDashboard | **OK** — progressive loading, shadow mode banner | `GET /recoverability/*` | Bien construido. Shadow mode explícito |

---

## 2. ANÁLISIS DE FALLAS POR COMPONENTE

### 2.1 SupplyView — CRÍTICO

**Síntoma:** Vista bloqueada si no se selecciona park. Si geo falla, parks vacíos → sin opciones para seleccionar → bloqueo total.

**Causa raíz:** Líneas 223-242 y 244-258 de SupplyView.jsx:
```js
if (!parkId?.trim()) {
  setOverviewData(...)
  return // no carga datos
}
```
Toda la carga depende de parkId. Sin park, no hay datos.

**Cascada:** Si `getSupplyGeo` falla → `geo.parks = []` → select park vacío → usuario no puede seleccionar → bloqueo permanente.

**Remediation requerida:**
- Permitir modo "Todos" con park_id vacío enviado como filtro opcional (o no enviado).
- Si geo falla, mostrar warning + permitir continuar sin filtro park.
- Data Foundation + Lifecycle Summary deberían cargarse sin park.
- El mensaje "Selecciona un park" debería ser opcional, no bloqueante.

### 2.2 Action Queues — WARNING

**Síntoma:** Si `/drivers/actionable-list` falla, muestra "No actionable drivers in selected queue" sin indicar si es error o vacío real.

**Causa raíz:**
```js
catch { setData(null) }
```
No diferencia entre endpoint caído y sin datos. Tampoco intenta `/drivers/actionable-summary` como fallback.

**Remediation requerida:**
- Diferenciar estado ERROR vs EMPTY en la UI.
- Si actionable-list falla, intentar actionable-summary como fallback.
- Mostrar botón "Reintentar" si error.

### 2.3 Lifecycle — CRÍTICO

**Síntoma:** Vista bloqueada si no se selecciona park.

**Causa raíz:**
```js
if (!parkId || parkId.trim() === '') {
  setSummary(null); setSeriesRows([]); return
}
```
Park obligatorio. Sin datos si no se selecciona.

**Remediation requerida:**
- Permitir ver resumen global sin park (lifecycle-summary ya soporta filtros opcionales).
- Cambiar "Selecciona un Park" de bloqueo a sugerencia.

### 2.4 Diagnostic / Future Tabs — OK

Todas las tabs de Diagnostic Readiness y Future Intelligence ya tienen `finally setLoading(false)` y manejo de errores. No hay loading infinito.

Sin embargo, ninguna muestra explícitamente que están en modo "preview" o "not production ready" cuando el endpoint falla (solo BehavioralAlerts y FleetLeakage tienen banners de "under_review").

**Remediation requerida:**
- Las tabs de Diagnostic/Future ya tienen governance banner vía DriverOperatingHub. Confirmar que se renderiza correctamente.
- Asegurar que si endpoint falla en estas tabs, no quede loading infinito (verificado OK).

---

## 3. DEPENDENCY CASCADE MAP

```
Supply → no depende de lifecycle ❌ (OK)
Supply → depende de geo ❗ (si geo falla, parks vacíos)
Action Queues → depende de actionable-list ❗ (si falla, no hay degradation)
Action Queues → NO depende de lifecycle ❌ (OK, llama actionable-list directo)
Lifecycle → depende de parks list ❗ (si parks vacíos, bloqueo)
Lifecycle → depende de lifecycle-summary ❗
DriverOperatingHub → DataFoundation depende de raw-freshness ❗
DriverOperatingHub → LifecycleSummary depende de lifecycle-summary ❗
```

---

## 4. CHECKLIST DE FETCH SAFETY

| Componente | finally setLoading(false) | timeout | error state | empty state | loading skeleton |
|------------|--------------------------|---------|-------------|-------------|-----------------|
| SupplyView | ✅ overview | ❌ sin timeout | ✅ error state | ✅ "Sin datos en el rango" | ✅ "Cargando…" |
| DriverActionableLists | ✅ | ✅ 30s | ❌ no diferencia error/vacío | ✅ "No actionable drivers" | ✅ skeleton |
| DriverLifecycleView | ✅ | ❌ sin timeout | ✅ error state | ✅ "No hay datos" | ✅ "Cargando..." |
| DriverDataFoundation | ✅ | ✅ 15s | ✅ "unavailable" | N/A | ✅ skeleton |
| DriverLifecycleSummary | ✅ | ✅ 25s | ✅ "unavailable" | N/A | ✅ skeleton |
| DriverLifecycleDashboard | ✅ | ❌ sin timeout | ✅ error state | ✅ empty | ✅ skeleton |
| DriverBehaviorBenchmarking | ✅ | ❌ sin timeout | ✅ error state | ✅ empty | ✅ "Cargando..." |
| BehavioralAlertsView | ✅ loadDrivers | ❌ sin timeout | ✅ error state | ✅ "Sin filas" | ✅ "Cargando…" |
| FleetLeakageView | ✅ | ❌ sin timeout | ✅ error state | ✅ "Sin filas" | ✅ "Cargando…" |
| DriverBehaviorView | ✅ | ❌ sin timeout | ✅ error state | ✅ "Sin filas" | ✅ "Cargando…" |
| BehavioralPatternDiagnosis | ✅ | ❌ sin timeout | ✅ error state | N/A | ❌ skeleton (button loading) |
| OperationalIntelligence | ✅ | ❌ (axios sin timeout) | ✅ error state | N/A | ❌ sleep (no skeleton) |
| RecoverabilityIntelligence | ✅ | ❌ sin timeout | ✅ error state | N/A | ✅ skeleton |

---

## 5. RESUMEN DE HALLAZGOS

### Críticos (bloquean uso operativo):
1. **SupplyView bloquea sin park** — no se puede ver data sin seleccionar park específico
2. **Lifecycle bloquea sin park** — ídem
3. **Geo falla → select vacío → bloqueo permanente** en Supply y Lifecycle

### Altos (degradan experiencia):
4. **Action Queues no diferencia error de vacío** — confunde al operador
5. **Sin timeout en axios** — múltiples componentes sin timeout configurado (default de axios es sin límite)
6. **Sin endpoint de health** — no hay forma de verificar estado de los servicios

### Medios (mejoran confiabilidad):
7. **Sin safeFetch centralizado** — cada componente repite lógica de error/loading
8. **OperationalIntelligence carga 8 endpoints en paralelo con 120s** — puede saturar

### Bajos (cosméticos):
9. Algunas tabs de Diagnostic no muestran banner explícito cuando endpoint falla
10. Recuperabilidad tiene shadow mode explícito (bueno)

---

**FIN DEL AUDIT DOC**
