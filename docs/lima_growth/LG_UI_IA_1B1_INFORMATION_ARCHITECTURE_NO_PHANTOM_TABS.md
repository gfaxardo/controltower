# LG-UI-IA-1B.1 — Information Architecture + No Phantom Tabs Contract

**Date:** 2026-06-14
**Phase:** LG-UI-IA-1B.1 (UI Information Architecture)
**Mode:** PRODUCT / UI ARCHITECTURE PATCH
**Status:** CERTIFIED

---

## 1. Executive Decision

### LG_UI_IA_1B1_CERTIFIED

Wiring endpoints alone is insufficient. The Intelligence UI must first be reorganized around operator workflow. The 7 technical tabs are mapped to 6 canonical operational tabs. The "No Phantom Tabs" principle is now part of the North Star UI contract.

---

## 2. Why Wiring Alone Is Not Enough

The current Intelligence UI has 7 tabs (Overview, Programs, Segments, Movement, RNA, Driver Explorer, Effectiveness). Some serve operational purpose; others are vestigial or redundant. Before wiring the 4 `exclusive-worklist` endpoints, the information architecture must be corrected to prevent:
- Phantom tabs with no real data source
- Redundant tabs (Programs + Segments overlapping)
- Tabs with no operational decision purpose (RNA without definition)
- Tabs showing partial or misleading data

---

## 3. Operator Workflow

```
Open Growth Machine → See today's health (Comando Diario)
                   → See who to work today (Listas de Trabajo)
                   → Drill into specific driver (Explorador)
                   → Check what changed (Movimientos)
                   → Verify Control Loop sync (Control Loop)
                   → Measure impact (Resultados)
```

Every tab answers a specific operator question and enables a specific action.

---

## 4. Canonical Tabs (6)

| # | Tab | Purpose | Source | Action Enabled |
|---|-----|---------|--------|---------------|
| 1 | **Comando Diario** | Daily health: generated_date, freshness, batch, alerts, day-over-day changes | `exclusive-worklist/summary`, `growth/health` | Is today's data ready? |
| 2 | **Listas de Trabajo** | Who to work today: 6 actionable universes, driver table with reason_text, gap, priority | `exclusive-worklist/rows` | Assign agents to lists |
| 3 | **Explorador de Conductores** | Driver drilldown: profile, evidence, target, gap, exit, transition history, actions | `exclusive-worklist/rows` (filtered), `transition_daily`, `control_loop_state` | Understand specific driver |
| 4 | **Movimientos** | What changed: stayed/moved/exited/recovered/goal met | `worklist_transition_daily` | Track fleet health |
| 5 | **Control Loop** | Execution: batch, READY/ASSIGNED/CONTACTED/DONE, coverage | `control_loop_state` by batch | Verify agents are working |
| 6 | **Resultados** | Did it work: actions vs outcomes, improvement/degradation | `control_loop_state` + `action_registry` | Measure impact |

---

## 5. Current Tabs Mapping

| Current Tab | Action | Rationale |
|-------------|--------|-----------|
| **Overview** | Fuse into Comando Diario | Shows summary/batch/health — core of Comando Diario |
| **Programs** | Deprecate → fuse into Listas de Trabajo | Universe lists replace program views |
| **Segments** | Deprecate → merge into Comando Diario | Segments = universe counts |
| **Movement** | Keep → fuse into Movimientos tab | Already shows movement, needs to consume transition fact |
| **RNA** | Hide/deprecate | No operational definition in current North Star |
| **Driver Explorer** | Keep → rename to Explorador de Conductores | Core product feature |
| **Effectiveness** | Hold → rename Resultados when action evidence exists | Placeholder with "coming soon" message |

---

## 6. No Phantom Tabs Principle

Every visible tab, section, card, button, or metric must pass:

| # | Question |
|---|----------|
| 1 | What is this for? |
| 2 | What decision does it help the operator make? |
| 3 | What operational action does it enable? |
| 4 | What source of truth does it use? |
| 5 | What does red/green/stale mean here? |
| 6 | What is the operator's next step? |

**If it does not pass → remove, hide, merge, or backlog.** Do NOT keep as a phantom tab.

---

## 7. Precheck Updates

UI precheck expanded to 13 questions (previously 9):
10. Does it avoid phantom tabs?
11. Does it have screenshot/render evidence?
12. What happens if the endpoint fails?
13. How does the operator know what to do next?

---

## 8. Files Updated

| File | Change |
|------|--------|
| `LG_NORTH_STAR_UI_OPERATIONAL_CONTRACT.md` | Sections 4 (No Phantom Tabs) + 5 (Canonical IA) |
| `GROWTH_MACHINE_CANONICAL.md` | UI Product Architecture section |
| `LG_UI_IA_1B1_*.md` | This certification |

---

## 9. What Remains Blocked

- Diagnostic Engine (until GM UI closure + OMNI-P0 closure)
- Forecast/Suggestion/Decision/Action/AI/Learning
- Program Registry V3, State Machine
- New assignment rules or thresholds

---

## 10. Next Phase

**LG-UI-LISTS-1C:** Wire `exclusive-worklist/summary` → Comando Diario cards. Wire `exclusive-worklist/rows` → Listas de Trabajo driver table. Deprecate/hide Programs and Segments tabs as per mapping.

---

## 11. Verdict

### LG_UI_IA_1B1_CERTIFIED

Information architecture defined. No phantom tabs principle established. 7→6 tab mapping complete. Ready for UI implementation phases.

---

*Architecture governs implementation. The operator sees what they need, not what the code happens to expose.*
