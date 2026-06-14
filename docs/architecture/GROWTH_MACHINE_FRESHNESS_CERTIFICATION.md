# GROWTH MACHINE — FRESHNESS CERTIFICATION

**Version:** 1.0.0
**Date:** 2026-06-13
**Status:** GM-F1A IMPLEMENTED — DRIVER HISTORY GUARDED
**Phase:** GM-F1A Driver History Weekly Governance
**Precedes:** GM-F1B Serving Registry/Freshness Registration
**Precedence:** TRUTH_MAP_V2.md prevails

---

## 0. Executive Decision

**GO: DRIVER HISTORY GUARDED AND CONDITIONALLY AUTO-REFRESHED**

The `growth.yango_lima_driver_history_weekly` table now has:
- A freshness gate (`check_driver_history_weekly_freshness()`) at the start of `lima_growth_autonomous_tick`
- Automated conditional refresh via `refresh_weekly_history()` running every tick
- Advisory lock protection (lock ID 9002)
- Fail-closed behavior: tick blocks downstream cascade if weekly history remains stale after refresh attempt
- The FH-1 threshold bug is fixed (was `latest_complete_monday - 7 days`, now `latest_complete_monday`)

The Growth Machine is NOT closed. Weekly cycle evidence pending. GM-F1B (serving registry formalization) is the next phase.

---

## 1. Scope

### GM-F1A: Driver History Weekly Governance

- `check_driver_history_weekly_freshness()` — freshness contract function
- `refresh_weekly_history()` — fixed threshold + advisory lock
- `autonomous_tick()` — freshness gate integration + fail-closed guard

### Out of Scope

- `program_eligibility` / `opportunity_list` DELETE transaction wrapping (GM-F1B)
- `freshness_registry` false-positive fix (GM-F1B)
- `control_loop_state` full freshness certification (GM-F1B)
- Diagnostic Engine, Forecast, UI, program rules

---

## 2. Driver History Weekly Contract

### 2.1 Freshness Check Function

```python
def check_driver_history_weekly_freshness() -> Dict[str, Any]
```

**Contract:**

| Status | Condition | Blocking | Meaning |
|--------|-----------|----------|---------|
| `fresh` | `MAX(week_start_date) >= current_week_start` or lag <= 7 days | No | Weekly history covers current/previous complete week |
| `stale` | lag 7-14 days | **Yes** | Weekly history is behind. Refresh attempted. |
| `stale` | lag > 14 days | **Yes** | Critically stale. Refresh attempted. |
| `missing` | row_count = 0 or max_week_start_date is NULL | **Yes** | Table empty. Run bootstrap. |
| `error` | Query exception | **Yes** | Fail-closed. |

**Response shape:**
```json
{
  "table": "growth.yango_lima_driver_history_weekly",
  "status": "fresh|stale|missing|error",
  "max_week_start_date": "2026-06-08",
  "current_week_start": "2026-06-08",
  "lag_days": 0,
  "row_count": 135812,
  "blocking": true|false,
  "reason": "..."
}
```

**Location:** `backend/app/services/yego_lima_growth_history_service.py`

### 2.2 Refresh Function

```python
def refresh_weekly_history() -> Dict[str, Any]
```

**Contract:**

| Return Status | Meaning |
|---------------|---------|
| `NOOP` | Weekly history is up to date (>= current complete Monday) or no daily data |
| `REFRESHED` | `_build_weekly_sql_bulk()` executed successfully |
| `SKIPPED_LOCKED` | Another refresh in progress (advisory lock 9002) |

**Lock:** `pg_try_advisory_lock(9002)` — prevents concurrent rebuilds.

**Location:** `backend/app/services/yego_lima_growth_history_service.py`

### 2.3 Writer

The canonical writer `_build_weekly_sql_bulk()` is:
- **Idempotent:** `INSERT ... ON CONFLICT (week_start_date, driver_profile_id) DO UPDATE`
- **Full rebuild:** reads ALL `driver_history_daily` rows, computes weekly aggregates + rolling window metrics
- **No DELETE:** never removes rows. In-flight failure leaves previous data intact.
- **Transaction:** wrapped in `conn.autocommit = False` → `conn.commit()`
- **Timeout:** `statement_timeout=600000` (10 min)
- **NOT safe for every 5 min on large datasets.** The NOOP guard prevents unnecessary rebuilds. When triggered, runs once then NOOPs for the rest of the week.

---

## 3. Tick Guard Behavior

### 3.1 autonomous_tick Flow (Updated)

```
1. acquire_tick_lock (advisory lock 9001)
2. check scheduler enabled
3. ingest_recent_orders() → raw ingestion
4. ── GM-F1A GUARD ──
   4a. refresh_weekly_history()
   4b. check_driver_history_weekly_freshness()
   4c. IF blocking → set status="blocked_by_stale_driver_history_weekly"
       → SKIP cascade, SKIP run_refresh, SKIP control_loop_sync
5. detect cascade_required / run_refresh
6. IF cascade_required AND NOT history_blocked → execute cascade
7. IF run_refresh AND NOT history_blocked → run_daily_refresh
8. IF NOT history_blocked → sync_assignment_queue_to_control_loop
9. Always: serving_facts, freshness_registry, governance, signals
```

### 3.2 Blocking Behavior

When `weekly_history_freshness.blocking == True`:
- `driver_state_snapshot` — **NOT built** (no cascade)
- `program_eligibility` — **NOT built** (no cascade)
- `daily_opportunity_list` — **NOT built** (no cascade)
- `control_loop_state` — **NOT synced**
- `run_daily_refresh` — **NOT triggered**
- Governance checks (read-only) — **still run**
- Tick returns: `status = "blocked_by_stale_driver_history_weekly"`

### 3.3 Remediation

When blocked, the tick result includes:
```json
{
  "status": "blocked_by_stale_driver_history_weekly",
  "blocking_reason": "Weekly history is stale: latest 2026-05-25, current week starts 2026-06-08 (lag: 14 days).",
  "blocking_freshness": { ... },
  "weekly_history": { ... }
}
```

Operator action: investigate why `driver_history_daily` is not updating (raw orders ingestion gap), or run manual `bootstrap_history()`.

---

## 4. Refresh Behavior

### 4.1 When refresh runs

`refresh_weekly_history()` is called on **every autonomous tick** (every 5 min). This is safe because:

1. Fast NOOP path checks `MAX(week_start_date)` vs `latest_complete_monday` → returns in <1s when up to date
2. Expensive `_build_weekly_sql_bulk()` only triggers when weekly < current complete Monday
3. Most ticks result in NOOP (weekly table only needs refresh once per week, on Monday)
4. Advisory lock prevents concurrent rebuilds

### 4.2 Refresh failure handling

If `refresh_weekly_history()` fails (exception or can't acquire lock):
- Lock busy: `status = "SKIPPED_LOCKED"` — another refresh in progress
- Exception: caught by try/except in autonomous_tick → sets `weekly_history.error`
- In both cases: freshness check runs after, and if still blocking → tick blocked

---

## 5. Failure Behavior

| Scenario | Tick Status | Cascade | Downstream | Remediation |
|----------|------------|---------|------------|-------------|
| Weekly history fresh | Normal operation | Runs if needed | Runs | None |
| Weekly history stale + refresh succeeds | Normal operation | Runs | Runs | Automatic recovery |
| Weekly history stale + refresh fails | `blocked_by_stale_driver_history_weekly` | Blocked | Blocked | Investigate daily history ingestion. Manual bootstrap. |
| Weekly history stale + lock busy | `blocked_by_stale_driver_history_weekly` | Blocked | Blocked | Wait for in-progress refresh to complete (next tick) |
| Weekly history missing/empty | `blocked_by_stale_driver_history_weekly` | Blocked | Blocked | Run `bootstrap_history()` to populate |
| Freshness check error (DB down) | `blocked_by_stale_driver_history_weekly` | Blocked | Blocked | Restore DB connectivity |

**Fail-closed design.** All failure modes block downstream writes. The system prefers no data over stale data.

---

## 6. Tests / Validation

### 6.1 Test File

`backend/tests/test_growth_machine_freshness_gate.py` — 9 tests, all non-destructive mocks.

| Test | Scope | Result |
|------|-------|--------|
| `test_freshness_check_fresh_not_blocking` | Current week data → not blocking | PASS |
| `test_freshness_check_stale_returns_blocking` | 16-day lag → blocking | PASS |
| `test_freshness_check_missing_empty_table` | 0 rows → blocking (missing) | PASS |
| `test_freshness_check_query_error_blocking` | DB error → blocking (fail-closed) | PASS |
| `test_freshness_check_acceptable_one_week_lag` | 7-day lag → not blocking (acceptable) | PASS |
| `test_refresh_weekly_noop_when_up_to_date` | Current week → NOOP | PASS |
| `test_refresh_weekly_noop_no_daily` | No daily data → NOOP | PASS |
| `test_refresh_weekly_triggers_when_stale` | Stale → REFRESHED | PASS |
| `test_refresh_weekly_locked_skips` | Lock busy → SKIPPED_LOCKED | PASS |

### 6.2 Compile Validation

`python -m compileall -q backend/app` — no errors.

### 6.3 Dead Writer Verification

`upsert_history_weekly()` in `yego_lima_growth_history_repository.py:51` remains defined but NEVER called by any code path. Not activated by GM-F1A.

### 6.4 Live DB State (2026-06-13)

| Metric | Value |
|--------|-------|
| Rows | 135,812 |
| MAX(week_start_date) | 2026-06-01 |
| Current ISO Monday | 2026-06-08 |
| Lag | 7 days (stale, would trigger refresh) |

---

## 7. Remaining Gaps

| # | Gap | Severity | Phase |
|---|-----|----------|-------|
| G1 | `freshness_registry` false positive for `driver_history_weekly` (labels stale as "FRESH") | HIGH (P1) | GM-F1B |
| G2 | `program_eligibility` + `opportunity_list` DELETE without transaction wrapping | MEDIUM (P1) | GM-F1B |
| G3 | `driver_history_daily` staleness root cause (raw orders ingestion gap) | HIGH (P1) | GM-F1C |
| G4 | No fail-closed cascade guard for `driver_history_weekly` staleness at individual pipeline step level (only top-level gate) | LOW (P2) | Backlog |

---

## 8. Next Phase GM-F1B

**Objective:** Formalize serving registry / freshness contract for all 5 tables.

1. Fix `compute_freshness()` false positive for weekly tables
2. Verify `freshness_registry` and `serving_freshness_fact` accuracy post-GM-F1A
3. Wrap `program_eligibility` + `opportunity_list` DELETEs in transactions
4. Formalize freshness SLA contracts per table

---

*Generated from GM-F1A implementation audit. 9/9 tests pass. No DB writes, refreshes, or UI changes executed outside of controlled code modifications.*
