# LG_EXP_DEPLOYMENT_PLAN

**Phase:** LG-CF-RECOVERY-2A — Control Foundation Closure  
**Generated:** 2026-06-12  
**Target:** Deploy Driver Explorer canonical serving fact to production  
**Status:** PLAN — NOT YET EXECUTED

---

## MIGRATION CHAIN

```
216_yego_lima_export_audit          (APPLIED in production)
  ↓
217_yego_lima_rna_priority          (TABLE EXISTS — DDL applied manually via LG-RNA-1B)
  ↓
218_yego_lima_rna_pilot_measurement (APPLIED)
  ↓
219_lg_perf_1a_driver_explorer_index (PENDING — adds indexes on ops.mv_driver_lifecycle_base)
  ↓
220_lg_exp_1d_driver_explorer_fact  (PENDING — creates growth.yego_lima_driver_explorer_fact)
```

### Special Note: Migration 217

Migration 217's table `growth.rna_priority_fact` already exists (888 rows, populated via LG-RNA-1B recovery DDL). When running `alembic upgrade head`:
- If 217 was marked as applied in `alembic_version` table → it will be skipped (correct)
- If 217 was NOT marked as applied → it will try to CREATE TABLE IF NOT EXISTS (safe, idempotent)

**Pre-flight check:**
```sql
SELECT version_num FROM alembic_version ORDER BY version_num DESC LIMIT 5;
```

---

## DEPLOYMENT SEQUENCE

### Step 1: Pre-Deployment Validation

```bash
# Check current alembic head
cd backend
alembic current

# Verify migration files exist
ls alembic/versions/219_lg_perf_1a_driver_explorer_index.py
ls alembic/versions/220_lg_exp_1d_driver_explorer_fact.py

# Verify source tables are fresh
python -c "
from app.db.connection import init_db_pool, _get_connection_params
import psycopg2
init_db_pool()
conn = psycopg2.connect(**_get_connection_params())
cur = conn.cursor()
for tbl, col in [
    ('growth.yango_lima_driver_state_snapshot', 'snapshot_date'),
    ('growth.yango_lima_program_eligibility_daily', 'eligibility_date'),
    ('growth.yego_lima_driver_lifecycle_daily', 'snapshot_date'),
    ('growth.rna_priority_fact', None),
]:
    if col:
        cur.execute(f'SELECT MAX({col}) FROM {tbl}')
    else:
        cur.execute(f'SELECT COUNT(*) FROM {tbl}')
    print(f'{tbl}: {cur.fetchone()[0]}')
cur.close(); conn.close()
"
# Expected: all tables have 2026-06-12 data or >0 rows

# Verify no blocking locks
python -c "
from app.db.connection import init_db_pool, _get_connection_params
import psycopg2
init_db_pool()
conn = psycopg2.connect(**_get_connection_params())
cur = conn.cursor()
cur.execute(\"SELECT pid, state, wait_event_type, query FROM pg_stat_activity WHERE state != 'idle' AND query NOT LIKE '%pg_stat_activity%'\")
for r in cur.fetchall():
    print(r)
cur.close(); conn.close()
"
```

**GO criteria:** All source tables fresh. No blocking locks. Alembic current shows latest applied migration.

---

### Step 2: Apply Migrations

```bash
cd backend
alembic upgrade head
```

**What this does:**
1. Migration 219: Creates 2 indexes on `ops.mv_driver_lifecycle_base` (idempotent, `IF NOT EXISTS`)
2. Migration 220: Creates `growth.yego_lima_driver_explorer_fact` table with PK, 47 columns, 6 indexes (idempotent, `IF NOT EXISTS`)

**Expected duration:** <5 seconds (indexes on existing MV may take longer if MV is large)

**Rollback:**
```bash
alembic downgrade -1  # Undo last migration (220)
alembic downgrade -1  # Undo migration 219
```

**Post-apply validation:**
```sql
SELECT EXISTS(
  SELECT 1 FROM information_schema.tables
  WHERE table_schema='growth' AND table_name='yego_lima_driver_explorer_fact'
);
-- Expected: TRUE

SELECT indexname FROM pg_indexes
WHERE tablename = 'yego_lima_driver_explorer_fact' AND schemaname = 'growth'
ORDER BY indexname;
-- Expected: 7 rows (1 PK + 6 indexes)
```

---

### Step 3: First Build (Initial Population)

```bash
cd backend
python -m scripts.build_driver_explorer_fact --date 2026-06-12 --validate
```

**What this does:**
- Reads `driver_state_snapshot` for 06-12 (18,545 drivers)
- LEFT JOINs 8 source tables
- UPSERTs into `driver_explorer_fact`
- Validates row counts

**Expected output:**
```
target_date:       2026-06-12
rows_upserted:     ~18,545
data_quality:      PARTIAL
sources_available: 7-9
sources_missing:   0-2
status:            SUCCESS
```

**Expected duration:** 30-90 seconds (9-table join on 18,545 base rows)

**If build fails:**
1. Check source table freshness
2. Check `rna_priority_fact` exists (should, 888 rows)
3. Check statement_timeout (60s in writer)
4. Run with individual source checks: modify `build_driver_explorer_fact()` to log per-source row counts

**Rollback:** `DELETE FROM growth.yego_lima_driver_explorer_fact WHERE target_date = '2026-06-12'`

---

### Step 4: Endpoint Validation

```bash
# Test endpoint
curl "http://localhost:8000/yego-lima-growth/driver-explorer?limit=5"

# Test with search
curl "http://localhost:8000/yego-lima-growth/driver-explorer?search=ABC&limit=5"

# Test with lifecycle filter
curl "http://localhost:8000/yego-lima-growth/driver-explorer?lifecycle=ACTIVE&limit=5"

# Test with program filter
curl "http://localhost:8000/yego-lima-growth/driver-explorer?program=ACTIVE_GROWTH&limit=5"
```

**Expected:**
- HTTP 200 for all queries
- `total > 0` for filtered queries
- `drivers` array with 47-field records
- Response time <2s

---

### Step 5: Backfill Previous Dates (optional but recommended)

```bash
# Backfill last 7 days to build history
for d in 2026-06-06 2026-06-07 2026-06-08 2026-06-09 2026-06-10 2026-06-11; do
  python -m scripts.build_driver_explorer_fact --date $d
done
```

**Note:** Only backfill dates where `driver_state_snapshot` has data. Pre-06-07 may have no snapshot.

---

### Step 6: Enable Feature Flag (Integration)

```bash
# Option A: Environment variable (affects all processes)
export LG_DRIVER_EXPLORER_FACT_ENABLED=true

# Option B: Restart with flag
LG_DRIVER_EXPLORER_FACT_ENABLED=true uvicorn app.main:app --reload
```

**What this does:** `autonomous_tick()` will call `build_driver_explorer_fact(op_date)` after `generate_all_serving_facts()`. Every 5 minutes, the fact will be UPSERTed with latest data.

**Validation:** Check `refreshed_at` column in explorer fact → should update every 5 minutes.

---

### Step 7: UI Go-Live

The UI is already deployed with the new code (LG-EXP-1E). Once the endpoint returns data, the DriverExplorerTab will automatically show real columns.

**Smoke test:**
1. Open `/lima-growth/intelligence`
2. Click "Driver Explorer" tab
3. Type a driver_id prefix in search → hit Enter
4. Verify: Lifecycle shows real value (not `—`)
5. Verify: Program shows real value (not `—`)
6. Verify: RNA shows COLD/WARM badge
7. Verify: Movement shows STATE_CHANGE/STABLE
8. Verify: Quality badge shows PARTIAL/COMPLETE
9. Click Export CSV → verify download

---

## DEPENDENCY MATRIX

| Dependency | Status | Action Required |
|-----------|--------|----------------|
| DB access (production) | Required | Connection string configured |
| `alembic_version` table | Must exist | Standard Alembic setup |
| Migration 217 table already exists | YES | Alembic will skip or CREATE IF NOT EXISTS |
| Source tables fresh (06-12) | YES | Confirmed in LG-CF-RECOVERY-1B |
| autonomous_tick running | YES | Every 5 min |
| Frontend built (LG-EXP-1E) | YES | npm run build PASS |
| Endpoint registered (LG-EXP-1E) | YES | main.py:216 |

---

## RISK MATRIX

| Risk | Probability | Impact | Mitigation |
|------|-----------|--------|------------|
| Migration 217 fails because table already exists | LOW | LOW | `CREATE TABLE IF NOT EXISTS` is idempotent |
| Migration 219 index creation slow on large MV | LOW | MEDIUM | `IF NOT EXISTS` — if index exists, instant |
| First build times out (>60s) | MEDIUM | LOW | Increase `TIMEOUT_MS` in writer to 120000 |
| First build returns 0 rows | LOW | HIGH | Rollback: DELETE 0 rows; investigate source freshness |
| Endpoint returns `NO_SERVING_DATA` | MEDIUM | MEDIUM | Indicates build failed silently; re-run with validation |
| UI shows `—` for some columns | LOW | LOW | Expected for NULL fields (name, phone, contact, impact) |
| Feature flag causes tick slowdown | LOW | MEDIUM | Monitor tick duration; fallback: unset flag |

---

## EXECUTION CHECKLIST

```
[ ] Step 1: Pre-deployment validation (source table freshness, no locks)
[ ] Step 2: alembic upgrade head (migrations 219 + 220)
[ ] Step 3: First build (build_driver_explorer_fact --date 2026-06-12 --validate)
[ ] Step 4: Endpoint validation (curl smoke tests)
[ ] Step 5: Backfill previous dates (optional)
[ ] Step 6: Enable feature flag (LG_DRIVER_EXPLORER_FACT_ENABLED=true)
[ ] Step 7: UI smoke test (browser, 5 filter combinations)
[ ] Sign-off: Driver Explorer canonical serving fact LIVE
```

## SIGN-OFF

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Developer | — | — | — |
| Reviewer | — | — | — |
| Operator | — | — | — |
