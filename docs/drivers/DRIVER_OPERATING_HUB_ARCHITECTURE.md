# DRIVER OPERATING HUB — PHASE D1.3 ARCHITECTURE

**Fecha:** 2026-05-25
**Fase activa:** 1H.4 — Operational Maturity Governance Layer
**Sub-fase Drivers:** D1.3 — Dominant Operational Navigation

---

## 1. WHAT IS DRIVERS

Drivers is the **Driver Operating System** of YEGO Control Tower. It is not a collection of isolated dashboards. It is a progressive operational system that provides:

- **Supply control** — monitoring driver supply dynamics, segments, migrations
- **Lifecycle intelligence** — activation, retention, churn, cohorts
- **Diagnostic readiness** — behavioral patterns, alerts, benchmarking (READY NEXT)
- **Future intelligence** — operational deep dives, recoverability (BACKLOG)

Everything orbits around **Supply Overview** as the operational core.

---

## 2. WHAT DRIVERS IS NOT

- **Not 9 independent dashboards** — it's 1 cohesive system with progressive phases
- **Not an AI recommendation engine** — all logic is deterministic
- **Not production-ready across all tabs** — only Foundation tabs are operational
- **Not a hidden roadmap** — all capabilities are visible but governed by maturity

---

## 3. DOMINANT OPERATIONAL NARRATIVE

```
Driver Operating System
├── Supply Overview (CORE — operational truth)
│   └── "How is our driver supply doing?"
├── Lifecycle (foundation layer)
│   └── "How do drivers behave over time?"
├── Diagnostic Readiness (READY NEXT)
│   └── "What patterns and anomalies exist?"
└── Future Intelligence (BACKLOG)
    └── "What deeper insights can we extract?"
```

---

## 4. CAPABILITY GROUPING

### 4.1 Operational Foundation (2 capabilities — productionReady)

| Tab | Motor | Fase | Maturity |
|-----|-------|------|----------|
| **Supply Overview** | Control Foundation | D1/D2 | HARDENING |
| **Lifecycle** | Control Foundation | D3 | UNDER CONSTRUCTION |

### 4.2 Diagnostic Readiness (5 capabilities — READY NEXT, not active)

| Tab | Motor | Fase | Maturity |
|-----|-------|------|----------|
| Diagnóstico | Diagnostic Engine | D3/D6 | UNDER CONSTRUCTION |
| Behavior | Diagnostic Engine | D6 | READY NEXT |
| Alertas de conducta | Diagnostic Engine | D6 | READY NEXT |
| Fuga de flota | Diagnostic Engine | D6/D7 | UNDER CONSTRUCTION |
| Patrones | Diagnostic Engine | D6 | READY NEXT |

### 4.3 Future Intelligence (2 capabilities — BACKLOG)

| Tab | Motor | Fase | Maturity |
|-----|-------|------|----------|
| Operational Intel | Decision / Suggestion | FUTURE | FUTURE |
| Recoverability | Reachability Engine | D7 | BLOCKED |

---

## 5. NAVIGATION HIERARCHY

### 5.1 Main tab bar (Control Tower global)
```
Performance | Drivers | Riesgo | Operación | Plan
```

Clicking "Drivers" navigates to `/drivers/supply` (Supply Overview landing).

### 5.2 Grouped sub-nav (Drivers-specific)

```
Foundation | Supply Overview  Lifecycle  |  Diagnostic Readiness | Diagnostico  Behavior  Alertas  Fuga  Patrones  |  Future Intelligence | Operational Intel  Recoverability
```

Group labels are non-clickable visual separators. Pills are compact (no maturity badges — governance moves to the content header).

### 5.3 Driver System Header (content area)
```
Drivers — Driver Operating System
Operational control center for driver supply, lifecycle and execution.

● 2 Operational  ● 5 Diagnostic  ● 2 Future
```

The header provides:
- Module name and subtitle
- Capability distribution summary (derived from registry, not hardcoded)
- Progressive disclosure of operational context

### 5.4 Content area
```
[Drive System Header]
[Governance Banner — only for non-productionReady tabs]
[Tab Content — SupplyView, LifecycleView, etc.]
```

---

## 6. RELATIONSHIP WITH CONTROL FOUNDATION

- Supply Overview and Lifecycle belong to **Control Foundation** (ACTIVE motor)
- They are the only tabs that operate on governed serving facts
- Everything else orbits around them as preview/readiness/backlog
- The Driver Operating Hub reinforces this dependency: Foundation is first, everything else follows

---

## 7. RELATIONSHIP WITH DIAGNOSTIC ENGINE

- 5 tabs belong to **Diagnostic Engine** (READY NEXT motor)
- They are visible as **roadmap preview** — users see what's coming
- Governance banners clearly state "Diagnostic Engine not active"
- Diagnostic Engine activation depends on Control Foundation stabilization
- No Diagnostic Engine tabs are `productionReady`

---

## 8. WHY VISIBLE TABS ≠ MATURE CAPABILITIES

Drivers shows its **full evolutionary roadmap**. This is intentional:

1. **Visibility = transparency** — users see the complete planned system
2. **Governance = honesty** — badges and banners prevent false expectations
3. **Progressive delivery** — Foundation first, then Diagnostic, then Intelligence

Hiding tabs would:
- Obscure the product roadmap
- Make the system feel incomplete
- Prevent users from previewing upcoming capabilities

Instead, **visual governance** communicates real maturity while keeping the roadmap visible.

---

## 9. FUTURE EVOLUTION ROADMAP

| Phase | Milestone | Capabilities |
|-------|-----------|-------------|
| **D1** (current) | Foundation + Governance | Supply Overview, Lifecycle, Capability Governance, Visual Maturity System |
| **D2** | Supply Hardening | Supply Overview with actionable lists P0, serving facts |
| **D3** | Lifecycle Intelligence | Lifecycle with enriched drilldown, phone integration |
| **D4** | Actionable Lists | `GET /drivers/actionable-list`, listas accionables completas |
| **D5** | Lifecycle Hardening | Fusión Diagnóstico + Lifecycle, cohorts avanzados |
| **D6** | Diagnostic Activation | Behavior, Patterns, Alerts activados (Diagnostic Engine GO) |
| **D7** | Recoverability Readiness | Recoverability scoring persistido (Reachability Engine GO) |

---

## 10. UX OPERATIONAL RULES

1. **Single operational flow** — no dead ends, no isolated views
2. **Progressive disclosure** — Foundation first, complexity hidden until needed
3. **Supply Overview is home** — `/drivers` land here, always
4. **Grouped navigation** — visual hierarchy reflects architectural hierarchy
5. **No visual noise** — enterprise sobriety, minimal colors, clean spacing
6. **Governance in content, not navigation** — maturity info lives in the content header, pills are clean
7. **Sticky headers don't break scroll** — Driver System Header is in content flow, not sticky
8. **No runtime heavy rendering** — capability counts from registry, not API calls

---

## 11. COMPONENT ARCHITECTURE

### Files
| File | Role |
|------|------|
| `frontend/src/components/driver/DriverOperatingHub.jsx` | Wrapper: header, capability summary, governance banner, content area |
| `frontend/src/App.jsx` | Integration: grouped sub-nav, DriverOperatingHub rendering |
| `frontend/src/config/operationalMaturityRegistry.js` | Canonical capability metadata |
| `frontend/src/components/operational/MaturityIndicators.jsx` | Reusable governance components |

### DriverOperatingHub API
```jsx
<DriverOperatingHub activeSub={key} refreshKey={n}>
  {/* Conditional tab content */}
</DriverOperatingHub>
```

Props:
- `activeSub` — current sub-tab key (e.g., `drivers_supply`)
- `refreshKey` — re-render trigger
- `children` — tab-specific content (rendered by App.jsx conditionally)

### DRIVER_CAPABILITY_GROUPS (App.jsx)
```js
const DRIVER_CAPABILITY_GROUPS = [
  { id: 'foundation', label: 'Foundation', keys: ['drivers_supply', 'drivers_lifecycle'] },
  { id: 'readiness', label: 'Diagnostic Readiness', keys: ['drivers_diagnostic', ...] },
  { id: 'future', label: 'Future Intelligence', keys: ['drivers_operational_intelligence', ...] },
]
```

---

**FIN DEL DOCUMENTO DE ARQUITECTURA DEL DRIVER OPERATING HUB**
