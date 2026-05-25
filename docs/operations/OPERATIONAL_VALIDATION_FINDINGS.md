# OPERATIONAL VALIDATION — CONSOLIDATED FINDINGS

**Date**: 2025-05-25
**Status**: FRAMEWORK COMPLETE — awaiting operational sessions

---

## 1. WHAT WE KNOW (pre-validation, from architecture)

### System Strengths
1. **Momentum + Plan coexist cleanly** — two cognitive layers (trend vs target) in one cell
2. **Deterministic everywhere** — 100% traceable classifications, no black boxes
3. **Release ready** — build passes, no regressions, matrix intact
4. **Honest MVP** — signal gaps documented, no invented metrics
5. **Single path** — `/operacion/omniview-matrix` is the only active Omniview route

### System Weaknesses (pre-validation)
1. **5 of 12 behavioral dimensions blocked** — missing fact table columns
2. **No holiday/special-day awareness** — DoD comparisons may show false declines
3. **Two color systems** — momentum (green/red) vs attainment (green/amber/red) may confuse
4. **Behavioral MVP not integrated** — standalone panel, not wired to Omniview
5. **No usage analytics** — we don't know what operators use

---

## 2. WHAT OPERATIONAL SESSIONS WILL REVEAL

| Unknown | How we'll learn |
|---|---|
| Do operators understand DoD/WoW/MoM? | Session log, first-scan test |
| Is priority strip useful or noise? | Track what operators click first |
| Do operators drill down? | Click count test |
| Is attainment useful alongside momentum? | Ask "which number matters more?" |
| Does behavioral classification match reality? | Compare vs operator manual flags |
| Is cognitive load too high? | Load scale 1-5 per session |
| What ONE signal is most missed? | Direct operator question |

---

## 3. DECISION FRAMEWORK AFTER VALIDATION

### If validation PASSES (GO for next engine):
- Operators use the system daily
- > 70% of critical alerts trigger actions
- Cognitive load ≤ 2
- < 20% false positives
- Operators can articulate what the system tells them

### If validation is CONDITIONAL GO:
- System is useful but needs specific fixes
- 1-2 features are confusing or unused
- Some false positives need threshold adjustment
- Proceed but fix identified issues first

### If validation is NO-GO:
- > 40% alerts dismissed as noise
- Cognitive load ≥ 4
- Operators prefer old tools
- STOP — fix fundamentals before adding more

---

## 4. PLACEHOLDER: Session Results

_This section will be filled after operational sessions._

### Session 1
- Date: _
- Operator: _
- Cognitive load: _/5
- Top friction: _
- Most useful feature: _
- Action taken: _

### Session 2
- Date: _
- Operator: _
- Cognitive load: _/5
- Top friction: _
- Most useful feature: _
- Action taken: _

### Session 3
- Date: _
- Operator: _
- Cognitive load: _/5
- Top friction: _
- Most useful feature: _
- Action taken: _

---

## 5. RECOMMENDATIONS (preliminary, subject to validation)

1. **Integrate Behavioral MVP into Omniview** — standalone panel limits adoption
2. **Add `online_hours` to fact table** — highest priority missing signal
3. **Add holiday calendar awareness** — reduces false positives for DoD comparisons
4. **Consolidate color language** — momentum green/red should be the primary visual anchor
5. **Measure before building more** — no new features until usage data exists
