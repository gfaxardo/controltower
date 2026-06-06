# Stalled Run Recovery Report

**Generated:** 2026-06-05T18:48:11.264320-05:00
**Park:** 08e20910d81d42658d4334d3f6d10ac0
**Date:** 2026-06-04
**Stale threshold:** 1 min

## Summary
- Stalled runs detected: 1
- Marked as stalled: 1
- Completed runs: 1

## Stalled Runs
| Run ID | Endpoint | Pages Done | Expected | Fetched | Inserted | Stale (min) |
|--------|----------|-----------|----------|---------|----------|-------------|
| ingest_20260605_183512_o | orders | ? | ? | 0 | 0 | 12.9 |

## Recovery Plan

### Resume: ingest_20260605_183512_orders
```bash
python -m scripts.recover_stalled_yango_ingestion_runs
  --date 2026-06-04
  --endpoint-group orders
  --resume-missing-pages
  --start-from-cursor ""
  --run-id ingest_20260605_183512_orders
  --expected-total 11085
  --confirm-live
```
## Completed Runs
| Run ID | Endpoint | Fetched | Inserted | Pages | Expected |
|--------|----------|---------|----------|-------|----------|
| ingest_20260605_064507_d | driver_profiles | 300 | 300 | ? | ? |