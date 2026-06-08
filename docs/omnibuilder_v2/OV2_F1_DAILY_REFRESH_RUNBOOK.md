# OV2-F.1 — DAILY REFRESH RUNBOOK

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Refresh Chain
> **Status:** DRAFT — PRODUCTION USE REQUIRES REVIEW

---

## 1. DAILY SEQUENCE

```bash
cd C:\cursor\controltower\controltower\backend
```

### Step 1: Refresh RAW/Yango API data (if needed)

```bash
# Refresh Yango raw MVs (orders, revenue, driver profiles)
python -m scripts.refresh_raw_yango_mvs
```

### Step 2: Refresh Business Slice Facts (day → week → month)

```bash
# Incremental refresh for Lima, last 7 days
python -m scripts.refresh_omniview_real_slice_incremental --city lima --days 7 --confirm

# For backfill (e.g., week_fact STALE since Apr 20):
python -m scripts.refresh_omniview_real_slice_incremental --city lima --from 2026-04-20 --to 2026-06-07 --confirm
```

### Step 3: Refresh OV2 Serving Snapshots

```bash
# Generate shell + matrix snapshots for latest closed date
python -m scripts.refresh_omniview_v2_snapshots --use-latest-closed-date --confirm

# Force specific date
python -m scripts.refresh_omniview_v2_snapshots --date 2026-06-06 --confirm
```

### Step 4: Refresh Plan vs Real Monthly MV (if plan version changed)

```bash
python -m scripts.refresh_plan_vs_real_monthly_mvs
```

### Step 5: Validate Freshness

```bash
python -m scripts.audit_ov2_refresh_freshness
```

Expected output shows all layers with gap <= 2 days.

### Step 6: Post-Refresh Validation

```bash
# Check day_fact / week_fact / month_fact consistency
python -m scripts.validate_omniview_real_slice_refresh_consistency

# Verify snapshots are healthy
python -m scripts.refresh_omniview_v2_snapshots --dry-run
```

---

## 2. SAFE ROLLBACK

### If day_fact refresh corrupts data

```bash
# Option A: Revert to previous backup table (if staging exists)
# The incremental script uses atomic staging→swap, so old data is preserved until swap

# Option B: Re-run refresh from source (safe — idempotent)
python -m scripts.refresh_omniview_real_slice_incremental --city lima --days 7 --confirm
```

### If snapshot refresh corrupts data

```bash
# Snapshots are time-point data. Just refresh again:
python -m scripts.refresh_omniview_v2_snapshots --date 2026-06-06 --confirm
```

---

## 3. REMEDIATION PER LAYER

| Layer | Symptom | Remediation |
|-------|---------|-------------|
| RAW trips | No new data (max = D-3+) | Check trips_2026 upstream ingestion |
| RAW Yango | No new data | Check Yango API credentials, rate limits |
| DAY_FACT | STALE or 0-row days | Re-run `refresh_omniview_real_slice_incremental --days 7` |
| WEEK_FACT | STALE (current: 48 days) | Re-run with `--from 2026-04-20 --to today` |
| MONTH_FACT | Missing months | Re-run after week_fact fixed |
| SNAPSHOT | STALE | Re-run `refresh_omniview_v2_snapshots` |
| PLAN_VERSION | Missing | Check `ops.plan_versions_metadata`, re-upload template |
| REVENUE | NULL in month_fact | Re-run month_fact refresh with revenue column included |

---

## 4. COMMANDS QUICK REFERENCE

```bash
# Master pipeline (full refresh)
python -m scripts.run_pipeline_refresh_and_audit

# Business slice facts only (operational window — 2 months)
# Triggered by APScheduler daily at 04:00
python -m scripts.refresh_all_operational_mvs

# Snapshots only
python -m scripts.refresh_omniview_v2_snapshots --use-latest-closed-date --confirm

# Freshness audit
python -m scripts.audit_ov2_refresh_freshness

# Certification
python -m scripts.certify_ov2_refresh_chain
```

---

## 5. MONITORING

| Signal | Threshold | Alert |
|--------|-----------|-------|
| `day_fact` max date > D-2 | CRITICAL | Investigate trips_2026 ingestion |
| `snapshot` max date > D-2 | WARNING | Re-run snapshot refresh |
| `week_fact` gap > 7 days | CRITICAL | Re-run week_fact refresh |
| `revenue` fill < 80% | WARNING | Check month_fact revenue column |
| `slice_coverage` < 5 slices | CRITICAL | Check day_fact business slices |

---

*End of Daily Refresh Runbook*
