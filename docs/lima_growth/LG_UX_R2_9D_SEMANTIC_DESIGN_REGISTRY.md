# LG-UX-R2.9D — Semantic Design Registry

**Date:** 2026-06-06
**Phase:** LG-UX-R2.9D Semantic Design Registry
**Scope:** Centralize all visual tokens into a single source of truth.
**Proof-of-concept:** StatusBadge migrated to use registry.

---

## 1. EXECUTIVE SUMMARY

Se creo `semanticRegistry.js` — registro central de tokens visuales para Lima Growth V2.

- **9 registries:** status, freshness, queue, programs, policy, channels, allocation, alert severity, export
- **32 semantic entries** covering all operational states
- **8 helper functions** with safe fallback to UNKNOWN
- **1 proof-of-concept:** StatusBadge migrado con exito

---

## 2. REGISTRIES CREATED

| Registry | Entries | Covers |
|----------|:---:|--------|
| QUEUE_STATUS_REGISTRY | 8 | READY, HELD, EXPORTED, UNASSIGNED, NOT_BUILT, FAILED, LIVE, DRY_RUN |
| PROGRAM_STATUS_REGISTRY | 6 | READY, ACTIVE, EMPTY, STALE, UNKNOWN, BLOCKED |
| POLICY_STATUS_REGISTRY | 5 | DRAFT, VALIDATED, ACTIVE, RETIRED, REJECTED |
| ALLOCATION_MODE_REGISTRY | 4 | STRICT_PRIORITY, PROPORTIONAL, HYBRID, FALLBACK |
| CHANNEL_REGISTRY | 4 | CALL_CENTER, SAC, BOT, UNASSIGNED |
| FRESHNESS_REGISTRY | 4 | FRESH, WARNING, STALE, UNKNOWN |
| ALERT_SEVERITY_REGISTRY | 4 | INFO, WARNING, HIGH, CRITICAL |
| EXPORT_STATUS_REGISTRY | 4 | exported, failed, draft, draft_dry_run |
| OPERATIONAL_STATUS_REGISTRY | 7 | QUEUE_NOT_BUILT through IDLE |
| STATUS_REGISTRY (composite) | 32 | All of the above merged |

---

## 3. STATES COVERED

32 semantic entries across 9 domains. Every entry has: `label`, `color`, `bg`, `border`, `dot`, `icon` (where applicable), `description`, `severity`.

Fallback: all helpers return UNKNOWN semantic when status is not recognized — no broken UI.

---

## 4. HELPER FUNCTIONS

| Function | Registry used | Fallback |
|----------|--------------|----------|
| `getStatusSemantic(status)` | STATUS_REGISTRY (composite) | UNKNOWN |
| `getFreshnessSemantic(status)` | FRESHNESS_REGISTRY | UNKNOWN |
| `getQueueStatusSemantic(status)` | QUEUE_STATUS_REGISTRY | NOT_BUILT |
| `getProgramStatusSemantic(status)` | PROGRAM_STATUS_REGISTRY | UNKNOWN |
| `getChannelSemantic(channel)` | CHANNEL_REGISTRY | UNASSIGNED |
| `getPolicyStatusSemantic(status)` | POLICY_STATUS_REGISTRY | DRAFT |
| `getAllocationModeSemantic(mode)` | ALLOCATION_MODE_REGISTRY | FALLBACK |
| `getAlertSeveritySemantic(severity)` | ALERT_SEVERITY_REGISTRY | INFO |

Key normalization: input is normalized to uppercase with underscores (e.g., `"ready"` → `"READY"`, `"call center"` → `"CALL_CENTER"`).

---

## 5. PROOF-OF-CONCEPT

**StatusBadge** migrated to use `getStatusSemantic()` from the registry.

Before:
```jsx
const map = { exported: 'bg-green-100 text-green-800', ... }
<span className={map[status] || 'bg-gray-100 text-gray-600'}>{status}</span>
```

After:
```jsx
const s = getStatusSemantic(status)
<span className={`px-2 py-0.5 rounded text-xs font-medium ${s.bg} ${s.color}`}>{s.label}</span>
```

Benefits:
- StatusBadge now handles ALL 32 statuses (was 8)
- Expired (`exported`) = green-800, now = purple-700 (consistent with EXPORTED in queue)
- DRY_RUN = yellow-800 (unchanged)
- LIVE = green-800 (unchanged)
- Unknown statuses show "UNKNOWN" label instead of raw status string
- No more hardcoded color map

---

## 6. COMPONENTS PENDING MIGRATION (R2.9E)

| Component | Current state | Registry to use |
|-----------|--------------|-----------------|
| ChannelBadge (ExecutionQueueSection) | Hardcoded map | CHANNEL_REGISTRY |
| Program status badges (ProgramsSection) | Inline STATUS_CONFIG | PROGRAM_STATUS_REGISTRY |
| FreshnessBadge | Own logic | FRESHNESS_REGISTRY |
| Operational status badges (TodayActionPlan) | Inline STATUS_LABELS | OPERATIONAL_STATUS_REGISTRY |
| Policy status badges (ControlConfigSection) | Inline classes | POLICY_STATUS_REGISTRY |
| Allocation mode badges (ControlConfigSection) | Inline classes | ALLOCATION_MODE_REGISTRY |

---

## 7. ARCHIVOS CREADOS / MODIFICADOS

### Creados:
| Archivo | Proposito |
|---------|-----------|
| `frontend/.../design/semanticRegistry.js` | 9 registries + 8 helpers |
| `docs/lima_growth/LG_UX_R2_9D_SEMANTIC_DESIGN_REGISTRY.md` | Este documento |

### Modificados:
| Archivo | Cambio |
|---------|--------|
| `frontend/.../components/SharedComponents.jsx` | StatusBadge migrated to use semanticRegistry |

---

## 8. QA

| Check | Resultado |
|-------|:---------:|
| Frontend build | PASS |
| 9 registries | CREATED |
| 32 states covered | YES |
| 8 helper functions | YES |
| StatusBadge migration | DONE (POC) |
| Fallback works | YES (unknown → UNKNOWN semantic) |
| No functional changes | YES |
| No business logic changes | YES |

---

## 9. VEREDICTO

```
GO para LG-UX-R2.9E Semantic Component Standardization
```

**Evidencia:**
- Registry central unico con todos los tokens visuales
- 32 estados semanticos documentados
- StatusBadge proof-of-concept exitoso
- Fallback seguro (nunca rompe UI)
- Build PASS, sin cambios funcionales
