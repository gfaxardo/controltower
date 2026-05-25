# DIAGNOSTIC EXPLANATION PRECHECK

**Date**: 2026-05-25
**Phase**: UX Hardening Stage 5

---

## ACTIVE PHASE

**Phase**: 1H.4 — Operational Maturity Governance Layer
**Motor**: Control Foundation
**Status**: ACTIVE

## READY NEXT

**Phase**: 2A.3 — Behavioral Pattern Diagnosis
**Motor**: Diagnostic Engine
**Status**: READY NEXT (NOT ACTIVE)

---

## WHY THIS TASK BELONGS TO DIAGNOSTIC ENGINE (TEMPRANO)

Diagnostic Engine se define como el motor que **explica el estado operacional sin recomendar acciones**.

Este Stage 5 implementa exactamente eso:
- Explicar por qué una señal es critical/blocked/elevated
- Decomponer la causalidad operacional
- Identificar el factor dominante

NO implementa:
- Reachability (¿adónde podemos llegar?)
- Forecast (¿adónde llegaremos?)
- Suggestion (¿qué deberías hacer?)
- Decision (¿qué acción tomar?)

---

## MOTORS PERMITTED

- Control Foundation (ACTIVE)
- Diagnostic Engine early (explicación determinística)

## MOTORS BLOCKED

- Reachability Engine (backlog)
- Forecast Engine (prototype only)
- Suggestion Engine (backlog)
- Decision Engine (backlog)
- Action Engine (backlog)
- AI Copilot (backlog)

---

## RISKS

| Risk | Mitigation |
|------|-----------|
| Explanation crosses into recommendation | Strict text policy: "why", never "what to do" |
| Too many diagnostic factors shown at once | Dominant factor rule: show 1 primary + max 2 secondary |
| Explanatory text too verbose | Compact format: "X due to Y" |
| Overlap with MatrixExecutiveBanner (already has explanations) | Weekly/Loyalty focus, Matrix explanation already exists |
| Runtime overhead from explanation computation | Pure functions, memoized, O(1) field reads |

---

## GO / NO-GO

**VERDICT: GO**

- Aligned with Diagnostic Engine early
- No blocked motors
- Deterministic (reads existing signals)
- Aditivo (no modifica nada existente)
- Reversible (pure frontend layer)
- No IA, no recommendations, no new endpoints
