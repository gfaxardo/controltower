# DRIVER CAPABILITY GOVERNANCE — FASE D1.1 / D1.2

**Fecha:** 2026-05-25
**Fase activa:** 1H.4 — Operational Maturity Governance Layer
**Sub-fase Drivers:** D1.1 (Capability Registry) / D1.2 (Visual Maturity System)

---

## 1. DEFINICIÓN — DRIVER OPERATING SYSTEM

Drivers no es un dashboard estático. Es un **Driver Operating System progresivo** que evoluciona en fases controladas, desde foundation operacional hasta inteligencia asistida.

Cada capacidad de Drivers pertenece a un motor arquitectónico y una fase. Ninguna capacidad debe comunicar madurez falsa.

### Principios

1. **Visible no significa maduro.** Todas las tabs del roadmap son visibles. Solo las capacidades de Control Foundation son `productionReady`.
2. **Gobernanza visual, no ocultamiento.** Las capacidades prematuras se muestran con badges de madurez y banners informativos, nunca se ocultan.
3. **IA no gobierna, interpreta.** Ninguna capacidad de Drivers usa IA para decisiones core. Primero lógica determinística.
4. **No activar motores prematuros.** Diagnostic, Reachability, Decision, Suggestion, Action, Learning — todos están bloqueados hasta que Control Foundation esté estable.

---

## 2. TABLA DE CAPABILITIES

| # | Tab | Motor | Fase | Maturity | productionReady | Visible |
|---|-----|-------|------|----------|----------------|---------|
| 1 | **Supply Overview** | Control Foundation | D1/D2 | HARDENING | SI | SI |
| 2 | **Ciclo de vida** | Control Foundation | D3 | UNDER CONSTRUCTION | NO | SI |
| 3 | **Diagnóstico** | Diagnostic Engine | D3/D6 | UNDER CONSTRUCTION | NO | SI |
| 4 | **Behavior** | Diagnostic Engine | D6 | READY NEXT | NO | SI |
| 5 | **Alertas de conducta** | Diagnostic Engine | D6 | READY NEXT | NO | SI |
| 6 | **Fuga de flota** | Diagnostic Engine | D6/D7 | UNDER CONSTRUCTION | NO | SI |
| 7 | **Patrones** | Diagnostic Engine | D6 | READY NEXT | NO | SI |
| 8 | **Operational Intel** | Decision / Suggestion | FUTURE | FUTURE | NO | SI |
| 9 | **Recoverability** | Reachability Engine | D7 | BLOCKED | NO | SI |

---

## 3. METADATA POR CAPABILITY

### 3.1 Supply Overview
- **Motor:** Control Foundation
- **Fase:** D1/D2 — Supply Foundation / Hardening
- **Maturity:** HARDENING
- **productionReady:** SI
- **Dependencias:** `serving.driver_identity_fact`, `serving.driver_activity_weekly_fact`
- **GO/NO-GO:** GO — data real estable, MVs consolidadas. Pendiente integración de listas accionables.
- **Qué falta:** Integrar actionable lists P0, enriquecer con serving facts unificados.

### 3.2 Lifecycle
- **Motor:** Control Foundation
- **Fase:** D3 — Lifecycle Intelligence
- **Maturity:** UNDER CONSTRUCTION
- **productionReady:** NO
- **Dependencias:** `serving.driver_lifecycle_fact`, `public.drivers_data.phone`
- **GO/NO-GO:** NO-GO para producción total. KPIs funcionales pero drilldown sin enriquecimiento de identidad (sin phone, sin nombre en algunas queries).
- **Qué falta:** Fusionar con risk list de Diagnóstico, integrar `drivers_data.phone`, mejorar drilldown.

### 3.3 Diagnóstico
- **Motor:** Diagnostic Engine
- **Fase:** D3/D6 — Lifecycle Intelligence / Diagnostic Readiness
- **Maturity:** UNDER CONSTRUCTION
- **productionReady:** NO
- **Dependencias:** `serving.driver_lifecycle_fact`, `driver_identity_resolver (phone)`
- **GO/NO-GO:** NO-GO. Diagnostic Engine no está ACTIVO (READY NEXT). Risk list funcional pero sin phone.
- **Qué falta:** Motor Diagnostic activado, phone integrado. Se fusionará con Lifecycle en fase D5.

### 3.4 Behavior Benchmarking
- **Motor:** Diagnostic Engine
- **Fase:** D6 — Diagnostic Readiness
- **Maturity:** READY NEXT
- **productionReady:** NO
- **Dependencias:** `driver_daily_activity_fact (estabilizar)`, `Diagnostic Engine activation`
- **GO/NO-GO:** NO-GO. Diagnostic Engine no está ACTIVO. Benchmarks funcionales pero sin serving fact dedicado.
- **Qué falta:** Estabilizar serving fact, activar Diagnostic Engine.

### 3.5 Alertas de conducta
- **Motor:** Diagnostic Engine
- **Fase:** D6 — Diagnostic Readiness
- **Maturity:** READY NEXT
- **productionReady:** NO
- **Dependencias:** `v_driver_behavior_alerts_weekly`, `Diagnostic Engine activation`
- **GO/NO-GO:** NO-GO. Alertas funcionales pero Diagnostic Engine no está ACTIVO.
- **Qué falta:** Activar Diagnostic Engine.

### 3.6 Fuga de flota
- **Motor:** Diagnostic Engine
- **Fase:** D6/D7
- **Maturity:** UNDER CONSTRUCTION
- **productionReady:** NO
- **Dependencias:** `v_fleet_leakage_snapshot (validar)`, `Diagnostic Engine activation`
- **GO/NO-GO:** NO-GO. Marcado "under_review" por el propio sistema. Requiere validación de estabilidad runtime.
- **Qué falta:** Validar snapshot, estabilizar runtime.

### 3.7 Patrones
- **Motor:** Diagnostic Engine
- **Fase:** D6 — Diagnostic Readiness
- **Maturity:** READY NEXT
- **productionReady:** NO
- **Dependencias:** `driver_daily_activity_fact`, `Diagnostic Engine activation`, `Serving Governance Foundation`
- **GO/NO-GO:** NO-GO. Diagnostic Engine no está ACTIVO. Pattern detection funcional pero sin serving fact estable.
- **Qué falta:** Estabilizar Serving Governance Foundation, activar Diagnostic Engine.

### 3.8 Operational Intel
- **Motor:** Decision / Suggestion
- **Fase:** FUTURE — Backlog
- **Maturity:** FUTURE
- **productionReady:** NO
- **Dependencias:** `Control Foundation completo`, `Diagnostic Engine activo`, `Suggestion Engine`
- **GO/NO-GO:** NO-GO. 7 sub-tabs con timeouts de 120s, raw api.get(), sin output accionable. Motores Decision/Suggestion en BACKLOG.
- **Qué falta:** Completar Control Foundation, activar Diagnostic, activar Suggestion.

### 3.9 Recoverability
- **Motor:** Reachability Engine
- **Fase:** D7 — Recoverability Readiness
- **Maturity:** BLOCKED
- **productionReady:** NO
- **Dependencias:** `Driver Lifecycle (D3-D5)`, `Diagnostic Engine`, `Reachability Engine activation`, `driver_identity_fact (phone)`
- **GO/NO-GO:** NO-GO. Reachability Engine en BACKLOG. Shadow mode activo sin acciones.
- **Qué falta:** Estabilizar Driver Lifecycle, activar Diagnostic, activar Reachability.

---

## 4. REGLAS DE GOVERNANCE

### 4.1 Visible no significa maduro
Todas las tabs del roadmap de Drivers son visibles para mostrar la evolución planeada. Pero solo las capacidades de Control Foundation deben aparecer como `productionReady`. Las demás muestran badges y banners de gobernanza.

### 4.2 IA no gobierna, interpreta
En fases futuras (Decision, Suggestion, AI Copilot), la IA podrá interpretar datos y sugerir. Pero nunca gobernará la verdad operacional core. Primero lógica determinística.

### 4.3 No activar Diagnostic/Suggestion/AI antes de Foundation
- Diagnostic Engine solo se activa cuando Control Foundation esté estable (Serving Governance Foundation estabilizada).
- Reachability solo se activa cuando Diagnostic esté estable.
- Suggestion/Decision/AI — solo cuando todos los anteriores estén cerrados.

### 4.4 productionReady solo para Control Foundation
En la fase activa 1H.4, solo las capacidades de Control Foundation pueden ser `productionReady`:
- Supply Overview (HARDENING)
- Lifecycle (próximamente)

Ninguna capacidad de Diagnostic, Reachability, Decision/Suggestion puede tener `productionReady: true`.

### 4.5 Una fase activa, una READY NEXT
- ACTIVE: Control Foundation (1H.4)
- READY NEXT: Diagnostic Engine (2A.3)
- BACKLOG: Reachability, Forecast, Suggestion, Decision, Action, AI Copilot, Learning

---

## 5. ESTRUCTURA DE ARCHIVOS

| Archivo | Rol |
|---------|-----|
| `frontend/src/config/operationalMaturityRegistry.js` | Registry canónico de madurez. Define MATURITY levels, ENGINE_OWNER, metadata por capability, helpers. |
| `frontend/src/config/controlTowerNavigationRegistry.js` | Registry de navegación. Define rutas, visibilidad, productionReady flags. |
| `frontend/src/components/operational/MaturityIndicators.jsx` | Componentes visuales: MaturityBadge, EngineIndicator, MaturityStatusBar, DriverCapabilityBadge, DriverCapabilityBanner. |
| `frontend/src/App.jsx` | Integración: sub-pills con badges, banners dentro de tabs no productionReady. |

---

## 6. SISTEMA VISUAL DE MADUREZ

### 6.1 Badges en navegación (sub-pills)
Cada tab de Drivers muestra un badge compacto con:
- Color por maturityStatus
- Label de estado
- Ícono de punto de color

### 6.2 Banners dentro de tabs
Cuando el usuario entra a una tab NO `productionReady`, aparece un banner con:
- Estado de madurez
- Motor arquitectónico
- Fase
- Dependencia principal
- Qué falta para GO

El banner no bloquea la navegación ni oculta el contenido existente.

### 6.3 Status bar en header
Para tabs no-STABLE/no-ACTIVE, una barra delgada en el header muestra:
- MaturityBadge
- PhaseIndicator
- EngineIndicator

### 6.4 Colores por estado

| Estado | Color | Tono |
|--------|-------|------|
| ACTIVE | Verde | success |
| HARDENING | Ámbar | amber |
| READY NEXT | Azul | blue |
| UNDER CONSTRUCTION | Morado | purple |
| FUTURE | Gris | gray |
| LEGACY | Rojo oscuro | red |
| BLOCKED | Naranja | warning |

---

## 7. HALLAZGOS DE LA IMPLEMENTACIÓN

### productionReady corregidos
Antes: 7/9 tabs Diagnostic Engine tenían `productionReady: true` (falsa madurez).
Ahora: Solo Supply (Control Foundation) es `productionReady`. 9/9 tabs visibles con metadata real.

### Niveles de madurez agregados
- `ACTIVE` — nuevo
- `READY_NEXT` — nuevo
- `FUTURE` — nuevo
- `BLOCKED` — nuevo

### Componentes creados
- `DriverCapabilityBadge` — badge reutilizable con metadata del registry
- `DriverCapabilityBanner` — banner informativo para tabs no productionReady

### Funciones helper agregadas
- `getCapabilityMeta(moduleKey)` — metadata completa de governance
- `isProductionReady(moduleKey)` — Control Foundation HARDENING+ o STABLE/ACTIVE

---

**FIN DEL DOCUMENTO DE CAPABILITY GOVERNANCE**
