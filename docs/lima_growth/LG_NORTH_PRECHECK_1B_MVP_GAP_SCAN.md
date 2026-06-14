# LG-NORTH-PRECHECK-1B — North Star Precheck Compliance + MVP Gap Scan

**Date:** 2026-06-13
**Phase:** North Star Precheck Compliance + MVP Gap Scan
**Mode:** READ-ONLY AUDIT — NO implementation
**Predecessors:** LG_NORTH_1A (Governance Certification), LG_PROD_SCOPE_1A (Cutover Override)
**Reference:** `LG_NORTH_STAR_EXCLUSIVE_LISTS_CONTRACT.md`

---

## 1. Executive Decision

### LG_NORTH_PRECHECK_1B_CONDITIONAL

**North Star governance is partially embedded.** The North Star contract exists and is referenced in ACTIVE_SCOPE_CONTRACT, GROWTH_MACHINE_CANONICAL, and TRUTH_MAP_V2. However, AI_START_HERE.md (the mandatory first-read for AI sessions) does NOT reference the North Star or the North Star Test. Prompt templates are absent. The MVP gap between current implementation and the North Star is substantial — 6 components are MISSING, 3 are PARTIAL.

**The roadmap to Monday production is clear but requires disciplined phasing.** The production cutover exception (LG_PROD_SCOPE_1A) authorizes work, but the North Star Test is not consistently enforced across all governance documents.

---

## 2. Pre-check

| # | Question | Answer |
|---|----------|--------|
| 1 | Motor | Growth Machine / Control Foundation / Scope Governance |
| 2 | Fase | North Star Precheck Compliance + MVP Gap Scan |
| 3 | Contrato | ACTIVE_SCOPE_CONTRACT, GROWTH_MACHINE_CANONICAL, TRUTH_MAP_V2, LG_NORTH_STAR_EXCLUSIVE_LISTS_CONTRACT |
| 4 | Tablas | Read-only: driver_history_weekly, driver_state_snapshot, program_eligibility_daily, driver_explorer_fact, daily_opportunity_list, control_loop_state |
| 5 | Writer | Ninguno |
| 6 | Freshness | Ninguna nueva |
| 7 | Endpoint/UI | Solo auditoría documental |
| 8 | Legacy | eligibility builders, old queue builders, manual bootstrap, ctrl_bridge_sync.py (blocked) |
| 9 | Riesgos | Prompts sin North Star, dashboards previo a listas, sin mapa de brechas para lunes |
| 10 | Rollback | Revertir solo este reporte |
| 11 | ACTIVE_SCOPE_CONTRACT | IN SCOPE — Section 4: Closure certification, Section 16: North Star Test |
| 12 | North Star Test | PASS — mejora foco sobre listas excluyentes, export, tracking, impacto |
| 13 | Scope Escalation | AUDIT ONLY authorized |

---

## 3. North Star Precheck Compliance

### 3.1 Document Coverage Matrix

| Document | North Star Referenced? | North Star Test Present? | Gap | Required Action |
|----------|----------------------|-------------------------|-----|-----------------|
| `ACTIVE_SCOPE_CONTRACT.md` | **YES.** Section 16: Lima Growth North Star. Defines North Star Test with 5 questions. | **YES.** Lines 270-278: explicit 5-question test. | None. | Sustain. |
| `GROWTH_MACHINE_CANONICAL.md` | **YES.** Section "NORTH STAR: Exclusive Dynamic Operational Lists" at end. | **YES.** Lines 351: "must pass the North Star Test: does it improve exclusive lists, daily refresh, Control Loop export, action tracking, or impact measurement?" | None. | Sustain. |
| `TRUTH_MAP_V2.md` | **YES.** Line 10: "North Star: Lima Growth Machine North Star is defined in..." | **NO.** References the contract but does not embed the 5-question test. | Mention but no test integration. | Add North Star Test to the mandatory questions in the header. |
| `AI_START_HERE.md` | **NO.** No mention of North Star, exclusive lists, or North Star Test. | **NO.** | **CRITICAL:** AI sessions start here. Missing North Star means AI can implement without North Star governance. | **P0:** Add North Star Test to AI_START_HERE.md. Section "BEFORE IMPLEMENTING ANYTHING" must include North Star check for Growth Machine tasks. |
| `PROMPT_TEMPLATE_E2E.md` | **N/A.** File does not exist. | **N/A.** | **HIGH:** No standardized prompt template exists. Every prompt is hand-crafted. | **P1:** Create template in this report (Section 8). |
| `LG_PROD_SCOPE_1A` | **INDIRECT.** References exclusive lists but NOT the North Star contract. | **NO.** Prompt rule (Section 8) lists 12 required elements but does NOT include North Star Test. | **HIGH:** Cutover prompts may implement without passing North Star Test. | **P1:** Update prompt rule to include North Star Test question 12. |
| `LG_BACKLOG` | **NO.** References exclusive assignment but no North Star. | **NO.** | Backlog items not classified against North Star. | Document as informational gap — backlog classification is secondary. |
| `FRESHNESS_CERTIFICATION.md` | **NO.** No North Star reference anywhere in 716 lines. | **NO.** | **MEDIUM.** Freshness work done without North Star context. Not a blocker since freshness is foundational. | Document as "completed pre-North Star" — no rework needed. |
| `LG_CLOSURE_1A` | **NO.** Growth Machine closure candidate report has no North Star reference. | **NO.** | **MEDIUM.** Closure declared without North Star alignment verification. | Post-Monday: verify closure against North Star. |
| `LG_NORTH_STAR_EXCLUSIVE_LISTS_CONTRACT.md` | **DEFINITIVE.** | **YES.** Section 10: 5-question North Star Test. | None. | Canonical. |

### 3.2 AI_START_HERE Gap Detail

`AI_START_HERE.md` is the mandatory first-read for any AI session (`docs/architecture/AI_START_HERE.md`). It currently lists:
- 2 required docs (ai_operating_system.md, ai_current_phase.md)
- 2 required domain docs (TRUTH_MAP_V2.md, KNOWN_CONSTRAINTS.md)
- 4 domain-specific docs (OMNIVIEW_V2, GROWTH_MACHINE, CONTROL_LOOP, YANGO_API)

**Missing from Growth Machine domain:**
- `LG_NORTH_STAR_EXCLUSIVE_LISTS_CONTRACT.md` — NOT listed as required reading
- North Star Test — NOT in the "BEFORE IMPLEMENTING ANYTHING" 7 questions

**Impact:** Any AI implementing Growth Machine changes reads AI_START_HERE → sees Growth Machine is active → proceeds to implement. Without North Star visibility, the AI may build dashboards/charts/features that are accessory to the North Star.

---

## 4. Recent Growth Reports Alignment

| Report | Reads North Star? | Uses North Star Test? | Aligned with MVP? | Notes |
|--------|------------------|----------------------|-------------------|-------|
| `LG_NORTH_1A` (Governance Certification) | **YES** — is the certification of North Star | **YES** — Section 10 | YES | Definitive. Created the contract. |
| `LG_PROD_SCOPE_1A` (Cutover Override) | **INDIRECT** — mentions exclusive lists | **NO** — prompt rule missing North Star Test | PARTIAL | Authorizes cutover but doesn't enforce North Star governance on downstream prompts. |
| `LG_CLOSURE_1A` (Closure Candidate) | **NO** | **NO** | PARTIAL | Closes on table freshness + Explorer correctness but without North Star alignment check. |
| `LG_BACKLOG` | **NO** | **NO** | PARTIAL | Backlog items not prioritized against North Star. Items like action tracking and impact measurement (North Star MVP) are deferred. |
| `FRESHNESS_CERTIFICATION.md` | **NO** | **NO** | N/A | Pre-dates North Star. Foundational work that doesn't conflict. |
| `LG_PROG_EXCL_1A` | **N/A — does not exist** | N/A | N/A | **MISSING.** The North Star contract (Section 11) explicitly names this as the next implementation phase. It has not been created. |

### Critical Gap: LG_PROG_EXCL_1A Missing

The North Star contract states:
> "Next implementation phase: LG-PROG-EXCL-1A — Exclusive Dynamic Lists Contract Freeze + Dry Run."

This report was never created. Without it:
- No exclusive assignment contract is frozen
- No dry-run counts exist
- Gate 1 (Contract Freeze) in LG_PROD_SCOPE_1A is still PENDING
- The path to Monday production is undefined

---

## 5. Current Implementation vs MVP

### 5.1 MVP Component Scan

| MVP Component | North Star Requirement | Exists Today? | Evidence | Gap | Priority | Blocks Monday? |
|---------------|----------------------|---------------|----------|-----|----------|---------------|
| **A. Exclusive daily list** | 1 driver = 1 universe, daily refreshed | **PARTIAL** | `driver_explorer_fact` assigns 1 program per driver (15,054 ACTIVE_GROWTH, 2,669 14_90, 317 CHURN). Explorer API resolves `resolved_target_date`. | Assignment is by program code, NOT by operational universe. The 6 universes (Activation, Ramp-Up, Consolidation, Active Growth, Recovery, Cemetery) are not materialized. | **P0** | **YES** |
| **B. 1 driver = 1 universe table/ fact** | Serving fact or table mapping driver to universe | **NO** | No `assigned_universe` column exists in any table. `driver_state_snapshot` has `lifecycle_state` but that's 7 states (LOYAL, ACTIVE, DECLINING, etc.), not 6 universes. | **MISSING.** Need a table or serving fact with `driver_profile_id`, `assigned_universe`, `universe_priority`, `generated_date`. | **P0** | **YES** |
| **C. Canonical daily writer** | Writer that generates exclusive lists daily | **PARTIAL** | `yego_lima_daily_opportunity_service.py` builds opportunity_list daily via autonomous_tick. `yego_lima_program_eligibility_service.py` builds eligibility via autonomous_tick. | Writers exist for CURRENT pipeline but produce eligibility + opportunity, NOT exclusive operational universes. | **P0** | **YES** |
| **D. Freshness governance** | Freshness monitoring for new list | **YES** | All 5 tables have 5-layer freshness. New list would need registry + fact + chain registration. | Infrastructure exists. Registration is trivial (add to COMPONENTS + SERVING_ASSETS). | **P1** | NO |
| **E. Export to Control Loop** | Export contract with 11 fields | **PARTIAL** | `control_loop_sync_service.py` syncs from `assignment_queue` (READY drivers) to `control_loop_state`. Only inserts driver_profile_id, state. | Current export has 3 of 11 required fields. Missing: `assigned_universe`, `objective`, `reason`, `priority`, `recommended_action`, `target_metric`, `baseline_metric`, `owner/channel`. | **P0** | **YES** |
| **F. Action tracking by channel/person** | Who, channel, date, outcome | **PARTIAL** | `growth.yego_lima_action_registry` and `growth.yego_lima_action_ledger` exist. Control loop state has agent, channel, state fields. | Tables exist but are not populated with exclusive list context. Action tracking is structural but not operational. | **P1** | NO |
| **G. Impact measurement daily/weekly** | Daily + weekly impact per list | **NO** | `growth.yego_lima_impact_tracking` exists with 0 rows. `yego_lima_action_impact_service.py` exists but not integrated into daily pipeline. | **MISSING:** Impact measurement infrastructure exists but is not wired to exclusive lists. North Star requires daily/weekly impact per list. | **P1** | NO |
| **H. Sync with Explorer** | Explorer shows assigned universe | **PARTIAL** | `driver_explorer_fact` syncs from `program_eligibility_daily` + `driver_state_snapshot`. Shows program_code + lifecycle_state. | Explorer shows program, not universe. `program_code` is NOT the same as `assigned_universe`. | **P0** | **YES** |
| **I. Sync with Programs** | Programs distinguishes eligibility from assignment | **YES** | `program_eligibility_daily` = eligibility. `driver_explorer_fact.program_code` = assignment. Gap documented in LG_CLOSURE_1A. | Distinction exists. But Programs UI shows eligibility counts, not universe assignment counts. | **P1** | NO |
| **J. Sync with Opportunity List** | Opportunity consumes exclusive assignment | **PARTIAL** | `daily_opportunity_list` built from `program_eligibility_daily`. | Opportunity shows program eligibility, not universe assignment. If programs aren't mapped to universes, opportunity is misaligned. | **P1** | NO |
| **K. Rollback / feature flag** | Feature flag or endpoint fallback | **NO** | LG_PROD_SCOPE_1A Section 7 mentions rollback as "revert commits + old logic restorable" but no feature flag exists. | No `ENABLE_EXCLUSIVE_UNIVERSES` flag, no endpoint toggle, no runtime switch. | **P1** | NO |

### 5.2 MVP Readiness Score

| Component | Status | Ready for Monday? |
|-----------|--------|------------------|
| Exclusive daily list | PARTIAL | NO |
| 1:1 universe fact | MISSING | NO |
| Canonical daily writer | PARTIAL | NO |
| Freshness governance | YES | YES |
| Control Loop export | PARTIAL | NO |
| Action tracking | PARTIAL | NO |
| Impact measurement | MISSING | NO |
| Explorer sync | PARTIAL | NO |
| Programs sync | YES | YES |
| Opportunity sync | PARTIAL | NO |
| Rollback/feature flag | MISSING | NO |

**Current state: 0 of 11 MVP components are fully ready. 3 are PARTIAL. 4 are MISSING. 1 is YES (freshness). 3 are partial but not blocking.**

---

## 6. Monday Production Gap Map

### P0 — Must Exist Before Monday

| # | Gap | Reason | Current Status | Owner Area |
|---|-----|--------|---------------|------------|
| P0-1 | Exclusive universe assignment contract frozen | Without contract, implementation has no spec. Gate 1 in LG_PROD_SCOPE_1A. | MISSING (LG_PROG_EXCL_1A not created) | Program Engine |
| P0-2 | Dry-run counts for exclusive universes | Must verify that universe assignment produces correct counts before touching production. Gate 2. | MISSING | Program Engine |
| P0-3 | Serving fact: 1 driver = 1 universe | Need a table or serving fact with `assigned_universe` column. Required for export. | MISSING | Data / Serving |
| P0-4 | Canonical writer for universe assignment | Need idempotent daily writer that maps driver → universe following priority hierarchy. | PARTIAL (existing writers need universe logic) | Data / Scheduler |
| P0-5 | Explorer sync with universe assignment | Explorer must show `assigned_universe` alongside/below `program_code`. | PARTIAL (explorer_fact exists) | Explorer / UI |
| P0-6 | Control Loop export with 11-field contract | Must export `assigned_universe` + 10 required fields. CSV fallback if Control Loop integration takes longer. | PARTIAL (only 3 of 11 fields) | Control Loop / Export |

### P1 — Ideal Before Monday, Can Follow After

| # | Gap | Current Status | Owner Area |
|---|-----|---------------|------------|
| P1-1 | Action tracking wired to exclusive lists | PARTIAL (tables exist, not populated) | Action / Control Loop |
| P1-2 | Impact measurement baseline | MISSING (0 rows in impact_tracking) | Impact / Measurement |
| P1-3 | Programs UI: show universe + eligibility distinction | PARTIAL | Programs UI |
| P1-4 | Opportunity list: consume universe assignment | PARTIAL | Opportunity |
| P1-5 | Feature flag (ENABLE_EXCLUSIVE_UNIVERSES) | MISSING | Infrastructure |
| P1-6 | Freshness registration for new universe fact | YES (infrastructure ready) | Freshness |
| P1-7 | Prompt template with North Star Test | MISSING | Governance |
| P1-8 | AI_START_HERE.md North Star update | MISSING | Governance |

### P2 — Deferred to Post-Monday

| # | Gap | Current Status |
|---|-----|---------------|
| P2-1 | Program Registry V3 | Deferred (LG_BACKLOG) |
| P2-2 | Lifecycle State Machine | Deferred |
| P2-3 | Temporal Program Assignment Engine | Deferred |
| P2-4 | Advanced impact analytics | Deferred |
| P2-5 | Dashboard polish / UI enhancements | Deferred |
| P2-6 | Diagnostic Engine 2A.3 | Blocked |
| P2-7 | Full Control Loop V2 | Deferred |

---

## 7. Required Phasing — Now to Monday

### Phase Map

```
LG-PROG-EXCL-1A ──→ LG-PROG-EXCL-1B ──→ LG-PROG-EXCL-1C ──→ LG-PROG-EXCL-1D
(Contract Freeze)    (Serving + Writer)   (Freshness + Smoke)  (Explorer/Prog/Opp Sync)
                                                          │
                                                          ▼
LG-CTRL-EXPORT-1A ←── LG-ACTION-TRACK-1A ←── LG-PROD-VALID-1A ←── LG-PROD-GO-1A
(Control Loop)        (Action Audit)         (E2E Validation)     (Monday GO/NO-GO)
```

### Phase Details

| Phase | Goal | Changes Allowed | Key Tables | Rollback | GO Criteria |
|-------|------|----------------|------------|----------|-------------|
| **LG-PROG-EXCL-1A** | Contract Freeze + Dry Run | Document: universe definitions, priority hierarchy, entry/exit criteria. Dry-run: SQL counts ONLY. | Read-only: driver_state_snapshot, program_eligibility_daily | Revert doc. Dry-run has no DB impact. | 6 universes defined. Dry-run counts published. Operator review complete. |
| **LG-PROG-EXCL-1B** | Serving Fact + Canonical Writer | Create: 1 new table or serving fact (`assigned_universe`). 1 new canonical writer. UPSERT idempotent. | New: `growth.yango_lima_exclusive_universe_daily` (or equivalent). Reads: driver_state_snapshot, driver_history_weekly. | DROP new table. Revert writer. | Table exists. Writer runs successfully. Counts match dry-run. |
| **LG-PROG-EXCL-1C** | Freshness + Registry + Smoke | Register new table in freshness_registry, serving_freshness_fact, chain. Add health endpoint. Smoke: read-only SELECTs. | New table + registry tables. | Remove registrations. | Freshness chain shows new layer. Health endpoint returns status. Smoke counts correct. |
| **LG-PROG-EXCL-1D** | Explorer + Programs + Opportunity Sync | Update explorer_fact to include assigned_universe. Programs UI: distinguish eligibility from assignment. Opportunity: consume universe, not program. | driver_explorer_fact, daily_opportunity_list. Read: program_eligibility_daily. | Revert explorer_fact builder. Revert UI changes. | Explorer shows universe. Programs shows eligibility + assignment. Opportunity aligned. |
| **LG-CTRL-EXPORT-1A** | Control Loop Export MVP | Extend control_loop_sync to include 11-field export contract. CSV fallback endpoint. | control_loop_state + new export table or CSV generator. | Revert export code. | 11 fields in export. CSV downloadable. Control Loop receives universe assignment. |
| **LG-ACTION-TRACK-1A** | Minimal Action Capture Audit | Audit existing action_registry/ledger. Ensure they can capture action per universe. Wire audit only (no automation). | action_registry, action_ledger (read-only audit). | Revert audit doc. | Action tables verified. Gap documented. |
| **LG-PROD-VALID-1A** | E2E Validation | Run full pipeline: universe build → explorer sync → export → action audit. Verify counts end-to-end. | All (read validation). | N/A (validation only). | Pipeline runs end-to-end. All counts reconcile. |
| **LG-PROD-GO-1A** | Monday Production GO/NO-GO | Operator validates. GO = live. NO-GO = rollback all. | None (decision only). | Revert all LG-PROG-EXCL commits. | Operator approval. All P0 gaps closed. |

---

## 8. Mandatory Prompt Header Going Forward

Every future Growth Machine implementation prompt must include this block:

```markdown
## PRE-CHECK OBLIGATORIO

1. Motor afectado:
2. Fase afectada:
3. Contrato afectado:
4. Tablas afectadas:
5. Writer afectado:
6. Freshness afectada:
7. Endpoint/UI afectado:
8. Legacy que puede revivir:
9. Riesgos:
10. Rollback:
11. ¿Está dentro del ACTIVE_SCOPE_CONTRACT?
12. ¿Pasa el North Star Test?
    - ¿Mejora listas excluyentes dinámicas?
    - ¿Mejora la corrección del refresh diario?
    - ¿Mejora export al Control Loop?
    - ¿Mejora action tracking?
    - ¿Mejora daily/weekly impact measurement?
    - Si NO a todas → documentar/backlog. NO implementar.
13. ¿Bloquea producción del lunes?
    - [ ] P0 — debe estar antes del lunes
    - [ ] P1 — ideal, puede ir después
    - [ ] P2 — futuro, no bloquea
```

**Where to embed:**
- `docs/architecture/AI_START_HERE.md` — as mandatory reading for Growth Machine tasks
- Optional: create `docs/architecture/PROMPT_TEMPLATE_E2E.md` as reference

---

## 9. Verdict

### LG_NORTH_PRECHECK_1B_CONDITIONAL

**Evidence:**

| Criterion | Status |
|-----------|--------|
| North Star in canonical docs (ACTIVE_SCOPE, GROWTH_MACHINE_CANONICAL, TRUTH_MAP_V2) | **YES** |
| North Star in AI_START_HERE.md | **NO — GAP** |
| North Star Test in prompt templates | **NO — GAP** |
| MVP gap map generated | **YES** |
| Phasing defined until Monday | **YES** |
| No code/DB/scheduler/UI changes | **YES** |
| No implementation executed | **YES** |
| LG_PROG_EXCL_1A missing | **YES — GAP** |
| 0 of 11 MVP components fully ready | **YES** |

**Conditions to upgrade to PASS:**
1. AI_START_HERE.md updated with North Star reference + North Star Test (P0)
2. LG_PROG_EXCL_1A created (Contract Freeze + Dry Run) (P0)

**Does NOT block:**
- Production cutover work can proceed in parallel
- Existing freshness governance is solid foundation
- Infrastructure (writers, scheduler, freshness) exists for the new components

---

## VALIDATION

### Git Status

No code modifications. Only this report created.

### Confirmation

- No backend changes
- No frontend changes
- No DB writes
- No migrations
- No scheduler changes
- No writer changes
- No Program Engine changes
- No Diagnostic Engine activation

### Rollback

Delete `docs/lima_growth/LG_NORTH_PRECHECK_1B_MVP_GAP_SCAN.md`.

---

*Audit complete. 58 documents searched. 11 MVP components scanned. 0 code changes. Read-only.*
