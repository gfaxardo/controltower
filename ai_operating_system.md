# YEGO CONTROL TOWER — AI OPERATING SYSTEM

## PURPOSE

This AI is operating inside a mission-critical operational intelligence system.

The objective is NOT merely writing code.

The objective is:

- protect architecture
- preserve data integrity
- avoid operational debt
- maintain deterministic behavior
- improve decision capability
- evolve the system safely by phases

This system is NOT a generic dashboard.

It is an evolving Operational Intelligence System.

---

# CORE RULE

THE AI MUST NEVER:

- improvise architecture
- create hidden technical debt
- mix responsibilities between layers
- create unnecessary abstractions
- refactor unrelated code
- invent business logic
- invent database columns
- create fake data
- bypass contracts
- break existing endpoints
- modify unrelated files
- change naming conventions
- create parallel logic
- introduce AI logic where deterministic logic should exist first

---

# SYSTEM EVOLUTION MODEL

The system evolves ONLY in this order:

1. CONTROL
2. DIAGNOSTIC
3. FORECAST
4. SUGGESTION
5. DECISION
6. EXECUTION
7. LEARNING

The AI MUST respect this maturity model.

NEVER implement future-stage logic inside previous stages.

Example:
- NO recommendation engines during CONTROL phase
- NO autonomous actions during DIAGNOSTIC phase
- NO AI predictions without reliable historical foundation

---

# ARCHITECTURE PRINCIPLE

Each engine is independent.

The AI MUST NOT mix responsibilities.

Current/future engines:

- Control Foundation
- Diagnostic Engine
- Reachability Engine
- Forecast Engine
- Suggestion Engine
- Decision Engine
- Action Engine
- Learning Engine

Every implementation must clearly belong to ONE layer.

---

# CURRENT PRIORITY

Current priority is:

RELIABILITY > FEATURES

The AI must prioritize:

1. consistency
2. traceability
3. auditability
4. deterministic logic
5. performance
6. scalability
7. UX improvements
8. AI enhancements

Never invert this order.

---

# NON-NEGOTIABLE RULES

## DATA

- Never invent columns
- Never assume schemas
- Always inspect real schema first
- Never fake joins
- Never fabricate metrics
- Never estimate missing data silently
- Null is better than fake data

## PLAN VS REAL

- Plan and Real are separate truths
- Never merge incorrectly
- Deltas only exist when comparison is valid
- Respect comparison_status rules

## DATABASE

- Avoid destructive migrations
- Prefer additive changes
- Never drop tables unless explicitly requested
- Never rewrite historical data silently

## FRONTEND

- Do not break existing UX
- Do not introduce incompatible API contracts
- Preserve existing filters and drilldowns
- Preserve backward compatibility whenever possible

## PERFORMANCE

- Avoid scanning raw tables repeatedly
- Prefer materialized views when available
- Avoid N+1 patterns
- Avoid unnecessary frontend recalculations

---

# IMPLEMENTATION DISCIPLINE

Before coding, the AI MUST determine:

1. Which phase does this belong to?
2. Is previous phase mature enough?
3. Is this additive?
4. Does this break architecture?
5. Does this introduce debt?
6. Is deterministic logic enough?
7. Is AI actually necessary?
8. Does this create operational value?

If uncertain:
STOP AND ASK.

---

# FILE MODIFICATION RULES

The AI MUST:

- modify the minimum number of files possible
- avoid unnecessary refactors
- preserve naming conventions
- preserve endpoint contracts
- avoid massive rewrites unless explicitly requested

---

# ENDPOINT RULES

When modifying APIs:

- preserve existing response structure
- preserve existing query params
- avoid breaking frontend consumers
- update schemas consistently
- update frontend client if necessary

---

# SQL RULES

- SQL must be auditable
- Explicit joins preferred
- Avoid hidden logic
- Avoid ambiguous aliases
- Never use SELECT *
- Prefer deterministic aggregations
- Respect grain consistency

---

# OBSERVABILITY RULES

Every major implementation should provide:

- logs
- validation
- explainability
- QA evidence
- deterministic outputs

---

# PHASE DISCIPLINE

The AI MUST NOT open multiple strategic phases simultaneously.

Allowed:
- 1 ACTIVE phase
- 1 READY NEXT phase

Everything else remains backlog.

---

# EXECUTION STYLE

The AI should work incrementally:

1. inspect existing implementation
2. identify constraints
3. propose minimal safe change
4. implement
5. validate
6. provide evidence
7. stop

Do NOT continue expanding scope automatically.

---

# REQUIRED RESPONSE FORMAT

For significant implementations, the AI should respond using:

1. Objective
2. Files impacted
3. Risks
4. Implementation plan
5. Validation plan
6. GO / NO-GO assessment

---

# WHEN THE AI SHOULD STOP

The AI MUST stop and ask before continuing if:

- architecture is unclear
- schemas are inconsistent
- business logic conflicts exist
- multiple valid interpretations exist
- implementation may break compatibility
- phase maturity is insufficient

---

# ABSOLUTE PRIORITY

This system is operationally critical.

Correctness is more important than speed.

Traceability is more important than cleverness.

Deterministic logic is more important than AI sophistication.

Reliability is more important than feature quantity.