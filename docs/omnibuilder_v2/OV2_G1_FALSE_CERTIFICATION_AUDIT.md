# OV2-G.1 — FALSE CERTIFICATION AUDIT

> **Date:** 2026-06-08
> **Status:** AUDIT COMPLETE — 2 false certification scenarios detected

---

## 1. SCENARIO A: Projection Fresh, REAL Stale

**Evidence from F.2 audit:**
- day_fact: 2026-05-31 (STALE, 7 days behind RAW)
- BUT snapshots: 2026-06-05 (appeared FRESH — only 2 days behind today)
- BUT operating_date returned 2026-05-31 (correctly reporting the stale date)

**False certification risk:** If a check only looks at snapshot or operating_date freshness, it would miss that day_fact was 7 days stale.

**Classification: WARN** — detected by observatory, not by individual checks.

## 2. SCENARIO B: Scheduler Reports "success", Data Stale

**Evidence from F.2/F.4B:**
- refresh_run_log: `business_slice | success | 2026-06-04 04:00`
- BUT day_fact max was 2026-05-31 (no new data loaded)
- Scheduler reported `success` but data hadn't advanced

**False certification risk:** `status=success` in the log is meaningless without verifying data advancement.

**Classification: FAIL** — scheduler success is a false positive.

## 3. SCENARIO C: Snapshot Fresh, Source Stale

**Current state:**
- Snapshot: 2026-06-05 (appears D-3, near-current)
- BUT day_fact: 2026-06-07 (actually fresher than snapshot)

**False certification risk:** This is an INVERTED case — the snapshot is staler than the source. The UI could serve D-3 data from snapshot while D-0 data exists in facts. Snapshot-first serving means the UI prefers the snapshot over fresher runtime data.

**Classification: WARN** — serving-first is correct but snapshot staleness can hide fresher real data.

## 4. RULES TO PREVENT FALSE CERTIFICATION

| Rule | Status |
|------|--------|
| Never certify REAL from PROJECTION freshness | ✅ Observatory separates REAL vs PROJECTION |
| Never trust scheduler `status=success` without data verification | ❌ Not implemented |
| Snapshot stale must be detected even when source is fresh | ✅ Observatory shows both |
| Layer date ≠ effective source date | ✅ Observatory captures both |

---

*End of False Certification Audit*
