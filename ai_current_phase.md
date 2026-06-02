# CURRENT ACTIVE PHASE — YEGO CONTROL TOWER

Last Updated: 2026-06-02

---

# CONTROL FOUNDATION — CLOSED

Motor:
Control Foundation

Phase:
1H.4 — Operational Maturity Governance Layer

Status:
**CLOSED** (2026-06-02)

Closure certification:
- CF-H1 Final Certification: PASS (CF_H1_FINAL_CERTIFICATION.md)
- CF-H1 Operational Refresh & Closure: PASS (this update)
- Canonical Registry: OMNIVIEW_CANONICAL_REGISTRY.md
- week_fact refreshed through S22 (2026-05-25)
- Freshness governance active (cross-validation breach on current intra-week S23 is expected temporal — governance refinement pending)
- Architecture: CERTIFIED | Serving: CERTIFIED | Lineage: CERTIFIED | Governance: CERTIFIED
- Tests: 23/24 PASS (1 known test gap: test_freshness_governance_returns_expected_keys lacks "breach" in expected set)
- Build: PASS (frontend 5.34s, Python compileall clean)

---

# ACTIVE PHASE

Motor:
**Diagnostic Engine**

Phase:
**2A.3 — Behavioral Pattern Diagnosis**

Status:
**ACTIVE** (unblocked 2026-06-02)

Goal:
Implementar diagnóstico de patrones conductuales de conductores usando serving facts gobernados. Clasificar drivers en segmentos conductuales determinísticos. Generar insights accionables sin AI.

---

# CURRENT PRIORITY

Current operational focus:

- Driver lifecycle diagnosis (behavioral patterns from activity facts)
- Deterministic driver classification (GROWING, DECLINING, AT_RISK, etc.)
- Behavioral benchmarking (TOP vs DECLINING cohorts)
- Recoverability scoring (0-100, 6-component deterministic)
- Periodic diagnostic runs (daily/weekly)

NOT building:
- nuevos motores (Forecast, Suggestion, Decision, Action, AI Copilot, Learning)
- AI Copilot
- speculative AI features
- Revenue Certification (separate track)
- Yego Lima Growth (separate phase)

---

# CURRENT PROBLEMS BEING SOLVED

1. Drivers without behavioral classification
2. No operational diagnosis of WHY drivers decline/churn
3. No recoverability scoring for intervention prioritization
4. No benchmark comparison between driver cohorts
5. Diagnostic Engine needs serving facts foundation (certified)

---

# ALLOWED CHANGES

- Driver behavioral pattern diagnosis
- Deterministic driver classification rules
- Recoverability intelligence service
- Behavioral benchmarking service
- Operational behavioral intelligence
- Diagnostic serving facts
- Diagnostic observability
- Driver lifecycle diagnostic hardening

---

# FORBIDDEN CHANGES

DO NOT:
- activate Forecast Engine
- activate Suggestion Engine
- activate Decision Engine
- activate Action Engine
- activate Learning Engine
- create AI automation loops
- mix Diagnostic with Forecast
- add speculative AI features
- re-enable heavy runtime fallback
- touch Revenue (separate certification track)
- touch Yego Lima Growth (separate phase)
- modify Omniview architecture
- break serving governance

---

# ARCHITECTURAL RULES

1. UI must read from serving facts
2. Runtime heavy calculations are forbidden for public UI
3. Facts must fully cover UI filters/grains
4. Every serving fact must have freshness + coverage metadata
5. Serving failures must fail gracefully
6. Control Foundation reliability > new features
7. Deterministic logic first — before any AI interpretation

---

# READY NEXT

Motor:
Revenue Detail Certification (CF-H2)

Phase:
Revenue Canonical Definition + Historical Logic Audit

Status:
READY NEXT (independent track — can proceed in parallel with Diagnostic)

Motor:
Diagnostic Engine sub-phase

Phase:
2A.4 — Behavioral Benchmarking Expansion

Status:
BACKLOG (after 2A.3 completion)

---

# BACKLOG MOTORS

3. Reachability Engine
4. Forecast Engine
5. Suggestion Engine
6. Decision Engine
7. Action Engine
8. AI Copilot
9. Learning Engine

---

# LAST MAJOR INCIDENT

Incident:
CF-H1: week_fact 43-day staleness (S18-S22 missing)

Root Cause:
Week_fact refresh had not been executed since commit c69a0f7 (SQL fix for revenue_yego_final column).

Resolution:
- Executed canonical incremental refresh: `refresh_omniview_real_slice_incremental --start-date 2026-05-01 --end-date 2026-06-01 --grain week`
- 3,074,016 raw trips materialized in 181s
- 112 rows inserted into week_fact
- All closed weeks S18-S22 populated (76K-177K trips each)
- Freshness governance breach resolved for closed weeks
- Current intra-week S23 shows expected temporal breach (serving ahead of canonical — governance refinement pending)

---

# SUCCESS CRITERIA TO OPEN DIAGNOSTIC ENGINE

- Serving Governance Foundation stabilized ✓
- week_fact reconciled through last closed week ✓
- Freshness monitoring active ✓
- Canonical Registry documented ✓
- No BLOCKED cross-validations on closed periods ✓
- Architecture certified ✓

# SUCCESS CRITERIA TO CLOSE DIAGNOSTIC ENGINE 2A.3

- Deterministic driver classification functional (all lifecycle states)
- Behavioral benchmarking producing valid TOP vs DECLINING comparisons
- Recoverability scoring calibrated (0-100)
- Diagnostic serving facts governed
- No runtime fallback in diagnostic endpoints
- Diagnostic observability active
- Driver behavioral diagnosis accuracy validated
