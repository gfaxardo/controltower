# OV2-D.0 — ROADMAP AFTER OV2-C CLOSURE

> **Date:** 2026-06-06
> **Motor:** Control Foundation / Roadmap

---

## 1. CURRENT ENGINE STATUS

| Engine | Status | Reason |
|--------|--------|--------|
| Control Foundation | **ACTIVE** | OV2-C complete. Slice Gov + PvR pending. |
| Diagnostic Engine | **PAUSED (READY NEXT)** | Awaiting Control Foundation GO with human QA |
| Reachability | BACKLOG | |
| Forecast | BLOCKED | Diagnostic not stable |
| Suggestion | BLOCKED | Forecast not built |
| Decision | BLOCKED | Suggestion not built |
| Action | BLOCKED | Decision not built |
| AI Copilot | BACKLOG | |
| Learning | BACKLOG | |

---

## 2. ACTIVE — Recommended

| Phase | Description | Priority |
|-------|-------------|----------|
| **OV2-D.0** | Human-in-the-loop UX QA with Gonzalo | P0 |
| **OV2-D.1** | Slice Governance Certification | P1 |
| **OV2-D.2** | Plan vs Real V2 in Omniview V2 | P1 |

---

## 3. READY NEXT

| Phase | Description | Condition |
|-------|-------------|-----------|
| OV2-D.3 | Multi-Park API Expansion | Credentials available |
| OV2-D.4 | Hourly Serving Activation | CT hour data or Yango hour MV |
| OV2-D.5 | Compare Mode UI | Wire `/compare` endpoint to frontend |

---

## 4. BACKLOG

| Phase | Description |
|-------|-------------|
| OV2-D.6 | Source Canonical Decision |
| OV2-D.7 | Production Shadow Deployment |
| OV2-D.8 | Diagnostic Engine 2A.3 (Behavioral Pattern Diagnosis) |
| OV2-E.x | Forecast Engine |

---

## 5. BLOCKERS

| Blocker | Blocks | Resolution |
|---------|--------|------------|
| Human QA not done | All further GO decisions | Gonzalo browser review |
| Yango < 30 days data | Canonical decision | Continue daily ingestion |
| Yango coverage < 99.5% | Canonical decision | Improve ingestion pipeline |
| Yango no slice mapping | Slice Governance | Implement OV2-D.1 |
| No multi-park credentials | Multi-Park expansion | Business provides credentials |
| CT hour_fact has 0 rows | Hourly serving (CT) | Data ingestion needed |
| No Yango hour MV | Hourly serving (Yango) | Migration needed |
| ai_operating_system.md rules | Forecast/Suggestion/Decision/Action | Previous engines must be stable |

---

## 6. GO/NO-GO CRITERIA

### GO for OV2-D.1 (Slice Governance):
- [ ] Human QA completed (OV2-D.0)
- [ ] CT slices verified operational
- [ ] Yango raw data verified available per order
- [ ] Slice mapping logic designed

### GO for OV2-D.2 (Plan vs Real):
- [ ] Slice Governance certified
- [ ] CT plan tables accessible
- [ ] CellContract extended for plan_value

### GO for Diagnostic Engine:
- [ ] Control Foundation fully closed with human QA GO
- [ ] Slice Governance certified
- [ ] Plan vs Real integrated
- [ ] 0 critical warnings on Shadow UI
- [ ] ai_current_phase.md updated
