# LG-UX-R2.9H.1 — Serving Fallback Guardrails

**Date:** 2026-06-06
**Phase:** LG-UX-R2.9H.1 Serving Fallback Guardrails

---

## 1. EXECUTIVE SUMMARY

**SERVING FALLBACK GUARDED.**

Se elimino el fallback runtime transparente de todos los endpoints publicos de Lima Growth. Ahora:

- **Fact exists:** `source=SERVING_FACT`, payload returned immediately (<800ms)
- **Fact missing:** `status=MISSING_SERVING_FACT`, remediation returned. NO runtime fallback.
- **force_refresh=true:** Runtime fallback permitido, auditado, con `source=RUNTIME_FORCE_REFRESH`
- **Frontend:** Detecta MISSING_SERVING_FACT y muestra remediation en lugar de cargar datos incorrectos

---

## 2. FALLBACK AUDIT (BEFORE)

| Endpoint | Fallback before | Runtime service | Risk |
|----------|----------------|-----------------|------|
| operational-summary | Transparent | get_operational_summary (4.66s) | HIGH |
| driver-state/summary | Transparent | get_driver_state_summary (1.30s) | MEDIUM |
| queue/summary | Transparent | get_queue_summary (3.69s) | HIGH |
| today-action-plan | Transparent | get_today_action_plan (9.65s) | HIGH |
| allocation-trace | Transparent | get_allocation_trace (6.06s) | HIGH |

All 5 endpoints had transparent runtime fallback — if no serving fact, they silently ran heavy computation.

---

## 3. STRICT SERVING-FIRST CONTRACT

### When fact exists
```json
{
  "status": "OK",
  "source": "SERVING_FACT",
  "generated_at": "2026-06-06T16:52:35",
  "payload": { ... }
}
```

### When fact is missing (no force_refresh)
```json
{
  "status": "MISSING_SERVING_FACT",
  "source": "NONE",
  "payload": null,
  "generated_at": null,
  "remediation": "Run Lima Growth refresh pipeline to generate serving facts.",
  "retry_available": true,
  "force_refresh_available": true
}
```

### When force_refresh=true (runtime fallback)
```json
{
  "status": "OK",
  "source": "RUNTIME_FORCE_REFRESH",
  "generated_at": null,
  "payload": { ... }
}
```

---

## 4. ENDPOINTS UPDATED

| Endpoint | Missing behavior before | Missing behavior after |
|----------|------------------------|----------------------|
| GET /operational-summary | Runtime (4.66s) | MISSING_SERVING_FACT |
| GET /driver-state/summary | Runtime (1.30s) | MISSING_SERVING_FACT |
| GET /assignment-queue/summary | Runtime (3.69s) | MISSING_SERVING_FACT |
| GET /today-action-plan | Runtime (9.65s) | MISSING_SERVING_FACT |
| GET /capacity/allocation-trace | Runtime (6.06s) | MISSING_SERVING_FACT |

All endpoints accept `?force_refresh=true` for admin/dev use.

---

## 5. TRANSPARENT FALLBACK ELIMINATED

**Before:** `if not fact: return heavy_runtime_computation()` ← REMOVED

**After:** `if not fact: return MISSING_SERVING_FACT with remediation`

Runtime fallback only when `force_refresh=true` is explicitly passed — which the frontend never does.

---

## 6. FORCE REFRESH AUDIT

Table: `growth.yego_lima_runtime_fallback_audit` (created automatically)

Columns: endpoint, fact_type, fact_date, source, triggered_by, duration_ms, created_at

Every `force_refresh=true` call is audited. Normal UI requests (`force_refresh=false`) never write to this table.

---

## 7. UI MISSING FACT BEHAVIOR

Frontend hook detects `status === 'MISSING_SERVING_FACT'`:
- Sets `errors[key]` to the remediation message
- Sets `data[key]` to `null`
- Section shows ErrorState with remediation text

No blank screen. No spinner forever. No interpretation of zeros.

---

## 8. ARCHIVOS CREADOS / MODIFICADOS

### Creados:
| Archivo | Proposito |
|---------|-----------|
| `docs/lima_growth/LG_UX_R2_9H_1_SERVING_FALLBACK_GUARDRAILS.md` | Este documento |

### Modificados:
| Archivo | Cambio |
|---------|--------|
| `backend/app/services/yego_lima_serving_facts_service.py` | +serving_or_missing(), +audit_force_refresh(), +audit table |
| `backend/app/routers/yego_lima_operational_summary.py` | Strict contract on 3 endpoints |
| `backend/app/routers/yego_lima_today_action_plan.py` | Strict contract |
| `backend/app/routers/yego_lima_allocation_trace.py` | Strict contract |
| `frontend/.../hooks/useLimaGrowthData.js` | +MISSING_SERVING_FACT detection |

---

## 9. QA

| Case | Result |
|------|:---:|
| Fact exists → returns payload (<1s) | PASS |
| Fact missing → returns MISSING_SERVING_FACT (no runtime) | PASS |
| force_refresh=true → runs runtime (audited) | PASS |
| UI detects MISSING_SERVING_FACT → shows error + remediation | PASS |
| Backend compile | OK |
| Frontend build | PASS |

---

## 10. VEREDICTO

```
SERVING FALLBACK GUARDED
```

All 5 public endpoints no longer fall back to heavy runtime computation transparently. Missing serving facts return a controlled MISSING_SERVING_FACT response with remediation. Runtime fallback requires explicit `force_refresh=true` and is audited.
