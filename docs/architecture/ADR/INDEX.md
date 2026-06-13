# Architecture Decision Records (ADR)

**Status:** DIRECTORY CREATED — No ADRs registered yet

---

## Purpose

This directory stores Architecture Decision Records (ADRs) for YEGO Control Tower. ADRs document significant architectural decisions, their context, consequences, and alternatives considered.

## Format

Each ADR follows the standard format:
- **Title:** Short noun phrase
- **Status:** Proposed | Accepted | Deprecated | Superseded
- **Context:** What is the issue?
- **Decision:** What was decided?
- **Consequences:** What becomes easier/harder?

## Existing Decisions (documented elsewhere)

The following architectural decisions are documented in existing architecture files but have not been extracted as standalone ADRs:

| Decision | Documented In | Date |
|----------|--------------|------|
| Engine-based architecture (9 motors) | `ARCHITECTURE_CANONICAL_ROADMAP.md` | 2026-05-15 |
| Control → Diagnostic → Forecast dependency chain | `ENGINE_BOUNDARIES.md` | 2026-05-15 |
| Serving-first architecture (RAW → MV → SERVING → UI) | `ai_operating_system.md` | — |
| Omniview as REAL ONLY (Plan separated) | `CONTROL_FOUNDATION_LIVING_ARCHITECTURE.md` | — |
| Hourly-first LOB chain | `CONTROL_FOUNDATION_LIVING_ARCHITECTURE.md` | — |
| Legacy phase nomenclature freeze | `LEGACY_PHASE_TRANSLATION_MAP.md` | 2026-05-15 |
| Lima Growth Daily Action List Reset | `CONTROL_LOOP_FOUNDATION.md` | — |
| State-Based Loyalty Architecture | `STATE_BASED_LOYALTY_ARCHITECTURE.md` | — |
| Vs Proy as single canonical operational view | `ai_current_phase.md` | 2026-06-03 |

## Future ADRs

ADRs should be created for any significant architectural decision going forward. See `ROADMAP_GOVERNANCE_RULES.md` for the feature declaration template that feeds into ADR creation.
