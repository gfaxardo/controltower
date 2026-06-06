# OV2-B.6B — INGESTION RELIABILITY CERTIFICATION

> **Date:** 2026-06-05
> **Motor:** Control Foundation / Ingestion Reliability
> **Prerequisite:** OV2-B.6A (FAIL — 40.6% coverage)

---

## 1. PROBLEM STATEMENT

OV2-B.6A revealed that Yango Fleet API ingestion for Park Lima on 2026-06-04 only recovered 4,500 of 11,085 expected orders (40.6%). Root causes identified:

| Issue | Evidence |
|-------|----------|
| Silent stops | 12 of 13 runs stuck in `started` status with no progress |
| Counter bug | `records_fetched=0` even when 4,500 records were inserted |
| No page tracking | Impossible to know which pages were ingested |
| No heartbeat | Runs that died couldn't be detected |
| No resume capability | Had to restart from scratch |
| No coverage guard | Ingestion "completed" with 40.6% coverage |

---

## 2. CHANGES IMPLEMENTED

### 2.1 Schema Migration (189_ingestion_reliability_hardening)

**Columns added to `raw_yango.api_ingestion_run`:**
- `heartbeat_at` — updated every page
- `current_page` — current page being processed
- `last_cursor` — last cursor seen
- `next_cursor` — next cursor to fetch
- `expected_pages` — total expected pages
- `pages_completed` — count of completed pages

**New table: `raw_yango.api_ingestion_page_checkpoint`**
- Tracks per-page progress: `(run_id, page_number)` unique
- Statuses: `pending`, `fetched`, `inserted`, `failed`, `skipped`
- Stores cursor, record count, error messages per page

### 2.2 Repository Functions (`raw_yango_repository.py`)

| Function | Purpose |
|----------|---------|
| `update_ingestion_heartbeat()` | Update heartbeat + page progress |
| `update_ingestion_counters()` | Increment fetched/inserted/skipped/error counters |
| `set_ingestion_expected_pages()` | Set expected page count |
| `set_ingestion_status()` | Explicit status transitions |
| `mark_stalled_runs()` | Mark runs with stale heartbeat as stalled |
| `get_stalled_runs()` | Query runs that appear stalled |
| `get_completed_runs()` | Query completed runs for a date range |
| `init_page_checkpoints()` | Create checkpoint rows for all expected pages |
| `record_page_completed()` | Mark a page as inserted |
| `record_page_failed()` | Mark a page as failed |
| `get_missing_pages()` | List pages not yet inserted |
| `get_page_checkpoint_summary()` | Summary of checkpoint progress |

### 2.3 Ingestion Script Updates (`ingest_yango_raw_landing.py`)

**New arguments:**
- `--resume-run-id` — resume a specific run
- `--expected-total` — expected record count (for coverage)
- `--fail-on-coverage-below` — fail if coverage < threshold (e.g. 0.99)
- `--mark-stalled-after-minutes` — auto-mark old runs

**Behavior changes:**
- Heartbeat updated after every successful page ingestion
- Counters (fetched, inserted, skipped) updated incrementally
- Page checkpoints recorded for resume capability
- Coverage validation at completion — fails explicitly if below threshold
- Status transitions: `started` → (running) → `completed`/`failed`/`failed_incomplete`

### 2.4 Stalled Run Recovery (`recover_stalled_yango_ingestion_runs.py`)

**Modes:**
- `diagnose` — detect stalled runs, show summary
- `--mark-stalled` — mark stalled runs (sets status + finished_at)
- `--resume-missing-pages` — resume ingestion for missing pages (with `--confirm-live`)

**Outputs:**
- `stalled_run_recovery.md` — human-readable report
- `stalled_runs.csv` — structured data
- `stalled_runs_diagnostic.json` — machine-readable

---

## 3. NO SILENT STOP TEST

### Simulation Protocol

1. Run ingestion with `--max-pages 3 --confirm-live`
2. After 3 pages (1,500 orders), the process stops
3. Heartbeat stops updating. After `--mark-stalled-after-minutes`, run is marked `stalled`
4. Run `recover_stalled_yango_ingestion_runs --resume-missing-pages --expected-total 11085`
5. Script detects gap (pages 4-23) and creates new ingestion for remaining pages
6. After completion, coverage >=99% validates success

This cannot be fully executed without live API credentials. The infrastructure is in place to support it.

### Dry-run verification

```
$ python -m scripts.recover_stalled_yango_ingestion_runs \
    --date 2026-06-04 --endpoint-group orders \
    --resume-missing-pages --expected-total 11085

[DRY RUN] Would resume orders ingestion for 2026-06-04
  Park: 08e20910d81d42658d4334d3f6d10ac0
  Expected total: 11085
  Start cursor: from beginning
  Run ID: new run

  To execute, add --confirm-live flag.
```

---

## 4. LIVE CONTROLLED COMPLETION (TAREA 7)

The following command would complete the missing pages for 2026-06-04:

```bash
cd backend
python -m scripts.recover_stalled_yango_ingestion_runs \
  --date 2026-06-04 \
  --endpoint-group orders \
  --expected-total 11085 \
  --resume-missing-pages \
  --confirm-live
```

Followed by verification:

```bash
python -m scripts.audit_api_completeness --date 2026-06-04 --fleet-room 11085
```

**Status: READY but requires `--confirm-live` and API credentials.**

---

## 5. VALIDATION CHECKLIST

| Rule | Status |
|------|--------|
| No UI touched | PASS |
| No Omniview V1 touched | PASS |
| No serving productivo reemplazado | PASS |
| No credenciales expuestas | PASS |
| No commit | PASS |
| Schema migration applied | PASS (manual, alembic chain broken) |
| Heartbeat columns exist | PASS |
| Page checkpoint table exists | PASS |
| Recovery script functional | PASS (dry-run) |
| Ingestion script counters fix | PASS (compiles, ready for live) |
| Coverage guard | PASS (fails if coverage < threshold) |
| Stalled runs marked | PASS (12 runs marked stalled) |

---

## 6. GO / NO-GO FOR OV2-B.7

**CONDITIONAL GO** — infrastructure ready, requires live execution to certify.

To achieve full GO:
1. Execute `recover_stalled_yango_ingestion_runs --confirm-live` for 2026-06-04
2. Verify `audit_api_completeness` shows coverage >= 99%
3. Confirm no new stalled runs
4. Confirm counters are correct (not 0)

**Blockers resolved:**
- Silent stops → heartbeat + stalled detection
- Counter bug → incremental `update_ingestion_counters()`
- No resume → `--resume-run-id` + page checkpoints
- No coverage guard → `--fail-on-coverage-below` + explicit failure

---

## 7. FILES CREATED / MODIFIED

| File | Action | Lines |
|------|--------|-------|
| `alembic/versions/189_ingestion_reliability_hardening.py` | New | 82 |
| `app/repositories/raw_yango_repository.py` | +220 lines (heartbeat, checkpoint, recovery) | 790→1016 |
| `scripts/recover_stalled_yango_ingestion_runs.py` | New | 266 |
| `scripts/ingest_yango_raw_landing.py` | Modified (+50 lines) | 1155→1205 |
| `docs/omnibuilder_v2/OV2_B6B_INGESTION_RELIABILITY_CERTIFICATION.md` | New | this file |
