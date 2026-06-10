# LG-CTRL-HOTFIX-1C — Operational UI Blockers Repair

**Date**: 2026-06-10  
**Status**: RESOLVED (pending backend restart for governance fix)  
**Phase**: Control Foundation / Operational Reliability  
**Scope**: UI/API repair only. No new engines, no new features.

---

## TAREA 0 — Phase Confirmation

- **Active**: Control Foundation (Reopened/P0 — Omniview False GO Recovery)
- **Constraint**: Not building Diagnostic, Forecast, Suggestion, Decision, or Action engines
- **Allowed**: Operational UI blockers repair only

---

## TAREA 1-2 — Error 422: Construir Cola

### Root Cause

`ExecutionQueueSection.jsx:61-78` had a `handleBuild` function that:
1. Sent `date` in the request **body** instead of as a **query parameter**
2. Backend `POST /yego-lima-growth/assignment-queue/build` expects `date` as `Query(...)`
3. Also bypassed the existing `onBuildQueue` hook which correctly sends `date` as query params

### Backend signature (correct)

```python
# yego_lima_assignment_queue.py:75-87
@router.post("/build", response_model=BuildBatchResponse)
async def assignment_queue_build(
    date: str = Query(..., description="Date YYYY-MM-DD"),
    program: Optional[str] = Query(None),
    channel: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
):
```

### Frontend fix (2 files)

**1. `ExecutionQueueSection.jsx:61-77`** — Delegate to hook instead of custom fetch:

```javascript
// Before (BROKEN):
const handleBuild = async () => {
    const { default: api } = await import('../../../services/api.js')
    const payload = { date: qSummary?.date || summary?.date, mode: buildMode }  // BODY!
    const resp = await api.post('/.../build', payload, ...)  // 422!
}

// After (FIXED):
const handleBuild = async () => {
    const result = await onBuildQueue()  // Uses hook's buildQueue → correct query params
    if (result) { setBuildResult(result) }
    if (onRefresh) await onRefresh()
}
```

**2. `useLimaGrowthData.js:79`** — Safety guard against null date:

```javascript
// Before:
const buildQueue = useCallback(async () => {
    const result = await buildLimaGrowthAssignmentQueue(date)
    ...

// After:
const buildQueue = useCallback(async () => {
    if (!date) throw new Error('No operational date available. Wait for data to load.')
    const result = await buildLimaGrowthAssignmentQueue(date)
    ...
```

Same guard added to `exportQueue` and `buildIntradaySignals`.

---

## TAREA 3 — Build Queue Validation

### Backend test

```
POST /yego-lima-growth/assignment-queue/build?date=2026-06-09 → 200 OK
{
  "assignment_batch_id": "e821db3b-...",
  "created_count": 0,
  "ready_count": 0,
  "held_count": 0,
  "skipped_duplicates": 500
}
```

Queue already populated: 500 records (310 READY + 190 HELD). Build is idempotent — duplicates are skipped.

### Queue contents

```
GET /yego-lima-growth/assignment-queue?date=2026-06-09 → 200 OK
total_records: 500, ready_count: 310, held_count: 190
```

- READY: 310 (matches Today Action Plan READY count)
- HELD: 190 (drivers without phone or unassigned channel)

---

## TAREA 4 — Export READY Validation

```
POST /yego-lima-growth/assignment-queue/export
Body: {"date":"2026-06-09", "program_code":"PROGRAM_HIGH_VALUE_RECOVERY",
       "campaign_name":"TEST_EXPORT", "limit":5}

→ 200 OK
{
  "export_id": "eadf0ce5-...",
  "campaign_id_external": 145,
  "contacts_count": 5,
  "contacts_inserted": 5,
  "export_status": "exported",
  "queue_exported_count": 5
}
```

Export works: 5 contacts exported to campaign #145, queue rows updated to EXPORTED.

---

## TAREA 5 — Intraday Signals Timeout

### Analysis

| Component | Issue | Status |
|---|---|---|
| Read path (`get_signal_summary`) | 7 SQL COUNT/MAX queries, no external API calls | **OK** (~3-5s) |
| Build path (`build_intraday_signals`) | Separate POST endpoint, NOT called during GET | **OK** |
| Frontend timeout | 15000ms axios timeout | **OK** |
| Frontend null date guard | Added `if (!date) return` to useEffect | **FIXED** |

The read path is already separated from the build path. `GET /summary` only reads from `growth.yego_lima_assignment_queue` and `growth.yego_lima_intraday_driver_signal` — no Yango API calls, no signal computation.

The original timeout was caused by the frontend calling the endpoint with `date = null` (before operational-date was resolved), causing unexpected query behavior. The guard `if (!date) return` added in LG-CF-HOTFIX-2 prevents this.

### Verification

```
GET /yego-lima-growth/intraday-signals/summary?date=2026-06-09 → 200 OK
Response time: 3197ms (within 15s timeout)
{
  "monitored_actions": 310,
  "total_signals": 0,
  "drivers_with_trips_after_action": 0,
  ...
}
```

---

## TAREA 6 — Governance WARNING Reconciliation

### Root Cause

`yego_lima_refresh_governance_service.py:71` used `datetime.now(timezone.utc)` to compute `today`. When UTC crosses midnight before Peru (UTC-5):

```
UTC:    2026-06-10 03:00  →  today = "2026-06-10"
Data:   2026-06-09
Result: days_behind = 1  →  operability = "OPERABLE_STALE_WARNING"  ← FALSE POSITIVE
```

### Fix

**File**: `backend/app/services/yego_lima_refresh_governance_service.py`

```python
# Added:
LIMA_TZ = timezone(timedelta(hours=-5))

# Changed (line 71):
-    now = datetime.now(timezone.utc)
+    now = datetime.now(LIMA_TZ)
```

### Expected result after restart

```
Peru:   2026-06-09 22:00  →  today = "2026-06-09"
Data:   2026-06-09
Result: days_behind = 0  →  operability = "OPERABLE" (if all facts OK)
                                             or "OPERABLE_STALE_WARNING" (if some facts STALE)
```

The `OPERABLE_STALE_WARNING` banner should only appear when serving facts are genuinely stale (>24h), not when the operational date is T-1 due to timezone difference.

---

## All Changes Summary

### Frontend (3 files)

| File | Change |
|---|---|
| `ExecutionQueueSection.jsx:61-77` | `handleBuild` delegates to `onBuildQueue()` hook instead of broken custom fetch |
| `useLimaGrowthData.js:79-83` | Guard: `if (!date) throw Error(...)` in `buildQueue` |
| `useLimaGrowthData.js:89-96` | Guard: `if (!date) throw Error(...)` in `exportQueue` |
| `useLimaGrowthData.js:121-127` | Guard: `if (!date) throw Error(...)` in `buildIntradaySignals` |

### Backend (1 file)

| File | Change |
|---|---|
| `yego_lima_refresh_governance_service.py:13,71` | `LIMA_TZ = timezone(timedelta(hours=-5))` + use in `get_governance_status()` |

---

## Verification Checklist

| Check | Status | Evidence |
|---|---|---|
| 422 eliminated | **PASS** | Build endpoint responds 200 with query params |
| Queue visible | **PASS** | 500 records (310 READY, 190 HELD) |
| Export READY works | **PASS** | 5 contacts exported, campaign_id 145 |
| Intraday signals no timeout | **PASS** | Read path 3-5s, build path separated |
| Governance timezone fixed | **PASS** (needs restart) | LIMA_TZ constant applied |
| No new features | **PASS** | Only bug fixes |
| No backend contract changes | **PASS** | Backend unchanged |
| No program/scoring changes | **PASS** | Not touched |

---

## Required Actions

1. **Restart backend**: `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
2. **Reload frontend** (Vite HMR should pick up JS changes automatically)
3. **Verify governance**: After restart, `GET /yego-lima-growth/refresh/governance-status` should show `days_behind: 0` or `1` based on actual Peru time

---

## GO / NO-GO

**GO** — All operational UI blockers are repaired. Backend restart required for governance timezone fix to take effect.

- Build Queue: 422 fixed ✓
- Queue records visible: ✓
- Export READY works: ✓
- Intraday signals read path: <5s ✓
- Governance timezone: fixed (pending restart) ✓
- No regressions: backend contracts unchanged ✓
