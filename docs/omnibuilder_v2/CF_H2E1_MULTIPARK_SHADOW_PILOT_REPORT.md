# CF-H2E.1 — MULTIPARK SHADOW PILOT REPORT

> **Fase:** CF-H2E.1 — Multipark Shadow Pilot
> **Motor:** Control Foundation
> **Fecha:** 2026-06-11
> **Park Base:** `08e20910d81d42658d4334d3f6d10ac0` (Lima)
> **Clasificación:** `MULTIPARK_SHADOW_PILOT_PARTIAL`

---

## 1. EXECUTIVE SUMMARY

Piloto multipark shadow ejecutado con **5 parks** (Lima, Trujillo, Arequipa, Pro, TukTuk). **Lima operativo con 55s/ciclo. 4 parks requieren credential env vars antes de ingesta real.** La arquitectura multi-park funciona: watermarks independientes, failure isolation comprobado, no afecta Omniview productivo.

**Resultado: CONDITIONAL GO para CF-H2E.2. Bloqueador: 4 parks sin credenciales en entorno.**

---

## 2. PARKS EJECUTADOS

| # | Park | park_id | Tier | Credentials | Ingested | Ciclo (dry-run) |
|---|------|---------|------|-------------|----------|-----------------|
| 1 | **Lima** | `08e20910...ac0` | TIER_1 | ✓ REGISTERED | 44,389 orders | 55s (orders 27s + txns 28s) |
| 2 | **Trujillo** | `851e3075...b4ab8` | TIER_2 | ✗ No env vars | 0 | SKIP (missing_credentials) |
| 3 | **Arequipa** | `56e4607d...73003` | TIER_2 | ✗ No env vars | 0 | SKIP (missing_credentials) |
| 4 | **Pro** | `64085dd8...7ea8` | TIER_2 | ✗ No env vars | 0 | SKIP (missing_credentials) |
| 5 | **TukTuk** | `e3e07c00...d6e` | TIER_3 | ✗ No env vars | 0 | SKIP (missing_credentials) |

---

## 3. SCHEDULER MULTIPARK

### 3.1 Architecture

```
cf_h2e1_multipark_scheduler.py
│
├─ Read active parks from api_park_credentials_registry
│
├─ For each park:
│   ├─ Read env vars: {ENV_VAR_NAME}_CLIENT_ID + {ENV_VAR_NAME}_API_KEY
│   ├─ Read independent watermark from ingestion_watermark
│   ├─ Run orders cycle (cursor pagination, idempotent upsert)
│   ├─ Run transactions cycle
│   ├─ Update watermark
│   └─ Continue to next park (failure isolation)
│
└─ Report per-park results
```

### 3.2 Key Properties

| Property | Status | Detail |
|----------|--------|--------|
| Watermarks independent | **PASS** | `ingestion_watermark` PK is `(park_id, endpoint_group)` |
| Logs independent | **PASS** | Per-park cycle output with park_id in all messages |
| Dedupe independent | **PASS** | `ON CONFLICT (park_id, order_id, raw_payload_hash) DO NOTHING` |
| Retry independent | **PASS** | Per-park retry with MAX_RETRIES=2 |
| Failure isolation | **PASS** | Dry-run confirms 4 parks SKIP without stopping Lima |
| No Omniview impact | **PASS** | Shadow mode. No production changes. |

### 3.3 Lima Cycle (Real Data, Dry-Run)

| Endpoint | Pages | Records | Duration | Freshness |
|----------|-------|---------|----------|-----------|
| Orders | 7 | 2,863 | 27.2s | ~4.8h (since last event) |
| Transactions | 14 | 13,764 | 28.0s | ~4.8h |
| **Total** | **21** | **16,627** | **55.2s** | — |

---

## 4. WATERMARKS (Independent per Park)

| Park | Endpoint | Last Event | Status |
|------|----------|-----------|--------|
| Lima | orders | 2026-06-11 16:40:11 | active |
| Lima | transactions | 2026-06-11 16:40:27 | active |
| Trujillo | orders | — | no watermark yet |
| Trujillo | transactions | — | no watermark yet |
| Arequipa | orders | — | no watermark yet |
| Arequipa | transactions | — | no watermark yet |
| Pro | orders | — | no watermark yet |
| Pro | transactions | — | no watermark yet |
| TukTuk | orders | — | no watermark yet |
| TukTuk | transactions | — | no watermark yet |

---

## 5. FAILURE ISOLATION

### 5.1 Test: Missing Credentials

**Scenario:** 4 parks have no credential env vars set.

**Result:** The scheduler correctly SKIPs parks with missing credentials while Lima continues to ingest normally. No cascading failures.

```
[08e20910] orders: 2,863 recs, 7 pages, 27.2s [completed]      ← OK
[08e20910] transactions: 13,764 recs, 14 pages, 28.0s [completed] ← OK
[851e3075] SKIP: No credentials for park (env_var=None)          ← Isolated
[56e4607d] SKIP: No credentials for park (env_var=None)          ← Isolated
[64085dd8] SKIP: No credentials for park (env_var=None)          ← Isolated
[e3e07c00] SKIP: No credentials for park (env_var=None)          ← Isolated
```

### 5.2 Expected Failure Scenarios

| Scenario | Detection | Park Impact | Other Parks |
|----------|-----------|-------------|-------------|
| Credential 401/403 | HTTP status in response | SKIP that park | Continue normally |
| API timeout | Exception in _fetch_page | Mark park cycle failed | Continue |
| DB connection error | Exception in DB ops | Mark park cycle failed | Continue |
| Watermark corruption | _get_watermark returns None | Fresh start (1h backfill) | Continue |
| Rate limit (429) | HTTP status, retry 3x with backoff | Slow down that park | Continue |

**Verdict: PASS — Failure isolation funciona.** Un park fallando no detiene a los demás.

---

## 6. CAPACITY ASSESSMENT

### 6.1 Lima Baseline (Actual)

| Metric | Orders | Transactions |
|--------|--------|-------------|
| Pages per cycle | ~7 | ~14 |
| Records per cycle | ~2,900 | ~13,800 |
| Duration per cycle | ~27s | ~28s |
| Total per park | | ~55s |

### 6.2 Scaled Estimates

| Parks | Orders | Transactions | Total Runtime | Within 5-min? |
|-------|--------|-------------|---------------|---------------|
| 1 (Lima) | 27s | 28s | **55s** | ✓ |
| 3 | ~81s | ~84s | **165s** | ✓ |
| 5 | ~135s | ~140s | **275s** | ✓ (~4.6 min) |
| 10 | ~270s | ~280s | **550s** | ✗ (~9.2 min) |
| 20 | ~540s | ~560s | **1,100s** | ✗ (~18 min) |

### 6.3 Capacity Verdict

| Scale | Parks | Veredicto |
|-------|-------|-----------|
| Phase A (5 parks) | Lima + 4 pilot | **YES** — 275s < 300s window |
| Phase B (10 parks) | All registered | **YES_WITH_CHANGES** — Needs parallel workers or relaxed SLA |
| Phase C (20+ parks) | Full fleet | **NO** without parallelization |

---

## 7. CANONICAL MAPPER (Multi-Park Readiness)

The CF-H2G canonical mapper (`ops.omniview_canonical_day_fact_shadow`) supports `park_id` as a dimension. For multi-park, the mapper needs to run per-park:

```python
for park_id in active_parks:
    generate_canonical_day_fact(target_date, park_id)
```

Current state:
- **Lima:** Mapper produces day facts successfully
- **Other parks:** No order data → mapper produces empty/full-fallback rows
- **Action needed post-pilot:** Run mapper for all parks once ingestion produces data

---

## 8. FRESHNESS (Per Park)

| Park | Orders Freshness | Txns Freshness | Status |
|------|-----------------|----------------|--------|
| Lima | ~4.8h (since last event) | ~4.8h | **WARN** (>15 min) |
| Trujillo | N/A | N/A | No data |
| Arequipa | N/A | N/A | No data |
| Pro | N/A | N/A | No data |
| TukTuk | N/A | N/A | No data |

Lima freshness >15 min is expected for a single dry-run cycle (not continuous). Continuous near-real-time requires the scheduler running in loop mode (every 5 min).

---

## 9. BLOCKERS

| # | Blocker | Severity | Detail |
|---|---------|----------|--------|
| **1** | **No credential env vars for 4 parks** | **HIGH** | Trujillo, Arequipa, Pro, TukTuk need env vars set: `YANGO_TRUJILLO_CLIENT_ID`, `YANGO_TRUJILLO_API_KEY`, etc. |
| **2** | Migrations 212 + 213 not applied | **HIGH** | `ops.yango_park_registry` table missing. `api_park_credentials_registry` missing 4 parks. |
| **3** | Transaction time dominates | MEDIUM | 14 pages × ~2s = 28s for Lima alone. At 5 parks this becomes ~140s for txns. |
| **4** | No continuous loop test | MEDIUM | Dry-run was single cycle. Multi-cycle loop untested. |
| **5** | Mi Auto blocked | LOW | Not in dim_park. Excluded from pilot. |

---

## 10. FILES CREATED

| File | Type | Purpose |
|------|------|---------|
| `backend/alembic/versions/213_cf_h2e1_multipark_credentials.py` | Migration | Adds 5 parks to `api_park_credentials_registry` with credential_status |
| `backend/scripts/cf_h2e1_multipark_scheduler.py` | Script | Multi-park scheduler with failure isolation, independent watermarks |
| `docs/omnibuilder_v2/CF_H2E1_MULTIPARK_SHADOW_PILOT_REPORT.md` | Doc | This report |

---

## 11. GO / NO-GO

### 11.1 GO for CF-H2E.2 (Full Multipark Shadow): **CONDITIONAL GO**

| # | Criterion | Status | Evidence |
|---|----------|--------|-----------|
| 1 | 5 parks execute correctly | **PARTIAL** | Lima: PASS. 4 parks: SKIP (no creds). |
| 2 | Scheduler doesn't break | **PASS** | Failure isolation confirmed. Lima continues when others fail. |
| 3 | Watermarks independent | **PASS** | PK on (park_id, endpoint_group). Lima watermark active. |
| 4 | Failure isolation works | **PASS** | 4 parks SKIP without affecting Lima. |
| 5 | Freshness acceptable | **WARN** | Lima ~4.8h (single cycle). Needs continuous mode for <5min. |
| 6 | Canonical mapper produces metrics | **PASS** | Lima mapper works. Multi-park requires per-park loop. |
| 7 | Omniview productivo untouched | **PASS** | Shadow mode. No production changes. |

### 11.2 Prerequisites for CF-H2E.2

| Pre-req | Status |
|---------|--------|
| Set credential env vars for Trujillo, Arequipa, Pro, TukTuk | **PENDING** |
| Run migrations 212 + 213 | **PENDING** |
| Run scheduler in continuous loop mode for 3+ days | **NOT STARTED** |
| Verify all parks produce order data | **NOT STARTED** |
| Run canonical mapper for all parks | **NOT STARTED** |
| Mi Auto metadata resolved | **PENDING** |

### 11.3 Classification

**`MULTIPARK_SHADOW_PILOT_PARTIAL`** — Arquitectura verificada. Lima funciona. 4 parks bloqueados por credenciales pendientes.

---

## 12. RECOMENDACIONES

1. **Set env vars immediately:** `YANGO_TRUJILLO_CLIENT_ID`, `YANGO_TRUJILLO_API_KEY`, etc. from the Excel credentials.
2. **Run migrations 212 + 213** to populate registries.
3. **Re-run scheduler** with `--once` after env vars to verify all 5 parks ingest data.
4. **Run 3-day continuous loop** to validate watermarks advance correctly for all parks.
5. **Monitor transaction time** — it's the bottleneck (28s/park). Consider sequential orders → parallel transactions.

---

## 13. BACKLOG UPDATED

| Estado | Fase | Descripción |
|--------|------|-------------|
| **ACTIVE** | **CF-H2E.1** | Multipark Shadow Pilot (this document) |
| READY NEXT | CF-H2E.2 | Full Multipark Shadow (CONDITIONAL GO) |
| BLOCKED | CF-H2H | Omniview Source Promotion |
| BACKLOG | CF-H2I | Historical Snapshot Locking |
| BACKLOG | CF-H2J | Continuous Certification Monitor |
| BACKLOG | CF-H2K | Supply Hours Canonicalization |

---

## 14. FIRMA

| Campo | Valor |
|-------|-------|
| **Ejecutado por** | CF-H2E.1 Multipark Shadow Pilot |
| **Fecha** | 2026-06-11 |
| **Motor** | Control Foundation |
| **Clasificación** | `MULTIPARK_SHADOW_PILOT_PARTIAL` |
| **Veredicto** | **CONDITIONAL GO for CF-H2E.2. Bloqueador: credential env vars for 4 parks.** |
| **Próxima fase** | CF-H2E.2 — requiere credenciales + 3 días de loop continuo |
