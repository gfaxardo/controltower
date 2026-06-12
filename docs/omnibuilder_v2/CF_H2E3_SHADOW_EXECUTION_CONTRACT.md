# CF-H2E.3 — SHADOW EXECUTION CONTRACT

> **Fase:** CF-H2E.3 — Continuous Multipark Shadow
> **Sub-document:** Execution Contract
> **Fecha:** 2026-06-12

---

## 1. SCHEDULER FREQUENCY

| Park Tier | Frequency | Rationale |
|-----------|-----------|-----------|
| TIER_1 (Lima) | Every 5 min | Production baseline. Highest volume. |
| TIER_2 (Trujillo, Arequipa, Pro) | Every 15 min | Moderate volume. 15 min acceptable for shadow. |
| TIER_3 (TukTuk) | Every 30 min | Low volume. 30 min sufficient. |

---

## 2. RETRY POLICY

| Condition | Retries | Backoff | After Max |
|-----------|---------|---------|-----------|
| HTTP 429 (rate limit) | 3 | 3s, 9s, 27s | Mark cycle as "rate_limited" |
| HTTP 5xx (server error) | 2 | 2s, 4s | Mark cycle as "failed" |
| Timeout (>60s) | 1 | 5s | Mark cycle as "timeout" |
| Connection error | 1 | 2s | Mark cycle as "connection_error" |

---

## 3. TIMEOUTS

| Endpoint | Timeout | Reason |
|----------|---------|--------|
| Orders API | 60s | Pages can be large |
| Transactions API | 60s | Transactions pages are larger |
| DB write | 600s | Statement timeout for batch |

---

## 4. CONCURRENCY

| Mode | Parks | Workers | Behavior |
|------|-------|---------|----------|
| Sequential (current) | 5 | 1 | One park at a time. Safe but slower. |
| Parallel (future) | 10+ | 4 | Independent workers per park. Requires DB pool expansion. |

**Current: Sequential. Recommended for 5 parks.**

---

## 5. WATERMARK BEHAVIOR

| Scenario | Behavior |
|----------|----------|
| Normal | Watermark advances to max(event_at) for each endpoint |
| Empty cycle | Watermark unchanged. Status stays "active". |
| Failed cycle | Watermark unchanged. Consecutive_failures incremented. |
| 3 consecutive failures | Watermark status → "failed". On-call alert. |
| Fresh start (no watermark) | Backfill 1 hour from now. Watermark created. |

---

## 6. FAILURE ISOLATION

| Scenario | Park Impact | Other Parks |
|----------|-------------|-------------|
| Auth fail (401/403) | Skip park. Mark "auth_failed". | Continue normally. |
| Rate limit (429) | Retry with backoff. If exhausted: skip. | Continue normally. |
| API timeout | Mark cycle failed. | Continue normally. |
| DB connection error | Mark cycle failed. | Continue normally (retry per-park). |
| Watermark corruption | Fresh start (1h backfill). | Continue normally. |

---

## 7. STORAGE GOVERNANCE

| Table | Retention | Cleanup |
|-------|-----------|---------|
| `raw_yango.orders_raw` | Indefinite (shadow) | No auto-delete |
| `raw_yango.transactions_raw` | Indefinite (shadow) | No auto-delete |
| `raw_yango.ingestion_watermark` | Active only | Auto-updated |
| `ops.yango_shadow_reconciliation_history` | 90 days | Manual purge after certification |

---

## 8. MONITORING

| Metric | Check Frequency | Alert Threshold |
|--------|----------------|-----------------|
| Watermark staleness | Every 15 min | > 1 hour for TIER_1, > 4 hours for TIER_2 |
| Consecutive failures | Per cycle | ≥ 3 |
| API latency (p95) | Daily | > 30s per page |
| DB row count growth | Weekly | > 1M new rows/week |
| Reconciliation delta | Daily | delta_pct > 10% |

---

## 9. SOURCE GOVERNANCE

| Rule | Enforcement |
|------|-------------|
| Yango is shadow only | `canonical_ready = false` in all responses |
| CT is canonical | V2 defaults to CT_TRIPS_2026 |
| No source promotion | CF-H2H remains BLOCKED |
| Reconciliation is read-only | No writes to CT serving facts |
