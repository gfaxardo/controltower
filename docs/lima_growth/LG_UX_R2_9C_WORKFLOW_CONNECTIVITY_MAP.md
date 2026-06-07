# LG-UX-R2.9C — Workflow Connectivity Map

**Date:** 2026-06-06
**Phase:** LG-UX-R2.9C Workflow Connectivity Hardening

---

## CONNECTIONS IMPLEMENTED

| # | Origin | Destination | Trigger | Filter | State |
|---|--------|-------------|---------|--------|:---:|
| 1 | Today Action Plan → Queue | Execution Queue | "Ir a Queue READY" button | status=READY | DONE |
| 2 | Today Action Plan → Config | Allocation Trace | "Ver Allocation Trace" button | scrollTo=allocation-trace-panel | DONE |
| 3 | Today Action Plan → Config | Capacity Config | "Ver capacidad por canal" button | — | DONE |
| 4 | Today Action Plan → Programs | Programs Section | "Ver Programas" button | — | DONE |
| 5 | Queue → Config | Build Audit → Policy | "Ver Program Capacity Policy" link | scrollTo=program-policy-panel | DONE |
| 6 | Config → Queue | Policy → Build Audit | "Ver Build Audit en Queue" link | — | DONE |

---

## CTAS ADDED

| CTA | Location | data-testid |
|-----|----------|-------------|
| Ir a Queue READY | Today Action Plan (EXPORT action present) | `cta-go-to-ready-queue` |
| Ver Allocation Trace | Today Action Plan (CAPACITY_GAP or CHANNEL_FULL blockers) | `cta-view-allocation-trace` |
| Ver capacidad por canal | Today Action Plan (SIN_CANAL_ASIGNADO blocker) | `cta-view-channel-capacity` |
| Ver Programas | Today Action Plan (priorities present) | `cta-view-programs` |
| Cargar Build Audit | Execution Queue (lazy-loaded) | `cta-view-build-audit` |
| Ver Build Audit en Queue | Control Config → Policy Panel | On "Guardrails" panel |

---

## FILTER HANDOFF

Cross-section navigation passes context via `crossSectionFilter` state:

```js
navigateTo('queue', { label: 'Exportar READY', status: 'READY' })
```

ExecutionQueueSection reads `sectionFilter.status` to pre-set the status dropdown filter.

Breadcrumb bar at top of main area shows active filter and "Limpiar filtro" button.

---

## BUILD AUDIT VISIBILITY

New `BuildAuditPanel` component in Execution Queue:
- Lazy-loaded (fetches on button click, not on mount)
- Shows last 5 build audit entries: date, policy applied badge, mode, assigned count
- Links to Program Capacity Policy for full details
- data-testid: `build-audit-panel`

---

## SECTION ANCHORS + DATA-TESTID

| Section | ID | data-testid |
|---------|-----|-------------|
| Today's Action Plan | `today-action-plan-section` | `today-action-plan-section` |
| Programs & State | `programs-section` | `programs-section` |
| Execution Queue | `execution-queue-section` | `execution-queue-section` |
| Control Config | `control-config-section` | `control-config-section` |
| Allocation Trace | `allocation-trace-panel` | `allocation-trace-panel` |
| Program Policy | `program-policy-panel` | `program-policy-panel` |
| Build Audit | — | `build-audit-panel` |

### Navigation buttons

| Button | data-testid |
|--------|-------------|
| Today's Action Plan nav | `nav-today-action-plan` |
| Programs nav | `nav-programs` |
| Execution Queue nav | `nav-execution-queue` |
| Control Config nav | `nav-control-config` |

### CTAs

| CTA | data-testid |
|-----|-------------|
| Go to Queue READY | `cta-go-to-ready-queue` |
| View Allocation Trace | `cta-view-allocation-trace` |
| View channel capacity | `cta-view-channel-capacity` |
| View Programs | `cta-view-programs` |
| Load Build Audit | `cta-view-build-audit` |

---

## WHAT WAS NOT IMPLEMENTED

- NO new backend code
- NO new API endpoints
- NO localStorage
- NO query params (uses React state)
- NO policy simulation button in UI (API simulation still works, UI button is R2.9E)
