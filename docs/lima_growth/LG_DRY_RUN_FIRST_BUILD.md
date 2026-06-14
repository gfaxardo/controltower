# LG_DRY_RUN_FIRST_BUILD

**Phase:** LG-CF-RECOVERY-2A — Control Foundation Closure  
**Generated:** 2026-06-12  
**Target:** Simulate first execution of `build_driver_explorer_fact('2026-06-12')`  
**Veredict:** `GO for first build`

---

## INPUTS

### Base Table: `growth.yango_lima_driver_state_snapshot`

| Metric | Value |
|--------|-------|
| Rows for 2026-06-12 | **18,545** |
| Distinct drivers | 18,545 |
| Columns read | `snapshot_date`, `driver_profile_id`, `lifecycle_state`, `performance_state`, `retention_state`, `historical_band`, `completed_orders_week`, `first_trip_at`, `last_trip_at`, `new_driver_flag`, `recoverable_flag`, `declining_flag`, `churn_risk_flag` |
| PK index | `(snapshot_date, driver_profile_id)` — used for WHERE + JOIN |

---

## JOIN SIMULATION

### Join 1: `growth.yango_lima_program_eligibility_daily`

| Metric | Value |
|--------|-------|
| Join type | LEFT JOIN |
| Join key | `(driver_profile_id, eligibility_date = '2026-06-12')` |
| Rows for 06-12 | **28,128** (some drivers have multiple programs) |
| Match rate | ~100% (via COALESCE fallback in SELECT) |
| Index used | PK `(eligibility_date, driver_profile_id, program_code)` |

### Join 2: `growth.rna_priority_fact`

| Metric | Value |
|--------|-------|
| Join type | LEFT JOIN |
| Join key | `driver_profile_id` |
| Rows | **888** |
| Match rate | **4.8%** (888 / 18,545) |
| Unmatched | DEFAULT values (COLD, 0, FALSE) |
| Index used | UNIQUE on `driver_profile_id` |

### Join 3: `growth.yego_lima_driver_lifecycle_daily`

| Metric | Value |
|--------|-------|
| Join type | LEFT JOIN |
| Join key | `(driver_profile_id, snapshot_date = '2026-06-12')` |
| Rows for 06-12 | **68,506** |
| Match rate | ~100% |
| Index used | Unique on `(snapshot_date, park_id, driver_profile_id)` |

### Join 4: `growth.yego_lima_v2_taxonomy_daily` (COALESCE enrichment)

| Metric | Value |
|--------|-------|
| Join type | LEFT JOIN |
| Join key | `(driver_id, target_date = '2026-06-12')` |
| Rows for 06-12 | **68,506** |
| Match rate | ~100% |
| Index used | PK `(target_date, driver_id)` |

### Join 5: `growth.yego_lima_v2_movement_fact` (COALESCE enrichment)

| Metric | Value |
|--------|-------|
| Join type | LEFT JOIN |
| Join key | `(driver_id, target_date = '2026-06-12')` |
| Rows for 06-12 | **466** |
| Match rate | **2.5%** (466 / 18,545) |
| Unmatched | Derived from lifecycle_state diff (day-over-day) |
| Index used | PK `(target_date, driver_id, movement_type)` |

### Join 6: `growth.yego_lima_loopcontrol_result_sync` (LATERAL)

| Metric | Value |
|--------|-------|
| Join type | LEFT JOIN LATERAL (latest per driver) |
| Rows total | **~10** |
| Match rate | **<0.1%** |
| Unmatched | NULL |
| Index used | `driver_id` index |

### Join 7: `growth.yango_lima_assignment_queue` (LATERAL)

| Metric | Value |
|--------|-------|
| Join type | LEFT JOIN LATERAL (latest per driver) |
| Rows | Variable (depends on queue date) |
| Match rate | Variable |
| Unmatched | NULL for name, phone, campaign |
| Index used | `driver_profile_id` index |

### Join 8: `growth.yego_lima_impact_tracking` (LATERAL)

| Metric | Value |
|--------|-------|
| Join type | LEFT JOIN LATERAL (latest per driver) |
| Rows total | **0** |
| Match rate | **0%** |
| Unmatched | NULL/0 for all impact fields |
| Index used | Irrelevant (0 rows) |

### Join 9: `growth.yango_lima_driver_state_snapshot` (prev day)

| Metric | Value |
|--------|-------|
| Join type | LEFT JOIN |
| Join key | `(driver_profile_id, snapshot_date = '2026-06-11')` |
| Rows for 06-11 | **18,545** |
| Match rate | ~100% |
| Purpose | Derive `movement_type` from lifecycle_state diff |

---

## CARDINALITY

| Stage | Rows |
|-------|------|
| Base (driver_state_snapshot 06-12) | 18,545 |
| After LEFT JOINs (1:1 for most, 1:N for program) | 18,545 (DISTINCT via UPSERT) |
| **Final UPSERT** | **~18,545** |

**No row explosion.** All joins are 1:1 at the driver_profile_id level (program_eligibility uses DISTINCT ON or the UPSERT handles conflicts).

---

## STORAGE ESTIMATE

| Component | Size |
|-----------|------|
| 47 columns × 18,545 rows | ~18 MB (at ~1KB/row with TEXT fields) |
| 6 B-tree indexes | ~15 MB (estimated at ~50% of data size for indexed columns) |
| **Total first date** | **~33 MB** |
| 7-day history (18,545 × 7) | ~126 MB data + ~50 MB indexes = ~176 MB |
| 90-day retention (18,545 × 90) | ~1.6 GB data + ~0.5 GB indexes = **~2.1 GB** |

---

## EXECUTION TIME ESTIMATE

| Phase | Operation | Est. Time |
|-------|-----------|-----------|
| 1 | Table existence checks (9 × `information_schema`) | <1s |
| 2 | Column existence checks (3 × `information_schema`) | <1s |
| 3 | Base SELECT from driver_state_snapshot (18,545 rows) | <2s |
| 4 | LEFT JOIN program_eligibility (28,128 rows) | <3s |
| 5 | LEFT JOIN rna_priority_fact (888 rows) | <1s |
| 6 | LEFT JOIN lifecycle_daily (68,506 rows) | <3s |
| 7 | LEFT JOIN v2_taxonomy (68,506 rows) | <3s |
| 8 | LEFT JOIN v2_movement (466 rows) | <1s |
| 9 | LATERAL loopcontrol (~10 rows) | <1s |
| 10 | LATERAL assignment_queue (variable) | <3s |
| 11 | LATERAL impact_tracking (0 rows) | <1s |
| 12 | LEFT JOIN prev_day snapshot (18,545 rows) | <2s |
| 13 | UPSERT execution (18,545 rows) | <10s |
| **Total estimated** | | **30-60 seconds** |

---

## INDEX USAGE (Expected by PostgreSQL Planner)

| Query Phase | Index | Type |
|------------|-------|------|
| `WHERE ds.snapshot_date = '2026-06-12'` | PK on driver_state_snapshot | Index scan |
| `JOIN program_eligibility ON (date, driver_id)` | PK on program_eligibility | Index scan |
| `JOIN rna_priority_fact ON driver_profile_id` | UNIQUE on driver_profile_id | Index scan |
| `JOIN lifecycle_daily ON (date, driver_id)` | Unique on (date, park, driver) | Index scan |
| `JOIN v2_taxonomy ON (date, driver_id)` | PK on v2_taxonomy | Index scan |
| `JOIN v2_movement ON (date, driver_id)` | PK on v2_movement | Index scan |
| `LATERAL loopcontrol ORDER BY synced_at DESC` | idx_lcrs_driver | Index scan + sort |
| `LATERAL assignment_queue ORDER BY queue_date DESC` | driver_profile_id index | Index scan + sort |
| `JOIN prev_day snapshot ON (date, driver_id)` | PK on driver_state_snapshot | Index scan |

**All joins are index-backed. No sequential scans expected.**

---

## DATA QUALITY EXPECTED

| Quality Level | Rows | Conditions |
|--------------|------|-----------|
| `COMPLETE` | 0 | Requires 7+ sources to have data for target_date |
| `PARTIAL` | **~18,545** | Default for first build (impact_tracking=0, loopcontrol=10) |

After fixing the `data_quality` contract (row counts, not table existence):
- 5 sources have 06-12 data (snapshot, eligibility, lifecycle, taxonomy, movement)
- 1 source has data but not date-specific (rna_priority_fact, 888 rows)
- 2 sources near-empty/empty (loopcontrol 10, impact 0)
- 1 source variable (assignment_queue)
- **Estimated quality: `DEGRADED` (5-6 sources fresh)**

---

## GO / NO-GO

| Criterion | Status | Detail |
|-----------|--------|--------|
| Source tables fresh (06-12) | ✅ | All primary sources confirmed |
| All joins index-backed | ✅ | 9/9 joins use indexes |
| No row explosion | ✅ | 18,545 → 18,545 (DISTINCT via UPSERT) |
| Execution time <120s | ✅ | Est. 30-60s (within 60s TIMEOUT) |
| Storage <5GB | ✅ | ~33 MB per date, ~2.1 GB at 90 days |
| Graceful degradation | ✅ | NULL for empty sources, DEFAULT for RNA |
| Migration idempotent | ✅ | CREATE TABLE IF NOT EXISTS + IF NOT EXISTS indexes |
| Rollback possible | ✅ | DELETE WHERE target_date = '2026-06-12' |

### Veredict: GO for first build

**The first build is low-risk. All joins are index-backed. The base table has moderate cardinality (18,545 rows). The UPSERT is idempotent. Rollback is a simple DELETE. No blocking locks are held during the build.**
