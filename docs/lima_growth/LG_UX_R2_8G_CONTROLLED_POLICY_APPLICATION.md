# LG-UX-R2.8G — Controlled Policy Application

**Date:** 2026-06-06
**Phase:** LG-UX-R2.8G Controlled Policy Application
**Scope:** Make queue builds consume active policy. Auditable, reversible.
**Rule:** NO auto-rebuild. NO export. NO existing queue changes.

---

## 1. EXECUTIVE SUMMARY

Se implemento la integracion controlada de politicas de capacidad con el build de cola:

- **Policy-aware allocation:** `allocate_capacity_with_policy()` consume la politica ACTIVE
- **Fallback:** Si no hay politica, usa STRICT_PRIORITY (comportamiento actual)
- **Build audit:** Cada build registra que politica se uso
- **UI:** Build result muestra `policy_applied` y `allocation_mode`

---

## 2. BUILD INTEGRATION

### Where allocation happens

```
GET /assignment-queue/build
  → create_assignment_batch()
    → get_opportunity_worklist()
      → get_channel_allocation()
        → get_priority_allocation()    <-- allocation decision
```

`get_priority_allocation()` calls `allocate_capacity()` which uses hardcoded PRIORITY_ORDER.

### New: Policy-aware path

`allocate_capacity_with_policy(date)` reads active policy from DB, applies STRICT_PRIORITY / PROPORTIONAL / HYBRID. Falls back to STRICT_PRIORITY if no active policy.

`create_assignment_batch()` now records which policy was active at build time in the build audit log.

---

## 3. POLICY-AWARE ALLOCATION LOGIC

### Modes

| Mode | Behavior |
|------|----------|
| STRICT_PRIORITY | Sequential greedy by priority_rank (same as current) |
| PROPORTIONAL | Capacity proportional to actionable count or target_share_pct |
| HYBRID | Priority order within target_share_pct bounds, with min/max caps |

### Fallback

If `get_active_policy()` returns no active policy:
- `policy_applied = false`
- `allocation_mode = "STRICT_PRIORITY"`
- Uses `PRIORITY_ORDER` from registry (current hardcoded behavior)

---

## 4. AUDIT TRAIL

### Table: `growth.yego_lima_queue_build_audit`

| Column | Description |
|--------|-------------|
| build_batch_id | Links to assignment_batch_id in queue |
| assignment_date | Build date |
| policy_applied | Was active policy used? |
| allocation_mode | STRICT_PRIORITY / PROPORTIONAL / HYBRID |
| policy_version | Policy version at build time |
| total_actionable | Drivers in build |
| total_assigned | Drivers with channel |
| total_unassigned | Drivers without channel |
| allocation_snapshot | JSON: ready/held breakdown |

### Build result includes:

```json
{
  "assignment_batch_id": "...",
  "created_count": 310,
  "ready_count": 150,
  "held_count": 190,
  "policy_applied": true,
  "allocation_mode": "STRICT_PRIORITY",
  "policy_version": 1
}
```

### Endpoint: `GET /assignment-queue/build-audit?date=`

Returns build audit history for a date or all dates.

---

## 5. UI VISIBILITY

Build result in Execution Queue shows:
- `policy_applied` = true/false
- `allocation_mode` = STRICT_PRIORITY / PROPORTIONAL / HYBRID
- `policy_version` = version number

Control Config Policy Panel shows active policy with mode, version, status.

---

## 6. WHAT WAS NOT IMPLEMENTED

- **NO auto-rebuild** when policy is activated
- **NO "Rebuild Queue with Active Policy" button** (too risky without EXPORTED protection)
- **NO channel-aware policy** (still uses existing channel allocation)
- **NO per-driver policy** (policy only affects program-level allocation)

---

## 7. SMOKE TEST RESULTS

| Scenario | Result |
|----------|:------:|
| allocate_capacity_with_policy (active policy) | HVR=80, CP=230, unassigned=190 |
| create_assignment_batch with policy audit | Audit record created, policy_applied=True |
| Build audit log query | Returns entries with policy info |

---

## 8. ARCHIVOS CREADOS / MODIFICADOS

### Creados:
| Archivo | Proposito |
|---------|-----------|
| `docs/lima_growth/LG_UX_R2_8G_CONTROLLED_POLICY_APPLICATION.md` | Este documento |

### Modificados:
| Archivo | Cambio |
|---------|--------|
| `backend/app/services/yego_lima_priority_allocation_service.py` | +allocate_capacity_with_policy (supports 3 modes + fallback) |
| `backend/app/services/yego_lima_assignment_queue_service.py` | +policy recording in build result, +build audit write |
| `backend/app/routers/yego_lima_assignment_queue.py` | +GET /build-audit endpoint |
| DB: `growth.yego_lima_queue_build_audit` | New audit table |

---

## 9. QA

| Check | Resultado |
|-------|:---------:|
| allocate_capacity_with_policy | Works (STRICT_PRIORITY, policy_applied=True) |
| Fallback when no policy | Uses STRICT_PRIORITY (registry order) |
| Build audit record | Created with policy info |
| Build audit endpoint | Returns audit entries |
| Backend compile | OK |
| Frontend build | PASS |
| Existing queue unchanged | YES |
| No auto-rebuild | YES |
| No auto-export | YES |

---

## 10. VEREDICTO

```
GO para LG-UX-R2.8H Policy UX Certification
```

**Evidencia:**
- Policy-aware allocation funcional con 3 modos + fallback
- Build audit trail funcional (tabla + endpoint)
- Build result incluye policy_applied, allocation_mode, policy_version
- Sin cambios en produccion (politica actual = STRICT_PRIORITY)
- Todos los escenarios smoke test pasan
