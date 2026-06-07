# LG-UX-R2.8F — Policy Activation Guardrails

**Date:** 2026-06-06
**Phase:** LG-UX-R2.8F Policy Activation Guardrails
**Scope:** Create safe activation flow for program capacity policy.
**Rule:** NO auto-rebuild. NO auto-export. NO assignment_queue changes.

---

## 1. EXECUTIVE SUMMARY

Se implemento un sistema completo de guardrails para activacion de politicas de capacidad:

- **Status model:** DRAFT → VALIDATED → ACTIVE → RETIRED / REJECTED
- **Validation:** 12 reglas (min>=0, max>=min, share 0-100, unique ranks, program exists, etc.)
- **Simulation required:** Validate-draft ejecuta simulacion y reporta risk_level
- **Activation:** Solo VALIDATED → ACTIVE. NO rebuild queue. NO export.
- **Audit log:** Tabla de auditoria registra cada accion (quien, cuando, que)
- **UI:** Panel muestra policy_status, guardrails explicados

---

## 2. STATUS MODEL

| Status | Meaning | Affects operation? |
|--------|---------|:---:|
| DRAFT | Saved but not validated | NO |
| VALIDATED | Passed validation + simulation | NO |
| ACTIVE | Live — governs future builds | YES (future only) |
| RETIRED | Deactivated, kept for audit | NO |
| REJECTED | Failed validation | NO |

Reglas:
- Solo una politica ACTIVE por programa en una ventana de fechas
- DRAFT no afecta operacion
- ACTIVATE requiere VALIDATED
- RETIRED queda auditado, no se borra

---

## 3. VALIDATION RULES

| # | Rule | Type |
|---|------|:---:|
| 1 | min_daily_capacity >= 0 | ERROR |
| 2 | max_daily_capacity >= 0 | ERROR |
| 3 | max >= min (if both set) | ERROR |
| 4 | target_share_pct between 0 and 100 | ERROR |
| 5 | Sum target_share_pct <= 100% | WARNING |
| 6 | priority_rank unique among enabled programs | WARNING |
| 7 | program_code exists in static registry | ERROR |
| 8 | allocation_mode is valid (STRICT_PRIORITY / PROPORTIONAL / HYBRID) | ERROR |
| 9 | At least one program enabled | ERROR |
| 10 | Simulation total_assigned > 0 | ERROR |
| 11 | Program with actionable > 0 gets 0 assigned | WARNING |
| 12 | Program consumes >80% of capacity | WARNING |

---

## 4. ACTIVATION FLOW

```
1. Edit Draft       → POST /save-draft
2. Simulate         → POST /simulate (with draft programs)
3. Validate Draft   → POST /validate-draft (runs all rules + simulation)
   ↳ If valid → VALIDATED
   ↳ If not  → REJECTED (must fix and re-draft)
4. Activate         → POST /activate
   ↳ Retires current ACTIVE
   ↳ Sets draft to ACTIVE
   ↳ Audited
```

**What activation does NOT do:**
- NO rebuild assignment_queue
- NO export to LoopControl
- NO change existing queue records
- NO affect Today's Action Plan immediately
- Only affects future builds (when queue is rebuilt)

---

## 5. ENDPOINTS

| Method | Path | Description |
|--------|------|-------------|
| GET | /program-capacity-policy?date= | Read active policy |
| GET | /program-capacity-policy/versions | Version history |
| GET | /program-capacity-policy/audit-log | Audit trail |
| POST | /program-capacity-policy/seed | Seed default |
| POST | /program-capacity-policy/simulate | Simulate allocation |
| POST | /program-capacity-policy/validate | Validate policy payload |
| POST | /program-capacity-policy/save-draft | Save DRAFT policy |
| POST | /program-capacity-policy/validate-draft | Validate + simulate draft |
| POST | /program-capacity-policy/activate | Activate DRAFT → ACTIVE |
| POST | /program-capacity-policy/retire | Retire active policy |

---

## 6. UI BEHAVIOR

Program Capacity Policy panel ahora muestra:
- `policy_status` badge (ACTIVE=green, DRAFT=yellow, RETIRED=gray)
- Guardrails warning: "Activation requires validation + simulation"
- "Changes affect future queue builds only"

---

## 7. AUDIT LOG

Table: `growth.yego_lima_program_capacity_policy_audit`

| Column | Description |
|--------|-------------|
| id | UUID PK |
| policy_id | Reference to policy |
| action | DRAFT_CREATED, ACTIVATED, RETIRED, etc. |
| detail | JSONB with context |
| created_at | Timestamp |
| created_by | Who performed action |

---

## 8. ARCHIVOS CREADOS / MODIFICADOS

### Creados:
| Archivo | Proposito |
|---------|-----------|
| `docs/lima_growth/LG_UX_R2_8F_POLICY_ACTIVATION_GUARDRAILS.md` | Este documento |

### Modificados:
| Archivo | Cambio |
|---------|--------|
| `backend/app/services/yego_lima_program_capacity_policy_service.py` | +save_draft, +validate_draft, +activate_policy, +retire_policy, +get_audit_log, +_write_audit, enhanced validate_policy |
| `backend/app/routers/yego_lima_program_capacity_policy.py` | +5 new endpoints |
| `frontend/.../sections/ControlConfigSection.jsx` | +policy_status badge, +guardrails warning |
| DB: `growth.yego_lima_program_capacity_policy` | +policy_status column |
| DB: `growth.yego_lima_program_capacity_policy_audit` | New audit table |

---

## 9. QA

| Check | Resultado |
|-------|:---------:|
| policy_status column added | YES |
| Audit table created | YES |
| save-draft | Functional (saves 4 programs as DRAFT) |
| validate-draft | Functional (validates + simulates + risk_level) |
| activate | Functional (DRAFT → ACTIVE, retires old) |
| audit-log | Functional (4 entries recorded) |
| Backend compile | OK |
| Frontend build | PASS |
| assignment_queue unchanged | YES |
| No auto-rebuild | YES |
| No auto-export | YES |

---

## 10. VEREDICTO

```
GO para LG-UX-R2.8G Controlled Policy Application
```

**Evidencia:**
- Status model completo (DRAFT → VALIDATED → ACTIVE → RETIRED)
- 12 reglas de validacion
- Simulation obligatoria en validate-draft
- Activation con guardrails (NO rebuild, NO export)
- Audit trail funcional
- UI muestra status y guardrails
- Sin cambios en produccion (politica actual = seed = STRICT_PRIORITY)
