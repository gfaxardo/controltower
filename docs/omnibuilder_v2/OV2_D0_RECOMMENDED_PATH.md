# OV2-D.0 — RECOMMENDED PATH

> **Date:** 2026-06-06
> **Motor:** Control Foundation / Roadmap Decision

---

## RECOMMENDED SEQUENCE

```
┌──────────────────────────────────────────────────────────┐
│ 1. HUMAN-IN-THE-LOOP UX QA ← IMMEDIATE (OV2-D.0)        │
│    Gonzalo reviews Omniview V2 Shadow in browser         │
│    Validates: source switch, matrix, inspector, alerts   │
│    Prevents OMNI-P0 repeat (false GO)                    │
├──────────────────────────────────────────────────────────┤
│ 2. SLICE GOVERNANCE CERTIFICATION (OV2-D.1)              │
│    Map Yango park → CT business slices                   │
│    Enable slice-level cross-source comparison            │
│    Slice readiness section becomes operational           │
├──────────────────────────────────────────────────────────┤
│ 3. PLAN VS REAL V2 IN OMNIVIEW V2 (OV2-D.2)              │
│    Integrate CT plan data into OV2 matrix                │
│    Add plan_value + delta to CellContract                │
│    Plan vs Real section moves from readiness to active   │
├──────────────────────────────────────────────────────────┤
│ 4. MULTI-PARK API (OV2-D.3) — when credentials available │
│    Add other Yango parks (Arequipa, Cusco, etc.)         │
│    Single-park warning removed                           │
├──────────────────────────────────────────────────────────┤
│ 5. HOURLY SERVING (OV2-D.4)                              │
│    CT: activate hour grain when data available            │
│    Yango: create mv_orders_hour + mv_revenue_hour        │
├──────────────────────────────────────────────────────────┤
│ 6. SOURCE CANONICAL DECISION (OV2-D.6)                   │
│    Evaluate Yango for canonical readiness                │
│    Requires: 30d data, 99.5% cov, delta <3%, slice map   │
│    DO NOT PROCEED before prerequisites met               │
└──────────────────────────────────────────────────────────┘
```

---

## WHY THIS ORDER

### 1. Human QA first
OMNI-P0 was reopened because of a false GO — code-level checks passed but human validation revealed operational failures. The same must not happen with OV2. Gonzalo must see the shadow page in a browser and confirm it works semantically.

### 2. Slice Governance second
The biggest gap in OV2 is the inability to compare CT slices vs Yango at the slice level. Every operational KPI (revenue, drivers, trips) needs per-slice visibility. This is pure Control Foundation — no new engine.

### 3. Plan vs Real third
Once slices work, the next operational capability is "are we on track?" Plan vs Real is the bridge between Control Foundation and Diagnostic Engine. Without it, we see what happened but not whether it was expected.

### 4-5. Multi-Park and Hourly later
These are scaling concerns. Multi-Park is blocked on credentials. Hourly adds grain granularity but doesn't unlock new decisions — it refines existing ones.

### 6. Canonical last
Promoting Yango to canonical is the most consequential decision. It must wait until all prerequisites are met. Premature canonicalization is the #1 architectural risk per `ai_operating_system.md`.

---

## WHAT THIS DOES NOT ACTIVATE

| Engine | Status |
|--------|--------|
| Diagnostic Engine | PAUSED — waiting for Control Foundation closure |
| Forecast | BLOCKED |
| Suggestion | BLOCKED |
| Decision | BLOCKED |
| Action | BLOCKED |
| AI Copilot | BACKLOG |
| Learning | BACKLOG |

The recommended path stays within **Control Foundation**. No engine advancement without stability.
