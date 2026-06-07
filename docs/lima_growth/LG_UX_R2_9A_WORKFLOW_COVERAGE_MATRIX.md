# LG-UX-R2.9A — Workflow Coverage Matrix

**Date:** 2026-06-06
**Phase:** LG-UX-R2.9A Workflow Audit

---

## WORKFLOW COVERAGE BY SECTION

| Step | Visible | Clickable | Explainable | Actionable | Missing |
|------|:---:|:---:|:---:|:---:|------|
| **1. Today's Action Plan** | YES | NO | PARTIAL | NO | No drilldown links. Cannot click actions to navigate. Must manually switch tabs. |
| **2. Programs & State** | YES | NO | PARTIAL | NO | No CTA for programs. Program Builder blocked. No click-through to program details. |
| **3. Driver State** | YES | NO | NO | NO | Fully read-only. No freshness badge. No drilldown into lifecycle groups. No explainability. |
| **4. Capacity Config** | YES | PARTIAL | NO | PARTIAL | Editable capacity table (YES). Policy editing via API only. No simulation UI. No explainability tooltips. |
| **5. Execution Queue** | YES | YES | NO | YES | Build + Export buttons functional. No pagination (50 limit). Hardcoded exports to CHURN_PREVENTION. |
| **6. Build Queue** | YES | YES | NO | YES | Button functional. No preview/dry-run before build. No build config options. |
| **7. Build Result** | YES | NO | NO | NO | Shows policy info. Transient (disappears on navigation). No persistent build history UI. |
| **8. Export** | YES | YES | NO | YES | Button functional. No program selection. Limit cap at 50. No campaign name customization. |
| **9. Audit** | NO | NO | NO | NO | **COMPLETELY MISSING.** Backend has audit data but zero frontend representation. |
| **10. LoopControl Config** | YES | NO | NO | NO | Read-only. No way to test connection, update config, or see remediation for missing config. |

---

## WORKFLOW FLOW AUDIT

### Flow A: See status → Understand → Act → Verify

| Step | Where |
|------|-------|
| See status | Today's Action Plan (what's happening today) |
| Understand why | Recommended actions show "Porque" + blockers show remediation |
| Act | Must navigate to Execution Queue manually (no link from Action Plan) |
| Verify result | Build result / export feedback in Queue section |

**Gap:** No hyperlink or CTA from Action Plan to Queue. User must know to switch tabs.

### Flow B: Edit config → Simulate → Apply

| Step | Where |
|------|-------|
| Edit | Capacity Config (editable table) |
| Simulate | API only (`POST /simulate`). No UI simulation button. |
| Apply | Guardar button in Config. Policy activation via API only. |

**Gap:** No simulation preview in UI. Policy editing/activation is API-only.

### Flow C: Detect blocker → Resolve

| Step | Where |
|------|-------|
| Detect | Today's Action Plan shows blockers. Queue shows hold reasons. |
| Understand | Remediation text shown ("Aumentar capacidad en Configuracion") |
| Resolve | No one-click resolution. User must navigate to Config tab. |

**Gap:** No "Fix this" button linking blockers to resolution screens.

---

## EXPLAINABILITY COVERAGE

| Section | Tooltips | Info Icons | Reasons | Remediation |
|---------|:---:|:---:|:---:|:---:|
| Today's Action Plan | NO | NO | YES (text) | YES |
| Programs & State | YES | YES | PARTIAL | YES |
| Driver State | NO | NO | NO | NO |
| Capacity Config | NO | NO | PARTIAL | YES (trace) |
| Execution Queue | NO | NO | PARTIAL | YES |
| LoopControl Config | NO | NO | NO | NO |
| Audit | N/A | N/A | N/A | N/A |

---

## STATE COVERAGE AUDIT

| State | Today's Action Plan | Programs | Queue | Config |
|-------|:---:|:---:|:---:|:---:|
| Loading | YES | YES | YES | YES |
| Error | YES | YES | YES | NO (silent) |
| Empty | YES (QUEUE_NOT_BUILT) | NO | YES (NOT_BUILT) | NO |
| All-exhausted | YES (ALL_EXPORTED) | NO | NO | NO |
| No-policy | YES (fallback banner) | NO | NO | YES (policy panel) |
| Stale data | YES (freshness) | YES | YES | PARTIAL |

---

## KEY MISSING ITEMS

| # | Item | Severity |
|---|------|:---:|
| W-1 | No hyperlinks between Action Plan and Queue | HIGH |
| W-2 | No simulation preview in UI | HIGH |
| W-3 | Audit section completely missing from frontend | HIGH |
| W-4 | No drilldown from Driver State into driver groups | MEDIUM |
| W-5 | Export hardcoded to CHURN_PREVENTION in hook | MEDIUM |
| W-6 | No program-level CTAs (no edit, no disable) | MEDIUM |
| W-7 | Build result transient (disappears on navigation) | MEDIUM |
| W-8 | LoopControl config read-only (no test/save UI) | LOW |
| W-9 | No pagination on queue records (50 limit) | LOW |
| W-10 | No freshness badge on Driver State | LOW |
