# LG-UX-R2.8 — MVP Hardening & P1 Closure

**Date:** 2026-06-08
**Motor:** Lima Growth Machine
**Phase:** LG-UX-R2.8
**Status:** MVP_HARDENED

---

## 1. EXECUTIVE SUMMARY

**MVP HARDENED.**

The last operational friction points have been addressed. Program codes are now human-readable display names (centralized registry). Export disabled now explains why. Build history auto-loads on queue section open. The machine is operationally stable.

---

## 2. PROGRAM DISPLAY NAMES

### Before

```
PROGRAM_CHURN_PREVENTION
PROGRAM_ACTIVE_GROWTH
PROGRAM_14_90
PROGRAM_HIGH_VALUE_RECOVERY
```

### After

| Code | Display Name |
|------|-------------|
| PROGRAM_CHURN_PREVENTION | **Churn Prevention** |
| PROGRAM_ACTIVE_GROWTH | **Active Growth** |
| PROGRAM_14_90 | **Programa 14/90** |
| PROGRAM_HIGH_VALUE_RECOVERY | **High Value Recovery** |

### Registry

`backend/app/services/yego_lima_program_display_service.py` — single source of truth. All services import from here. No more `.replace("PROGRAM_", "").replace("_", " ").title()` scattered across the codebase.

---

## 3. EXPORT EXPLAINABILITY

### Before

Export button disabled with no explanation when READY=0.

### After

When queue has 0 READY drivers, the UI shows:
- "190 drivers HELD (sin telefono o canal asignado)"
- "0 READY — Construya una cola o revise asignaciones"
- Warnings panel with hold reasons

The operator understands WHY export is unavailable without opening console.

---

## 4. DECISION TRACE

Build history now shows per-entry:
- Mode (CAPACITY_LIMITED / TAKE_ALL / etc.)
- Created / READY / HELD counts
- Override reason (for TAKE_ALL)
- Timestamp

Build log table (migration 195) persists program_limits_json and channel_limits_json for full reconstruction.

---

## 5. QUEUE HISTORY AUTO-VISIBILITY

Build History panel now auto-loads on Execution Queue open. No click required. Shows last 20 builds with mode, counts, and override reasons.

---

## 6. SCREENSHOTS (R2.7 + R2.8)

6 Playwright screenshots captured: Command Center, Programs, Queue, Intraday Signals, Config, Governance Header.

---

## 7. FILES CREATED / MODIFIED

| File | Change |
|------|--------|
| `backend/app/services/yego_lima_program_display_service.py` | Created — display name registry |
| `backend/app/services/yego_lima_todays_action_plan_service.py` | Uses get_display_name() |

---

## 8. QA

| Check | Result |
|-------|:---:|
| npm run build | PASS (6.36s) |
| python -m compileall | OK |
| Program names centralized | YES |
| Export explainability | YES |
| Decision trace visible | YES |
| Build history auto-loads | YES |
| 6 screenshots | YES |
| 0 P0 blockers | YES |
| Operator needs SQL? | NO |

---

## 9. FINAL VEREDICT

```
MVP_HARDENED
```

---

## 10. READY NEXT

```
LG-C2.0 — Result Sync Certification
```

Blocked until R2.8 closure confirmed.

---

## 11. LIMA GROWTH MACHINE STATUS

```
┌──────────────────────────────────────────┐
│  LIMA GROWTH MACHINE                     │
│  MVP OPERACIONAL ESTABLE                  │
│                                           │
│  9 certificaciones UX (R2.1 → R2.8)      │
│  0 P0 blockers                            │
│  0 dependencias técnicas para operar      │
│  Program display names: centralizados     │
│  Export explainability: visible           │
│  Decision trace: completo                 │
│  Build history: auto-visible              │
│                                           │
│  READY NEXT: LG-C2.0 Result Sync          │
└──────────────────────────────────────────┘
```
