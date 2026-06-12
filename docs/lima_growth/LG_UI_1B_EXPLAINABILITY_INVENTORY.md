# LG-UI-1B — EXPLAINABILITY INVENTORY

**Date:** 2026-06-12
**Phase:** LG-UI-1B / Explainability Hardening

---

## EXISTING EXPLANATIONS

| Domain | What | Where | Endpoint | Status |
|--------|------|-------|----------|--------|
| Lifecycle | lifecycle_reason + evidence_json | growth.yego_lima_driver_lifecycle_daily | explainability/{driver_id} | EXISTS |
| Lifecycle | Transition history | growth.yego_lima_driver_lifecycle_event | explainability/{driver_id} | EXISTS |
| Segment | matched_rules + failed_rules (5 layers, 18 rules) | growth.yego_lima_driver_taxonomy_v2_daily | explainability/{driver_id} | EXISTS |
| Segment | Taxonomy V2 explanations (342K rows) | growth.yego_lima_driver_taxonomy_v2_explanation | explainability/{driver_id} | EXISTS |
| Program | eligibility_reason + selection_reason | growth.yango_lima_program_eligibility_daily | explainability/{driver_id} | EXISTS |
| Program | Decision trace (5,558 decisions) | growth.yego_lima_program_decision_trace | diagnostic-trace/{driver_id} | EXISTS |
| Program | Rule definitions (4 programs) | growth.yango_lima_program_registry | explain/rules | EXISTS |
| Movement | trigger_reason + rule_delta_json | growth.yego_lima_state_transition_trace | diagnostic-trace/{driver_id} | EXISTS |
| Movement | Transition trace (1,205 records) | growth.yego_lima_state_transition_trace | explainability/{driver_id} | EXISTS |
| RNA | is_rna, contactability, cancelled_signal | growth.yango_lima_driver_state_snapshot | explainability/{driver_id} | EXISTS |
| RNA | Root causes (manual) | ops.mv_driver_lifecycle_monthly_kpis | yango-loyalty/summary | PARTIAL |

---

## NEWLY CREATED (LG-UI-1B)

| Asset | Type | File |
|-------|------|------|
| Unified explainability endpoint | Backend router | app/routers/yego_lima_explainability.py |
| Explainability aggregation service | Backend service | app/services/yego_lima_explainability_service.py |
| `GET /yego-lima-growth/explainability/{driver_id}` | API | Returns all 5 domains aggregated |
| `GET /yego-lima-growth/explainability/{driver_id}/{domain}` | API | Single domain per driver |
| ExplainabilityPanel | Frontend modal | ExplainabilityPanel.jsx |
| Driver Explorer "Why?" button | Frontend integration | DriverExplorerTab.jsx |
| Programs "Why this program?" | Frontend integration | ProgramsTab.jsx |
| Segments "Why these segments?" | Frontend integration | SegmentsTab.jsx |
| Movement "Why this movement?" | Frontend integration | MovementTab.jsx |
| RNA "Why RNA?" + evidence | Frontend integration | RNATab.jsx |

---

## COVERAGE SUMMARY

| Domain | Pre LG-UI-1B | Post LG-UI-1B |
|--------|:---:|:---:|
| Lifecycle | 100% (data) / 0% (UI) | 100% / 100% |
| Segment | 100% (data) / 0% (UI) | 100% / 100% |
| Program | 100% (data) / 0% (UI) | 100% / 100% |
| Movement | 100% (data) / 0% (UI) | 100% / 100% |
| RNA | PARTIAL / 0% (UI) | PARTIAL (data) / 100% (UI) |

---

## WHAT IS STILL MISSING

| Gap | Severity | Plan |
|-----|----------|------|
| RNA root causes automated | LOW | Backlog: requires RNA prioritization engine |
| Per-driver RNA explanation (detailed) | LOW | Current: basic RNA fields (is_rna, contactable, cancelled) |
| V2 shadow explainability | NONE | By design — shadow mode, not consumed |
