# OV2-D.0 — PRODUCT READINESS MATRIX

> **Date:** 2026-06-06
> **Motor:** Control Foundation / Product Readiness
> **Status:** ASSESSMENT

---

## 1. READINESS BY AREA

| # | Area | Status | Blocker | Priority | Next Phase |
|---|------|--------|---------|----------|------------|
| 1 | Source Switching (CT ↔ Yango) | **READY** | — | HIGH | Done in OV2-C |
| 2 | Matrix UI (Shadow) | **READY** | — | HIGH | Done in OV2-C |
| 3 | CT day/week/month | **READY** | Hour grain has 0 rows | MEDIUM | OV2-D.1 |
| 4 | Yango day | **PARTIAL** | Single park only | MEDIUM | OV2-D.3 |
| 5 | Revenue Yango (Shadow) | **CERTIFIED** | Partial coverage (~21% of CT) | MEDIUM | OV2-D.3 |
| 6 | Slice Governance | **NOT CERTIFIED** | Yango has no slice mapping | **HIGH** | OV2-D.1 |
| 7 | Plan vs Real | **CT READY / YANGO BLOCKED** | Yango has no plan infrastructure | **HIGH** | OV2-D.2 |
| 8 | Multi-Park API | **NOT READY** | No credentials for other parks | WAITING | OV2-D.3 |
| 9 | Hourly Serving | **NOT READY (CT)** / **NOT READY (Yango)** | CT: 0 rows. Yango: no hour MV. | MEDIUM | OV2-D.4 |
| 10 | Human QA (browser) | **PENDING** | Needs Gonzalo manual review | **HIGH** | OV2-D.0 |
| 11 | Source Canonical Decision | **NOT READY** | Yango needs ≥30d, ≥99.5% coverage, delta <3% | DEFERRED | OV2-D.6 |
| 12 | Forecast Engine | **BLOCKED** | Per ai_operating_system.md — blocked until Control Foundation closed | BLOCKED | Not yet |
| 13 | Suggestion/Decision/Action | **BLOCKED** | Same as above — previous engines not stable | BLOCKED | Not yet |

---

## 2. DETAIL BY AREA

### 2.1 Source Switching — READY
| Aspect | Status |
|--------|--------|
| CT_TRIPS_2026 as default | Active |
| YANGO_API_RAW as shadow | Active |
| Source selector in UI | Active |
| canonical_ready explicit | Yes |
| Compare mode backend | Ready (endpoint exists) |
| Compare mode UI | Not yet wired |

### 2.2 Matrix UI — READY
| Aspect | Status |
|--------|--------|
| MatrixShell source-agnostic | Active |
| Visual system unified | Certified (OV2-C.2B) |
| All grains consistent | Day/week/month tested |
| Inspector | Active |
| Error/empty/loading states | All handled |
| Fallback | Disabled by default |

### 2.6 Slice Governance — NOT CERTIFIED
| Gap | Impact |
|-----|--------|
| Yango has no `business_slice_name` | Cannot compare CT slices vs Yango at slice level |
| CT slices: 6 (Auto regular, YMA, Tuk Tuk, PRO, Delivery, Carga) | Active |
| Yango: single "Lima Fleet" row | No slice breakdown |
| Slice mapping requires park→slice logic | Not implemented |

### 2.7 Plan vs Real — CT READY / YANGO BLOCKED
| Source | Plan Available? |
|--------|----------------|
| CT_TRIPS_2026 | Yes — `ops.plan_*` tables exist |
| YANGO_API_RAW | No — plan infrastructure is CT-native |

---

## 3. BLOCKERS BY PRIORITY

| Priority | Area | Blocker |
|----------|------|---------|
| **P0** | Human QA | Gonzalo needs to review Omniview V2 Shadow in browser |
| **P1** | Slice Governance | Yango has no slice mapping |
| **P1** | Plan vs Real | Yango blocked; CT integration needed in OV2 |
| **P2** | Multi-Park | No credentials for other parks |
| **P2** | Hourly Serving | CT hour_fact has 0 rows; Yango has no hour MV |
| **P3** | Source Canonical | Yango needs ≥30d data, ≥99.5% coverage |

---

## 4. WHAT MUST NOT BE DONE YET

Per `ai_operating_system.md`:

| Engine | Status | Reason |
|--------|--------|--------|
| Forecast | BLOCKED | Control Foundation not fully closed |
| Suggestion | BLOCKED | Previous engines not stable |
| Decision | BLOCKED | Previous engines not stable |
| Action | BLOCKED | Previous engines not stable |
| AI Copilot | BACKLOG | Deterministic first principle |
| Learning | BACKLOG | All previous engines must be stable |

---

## 5. READINESS SUMMARY

| Status | Count | Areas |
|--------|-------|-------|
| READY | 3 | Source Switching, Matrix UI, CT grains |
| PARTIAL | 2 | Yango day, Revenue Yango |
| NOT CERTIFIED | 2 | Slice Governance, Yango Plan vs Real |
| NOT READY | 3 | Multi-Park, Hourly Serving, Canonical Decision |
| PENDING | 1 | Human QA |
| BLOCKED | 4 | Forecast, Suggestion, Decision, Action |
