# LG-UX-R2.8E — Program Capacity Policy Foundation

**Date:** 2026-06-06
**Phase:** LG-UX-R2.8E Program Capacity Policy Foundation
**Scope:** Create governed foundation for program capacity allocation policy. NO auto-apply.
**Rule:** NO Program Builder. NO new score. NO production changes without preview.

---

## 1. EXECUTIVE SUMMARY

Se creo la base gobernada para configurar como se reparte capacidad entre programas:

- **Tabla:** `growth.yego_lima_program_capacity_policy` — versioned, auditable
- **Servicio:** `yego_lima_program_capacity_policy_service.py` — read, simulate, validate, seed
- **API:** 5 endpoints (GET policy, GET versions, POST seed, POST simulate, POST validate)
- **UI:** Panel "Program Capacity Policy" en Control Config (read-only)
- **Seed:** Replica comportamiento actual STRICT_PRIORITY (HVR=80, CP=230)

---

## 2. DATA MODEL

### Table: `growth.yego_lima_program_capacity_policy`

| Column | Type | Description |
|--------|------|-------------|
| id | uuid PK | Unique identifier |
| version | integer | Policy version (1, 2, 3...) |
| policy_date_from | date | When this policy takes effect |
| policy_date_to | date | When this policy expires (null = indefinite) |
| program_code | text | Program identifier |
| priority_rank | integer | Priority order (1 = highest) |
| allocation_mode | text | STRICT_PRIORITY / PROPORTIONAL / HYBRID |
| min_daily_capacity | integer | Minimum slots guaranteed |
| max_daily_capacity | integer | Maximum slots allowed |
| target_share_pct | numeric(5,2) | Target % of total capacity |
| is_enabled | boolean | Active/inactive |
| policy_reason | text | Human-readable justification |
| created_at | timestamptz | Creation timestamp |
| updated_at | timestamptz | Last update timestamp |
| created_by | text | Who created/modified |

### Allocation Modes

| Mode | Behavior |
|------|----------|
| STRICT_PRIORITY | Sequential greedy: first program takes all it needs, then next, etc. |
| PROPORTIONAL | Capacity distributed proportionally to actionable count or target_share_pct |
| HYBRID | Priority order within min/max bounds and target share limits |

---

## 3. SEED POLICY

Replicates current production behavior:

| Program | Rank | Mode | Min | Max | Share |
|---------|:----:|------|:---:|:---:|:---:|
| HIGH_VALUE_RECOVERY | 1 | STRICT_PRIORITY | — | — | — |
| CHURN_PREVENTION | 2 | STRICT_PRIORITY | — | — | — |
| 14_90 | 3 | STRICT_PRIORITY | — | — | — |
| ACTIVE_GROWTH | 4 | STRICT_PRIORITY | — | — | — |

**Verification (2026-06-02 data):** HVR=80, CP=230, 14_90=0, AG=0, unassigned=190. Matches production.

---

## 4. API ENDPOINTS

| Method | Path | Description |
|--------|------|-------------|
| GET | /program-capacity-policy?date= | Read active policy for date |
| GET | /program-capacity-policy/versions?program_code= | Version history |
| POST | /program-capacity-policy/seed | Seed default policy |
| POST | /program-capacity-policy/simulate | Simulate allocation with draft policy |
| POST | /program-capacity-policy/validate | Validate policy payload |

### Simulate Response

```json
{
  "current_policy": { "programs": [...], "active": true },
  "simulation": {
    "total_actionable": 500,
    "total_capacity": 310,
    "total_assigned": 310,
    "unassigned_total": 190,
    "programs": [
      {"program_code": "PROGRAM_HIGH_VALUE_RECOVERY", "actionable": 80, "assigned": 80, "unmet": 0}
    ]
  },
  "comparison": {
    "simulated_unassigned": 190,
    "total_capacity": 310,
    "total_actionable": 500
  }
}
```

---

## 5. UI FOUNDATION

Panel "Program Capacity Policy" en Control Config muestra:

- Tabla con: programa, rank, mode, min, max, share%, enabled, reason
- Color-coded allocation modes (blue=STRICT_PRIORITY, purple=PROPORTIONAL, green=HYBRID)
- Version indicator
- Legend for modes
- "Edicion pendiente" notice (R2.8F)

---

## 6. GOVERNANCE

### Reglas

1. No borrar politicas antiguas — versionar
2. Solo una politica activa por programa y fecha
3. No SQL libre desde UI
4. Simulacion obligatoria antes de aplicar
5. NO aplicar automaticamente

### Explainability

Cada politica debe explicar:
- Por que existe (`policy_reason`)
- Quien la creo (`created_by`)
- Que version es (`version`)
- Que cambiaria (via simulate endpoint + UI comparison)

---

## 7. WHAT WAS NOT IMPLEMENTED

- **NO** apply/save-draft endpoint (R2.8F)
- **NO** auto-rebuild de cola al cambiar politica
- **NO** auto-export al cambiar politica
- **NO** Program Builder integration
- **NO** editing in UI (read-only)
- **NO** individual driver scoring changes

---

## 8. RISKS

| Risk | Mitigation |
|------|------------|
| Cambiar politica sin preview | Simulate endpoint obligatorio + UI comparison |
| Politica inconsistente entre fechas | Versioning + date_from/date_to |
| Politica hardcodeada en codigo | Seed replica comportamiento actual verificable |
| Aplicar sin entender impacto | Validate endpoint + simulate muestra before/after |

---

## 9. ARCHIVOS CREADOS / MODIFICADOS

### Creados:
| Archivo | Proposito |
|---------|-----------|
| `backend/alembic/versions/188_yego_lima_program_capacity_policy.py` | Migration |
| `backend/app/services/yego_lima_program_capacity_policy_service.py` | Service |
| `backend/app/routers/yego_lima_program_capacity_policy.py` | Router |
| `docs/lima_growth/LG_UX_R2_8E_PROGRAM_CAPACITY_POLICY_FOUNDATION.md` | Este documento |

### Modificados:
| Archivo | Cambio |
|---------|--------|
| `backend/app/main.py` | +program_capacity_policy router |
| `frontend/src/services/api.js` | +getProgramCapacityPolicy, +simulate |
| `frontend/.../hooks/useLimaGrowthData.js` | +programPolicy fetch |
| `frontend/.../sections/ControlConfigSection.jsx` | +ProgramPolicyPanel |

---

## 10. QA

| Check | Resultado |
|-------|:---------:|
| Migration executed | Table created (4 rows) |
| Seed policy | 4 programs, STRICT_PRIORITY |
| Seed matches production | YES (HVR=80, CP=230, unassigned=190) |
| Simulate endpoint | Functional |
| Backend compile | OK |
| Frontend build | PASS |
| Assignment queue unchanged | YES |
| No auto-apply | YES |

---

## 11. VEREDICTO

```
GO para LG-UX-R2.8F Policy Activation Guardrails
```

**Evidencia:**
- Tabla de politica creada y poblada con seed
- Seed replica comportamiento actual verificado
- Servicio con read + simulate + validate funcional
- 5 endpoints API
- UI panel read-only con todos los campos visibles
- NO cambios en produccion (politica actual = seed = STRICT_PRIORITY)
