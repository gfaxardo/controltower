# OV2-B.0 — SOURCE TRANSITION DECISION: raw_yango Landing Layer

> **Fase:** OV2-B.0 — Source Transition Decision
> **Fecha:** 2026-06-05
> **Dependencia:** OV2-A.4 (Revenue API Certification)
> **Propósito:** Formalizar la decisión de crear la capa de landing `raw_yango` y definir el camino de transición hacia Omniview V2

---

## 1. CURRENT STATE

### 1.1 Canonical Sources (Omniview V1)

| Source | Schema | Role | Status |
|--------|--------|------|--------|
| `trips_2025` / `trips_2026` | `public` | Canonical trip source for Omniview V1 | **ACTIVE** — serving production UI |
| `ops.real_business_slice_day_fact` | `ops` | Canonical daily metrics (trips, drivers, revenue) | **ACTIVE** — primary serving fact |
| `ops.real_business_slice_month_fact` | `ops` | Canonical monthly roll-up | **ACTIVE** — serving + historical |
| `ops.real_business_slice_week_fact` | `ops` | Canonical weekly roll-up | **ACTIVE** — serving + projections |

### 1.2 Audit Sources (Certified, Not Canonical)

| Source | Schema | Role | Certification |
|--------|--------|------|---------------|
| Yango Fleet API (`partner_rides`) | External | Revenue audit source | `CERTIFIED_REVENUE_AUDIT` (OV2-A.4) |
| Yango Fleet API (`/v2/parks/transactions/list`) | External | Transaction feed for reconciliation | `FINANCIAL_CANDIDATE` (OV2-A.2) |

### 1.3 New Landing Layer (This Phase)

| Source | Schema | Role | Status |
|--------|--------|------|--------|
| `raw_yango.orders_raw` | `raw_yango` | Landing table for Yango Fleet API orders | **DESIGNED** — migration pending |
| `raw_yango.transactions_raw` | `raw_yango` | Landing table for Yango Fleet API transactions | **DESIGNED** — migration pending |
| `raw_yango.driver_profiles_raw` | `raw_yango` | Landing table for Yango Fleet API driver profiles | **DESIGNED** — migration pending |

---

## 2. TRANSITION PATH

```
Phase OV2-B.0 (NOW):       raw_yango landing tables
Phase OV2-B.1 (NEXT):      materialized views from raw_yango
Phase OV2-B.2 (LATER):     serving facts from MVs
Phase OV2-B.3 (FUTURE):    UI OV2 reads from serving
```

### Phase Detail

| Phase | Deliverable | Gate Condition |
|-------|-------------|----------------|
| **OV2-B.0** | `raw_yango` schema + 3 landing tables + ingestion CLI | Migration 181 applied, dry-run passes, coverage audit positive |
| **OV2-B.1** | `mv.yango_*` MVs: dedup + normalize raw_yango into daily fact grain | raw_yango coverage >= 95%, reconciliation delta <= 1% (sustained 7d) |
| **OV2-B.2** | `serving.yango_*` serving facts: pre-aggregated for UI consumption | MVs stable, backfill complete, performance tests pass |
| **OV2-B.3** | Omniview V2 UI reads from `serving.yango_*` (shadow mode first) | Serving facts validated, UI parity with V1 confirmed |

---

## 3. WHAT CHANGES AND WHAT DOESN'T

### 3.1 NOT MODIFIED

| Component | Action | Rationale |
|-----------|--------|-----------|
| `trips_2025` / `trips_2026` | **REMAIN** as historical/legacy fallback | Historical data; zero-risk to keep |
| `ops.real_business_slice_day_fact` | **NOT MODIFIED** | Continues serving Omniview V1 during transition |
| `ops.real_business_slice_month_fact` | **NOT MODIFIED** | Production fact; no disruption |
| `ops.real_business_slice_week_fact` | **NOT MODIFIED** | Production fact; no disruption |
| Omniview V1 UI | **NOT MODIFIED** | Zero-touch policy during OV2 build |
| Serving endpoints | **NOT MODIFIED** | No API changes; no UI impact |

### 3.2 ADDED

| Component | Action | Rationale |
|-----------|--------|-----------|
| `raw_yango` schema | **CREATED** via Migration 181 | New schema for Yango API landing data |
| `raw_yango.orders_raw` | **CREATED** | Landing table: 1 row per order × fetch |
| `raw_yango.transactions_raw` | **CREATED** | Landing table: 1 row per transaction × fetch |
| `raw_yango.driver_profiles_raw` | **CREATED** | Landing table: 1 row per driver profile × fetch |
| `ingest_yango_raw_landing.py` | **CREATED** | CLI script for safe ingestion (dry-run by default) |
| `audit_yango_raw_coverage.py` | **CREATED** | Coverage audit script |
| `reconcile_yango_raw_vs_ct.py` | **CREATED** | Reconciliation script: raw_yango vs CT day_fact |

### 3.3 ROLES REMAIN

| Role | Current Source | New Source | Decision |
|------|---------------|------------|----------|
| Revenue canonical | `revenue_yego_final` in CT | N/A (not yet) | CT remains canonical |
| Revenue audit | Yango Fleet API (`partner_rides`) | `raw_yango.transactions_raw` | API remains audit; raw_yango enables automated audit |
| Trip count canonical | `trips_completed` in CT | N/A (not yet) | CT remains canonical |
| Driver count canonical | `active_drivers` in CT | N/A (not yet) | CT remains canonical |

---

## 4. CONDITIONS FOR CANONICAL_READY

Before `raw_yango` can be promoted from `AUDIT_READY` to `CANONICAL_READY`, ALL of the following must be satisfied:

### 4.1 Coverage

- [ ] **raw_yango coverage >= 95%** of days per park (no gaps >2 consecutive days)
- [ ] **raw_yango tables populated with 30+ days** of data (sustained validation window)
- [ ] **All three endpoint groups** (orders, transactions, driver_profiles) ingested successfully

### 4.2 Reconciliation

- [ ] **Trips reconciliation delta <= 1%** (sustained for 7+ consecutive days)
- [ ] **Revenue reconciliation delta <= 3%** (sustained for 7+ consecutive days)
- [ ] **Daily reconciliation automated** (script runs via scheduler, results logged)

### 4.3 Backfill Strategy

- [ ] **Historical backfill strategy defined** (at minimum: from API cutover date)
- [ ] **Backfill window scope agreed** (how far back to backfill from API)
- [ ] **CT historical data remains as pre-cutover source** (no data loss)

### 4.4 Infrastructure

- [ ] **Credentials stable per park** (no rotation during validation period)
- [ ] **Rate limits sustainable** for daily refresh schedule
- [ ] **Schema version tracking active** — alert on API schema changes
- [ ] **`schema_version` column populated** in all raw_yango tables

### 4.5 Design Approval

- [ ] **Serving facts derivable from raw_yango MVs** (design approved)
- [ ] **MV layer design documented** (dedup, normalization, aggregation logic)
- [ ] **UI integration path defined** (shadow mode → cutover procedure)

---

## 5. RISK REGISTER

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| **API downtime** | HIGH | LOW | Keep CT canonical as fallback. raw_yango is additive, not replacement. Ingestion failures do not break serving. |
| **Schema changes** | MEDIUM | MEDIUM | `schema_version` column tracks API schema at ingestion time. Reconciliation script detects drift (delta spike → alert). |
| **Rate limit increase** | MEDIUM | LOW | Gradual ramp-up: start with 3 concurrent requests, increase to 5 only after 7 days of zero 429s. Monitoring via `ingestion_errors.csv`. |
| **Credential rotation** | LOW | LOW | Env var pattern: `YANGO_CLIENT_ID`, `YANGO_API_KEY` in `.env`. Registry update procedure documented. No hardcoded credentials. |
| **Data volume growth** | LOW | LOW | Pagination (cursor/offset) + incremental daily ingestion. Estimated: ~300-800 orders/day, 2-5x transactions. Partitioning designed (OV2-A.2 §4.6) for future scale. |
| **raw_yango / CT schema conflict** | LOW | LOW | Separate schema (`raw_yango`), separate naming. No overlap with existing `ops.*` or `staging.*` objects. |
| **Ingestion job failure mid-run** | MEDIUM | LOW | Checkpoint-based resume (`--resume` flag). Each page saved to checkpoint. Retry preserves progress. |
| **Dry-run bypass** | MEDIUM | LOW | `--confirm-live` required for real ingestion. Dry-run is default. `YANGO_API_ENABLED=false` forces dry-run. |

---

## 6. DECISION: GO for OV2-B.0

### 6.1 Decision

> **OV2-B.0 is APPROVED for execution.**
>
> Create the `raw_yango` landing tables via Migration 181. Deploy ingestion, audit, and reconciliation CLI scripts. Begin populating raw_yango with live API data.

### 6.2 Rationale

1. **Zero production risk.** `raw_yango` is a new schema with new tables. Nothing in Omniview V1 is touched. No serving facts are modified. No UI queries are changed.
2. **Safe-by-default ingestion.** The CLI script requires `--confirm-live` for real writes. All runs are dry-run unless explicitly confirmed. This matches the project's Control Foundation governance.
3. **Progressive validation.** Coverage audit and reconciliation scripts provide immediate feedback on data quality before any downstream consumption.
4. **Precedent from OV2-A.4.** Revenue API certification showed that `Partner fee for trip` correlates with CT revenue at <5% delta. Landing this data into raw_yango is the logical next step toward automated reconciliation.
5. **Reversible.** If raw_yango proves unreliable, the schema can be dropped with zero impact. CT remains the authoritative source.

### 6.3 Gate to OV2-B.1

Progress to OV2-B.1 (materialized views from raw_yango) when:

1. **Migration 181 applied successfully** — `raw_yango` schema and all 3 tables exist
2. **Dry-run ingestion works** for all endpoint groups (orders, transactions, driver_profiles)
3. **Coverage audit reports positive** — at least 1 day with >0 rows in all 3 tables
4. **At least 1 day of live data ingested successfully** — `--confirm-live` completes without errors
5. **Reconciliation script produces valid comparison** — raw_yango vs CT delta computed

---

## 7. GOVERNANCE CHECK

| Rule | Status | Evidence |
|------|--------|----------|
| No modifica Omniview V1 | ✅ PASS | New schema `raw_yango`; zero impact on `ops.*` or `public.*` |
| No modifica UI productiva | ✅ PASS | UI reads from `serving.*` only; raw_yango is RAW layer |
| No modifica serving actual | ✅ PASS | `serving.*` facts unchanged during OV2-B.0 |
| No se promueve a fuente canónica | ✅ PASS | raw_yango is `AUDIT_READY` only; canonical promotion requires OV2-B.3 gate |
| No carga masiva sin control | ✅ PASS | `--max-pages` limits API calls; `--max-concurrency` limits parallelism |
| No expone credenciales | ✅ PASS | CLI scripts mask credentials in all outputs (same pattern as probe scripts) |
| Read-only / Control Foundation | ✅ PASS | Ingestion writes to `raw_yango.*` only (new, isolated schema) |
| Safe-by-default | ✅ PASS | Dry-run is default; `--confirm-live` gate; `YANGO_API_ENABLED` guard |
| Idempotent ingestion | ✅ PASS | `ON CONFLICT DO NOTHING` on all inserts; checkpoint-based resume |
| Pipeline separation | ✅ PASS | RAW (`raw_yango`) → MV (future) → SERVING (future) → UI (future) |

---

## 8. IMPLEMENTATION ARTIFACTS

| Artifact | Path | Purpose |
|----------|------|---------|
| Migration 181 | `backend/migrations/versions/0181_raw_yango_landing.py` | Creates `raw_yango` schema + 3 tables |
| Ingestion CLI | `backend/scripts/ingest_yango_raw_landing.py` | Safe ingestion with dry-run default |
| Coverage Audit | `backend/scripts/audit_yango_raw_coverage.py` | Measures API/DB coverage by park and date |
| Reconciliation | `backend/scripts/reconcile_yango_raw_vs_ct.py` | Compares raw_yango against CT day_fact |
| This Decision | `docs/omnibuilder_v2/OV2_B0_SOURCE_TRANSITION_DECISION.md` | Formalizes transition decision |

---

## 9. FIRMA

| Campo | Valor |
|-------|-------|
| **Decisión tomada por** | OV2-B.0 Source Transition |
| **Fecha** | 2026-06-05 |
| **Estado** | `GO` — proceed with Migration 181 + ingestion scripts |
| **Próximo hito** | OV2-B.1 gate review (after 30+ days of raw_yango data) |
| **Dependencia** | OV2-A.4 Revenue API Certification (completed) |
| **Precede a** | OV2-B.1 Materialized Views from raw_yango |
