# DRIVERS H1 MANUAL QA CHECKLIST

**Fecha:** 2026-05-26
**Fase:** H1 — Drivers Operational Hardening

---

## GO/NO-GO CRITERIA

| Criterio | GO | NO-GO |
|----------|-----|-------|
| Todas las rutas abren sin error de consola | [ ] | [ ] |
| Ningún tab queda con loading infinito (>15s) | [ ] | [ ] |
| Supply carga sin park seleccionado | [ ] | [ ] |
| Action Queues muestra error con remediation si endpoint falla | [ ] | [ ] |
| Lifecycle muestra datos agregados sin park | [ ] | [ ] |
| Health endpoint responde status ok/warning/blocked | [ ] | [ ] |
| Backend compile sin errores | [ ] | [ ] |
| Frontend build sin errores | [ ] | [ ] |
| Omniview no roto | [ ] | [ ] |

---

## ROUTE-BY-ROUTE CHECKLIST

### 1. `/drivers/supply`

| Verificación | Esperado | Estado |
|-------------|----------|--------|
| Abre sin errores | Se renderiza SupplyView | [ ] |
| Data Foundation card visible | Muestra freshness status | [ ] |
| Lifecycle Distribution card visible | Muestra distribución de lifecycle | [ ] |
| Select Park = "Todos" | Muestra "Sin park seleccionado. Mostrando datos agregados." | [ ] |
| Overview con park vacío | Intenta cargar datos (puede mostrar error o vacío) | [ ] |
| Seleccionar park | Carga datos detallados | [ ] |
| Cambiar tabs internos (Composition, Migration, Alerts) | Cada uno carga sin bloquear | [ ] |
| Sin loading infinito | < 15s o muestra error/empty | [ ] |

**Endpoints esperados:** `GET /ops/supply/geo`, `GET /ops/supply/series`, `GET /ops/supply/segments/series`, `GET /ops/supply/migration`, `GET /ops/supply/alerts`, `GET /drivers/raw-freshness`, `GET /drivers/lifecycle-summary`

---

### 2. `/drivers/action-queues`

| Verificación | Esperado | Estado |
|-------------|----------|--------|
| Abre sin errores | Se renderiza DriverActionableLists | [ ] |
| Queue pills visibles | All, No First Trip, Declining, At Risk, Recent Churn, Underutilized | [ ] |
| Summary cards si hay data | Total, CRITICAL, HIGH counts | [ ] |
| Si endpoint falla | Muestra error rojo + remediation + "Reintentar" | [ ] |
| Si no hay data | "No hay drivers accionables con los filtros actuales." | [ ] |
| Quick actions (Assign) | Funcionan (POST /drivers/workflow/assign) | [ ] |

**Endpoints esperados:** `GET /drivers/actionable-list`, `POST /drivers/workflow/*`

---

### 3. `/drivers/lifecycle`

| Verificación | Esperado | Estado |
|-------------|----------|--------|
| Abre sin errores | Se renderiza DriverLifecycleView | [ ] |
| Select Park = "Todos" | Muestra "Mostrando datos agregados." | [ ] |
| Con park vacío | Carga summary + series agregadas | [ ] |
| Lifecycle Distribution card (vía DriverLifecycleSummary) | Muestra distribución | [ ] |
| Cohortes con park vacío | Muestra "Todos" en el select | [ ] |
| Drilldown KPI click | Abre modal | [ ] |

**Endpoints esperados:** `GET /ops/driver-lifecycle/*`, `GET /drivers/lifecycle-summary`

---

### 4. `/drivers/diagnostic`

| Verificación | Esperado | Estado |
|-------------|----------|--------|
| Governance banner visible | Muestra banner "Diagnostic Engine — READY NEXT" | [ ] |
| KPI cards si endpoint responde | Muestra Active 7D, Active 28D, etc. | [ ] |
| Si endpoint falla | Muestra error controlado, no loading infinito | [ ] |

**Endpoints esperados:** `GET /driver-lifecycle/*`

---

### 5. `/drivers/behavior-benchmarking`

| Verificación | Esperado | Estado |
|-------------|----------|--------|
| Governance banner visible | Muestra banner Diagnostic Engine | [ ] |
| Carga sin bloquear | Menos de 15s | [ ] |
| Métricas faltantes | Muestra warning banner si hay | [ ] |

**Endpoints esperados:** `GET /driver-behavior/*`

---

### 6. `/drivers/behavioral-alerts`

| Verificación | Esperado | Estado |
|-------------|----------|--------|
| Banner "under_review" visible | Muestra advertencia | [ ] |
| Filtros funcionan | País, Ciudad, Park, Segmento, etc. | [ ] |
| KPI cards | Total, Sudden Stop, Critical Drops, etc. | [ ] |
| Tabla con paginación | Drivers listados | [ ] |

**Endpoints esperados:** `GET /ops/supply/geo`, behavioral alerts endpoints

---

### 7. `/drivers/fleet-leakage`

| Verificación | Esperado | Estado |
|-------------|----------|--------|
| Badge "under_review" visible | Muestra advertencia | [ ] |
| Park opcional = "Todos" | No bloquea | [ ] |
| KPI cards | Under watch, Fuga progresiva, etc. | [ ] |

**Endpoints esperados:** `GET /ops/supply/geo`, leakage endpoints

---

### 8. `/drivers/behavioral-patterns`

| Verificación | Esperado | Estado |
|-------------|----------|--------|
| Governance banner | Muestra banner Diagnostic Engine | [ ] |
| Filtros funcionales | País, Ciudad, Ventana | [ ] |
| Group profile cargable | Cambiar grupo recarga | [ ] |

**Endpoints esperados:** `GET /behavioral-patterns/*`

---

### 9. `/drivers/operational-intelligence`

| Verificación | Esperado | Estado |
|-------------|----------|--------|
| Governance banner | Muestra banner FUTURE | [ ] |
| 7 secciones | Efficiency, Sessions, Archetypes, Time, Zones, Pre-Churn, Comparison | [ ] |
| Carga con timeout 60s | No bloquea infinito | [ ] |

**Endpoints esperados:** `GET /operational-intelligence/*`

---

### 10. `/drivers/recoverability`

| Verificación | Esperado | Estado |
|-------------|----------|--------|
| Banner SHADOW MODE | Muestra advertencia naranja | [ ] |
| Summary cargado | KPI cards | [ ] |
| Filtros | Búsqueda, Period days | [ ] |

**Endpoints esperados:** `GET /recoverability/*`

---

## HEALTH ENDPOINT

| Verificación | Esperado | Estado |
|-------------|----------|--------|
| `GET /drivers/health` responde | JSON con status + checks array | [ ] |
| Cada check tiene name, status, message, remediation | Campos completos | [ ] |
| Status general ok/warning/blocked | Coherente con checks | [ ] |

---

## GLOBAL CHECKS

| Verificación | Esperado | Estado |
|-------------|----------|--------|
| Navegar entre tabs Drivers sin error | Transiciones limpias | [ ] |
| Recargar página en cada ruta | Renderiza correctamente | [ ] |
| Omniview no roto | `/operacion/omniview` funciona | [ ] |
| Consola sin errores rojos | Solo warnings esperados | [ ] |

---

**FIN DEL QA CHECKLIST**
