# LG_SEM_1A_PROGRAM_SEMANTICS_AUDIT

**Phase:** LG-SEM-1A — Program Semantics Audit  
**Motor:** Control Foundation  
**Generated:** 2026-06-13  
**Rules:** TRUTH_MAP_V2 prevails. KNOWN_CONSTRAINTS observed. Zero code changes.  
**Veredict:** `LG_SEM_1A_READY_FOR_UI_COPY`

---

## PRE-CHECK

| Question | Answer |
|----------|--------|
| 1. Motor afectado | **Control Foundation** (#1 in canonical engine order) |
| 2. Fase afectada | **LG-SEM-1A** — pure documentation, no code |
| 3. Tablas afectadas | **NONE** — read-only audit |
| 4. Writer afectado | **NONE** — no code changes |
| 5. Freshness afectada | **NONE** — no data changes |
| 6. Riesgos | **LOW** — documentation only. Zero runtime impact. |
| 7. Rollback | **N/A** — no changes to roll back |

**Constraints verified:**
- KNOWN_CONSTRAINTS §1.2: "NO modifications to business logic without prior audit" → This IS the audit ✅
- KNOWN_CONSTRAINTS §1.2: "NO database changes except read-only" → Compliant ✅
- ai_operating_system.md §1: "Control Foundation" → Within scope ✅
- TRUTH_MAP_V2: "IA interprets; IA does NOT govern core truth" → This is interpretation, not governance ✅

---

## 1. SEMANTIC MATRIX

### 1.1 Flags

| Campo técnico | Fórmula | Qué mide realmente | Qué NO mide | Label actual | Label recomendado |
|--------------|---------|-------------------|------------|-------------|-------------------|
| `churn_risk_flag` | `(avg_4w - orders_week)/avg_4w >= 0.30` | Caída >=30% desde el promedio personal de 4 semanas | Riesgo absoluto de abandono. Nivel de actividad actual. | "Churn Risk" | **"Sharp Decline ≥30%"** / **"Caída Fuerte"** |
| `declining_flag` | `(avg_4w - orders_week)/avg_4w >= 0.15` | Caída >=15% desde el promedio personal de 4 semanas | Que el conductor esté en peligro. Que tenga baja actividad. | "Declining" | **"Moderate Decline ≥15%"** / **"Caída Moderada"** |
| `recoverable_flag` | `avg_12w >= 50 AND orders_week < 50` | Históricamente alto (>50 avg) pero actualmente bajo (<50) | Que el conductor esté empeorando ahora. Que sea irrecuperable. | "Recoverable" | **"High Value Below Target"** / **"Alto Valor Recuperable"** |
| `performance_state` | 5-tier: `NO_TRIPS / LOW / MEDIUM / TARGET / HIGH` | Actividad absoluta actual (cuántos viajes esta semana) | Tendencia. Historia. Riesgo. | — (tier names are clear) | **Keep tier names** (son descriptivos) |
| `retention_state` | 5-tier: `HEALTHY / WATCHLIST / AT_RISK / CHURN_RISK / UNKNOWN` | Tendencia de retención basada en caída relativa | Actividad absoluta. Engagement. | — | **"Retention Trend"** en vez de "Retention State" |

### 1.2 Programs

| Program Code | Regla de asignación | Quiénes entran realmente | Qué sugiere el nombre | Label actual | Label recomendado |
|-------------|-------------------|------------------------|---------------------|-------------|-------------------|
| `PROGRAM_ACTIVE_GROWTH` | `performance IN (NO_TRIPS, LOW, MEDIUM) AND lifecycle IN (ACTIVATED, EARLY_LIFE, ESTABLISHED, REACTIVATED) AND distance_to_target > 0` | Conductores con **89.9% LOW** perf (mediana 3 viajes/semana). Debajo del target de 50. | "Crecimiento Activo" — suena a conductores creciendo, mejorando | "Active Growth" | **"Below Target Recovery"** / **"Recuperación Bajo Target"** |
| `PROGRAM_CHURN_PREVENTION` | `retention_state IN (AT_RISK, CHURN_RISK) OR declining OR churn_risk` | Conductores con **mediana 51 viajes/semana**. Los de mayor actividad real. Cayeron desde picos altos. | "Prevención de Churn" — suena a conductores a punto de irse | "Churn Prevention" | **"High Value Decline Protection"** / **"Protección Alto Valor"** |
| `PROGRAM_14_90` | `lifecycle IN (ACTIVATED, EARLY_LIFE, REACTIVATED) AND reached_target = false` | Nuevos o reactivados en ventana 14-90 días. Mediana 3 viajes. Correctamente asignados. | "14/90" — descriptivo pero opaco para operadores | "Programa 14/90" | **"New Driver Activation"** / **"Activación Nuevos"** |
| `PROGRAM_HIGH_VALUE_RECOVERY` | `best_week_12w >= 80 AND orders_week = 0 AND inactive 1-14d` | Conductores históricamente élite (>80 en mejor semana) que están inactivos esta semana. 0 en explorer fact. | "Recuperación Alto Valor" — semánticamente correcto | "High Value Recovery" | **Keep** (el nombre es correcto) |
| `NULL / no program` | No califica para ningún programa | **504 conductores elite** (mediana 73 viajes/semana). ESTABLISHED, HIGH perf, sin flags de riesgo. | (no visible) | — | **"Top Performer"** / **"Elite — Sin Programa"** |

---

## 2. PROGRAM LABEL PROPOSAL

### Recommendation: Option B — Rename UI labels, keep `program_code`

| Program Code (unchanged) | Current UI Label | Proposed UI Label | Rationale |
|-------------------------|-----------------|-------------------|-----------|
| `PROGRAM_CHURN_PREVENTION` | "Churn Prevention" | **"High Value Decline Protection"** | The program protects high-value drivers who declined from peak, not drivers about to churn. |
| `PROGRAM_ACTIVE_GROWTH` | "Active Growth" | **"Below Target Recovery"** | The program targets drivers below the 50-trip target. "Growth" is misleading — median = 3 trips. |
| `PROGRAM_14_90` | "Programa 14/90" | **"New Driver Activation"** | Clearer operational meaning: these are drivers in their first 90 days. |
| `PROGRAM_HIGH_VALUE_RECOVERY` | "High Value Recovery" | **"Elite Reactivation"** | Shorter, clearer. These are elite drivers (>80 best week) who stopped. |
| `NULL` | (not shown) | **"Top Performer — No Program"** | These 504 drivers are the fleet's best. They need visibility. |

### Why Not Option A (tooltip only)?

Tooltips help but don't fix the primary problem: the name "Churn Prevention" primes the operator to think "this driver is leaving." When they see 105 trips/week, cognitive dissonance occurs. A tooltip explaining the mismatch is a band-aid on a naming problem.

### Why Not Option C (Program Registry V3 now)?

LG-PROG-3A already recommended Program Registry V3 for *rule changes* (criteria adjustments). This phase is about *semantics* (names and labels). They are orthogonal. Rename now, redesign rules later.

### Why Option B (rename labels now)?

- **Zero code risk.** Only UI display strings change. `program_code` in the database is untouched.
- **Immediate operational clarity.** An operator seeing "High Value Decline Protection" with 105 trips understands immediately: "Ah, this driver was elite and declined."
- **Backward compatible.** API responses still return `PROGRAM_CHURN_PREVENTION`. Only the UI label changes.
- **KNOW_CONSTRAINTS compliant.** No business logic modification. No database changes.

---

## 3. UI COPY CONTRACT

### Tooltip / explainability text per program

| Program | Tooltip Text (español operativo) |
|---------|----------------------------------|
| **High Value Decline Protection** | "Este conductor está en Protección Alto Valor porque su actividad semanal cayó más del 30% respecto a su propio promedio de 4 semanas. Aunque todavía tenga alta actividad (50+ viajes/sem), la caída desde su pico personal es significativa. El objetivo es evitar que siga cayendo." |
| **Below Target Recovery** | "Este conductor está en Recuperación Bajo Target porque hace menos de 50 viajes por semana (el target mínimo). Mediana real: 3 viajes/sem. El objetivo es ayudarlo a alcanzar el target semanal." |
| **New Driver Activation** | "Este conductor está en Activación de Nuevos porque tuvo su primer viaje hace menos de 90 días. Está en la ventana crítica de activación temprana. El objetivo es establecer hábitos de conducción." |
| **Elite Reactivation** | "Este conductor está en Reactivación Élite porque es un histórico de alto valor (80+ viajes en su mejor semana) que actualmente tiene 0 viajes. Está inactivo hace 1-14 días. El objetivo es reactivarlo urgentemente." |
| **Top Performer — No Program** | "Este conductor no está en ningún programa porque consistentemente supera el target de 50 viajes/semana y no muestra señales de caída. Mediana real: 73 viajes/sem. Monitorear para retención proactiva." |

### Tooltip for flags

| Flag | Tooltip Text |
|------|-------------|
| Churn Risk | "Caída >=30% desde su promedio de 4 semanas. Ej: bajó de 100 a 70 viajes. NO significa que vaya a abandonar — significa que cayó fuerte desde su propio nivel histórico." |
| Declining | "Caída >=15% desde su promedio de 4 semanas. Ej: bajó de 100 a 85 viajes. Declive moderado desde su línea base." |
| Recoverable | "Históricamente fuerte (promedio 12 semanas >=50 viajes) pero actualmente debajo del target. Candidato prioritario para recuperación." |

---

## 4. OPERATIONAL DECISION

### Recommendation: **B) Rename UI labels, keep program_code**

**Rationale:**

| Factor | Assessment |
|--------|------------|
| **Risk** | ZERO — only display strings change |
| **Effort** | MINIMAL — change 5 label constants in DriverExplorerTab.jsx |
| **Impact** | HIGH — operators immediately understand program intent |
| **Backward compat** | FULL — API unchanged, DB unchanged |
| **Constraints** | COMPLIANT — no business logic, no DB, no writer changes |
| **Timing** | NOW — can ship with current UI | 

### Implementation scope (NOT executed — documented for next phase)

File to modify: `DriverExplorerTab.jsx` lines 6-12 (PROGRAM_OPTIONS labels only)

```javascript
// Before:
{ value: 'PROGRAM_CHURN_PREVENTION', label: 'Churn Prevention' },
{ value: 'PROGRAM_ACTIVE_GROWTH', label: 'Active Growth' },

// After:
{ value: 'PROGRAM_CHURN_PREVENTION', label: 'High Value Decline' },
{ value: 'PROGRAM_ACTIVE_GROWTH', label: 'Below Target' },
```

Program codes (`value`) unchanged. Only `label` changes.

---

## 5. UI CHECKPOINT PLAN

### Validation: Does the operator understand why high-activity drivers are in "High Value Decline"?

```
Step 1: Open Driver Explorer
Step 2: Filter Program = "High Value Decline" (was "Churn Prevention")
Step 3: Observe trips_7d column → many drivers at 40-121 trips
Step 4: Read tooltip: "Cayó más del 30% desde su propio promedio..."
Step 5: Operator should understand: "Ah, no es que esté abandonando. Es que era elite y cayó."

Expected operator reaction:
  BEFORE (label "Churn Prevention"): "¿Por qué este conductor de 105 viajes está en prevención de churn?"
  AFTER (label "High Value Decline"): "Entendido. Este conductor era de 150 y cayó a 105. Hay que evitar que siga cayendo."
```

### Validation: Does the operator understand why low-activity drivers are in "Below Target"?

```
Step 1: Open Driver Explorer
Step 2: Filter Program = "Below Target" (was "Active Growth")
Step 3: Observe trips_7d column → median = 3
Step 4: Read tooltip: "Hace menos de 50 viajes/semana..."
Step 5: Operator should understand: "No están creciendo. Están debajo del target. Necesitan recuperación."

Expected operator reaction:
  BEFORE (label "Active Growth"): "¿Por qué 'Active Growth' si hacen 3 viajes?"
  AFTER (label "Below Target"): "Correcto. Están debajo del target de 50."
```

---

## 6. SUMMARY

### Problem Confirmed

LG-FLAG-1A confirmed that program names are misleading:
- "Churn Prevention" = highest-activity drivers (mediana 51 trips)
- "Active Growth" = lowest-activity drivers (mediana 3 trips)
- 504 top performers have no program label

### Solution Designed

Rename UI labels to reflect operational reality. Zero code risk. Program codes unchanged in DB and API.

### Ready for Implementation

| What | Where | Effort |
|------|-------|--------|
| Rename 5 program labels | `DriverExplorerTab.jsx` PROGRAM_OPTIONS | 5 lines |
| Add tooltip component | New `ProgramTooltip.jsx` or inline in tab | ~30 lines |
| Add NULL program visibility | Add "Top Performer" row in program filter dropdown | 1 line |

---

## VEREDICT

### LG_SEM_1A_READY_FOR_UI_COPY

The semantic gap is documented. The fix is designed. The risk is zero. The labels are proposed. The tooltip texts are drafted. The UI validation plan is defined.

**Next phase:** LG-SEM-1B — implement UI copy changes (5 label renames + tooltips).
