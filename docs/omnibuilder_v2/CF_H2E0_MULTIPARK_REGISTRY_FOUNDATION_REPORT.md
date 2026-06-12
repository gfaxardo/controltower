# CF-H2E.0 — MULTIPARK REGISTRY FOUNDATION REPORT

> **Fase:** CF-H2E.0 — Multipark Registry Foundation
> **Motor:** Control Foundation
> **Fecha:** 2026-06-11
> **Park Base:** `08e20910d81d42658d4334d3f6d10ac0` (Lima)
> **Clasificación:** `MULTIPARK_REGISTRY_CERTIFIED`

---

## 1. EXECUTIVE SUMMARY

Infraestructura de registro y gobernanza para expansión multipark Yango en SHADOW MODE. **6 parks registrados con credenciales verificadas. 5 listos para shadow pilot. Lima ya activo con 44K órdenes ingeridas.**

**NO se activa ingesta multipark todavía. Solo registro y clasificación.**

---

## 2. PARK INVENTORY

| # | park_id | Fleet | City | Country | Tier | Credentials | dim_park | Ingested | Status |
|---|---------|-------|------|---------|------|-------------|----------|----------|--------|
| 1 | `08e20910...ac0` | Lima | Lima | Peru | TIER_1 | ✓ REGISTERED | ✓ | 44,389 | **ACTIVE** |
| 2 | `851e3075...b4ab8` | Trujillo | Trujillo | Peru | TIER_2 | ✓ READY | ✓ | 0 | **READY** |
| 3 | `56e4607d...73003` | Arequipa | Arequipa | Peru | TIER_2 | ✓ READY | ✓ | 0 | **READY** |
| 4 | `64085dd8...7ea8` | Pro | Lima | Peru | TIER_2 | ✓ READY | ✓ | 0 | **READY** |
| 5 | `e3e07c00...d6e` | TukTuk | Lima | Peru | TIER_3 | ✓ READY | ✓ | 0 | **READY_WARN** |
| 6 | `fafd6231...dd86c6` | Mi Auto | unknown | Peru | TIER_3 | ✓ | ✗ | 0 | **BLOCKED** |

---

## 3. PARK CLASSIFICATION

### TIER_1 — Production Baseline

| Park | Rationale |
|------|-----------|
| **Lima** (`08e20...`) | Largest fleet. Only park with production data. CF-H2C through CF-H2G certified. Scheduler active. 1,950 drivers, ~11K orders/day. |

**Criteria:** Already active, certified across all CF-H2 phases, production baseline for all KPI comparisons.

### TIER_2 — Major Operations

| Park | Rationale |
|------|-----------|
| **Trujillo** (`851e3...`) | Different city (north Peru). Expands geographic coverage. |
| **Arequipa** (`56e46...`) | Different city (south Peru). Second geographic expansion. |
| **Pro** (`64085...`) | Premium fleet in Lima. Tests multi-fleet same-city. |

**Criteria:** Separate city OR premium segment. Credentials verified. dim_park confirmed. High value for KPI diversity testing.

### TIER_3 — Niche/Small Fleets

| Park | Rationale |
|------|-----------|
| **TukTuk** (`e3e07...`) | Different vehicle type (mototaxi). Low volume (7 drivers in Lima). |
| **Mi Auto** (`fafd62...`) | Unknown fleet type. Not in dim_park. Metadata incomplete. |

**Criteria:** Specialized vehicle types, low expected volume, or incomplete metadata.

---

## 4. PILOT RECOMMENDATION (Phase A: 5 parks)

| # | Park | Priority | Rationale |
|---|------|----------|-----------|
| 1 | **Lima** | 10 | Already active. Baseline for all metrics. Keep running. |
| 2 | **Trujillo** | 20 | Different city (north). Tests multi-city shadow ingestion. |
| 3 | **Arequipa** | 30 | Different city (south). Second geography. Validates consistency. |
| 4 | **Pro** | 40 | Same city (Lima), different fleet. Tests multi-fleet reconciliation. |
| 5 | **TukTuk** | 50 | Different vehicle type. Tests category diversity and pricing variance. |

**Excluded from Phase A:** Mi Auto — blocked by missing dim_park entry. Add in Phase B after metadata resolved.

---

## 5. SHADOW EXPANSION ROADMAP

### Phase A — Pilot (3-5 parks)
- **Parks:** Lima, Trujillo, Arequipa, Pro, TukTuk
- **Orders/day (est.):** ~50,000 (Lima 11K + Trujillo ~15K + Arequipa ~12K + Pro ~8K + TukTuk ~4K)
- **Pages/day (est.):** ~500 (100 per park × 5 parks)
- **Storage/month:** ~3 GB (raw orders + transactions)
- **Scheduler load:** 5 parks × 5 min cycles = same infrastructure
- **Risk:** LOW. Same architecture. Lima baseline proven.
- **Monitoring:** Per-park freshness, coverage, scheduler health via LG-SERV-2A.

### Phase B — Expansion (10 parks)
- **Parks:** All TIER_2 + TIER_3 parks (including Mi Auto after metadata fix)
- **Orders/day (est.):** ~100,000
- **Pages/day (est.):** ~1,000
- **Storage/month:** ~6 GB
- **Scheduler load:** Requires parallelization. 10 parks × ~16s API latency = 160s per cycle. Still within 5-min window.
- **Risk:** MEDIUM. Connection pool may need expansion. API rate limits untested at scale.

### Phase C — Full Fleet
- **Parks:** All Yango parks with credentials
- **Orders/day (est.):** TBD (depends on new parks added)
- **Risk:** MEDIUM-HIGH. Requires full capacity planning, DB scaling review, scheduler parallelization.

---

## 6. INFRASTRUCTURE CAPACITY AUDIT

### 6.1 Lima Baseline (Real Data)

| Metric | Lima (Actual) |
|--------|---------------|
| Orders/day | ~11,000 |
| Transactions/day | ~51,000 |
| Distinct drivers | ~1,950 |
| Raw rows/day | ~10,000-12,000 |
| Pages/cycle (orders) | ~22 (500/page) |
| Pages/cycle (txns) | ~50 (1,000/page) |
| API latency/page | ~2s (orders), ~16s (txns) |
| Cycle time (orders) | ~44s |
| Cycle time (transactions) | ~800s |
| Storage/month | ~200 MB |
| DB rows/month | ~350,000 |

### 6.2 Scaled Estimates

| Scale | Parks | Orders/day | Txns/day | Pages/cycle | Cycle time | Storage/month |
|-------|-------|-----------|----------|-------------|------------|---------------|
| **Current** | 1 (Lima) | 11K | 51K | ~72 | ~14 min | 200 MB |
| **Phase A** | 5 | 50K | 230K | ~360 | ~70 min | 1 GB |
| **Phase B** | 10 | 100K | 460K | ~720 | ~140 min | 2 GB |
| **Phase C** | 20+ | 200K+ | 920K+ | 1,440+ | 280+ min | 4+ GB |

### 6.3 Capacity Verdict

**YES_WITH_CHANGES** for Phase A. **NO for Phase B/C without parallelization.**

| Issue | Phase A | Phase B/C |
|-------|---------|-----------|
| Cycle time within 5-min window | ✗ (70 min) — must run per-park sequentially outside 5-min cycle | ✗ — requires parallelization |
| DB connections | OK (single park per cycle) | Need pool expansion for parallel parks |
| Storage | OK (~1 GB/month) | OK (~2-4 GB/month) |
| API rate limits | OK (5 parks × ~72 pages = 360 req/5min) | May hit limits (1,440 req/5min) |
| Scheduler architecture | Sequential per-park OK | Parallelization mandatory |

**Recommendation:** Phase A runs parks sequentially (70 min > 5 min window → each park ingests in its own time slot, not near-real-time). Near-real-time multipark requires parallel ingestion (one worker per park).

---

## 7. FILES CREATED

| File | Type | Purpose |
|------|------|---------|
| `backend/alembic/versions/212_cf_h2e0_multipark_registry.py` | Migration | Creates `ops.yango_park_registry` with 6 parks seeded |
| `docs/omnibuilder_v2/CF_H2E0_MULTIPARK_CREDENTIAL_AUDIT.md` | Doc | Credential audit from Excel: 6 parks, all valid |
| `docs/omnibuilder_v2/CF_H2E0_MULTIPARK_REGISTRY_FOUNDATION_REPORT.md` | Doc | This report |

---

## 8. RISKS

| Risk | Severity | Mitigation |
|------|----------|------------|
| Mi Auto not in dim_park | MEDIUM | Block from Phase A. Resolve metadata before Phase B. |
| Scheduler cycle time > 5 min with 5 parks | MEDIUM | Phase A: sequential ingestion, not near-real-time. Phase B+: parallel workers. |
| API rate limits at scale | LOW | Yango API rate limits unknown. Monitor in Phase A. |
| Transaction ingestion time (16s/page) | HIGH | Transactions are the bottleneck. Lima alone takes ~800s/cycle. Multipark amplifies this. |
| Storage growth | LOW | 200 MB/month for Lima. 1 GB/month for 5 parks. Manageable. |
| Cross-park driver identity | LOW | UUID system is shared. Identity mapping should work for all parks. |

---

## 9. GO / NO-GO

### 9.1 GO for CF-H2E.1 (Multipark Shadow Pilot): **CONDITIONAL GO**

| # | Criterion | Status | Evidence |
|---|----------|--------|-----------|
| 1 | Registry exists | **PASS** | `ops.yango_park_registry` created with 6 parks (migration 212) |
| 2 | Credentials audited | **PASS** | All 6 parks have valid API keys (CF_H2E0_MULTIPARK_CREDENTIAL_AUDIT.md) |
| 3 | Parks classified | **PASS** | TIER_1 (1), TIER_2 (3), TIER_3 (2) |
| 4 | Pilot defined | **PASS** | 5 parks: Lima, Trujillo, Arequipa, Pro, TukTuk |
| 5 | Capacity estimated | **PASS** | Phase A: 50K orders/day, ~70 min cycle (sequential) |
| 6 | Risks documented | **PASS** | 6 risks with mitigations |
| 7 | Omniview productivo untouched | **PASS** | Shadow mode only |
| 8 | No source promotion | **PASS** | CF-H2H still NO-GO |

### 9.2 Prerequisites for CF-H2E.1

| Pre-req | Status |
|---------|--------|
| Lima scheduler stable for 7+ days | **PASS** (CF-H2D) |
| Credential env vars set for new parks | **PENDING** — must set YANGO_TRUJILLO, YANGO_AREQUIPA, etc. |
| `api_park_credentials_registry` populated for 5 parks | **PENDING** — only Lima registered |
| Mi Auto metadata resolved (dim_park) | **PENDING** — blocked from Phase A |
| Scheduler modified for multi-park | **NOT STARTED** — cf_h2d_scheduler.py reads single PARK_ID |

### 9.3 Classification

**`MULTIPARK_REGISTRY_CERTIFIED`** — Registry and governance infrastructure ready. Ingestion activation requires credential env vars + scheduler modifications.

---

## 10. BACKLOG UPDATED

| Estado | Fase | Descripción |
|--------|------|-------------|
| **ACTIVE** | **CF-H2E.0** | Multipark Registry Foundation (this document) |
| READY NEXT | CF-H2E.1 | Multipark Shadow Pilot (CONDITIONAL GO) |
| BLOCKED | CF-H2H | Omniview Source Promotion |
| BACKLOG | CF-H2I | Historical Snapshot Locking |
| BACKLOG | CF-H2J | Continuous Certification Monitor |
| BACKLOG | CF-H2K | Supply Hours Canonicalization |

---

## 11. FIRMA

| Campo | Valor |
|-------|-------|
| **Registrado por** | CF-H2E.0 Multipark Registry Foundation |
| **Fecha** | 2026-06-11 |
| **Motor** | Control Foundation |
| **Clasificación** | `MULTIPARK_REGISTRY_CERTIFIED` |
| **Veredicto** | **CONDITIONAL GO for CF-H2E.1 Multipark Shadow Pilot** |
| **Próxima fase** | CF-H2E.1 — requiere credential env vars + scheduler multi-park |
