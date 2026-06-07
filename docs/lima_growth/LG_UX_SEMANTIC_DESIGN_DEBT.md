# LG-UX — Semantic Design Debt

**Date:** 2026-06-06
**Phase:** LG-UX-R2.9A UX Audit
**Scope:** Classified UX inconsistencies and gaps.

---

## HIGH PRIORITY

| # | Issue | Affected areas | Remediation |
|---|-------|---------------|-------------|
| H-1 | No hyperlinks from Today's Action Plan to Queue | Cross-section navigation | Add "Ir a Execution Queue" button when status = QUEUE_NOT_BUILT or READY > 0 |
| H-2 | Audit section has zero frontend representation | Audit visibility | Add "Build Audit" or "Policy Audit" panel to Control Config or Queue |
| H-3 | Simulation preview not available in UI | Policy UX | Add simulation results panel to Policy section |
| H-4 | `EXPORTED` status badge missing from V2 StatusBadge | Queue records, export history | Add `EXPORTED` to StatusBadge mappings |
| H-5 | Export hardcoded to CHURN_PREVENTION in frontend hook | Export workflow | Add program selector dropdown to export UI |

---

## MEDIUM PRIORITY

| # | Issue | Affected areas | Remediation |
|---|-------|---------------|-------------|
| M-1 | No drilldown from Driver State into driver groups | Programs section | Add clickable bar segments that filter queue by state |
| M-2 | Build result transient — disappears on tab switch | Queue UX | Persist build result in component state until next build |
| M-3 | No program-level CTAs | Program cards | Add "Ver en Queue" or "Exportar programa" buttons |
| M-4 | `decisionColors.js` unused in V2 codebase | Theme consistency | Either integrate or deprecate with comment |
| M-5 | ExplainabilityTooltip missing from TodayActionPlan and Queue | Explainability coverage | Add tooltips to KPI blocks and actions |
| M-6 | Freshness badge missing from Driver State | Freshness coverage | Add FreshnessBadge to Driver State sub-section |
| M-7 | Program ACTIVE = blue (V2) vs green (legacy) | Color consistency | Standardize to blue for ACTIVE, green for READY |
| M-8 | `draft_dry_run` (blue) ≈ `STRICT_PRIORITY` (blue) | Color ambiguity | Use different color tones (e.g., teal for draft_dry_run) |

---

## LOW PRIORITY

| # | Issue | Affected areas | Remediation |
|---|-------|---------------|-------------|
| L-1 | Export history `exported` vs `EXPORTED` case mismatch risk | StatusBadge | Add uppercase mapping or normalize before display |
| L-2 | LoopControl config read-only (no test/save UI) | Config section | Add test connection button in future sprint |
| L-3 | No pagination on queue records (50 limit) | Queue table | Add pagination or "Load more" button |
| L-4 | Empty state missing from Programs when no data | Programs section | Add EmptyState component for programs with 0 metrics |
| L-5 | No "NOT_BUILT" badge in StatusBadge mapping | Queue | Add NOT_BUILT to StatusBadge with gray styling |
| L-6 | Config loading state returns text "Cargando configuracion..." instead of LoadingState component | Config section | Use shared LoadingState component |

---

## SUMMARY

| Priority | Count |
|----------|:---:|
| HIGH | 5 |
| MEDIUM | 8 |
| LOW | 6 |
| **TOTAL** | **19** |

Items marked HIGH block real operational use. Items marked MEDIUM degrade experience but don't block. Items marked LOW are polish.

---

## RECOMMENDATION

Resolve H-1 through H-5 before declaring R2.9B "Human-in-the-Loop Operational Walkthrough" complete. Without cross-section navigation (H-1), audit visibility (H-2), simulation UI (H-3), and proper export selector (H-5), the operational walkthrough cannot be completed from the UI alone.
